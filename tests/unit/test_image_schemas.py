"""Tests for P4-T01 image request/result schemas.

Covers the field surface MASTER_PLAN P4-T01 requires (prompt, role,
reference images, aspect, seed, candidate count, output path), role/seed
validation, and to_dict/from_dict round-trips used by P4-T05 candidate
versioning and job persistence.
"""

from __future__ import annotations

import pytest

from app.providers.base import (
    IMAGE_ROLES,
    ImageGenerationRequest,
    ImageGenerationResult,
)


# --------------------------------------------------------------------------- #
# ImageGenerationRequest fields
# --------------------------------------------------------------------------- #
def test_request_defaults() -> None:
    req = ImageGenerationRequest(prompt="a cat", role="subject")
    assert req.prompt == "a cat"
    assert req.role == "subject"
    assert req.negative_prompt == ""
    assert req.reference_images == []
    assert req.aspect_ratio == "16:9"
    assert req.seed is None
    assert req.candidate_count == 1
    assert req.output_path == ""
    assert req.provider_params == {}


def test_request_full_fields() -> None:
    req = ImageGenerationRequest(
        prompt="a cat",
        role="background",
        negative_prompt="blur",
        reference_images=["ref1.png", "ref2.png"],
        aspect_ratio="4:3",
        seed=42,
        candidate_count=3,
        output_path="out/scene_001.png",
        provider_params={"size": "1024x1024"},
    )
    assert req.role == "background"
    assert req.reference_images == ["ref1.png", "ref2.png"]
    assert req.aspect_ratio == "4:3"
    assert req.seed == 42
    assert req.candidate_count == 3
    assert req.output_path == "out/scene_001.png"
    assert req.provider_params == {"size": "1024x1024"}


# --------------------------------------------------------------------------- #
# Role validation
# --------------------------------------------------------------------------- #
def test_role_enum_values() -> None:
    assert IMAGE_ROLES == ("background", "subject", "foreground", "texture", "composite")


@pytest.mark.parametrize("role", IMAGE_ROLES)
def test_role_accepted(role: str) -> None:
    req = ImageGenerationRequest(prompt="p", role=role)
    assert req.role == role


@pytest.mark.parametrize("role", ["", "bg", "layer", "unknown", None, 3])
def test_role_invalid_raises(role) -> None:
    with pytest.raises(ValueError):
        ImageGenerationRequest(prompt="p", role=role)


# --------------------------------------------------------------------------- #
# Seed validation
# --------------------------------------------------------------------------- #
def test_seed_none_allowed() -> None:
    assert ImageGenerationRequest(prompt="p", role="subject", seed=None).seed is None


@pytest.mark.parametrize("seed", [0, 1, 2**32 - 1])
def test_seed_range_accepted(seed: int) -> None:
    assert ImageGenerationRequest(prompt="p", role="subject", seed=seed).seed == seed


@pytest.mark.parametrize("seed", [-1, -42, 2**32])
def test_seed_out_of_range_raises(seed: int) -> None:
    with pytest.raises(ValueError):
        ImageGenerationRequest(prompt="p", role="subject", seed=seed)


# --------------------------------------------------------------------------- #
# candidate_count / aspect_ratio validation
# --------------------------------------------------------------------------- #
def test_candidate_count_zero_raises() -> None:
    with pytest.raises(ValueError):
        ImageGenerationRequest(prompt="p", role="subject", candidate_count=0)


def test_candidate_count_negative_raises() -> None:
    with pytest.raises(ValueError):
        ImageGenerationRequest(prompt="p", role="subject", candidate_count=-2)


def test_empty_aspect_ratio_raises() -> None:
    with pytest.raises(ValueError):
        ImageGenerationRequest(prompt="p", role="subject", aspect_ratio="")


# --------------------------------------------------------------------------- #
# Serialization round-trips
# --------------------------------------------------------------------------- #
def test_request_to_dict() -> None:
    req = ImageGenerationRequest(
        prompt="a cat",
        role="background",
        negative_prompt="blur",
        reference_images=["ref1.png"],
        aspect_ratio="4:3",
        seed=42,
        candidate_count=3,
        output_path="out/scene_001.png",
        provider_params={"size": "1024x1024"},
    )
    data = req.to_dict()
    assert data["prompt"] == "a cat"
    assert data["role"] == "background"
    assert data["negative_prompt"] == "blur"
    assert data["reference_images"] == ["ref1.png"]
    assert data["aspect_ratio"] == "4:3"
    assert data["seed"] == 42
    assert data["candidate_count"] == 3
    assert data["output_path"] == "out/scene_001.png"
    assert data["provider_params"] == {"size": "1024x1024"}


def test_request_round_trip() -> None:
    req = ImageGenerationRequest(
        prompt="a cat",
        role="composite",
        reference_images=["a.png"],
        aspect_ratio="1:1",
        seed=7,
        candidate_count=2,
        output_path="out/comp.png",
        provider_params={"x": 1},
    )
    rebuilt = ImageGenerationRequest.from_dict(req.to_dict())
    assert rebuilt == req


def test_request_round_trip_defaults_preserved() -> None:
    req = ImageGenerationRequest(prompt="p", role="foreground")
    rebuilt = ImageGenerationRequest.from_dict(req.to_dict())
    assert rebuilt == req
    assert rebuilt.reference_images == []
    assert rebuilt.provider_params == {}


def test_result_round_trip() -> None:
    res = ImageGenerationResult(
        path="out/scene_001/cand_1.png",
        provider="cliproxy",
        provider_task_id="job-abc",
        width=1408,
        height=768,
        prompt_hash="abc123",
        sha256="def456",
    )
    rebuilt = ImageGenerationResult.from_dict(res.to_dict())
    assert rebuilt == res


def test_result_round_trip_defaults() -> None:
    res = ImageGenerationResult(path="out/x.png", provider="fake")
    rebuilt = ImageGenerationResult.from_dict(res.to_dict())
    assert rebuilt == res
    assert rebuilt.provider_task_id == ""
    assert rebuilt.width == 0
    assert rebuilt.height == 0
