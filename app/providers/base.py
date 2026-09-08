"""Provider protocols and registry (MASTER_PLAN section 8, P2-T01).

Defines the contracts every provider must satisfy, plus a registry that maps
provider names to implementations and exposes capability discovery.
"""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol, runtime_checkable


# --------------------------------------------------------------------------- #
# LLM
# --------------------------------------------------------------------------- #
@runtime_checkable
class LLMProvider(Protocol):
    async def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema: dict,
        temperature: float,
        request_id: str,
    ) -> dict: ...


# --------------------------------------------------------------------------- #
# Image
# --------------------------------------------------------------------------- #
# P4-T01: layer roles accepted by ImageGenerationRequest.role
IMAGE_ROLES: tuple[str, ...] = ("background", "subject", "foreground", "texture", "composite")

# seed must fit the non-negative 32-bit range most image providers accept.
_MAX_SEED = 2**32 - 1


def _is_valid_seed(value: int | None) -> bool:
    return value is None or 0 <= value <= _MAX_SEED


@dataclass
class ImageGenerationRequest:
    """Image generation request (MASTER_PLAN P4-T01, section 8.2).

    Fields: prompt, role, reference images, aspect, seed, candidate count,
    and output path. Values are coerced/validated in ``__post_init__`` so
    adapters receive a normalized shape and jobs can be persisted/round-tripped
    via ``to_dict``/``from_dict``.
    """

    prompt: str
    role: str  # background|subject|foreground|texture|composite
    negative_prompt: str = ""
    reference_images: list[str] = field(default_factory=list)
    aspect_ratio: str = "16:9"
    seed: int | None = None
    candidate_count: int = 1
    output_path: str = ""
    provider_params: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.role, str) or self.role not in IMAGE_ROLES:
            raise ValueError(f"invalid image role {self.role!r}; expected one of {IMAGE_ROLES}")
        if not _is_valid_seed(self.seed):
            raise ValueError(f"invalid seed {self.seed!r}; must be in [0, {_MAX_SEED}] or None")
        if self.candidate_count < 1:
            raise ValueError(f"candidate_count must be >= 1, got {self.candidate_count}")
        if not self.aspect_ratio:
            raise ValueError("aspect_ratio must not be empty")

    def to_dict(self) -> dict[str, Any]:
        """Serialize for persistence/job metadata (MASTER_PLAN P4-T05 candidate)."""
        data: dict[str, Any] = {
            "prompt": self.prompt,
            "role": self.role,
            "negative_prompt": self.negative_prompt,
            "reference_images": list(self.reference_images),
            "aspect_ratio": self.aspect_ratio,
            "seed": self.seed,
            "candidate_count": self.candidate_count,
            "output_path": self.output_path,
            "provider_params": dict(self.provider_params),
        }
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ImageGenerationRequest:
        """Rebuild from ``to_dict`` output (provider_params are optional)."""
        return cls(
            prompt=data["prompt"],
            role=data["role"],
            negative_prompt=data.get("negative_prompt", ""),
            reference_images=list(data.get("reference_images", [])),
            aspect_ratio=data.get("aspect_ratio", "16:9"),
            seed=data.get("seed"),
            candidate_count=data.get("candidate_count", 1),
            output_path=data.get("output_path", ""),
            provider_params=dict(data.get("provider_params", {})),
        )


@dataclass
class ImageGenerationResult:
    path: str
    provider: str
    provider_task_id: str = ""
    width: int = 0
    height: int = 0
    prompt_hash: str = ""
    sha256: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize for candidate metadata / result persistence."""
        return {
            "path": self.path,
            "provider": self.provider,
            "provider_task_id": self.provider_task_id,
            "width": self.width,
            "height": self.height,
            "prompt_hash": self.prompt_hash,
            "sha256": self.sha256,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ImageGenerationResult:
        return cls(
            path=data["path"],
            provider=data["provider"],
            provider_task_id=data.get("provider_task_id", ""),
            width=data.get("width", 0),
            height=data.get("height", 0),
            prompt_hash=data.get("prompt_hash", ""),
            sha256=data.get("sha256", ""),
        )


@dataclass
class ProviderHealth:
    status: str = "unknown"  # ok | unavailable | error
    detail: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status == "ok"


@dataclass
class ProviderCapabilities:
    supports_text_to_image: bool = False
    supports_image_to_image: bool = False
    supports_reference_image: bool = False
    supports_alpha: bool = False
    aspect_ratios: list[str] = field(default_factory=list)
    max_concurrency: int = 1


@runtime_checkable
class ImageProvider(Protocol):
    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult: ...

    async def health(self) -> ProviderHealth: ...

    async def capabilities(self) -> ProviderCapabilities: ...


# --------------------------------------------------------------------------- #
# TTS
# --------------------------------------------------------------------------- #
@dataclass
class TTSRequest:
    segment_id: str
    text: str
    language: str = "vi"
    voice_profile_id: str = "voice_vi_01"
    reference_audio_path: str = ""
    seed: int = 42
    output_path: str = ""
    speed: float = 1.0
    provider_params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TTSWordTiming:
    """Measured word boundary emitted by a TTS worker or acoustic aligner."""

    text: str
    start_ms: int
    end_ms: int

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValueError("TTS word timing text must not be empty")
        if self.start_ms < 0 or self.end_ms <= self.start_ms:
            raise ValueError("TTS word timing must have a positive duration")


@dataclass
class TTSResult:
    wav_path: str
    duration_ms: int
    sample_rate: int = 24000
    channels: int = 1
    provider: str = "omnivoice"
    word_timings: tuple[TTSWordTiming, ...] = ()


@runtime_checkable
class TTSProvider(Protocol):
    async def synthesize(self, request: TTSRequest) -> TTSResult: ...


# --------------------------------------------------------------------------- #
# Motion
# --------------------------------------------------------------------------- #
@dataclass
class MotionRenderRequest:
    scene_id: str
    motion_plan: dict  # MotionPlan JSON
    assets: dict  # role -> path
    voice_duration_ms: int
    fps: int = 30
    width: int = 1920
    height: int = 1080
    output_path: str = ""
    provider_params: dict[str, Any] = field(default_factory=dict)


@dataclass
class MotionRenderResult:
    path: str
    duration_ms: int
    fps: int
    width: int
    height: int
    provider: str
    command: str = ""


@runtime_checkable
class MotionProvider(Protocol):
    async def render(self, request: MotionRenderRequest) -> MotionRenderResult: ...


# --------------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------------- #
class ProviderNotFoundError(KeyError):
    pass


class ProviderRegistry:
    """Maps provider kind+name to an instance and reports capabilities."""

    def __init__(self) -> None:
        self._llm: dict[str, LLMProvider] = {}
        self._image: dict[str, ImageProvider] = {}
        self._tts: dict[str, TTSProvider] = {}
        self._motion: dict[str, MotionProvider] = {}

    # register
    def register_llm(self, name: str, provider: LLMProvider) -> None:
        self._llm[name] = provider

    def register_image(self, name: str, provider: ImageProvider) -> None:
        self._image[name] = provider

    def register_image_alias(self, alias: str, canonical: str) -> None:
        provider = self._image.get(canonical)
        if provider is None:
            raise ProviderRegistryError(f"no image provider: {canonical}")
        self._image[alias] = provider

    def register_tts(self, name: str, provider: TTSProvider) -> None:
        self._tts[name] = provider

    def register_motion(self, name: str, provider: MotionProvider) -> None:
        self._motion[name] = provider

    # get
    def llm(self, name: str) -> LLMProvider:
        if name not in self._llm:
            raise ProviderRegistryError(f"no LLM provider: {name}")
        return self._llm[name]

    def image(self, name: str) -> ImageProvider:
        if name not in self._image:
            raise ProviderRegistryError(f"no image provider: {name}")
        return self._image[name]

    def tts(self, name: str) -> TTSProvider:
        if name not in self._tts:
            raise ProviderRegistryError(f"no TTS provider: {name}")
        return self._tts[name]

    def motion(self, name: str) -> MotionProvider:
        if name not in self._motion:
            raise ProviderRegistryError(f"no motion provider: {name}")
        return self._motion[name]

    # discovery
    def capabilities(self, kind: str, name: str | None = None) -> dict[str, Any]:
        if kind == "image" and name:
            coro = self.image(name).capabilities()
            if asyncio.iscoroutine(coro):
                coro = asyncio.run(coro)
            return _capabilities(coro)
        # for non-image or generic: list registered names
        return {"providers": self.names(kind)}

    def names(self, kind: str) -> list[str]:
        return {"llm": list(self._llm), "image": list(self._image), "tts": list(self._tts), "motion": list(self._motion)}.get(kind, [])


class ProviderRegistryError(ValueError):
    pass


def _capabilities(cap: Any) -> dict[str, Any]:
    if callable(cap):
        cap = cap()
    dump = getattr(cap, "model_dump", None)
    if callable(dump):
        result = dump()
        if isinstance(result, dict):
            return {str(k): v for k, v in result.items()}
    if isinstance(cap, dict):
        return {str(k): v for k, v in cap.items()}
    asdict_cap = asdict(cap)
    if isinstance(asdict_cap, dict):
        return {str(k): v for k, v in asdict_cap.items()}
    return {}


_registry: ProviderRegistry | None = None


def get_registry() -> ProviderRegistry:
    global _registry
    if _registry is None:
        _registry = ProviderRegistry()
    return _registry
