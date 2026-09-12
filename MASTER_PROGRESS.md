# MASTER PROGRESS

## Project status

- Current phase: QUIZ LINE (2026-09) — dòng storyboard/vox tạm dừng (không có hoạt động source từ 2026-08-19)
- Current task: QZ-T01 DONE — quiz engine v2 consolidation + pilot re-render (commit `d2afac6`)
- Overall status: QUIZ ENGINE GREEN (323/323 test quiz); 3 MP4 đã render, chờ Boss nghiệm thu nội dung/giọng
- Last updated: 2026-09-12
- Core blockers: none technical — risk còn treo: quota/moderation đường ảnh AI (đã có luật chibi); piper TTS không tất định (~1s tổng thời lượng mỗi render khi cache audio lạnh)

## Environment discovery

| Component | Status | Location/URL | Notes |
|---|---|---|---|
| Python | OK | 3.11.9 (venv: `D:\ALL AI\Hermes-argent-runtime\hermes-agent\venv`) | pytest 9.1.1, httpx 0.28.1, fastapi 0.133.1, pydantic 2.13.4, Pillow 12.2.0; SQLAlchemy chưa cài |
| FFmpeg | OK | `D:\Tool\ffmpeg-7.1.1-full_build\...\bin\ffmpeg.EXE` | version 7.1.1-full_build-www.gyan.dev |
| ffprobe | OK | `D:\Tool\ffmpeg-7.1.1-full_build\...\bin\ffprobe.EXE` | version 7.1.1-full_build |
| CLIProxyAPI | **OK (AVAILABLE)** | `http://127.0.0.1:8317/v1` | 18 models (12 antigravity + 6 openai); chat completion JSON OK; image gen qua `/v1/images/generations` (`gpt-image-2`) và `/v1beta/...:generateContent` (`gemini-3.1-flash-image`); key đọc runtime từ `CLIProxyAPI/config.yaml` |
| FlowKit | **NOT_INSTALLED** | — | quét toàn máy không thấy. User quyết định: CLIProxy là image provider chính, FlowKit optional. Contract trong `flowkit.json` |
| Antigravity image route | **AVAILABLE** | `POST /v1beta/models/gemini-3.1-flash-image:generateContent` | → 200, JPEG 1408×768 thật (fixture). KHÔNG control aspect ratio ở tầng translator (phải crop/fit ở render). `config/discovered/antigravity.json` |
| OmniVoice venv | **OK (AVAILABLE)** | `D:\ALL AI\VScode\voice-clone-tool\.venv\Scripts\python.exe` | package `omnivoice` 0.1.5, torch 2.10.0+cu126 CUDA; model `k2-fsa/OmniVoice` cache `out\models`; entry `synth.synthesize`; WAV probe 24kHz mono 3.52s. `config/discovered/omnivoice.json` |
| CUDA/GPU | OK (trong venv OmniVoice) | torch cu126 | **venv voice-clone-tool CUDA available**; venv dự án (hermes-agent) torch bị hỏng WinError 127 → không dùng torch trong app chính |

**Phase 0 hoàn tất (P0-T01 → P0-T06 all DONE).** Doctor giờ báo: python/ffmpeg/ffprobe/cliproxy/omnivoice all OK; flowkit NOT_INSTALLED (user chọn CLIProxy là image provider); gpu error (torch venv dự án hỏng — worker dùng venv voice-clone-tool có CUDA).

## Task log

### TASK P0-T01 — DONE

- Started: 2026-08-03
- Finished: 2026-08-03
- Files changed:
  - `pyproject.toml` — project config, deps, pytest/ruff/coverage config
  - `.env.example` — cấu hình môi trường theo MASTER_PLAN section 5.1, placeholder C:/PATH/TO
  - `.gitignore`
  - `README.md`
  - `app/__init__.py`, `tests/conftest.py`, `tests/unit/test_scaffold.py`
  - Cây thư mục chuẩn section 4 + `__init__.py` cho app/workers + `.gitkeep` cho thư mục trống
- Commands run:
  - `New-Item` tạo cây thư mục (14 package dirs + tests + projects + config/discovered + data/logs/input/output)
  - `python -m pytest -v`
- Tests: `tests/unit/test_scaffold.py` — 4 tests (dirs exist, files exist, app importable, no hardcoded venv)
- Result: **4 passed in 0.21s** — acceptance criteria đạt (`python -m pytest` chạy được)
- Known limitations:
  - Python hiện dùng là venv kế thừa `hermes-agent` (không phải venv riêng dự án). P0-T01 không yêu cầu tạo venv; quyết định tạo `.venv` riêng cho dự án để tránh phụ thuộc sẽ được ghi nhận khi P1-T01/P1-T02 cần cài dependency (fastapi/sqlalchemy...).
  - `ruff` chưa cài trong venv hiện tại → chưa chạy được `ruff check`. Sẽ cài khi tạo venv riêng hoặc `pip install -e ".[dev]"`.
- Next eligible task: P0-T02

### TASK P0-T02 — DONE

- Started: 2026-08-03
- Finished: 2026-08-03
- Files changed:
  - `app/config.py` — loader .env nhẹ không phụ thuộc, dùng cho Phase 0 tooling
  - `app/tooling/__init__.py`, `app/tooling/doctor.py` — logic doctor (check python/ffmpeg/ffprobe/project_dir/cliproxy/flowkit/omnivoice/gpu)
  - `app/cli.py` — CLI entry `python -m app.cli doctor`
  - `tests/unit/test_doctor.py` — 9 unit tests
- Commands run:
  - `python -m app.cli doctor`
  - `python -m pytest -v`
  - probe thủ công `/v1/models` không/sai key → 401
- Tests: `tests/unit/test_doctor.py` — 9 passed (cô lập lỗi GPU, placeholder OmniVoice, run_all không crash khi provider chết, core_ok)
- Result: **13 passed in 0.44s**; CLI `doctor` chạy end-to-end, exit 0, ghi `config/discovered/doctor_report.json`
- Known limitations:
  - CLIProxy trả 401 (cần key đúng); FlowKit không health; OmniVoice placeholder; torch GPU hỏng (WinError 127) — đây là trạng thái thật, ghi rõ cho các probe sau.
  - Doctor dùng venv kế thừa hermes-agent; chưa có venv riêng dự án.
- Next eligible task: P0-T03

### TASK P0-T03 — DONE

- Started: 2026-08-03
- Finished: 2026-08-03
- Files changed:
  - `app/config.py` — thêm `_discover_cliproxy_api_key()` (đọc client key từ `CLIProxyAPI/config.yaml`, strip quote), tích hợp vào loader; sentinel `local-placeholder` xử lý như chưa cấu hình
  - `config/discovered/cliproxy.json` — capability report (18 models, contract auth, model gợi ý)
  - `tests/unit/test_config_probe.py` — 4 tests (discovery parser, strip quote, fallback empty, env override)
  - doctor_report.json cập nhật CLIProxy → OK
- Commands run:
  - probe `/v1/models` với key `sk-...dung` (17 chars) → **200 OK, 18 models**
  - `POST /v1/chat/completions` với `gemini-3.1-flash-lite` → **200 OK, JSON parse được** (`{"scene_count":2,...}`)
  - `gpt-5.6-sol` → 502 "unknown provider" (model không tồn tại — chứng minh auth pass, chỉ model alias sai)
  - `python -m app.cli doctor` → CLIProxy status **ok**, model_count 18
  - `python -m pytest -q` → **17 passed**
- Tests: `tests/unit/test_config_probe.py` (4) + toàn bộ suite 17 passed
- Result: acceptance criteria đạt — `cliproxy.json` tồn tại; chat completion trả JSON parse được; credential redacted (không key trong log/report/.env; key đọc runtime từ config tool)
- Known limitations:
  - Key CLIProxy không có trong `.env` — dựa vào discovery runtime từ `CLIProxyAPI/config.yaml`. Nếu user đổi path tool, phải cập nhật `_CLIPROXY_CONFIG_CANDIDATES`.
  - Model gợi ý cho LLM storyboard: `gemini-3.6-flash-high` (default) / `gemini-3.1-flash-lite` (rẻ); image: `gpt-image-2` (dùng trong /v1/images/generations); `gemini-3.1-flash-image` KHÔNG dùng được trên /v1/images/generations (400).
  - Model `gpt-5.6-sol` KHÔNG tồn tại — tránh dùng.
- Next eligible task: P0-T04

### TASK P0-T04 — DONE

- Started: 2026-08-03
- Finished: 2026-08-03
- Status note: FlowKit KHÔNG có trên máy (quét kỹ). User quyết định CLIProxy là image provider chính; FlowKit optional về sau.
- Files changed:
  - `config/discovered/flowkit.json` — trạng thái NOT_INSTALLED + contract image CLIProxy (endpoint, model, request/response, proof)
  - `tests/fixtures/cliproxy_image_probe.png` — ảnh thật sinh bằng `gpt-image-2` (1254×1254 RGB) làm fixture
  - `data/probe_image.py` — tạo rồi xóa (probe tạm, không phải script cấu trúc)
- Commands run:
  - quét toàn máy tìm FlowKit (dirs/process/ports/files) → không thấy
  - `POST /v1/images/generations` với `gpt-image-2` → **200**, PNG 879KB b64, decode hợp lệ qua Pillow
  - `gemini-3.1-flash-image` trên `/v1/images/generations` → **400** (không supported, phải dùng gpt-image-2)
- Tests: xác nhận ảnh probe decode (Pillow: PNG 1254×1254 RGB); chạy `python -m pytest -q` → **17 passed**
- Result: P0-T04 đạt AC theo hướng user chọn — có `flowkit.json` (trạng thái chưa cài rõ), tạo được ít nhất một ảnh test thật (qua CLIProxy), contract image ghi lại đầy đủ
- Known limitations:
  - FlowKit chưa cài; mọi image generation hiện đi qua CLIProxy `gpt-image-2`.
  - `gemini-3.1-flash-image` không dùng được cho sinh ảnh qua OpenAI-compatible endpoint.
  - Concurrency image mặc định nên giữ 1 (một client key shared).
- Next eligible task: P0-T05

### TASK P0-T05 — DONE

- Started: 2026-08-03
- Finished: 2026-08-03
- Files changed:
  - `config/discovered/antigravity.json` — contract text-to-image qua CLIProxy (endpoint, request/response, limitation aspect)
  - `tests/fixtures/antigravity_image_probe.jpg` — ảnh thật gemini-3.1-flash-image (JPEG 1408×768, 491KB)
  - `data/probe_antigravity*.py` — tạo rồi xóa (probe tạm)
- Commands run:
  - `POST /v1beta/models/gemini-3.1-flash-image:generateContent` với `responseModalities:["IMAGE"]` → **200**, inlineData JPEG
  - `/v1/models/gemini-3.1-flash-image:generateContent` (không v1beta) → **404**
  - Pillow validate → JPEG 1408×768 RGB, hợp lệ
- Tests: ảnh probe decode hợp lệ; full suite `python -m pytest -q` → **17 passed**
- Result: P0-T05 đạt AC — trạng thái **AVAILABLE**; tạo được ảnh thật; response shape redacted ghi lại đầy đủ
- Known limitations:
  - Aspect ratio KHÔNG điều khiển được qua translator gemini (ảnh ra 1408×768 mặc định). Phải crop/fit ở tầng layer/render (đã ghi rõ cho P4/P5/P6).
  - Model image Antigravity chỉ chạy qua route `/v1beta/models/{model}:generateContent`; `gpt-image-2` qua `/v1/images/generations` (OpenAI, có size param).
- Next eligible task: P0-T06

### TASK P0-T06 — DONE

- Started: 2026-08-03
- Finished: 2026-08-03 (Phase 0 COMPLETE)
- Files changed:
  - `config/discovered/omnivoice.json` — venv path, package, model, entrypoint synth.synthesize, ref samples, command, probe result
  - `tests/fixtures/omnivoice_probe.wav` — WAV tiếng Việt thật (24kHz mono, 3.52s)
  - `data/probe_omnivoice.py` — tạo rồi xóa (probe tạm)
- Commands run:
  - `.venv\Scripts\python.exe -c "import omnivoice"` → 0.1.5; `import torch` → 2.10.0+cu126 CUDA available
  - probe synth.synthesize() với ref `Sử đại phát minh_preview.wav`, language vi → WAV 169KB
  - `ffprobe` → pcm_s16le, 24000Hz, mono, duration 3.52s
- Tests: ffprobe đọc được WAV (acceptance đạt); full suite `python -m pytest -q` → **17 passed**
- Result: P0-T06 đạt AC — tạo `tests/fixtures/omnivoice_probe.wav`; ffprobe đọc được; có `config/discovered/omnivoice.json`
- Known limitations:
  - OmniVoice chạy bằng venv `voice-clone-tool`, KHÔNG phải venv dự án. Worker (P3) phải dùng venv này.
  - App chính KHÔNG được import torch/omnivoice (venv dự án torch hỏng WinError 127). Phải bọc thành worker riêng — đúng master plan.
  - Model load ~vài giây + gán hơn (CUDA); nên preload 1 lần trong worker.
- Next eligible task: P1-T01

### TASK P1-T01 — DONE

- Started: 2026-08-03
- Finished: 2026-08-03
- Files changed:
  - `app/settings.py` — Settings(BaseSettings): env + `.env`, validator path Windows, redacted_dict, discovery fallback (CLIProxy key, OmniVoice venv), singleton get_settings
  - `tests/unit/test_settings.py` — 7 tests
- Commands run:
  - `python -c` verify settings: project_root absolute, ffmpeg/ffprobe path, omnivoice venv discovery, cliproxy redacted
  - `python -m pytest -q` → **25 passed**
- Tests: `tests/unit/test_settings.py` — 7 passed (defaults, env override, project_root resolve, redacted, secret not printed, omnivoice discovery, singleton)
- Result: P1-T01 đạt AC — Pydantic Settings, load .env, validate path Windows, default config, redacted dump, missing secret không in log
- Known limitations:
  - `Settings` dùng defaults từ `.env.example` + discovery; nếu `.env` không tồn tại, vẫn chạy được nhờ discovery (key CLIProxy + OmniVoice venv).
  - Field `cliproxy_api_key` là secret mask; chưa có cơ chế encrypt, chỉ redact khi in/log.
- Next eligible task: P1-T02

### TASK P1-T02 — DONE

- Started: 2026-08-03
- Finished: 2026-08-03
- Files changed:
  - `app/storage/database.py` — engine/session/schema; SQLite path absolute Windows; `PRAGMA foreign_keys=ON` per connection; reset_engine
  - `app/models/project.py`, `scene.py`, `asset.py`, `state.py` — 7 bảng (projects/scenes/assets/provider_jobs/render_attempts/state_events/voice_profiles)
  - `app/models/__init__.py` — export models
  - `app/storage/repositories.py` — CRUD (ProjectRepo/SceneRepo/AssetRepo/StateEventRepo/ProviderJobRepo/RenderAttemptRepo/VoiceProfileRepo)
  - `tests/unit/test_database.py` — 7 tests
- Commands run:
  - `pip install sqlalchemy>=2.0` → 2.0.51 (venv dự án)
  - `python -m pytest -q` → **32 passed**
- Tests: `tests/unit/test_database.py` — 7 passed (schema tables, project CRUD, scene CRUD+order, voice_profile upsert, state_event, FK constraint, transaction rollback)
- Result: P1-T02 đạt AC — 7 bảng tạo; CRUD test pass; transaction rollback pass; SQLite local hoạt động
- Known limitations:
  - SQLite cần bật FK pragma mỗi connection (đã fix trong engine).
  - Chưa có migration framework (Alembic); dùng `create_all` idempotent cho MVP.
  - DB file `data/app.db` sẽ tạo khi init; test dùng in-memory/tmp riêng.
- Next eligible task: P1-T03

### TASK P1-T03 — DONE

- Started: 2026-08-03
- Finished: 2026-08-03
- Files changed:
  - `app/storage/asset_store.py` — AssetStore: layout projects/{id}/{8 subdirs}, validate project_id regex, path traversal block, atomic write (temp+rename), SHA-256, versioned assets `_v001`, manifest JSON helper
  - `tests/unit/test_asset_store.py` — 7 tests
- Commands run:
  - `python -m pytest -q` → **39 passed**
- Tests: `tests/unit/test_asset_store.py` — 7 passed (init subdirs, invalid id, path traversal block, unknown subdir, atomic+sha256, versioned no-overwrite, manifest json)
- Result: P1-T03 đạt AC — path traversal bị chặn; atomic write; SHA-256 metadata; versioned assets; layout đúng
- Known limitations:
  - `project_id` phải khớp regex an toàn; subdir allowlist cố định 8.
  - Manifest sha256 embed sau write (không ghi lại vào file).
- Next eligible task: P1-T04

### TASK P1-T04 — DONE

- Started: 2026-08-03
- Finished: 2026-08-03
- Files changed:
  - `app/core/state_machine.py` — PROJECT_STATES/SCENE_STATES/ERROR_STATES, can_transition (forward ≤2 bước, error terminal trừ retryable reset), StateMachine (transition_project/scene ghi state_event), pending_scenes resume
  - `tests/unit/test_state_machine.py` — 8 tests
- Commands run:
  - `python -m pytest -q` → **47 passed**
- Tests: 8 passed (project progression, invalid jump reject, scene backward reject, forward works, error recovery, hot scene doesn't affect done, resume pending, state_events)
- Result: P1-T04 đạt AC — invalid transition từ chối; restart/resume qua SQLite; hỏng scene không đổi scene đã hoàn thành
- Known limitations:
  - `MAX_TRANSITION_ADVANCE=2` (cho skip IMAGE_SUBMITTED, chặn jump lớn); nếu workflow cần jump xa hơn, điều chỉnh hằng số.
  - FAILED_PERMANENT/CANCELLED là terminal (không reset).
- Next eligible task: P1-T05

### TASK P1-T05 — DONE

- Started: 2026-08-03
- Finished: 2026-08-03 (Phase 1 COMPLETE)
- Files changed:
  - `app/core/job_runner.py` — JobRunner (in-process async queue): per-provider concurrency semaphore, retry+backoff, timeout wait_for, cancellation, heartbeat ticker, pending_jobs, wait, shutdown
  - `tests/unit/test_job_runner.py` — 6 tests
- Commands run:
  - `python -m pytest -q` → **53 passed**
- Tests: 6 passed (success, retry-then-success, cancellation, timeout, failed không dừng queue, concurrency limit)
- Result: P1-T05 đạt AC — retry, cancellation, one failed job không dừng queue, concurrency theo provider
- Known limitations:
  - Queue in-process (chưa persist task giữa restart ở tầng này; resume nhờ DB state ở P1-T04).
  - Retry delay dùng backoff tuyến tính.
- Next eligible task: **P2-T01 — Base provider interfaces**

### TASK P2-T01 — DONE

- Started: 2026-08-03
- Finished: 2026-08-03 (Phase 2 COMPLETE)
- Files changed:
  - `app/providers/base.py` — protocols LLM/Image/TTS/Motion (runtime_checkable), dataclass requests/results (ImageGenerationRequest/Result, TTSRequest/Result, MotionRenderRequest/Result, ProviderHealth, ProviderCapabilities), ProviderRegistry (register/get/capabilities/names), `_capabilities()` fix (hỗ trợ dataclass asdict)
  - `tests/unit/test_provider_base.py` — 6 tests (runtime_checkable, register/get, missing raises, names, capabilities discovery, fake providers run)
- Commands run:
  - `python -m pytest -q` → **59 passed**
- Tests: 6 passed; `test_capabilities_discovery_image` bị lỗi KeyError do `_capabilities()` không hỗ trợ dataclass → fix thêm `asdict`, toàn suite 59 passed
- Result: P2-T01 đạt AC — fake providers cho test; provider registry; capability discovery (ProviderCapabilities asdict serialize)
- Known limitations:
  - `_capabilities()` giờ xử lý Pydantic model_dump, dict, và dataclass asdict. ProviderCapabilities là dataclass (không phải Pydantic) nên asdict là path chính.
  - Chưa có auto-discovery từ config/discovered/*.json ở tầng registry (sẽ làm ở P2-T02+ adapter).
- Next eligible task: **P2-T02 — Cliproxy LLM adapter**

### TASK P2-T02 — DONE

- Started: 2026-08-03
- Finished: 2026-08-03
- Files changed:
  - `app/providers/llm/cliproxy.py` — CliproxyLLMProvider: OpenAI-compatible client (httpx.AsyncClient + MockTransport injectable), timeout (CLIPROXY_TIMEOUT_SECONDS, mặc định 180), retry tenacity (429/500/502/503/504, exponential backoff, max_retries=3), JSON parse + schema required-keys check, request ID (body field), model config (settings.cliproxy_model), health (GET /models). Lỗi: CliproxyLLMError hierarchy (Auth 401 / ModelNotFound 404 / Validation non-retryable / Retryable transport+4xx/5xx). Auth header gửi per-request để hỗ trợ client injected. Không log credential/key.
  - `app/providers/llm/__init__.py` — export provider + error types
  - `tests/unit/test_llm_cliproxy.py` — 18 tests + marker integration (17 unit + 1 integration thật)
  - `pyproject.toml` — đăng ký markers `integration`
- Commands run:
  - probe thật: `CliproxyLLMProvider().health()` → ok, model_count 21 (lưu ý: `gpt-5.6-sol` giờ TỒN TẠI, khác P0-T03 lúc trước 502)
  - probe thật: `generate_json` với gemini-3.6-flash-high → JSON đúng schema `{scene_count, summary}`
  - `python -m pytest -q` → **77 passed** (P2-T01 fix đã đưa suite từ 58 → 59 ở task trước, +18 mới)
  - `python -m pytest tests/unit/test_llm_cliproxy.py -q` → **18 passed**; `-m "not integration"` → 17 passed, 1 deselected
- Tests: 18 (success + markdown fence, retry 429→success 3 calls, retry 503, 429 exhaust → error, malformed/non-object/missing-required → ValidationError, validation NOT retried (1 call), 401 → AuthError, 404 → ModelNotFound, health ok/unavailable/401, request gồm auth header + request_id + model, credentials không vào log)
- Result: P2-T02 đạt AC — integration test với CLIProxy local pass (service chạy); mock test 429 pass; mock test malformed JSON pass; no credential log pass.
- Known limitations:
  - Auth gửi per-request (header Authorization) + cũng set ở client-owned; client injected không tự có key nhưng request gửi đủ auth.
  - `gpt-5.6-sol` giờ có trong catalog model (khác P0-T03 ghi chú cũ "không tồn tại") — mức độ liên quan thấp vì dùng gemini-3.6-flash-high mặc định.
  - Deep schema field-type validation defer P2-T03 (jsonschema).
- Next eligible task: **P2-T03 — Storyboard JSON Schema**

### TASK P2-T03 — DONE

- Started: 2026-08-03
- Finished: 2026-08-03
- Files changed:
  - `app/schemas/storyboard.schema.json` — JSON Schema (draft-07): required summary/style_anchor/characters/locations/scenes; style_anchor {visual_language, palette, texture, typography, continuity_rules}; characters/locations arrays; scenes minItems=4 maxItems=20; Scene def bắt buộc scene_id/order/script_span/narration_text/visual_summary/image_prompt/motion_template/estimated_duration_seconds
  - `app/schemas/storyboard.py` — validator dùng jsonschema + workflow rules section 17.1: scene count clamp 4..20, scene ids unique, order contiguous 1..N, script_span không overlap
  - `app/schemas/__init__.py` — export
  - `tests/unit/test_storyboard_schema.py` — 18 tests
- Commands run:
  - `python -m pytest tests/unit/test_storyboard_schema.py -q` → **18 passed**
  - `python -m pytest -q` → **95 passed**
- Tests: 18 (valid fixture, required core fields, min/max bounds, missing summary/scenes/style_anchor fail, scene missing narration/motion_template/image_prompt/duration fail, invalid character fail, scene count too few/many fail, min/max ok, duplicate ids fail, non-contiguous order fail, overlapping span fail)
- Result: P2-T03 đạt AC — valid fixture pass; invalid fixture fail; scene count rule test (4..20).
- Known limitations:
  - Schema `additionalProperties: true` ở top-level + scene (mở rộng được, mạnh hơn strict reject). Field `target_duration_seconds` optional (orchestrator fill).
  - Workflow rules (unique id, contiguous order, span overlap) nằm ngoài JSON schema vì khó biểu diễn gọn; nằm trong validator Python.
- Next eligible task: **P2-T04 — Prompt pack**

### TASK P2-T04 — DONE

- Started: 2026-08-03
- Finished: 2026-08-03
- Files changed:
  - `prompts/system_storyboard.md` — system prompt: chỉ trả JSON, tuân thủ schema, không markdown, không bịa provider/model, narration-first, scene 4–7s, motion ≥3 layer (không Ken Burns), text render local, character consistency. Template Jinja2 với `{% if style_block %}` để inject preset.
  - `prompts/scene_planner.md` — role chia scene: coverage toàn script, không cắt giữa câu/tên/số, bảng timing hook 3–6s / body 4–6s / conclusion 4–8s
  - `prompts/image_prompt.md` — prompt ảnh sạch (không text trong image), 3 lớp cho parallax, nhất quán nhân vật, fixed aspect
  - `prompts/motion_prompt.md` — VoxStyle motion: 3 layer tối thiểu (bg/camera, subject, text/fg/effect), 12 template, effects list, amplitude
  - `prompts/repair_json.md` — role sửa JSON hỏng, chỉ sửa lỗi không đổi nội dung khác
  - `presets/editorial_collage.yaml`, `documentary.yaml`, `minimal_motion.yaml` — 3 style preset
  - `app/services/prompts.py` — PromptPack (Jinja2 loader + cache), StylePreset, load_presets() (yaml), inject_style(), system_prompt(preset), get_prompt_pack()
  - `app/services/__init__.py` — export
  - `tests/unit/test_prompt_pack.py` — 13 tests
- Commands run:
  - `python -m pytest tests/unit/test_prompt_pack.py -q` → **13 passed**
  - `python -m pytest -q` → **108 passed**
  - verify encoding: đọc cả 5 prompt files, badchars=0 (UTF-8 sạch)
- Tests: 13 (all files present, nonempty, system prompt JSON-only+markdown, no hardcoded model/provider (gemini/claude/gpt-/cliproxy/flowkit), motion rule Ken Burns + three layers, scene duration rule, motion templates list, presets discovered, editorial content, inject_style, system_prompt() end-to-end inject, unknown prompt raises)
- Result: P2-T04 đạt AC — prompt snapshot tests; không chứa model ID hard-coded; style preset inject được (system_prompt() + inject_style).
- Known limitations:
  - `render()` dùng StrictUndefined → template có biến chưa cung cấp sẽ raise; `system_prompt()` là path chính cho inject.
  - Preset loader yêu cầu `pyyaml` (đã có trong env). Nếu máy khác thiếu, `load_presets()` trả empty dict (không crash).
- Next eligible task: **P2-T05 — Script analysis service**

### TASK P2-T05 — DONE

- Started: 2026-08-03
- Finished: 2026-08-03
- Files changed:
  - `app/services/script_analysis.py` — ScriptAnalyzer pipeline: normalize → word count → estimate duration (2.7–3.3 từ/s, clamp) → estimate scene count (section 7.2: clamp(round(dur/5.5), 4, 20)) → planner call → schema validate → repair loop (repair_json, max 2) → persist (storyboard.json manifest + DB scenes + project state SCRIPT_ANALYZED→STORYBOARD_DRAFTED). `_normalize_storyboard` ép continuity_rules string→list, fill purpose rỗng.
  - `app/schemas/storyboard.schema.json` — nới lỏng motion_prompt/transition_out (string|object), continuity_rules (array|string) vì LLM thật hay trả dạng object/string
  - `tests/unit/test_script_analysis.py` — 16 tests (fixture ngắn/60s/dài, coverage, determinism, repair loop, persist DB, state, normalize, clamp)
  - `tests/unit/test_storyboard_schema.py` — +3 tests (object fields allowed)
- Commands run:
  - `python -m pytest -q` → **127 passed**
  - Integration thật với CLIProxy: `ScriptAnalyzer(CliproxyLLMProvider, style_preset=editorial_collage)` trên script tiếng Việt → **4 scenes, 25 từ, 8.33s, summary editorial collage (style inject hoạt động), 4 scenes persist DB, 1 repair call** — end-to-end pass
- Tests: 16 (normalize, count_words, estimate clamp, short/60s/long fixture, persist scenes DB, state STORYBOARD_DRAFTED, script coverage, repair loop invoked, repair exhausts raises, deterministic low temp, words/s clamp, normalize rules, + schema object tests)
- Result: P2-T05 đạt AC — fixture ngắn/60 giây/dài pass; coverage toàn script (script_text persist); output deterministic ở temperature thấp (fake planner same input → same output).
- Known limitations:
  - Integration test (model thật) cần CLIProxy đang chạy; không nằm trong unit suite (chỉ smoke thủ công). Unit dùng FakePlanner deterministic.
  - LLM thật hay trả motion_prompt object, continuity_rules string → đã nới schema + normalize. Vẫn có thể cần repair cho lỗi sâu hơn (max 2 lần).
  - Scene heuristic chỉ là gợi ý; model được phép lệch ±25%.
- Next eligible task: **P2-T06 — Storyboard CLI**

### TASK P2-T06 — DONE

- Started: 2026-08-03
- Finished: 2026-08-03 (Phase 2 COMPLETE)
- Files changed:
  - `app/services/project_manager.py` — ProjectManager: create_project (script → project row + input/script.txt + SHA-256 + idempotent theo script_hash), get_project, plan (gọi ScriptAnalyzer + transition STORYBOARD_VALIDATED), generate_project_id
  - `app/cli.py` — thêm `create-project --script --title --style --aspect-ratio --fps` và `plan --project --temperature` subcommands
  - `app/schemas/storyboard.schema.json` — nới lỏng palette/texture (array|string), characters/locations chỉ require `name` (id auto-gen)
  - `app/services/script_analysis.py` — `_normalize_storyboard` mở rộng: palette/texture string→list, auto-id character_id/location_id; fix commit sau transition STORYBOARD_DRAFTED
  - `app/services/__init__.py` — export ProjectManager + script_analysis symbols
  - `tests/unit/test_project_manager.py` — 10 tests
  - `tests/unit/test_storyboard_schema.py` — +1 test (character without id allowed, without name fails)
- Commands run:
  - `python -m app.cli create-project --script /tmp/sample_script.txt` → `prj_20260803_c063b0` created
  - create lại cùng script → `reused (same script content)` (idempotent, không duplicate)
  - `python -m app.cli plan --project prj_20260803_2798f1` → 5 scenes, storyboard.json, status STORYBOARD_VALIDATED, events INGESTED→SCRIPT_ANALYZED→DRAFTED→VALIDATED
  - plan lần 2 → 5 scenes unique (không duplicate), repair warning VALIDATED→VALIDATED đã fix (skip nếu đã VALIDATED)
  - `python -m pytest -q` → **138 passed**
- Tests: 10 (create project row+input file, idempotent same script, empty script raises, project id unique, sha deterministic, plan creates storyboard+scenes, plan status validated + events, plan 2nd time no duplicate, plan missing project raises, CLI subcommands present)
- Result: P2-T06 đạt AC — tạo storyboard.json; DB có scenes; status đúng (STORYBOARD_VALIDATED); chạy lần hai không duplicate nếu input không đổi.
- Known limitations:
  - `create-project` idempotency dựa trên script_hash (cùng script + hash → reuse). Title khác nhưng script giống vẫn reuse.
  - LLM thật hay trả palette/texture dạng comma-string, thiếu character_id/location_id → normalize tự xử lý (giảm repair calls, integration: 0 repair lần cuối).
  - Warning VALIDATED→VALIDATED khi re-plan đã xử lý (skip transition nếu đã VALIDATED).
- Next eligible task: **P3-T01 — OmniVoice worker skeleton**

### TASK P3-T01 — DONE

- Started: 2026-08-03
- Finished: 2026-08-03
- Files changed:
  - `workers/omnivoice_worker/main.py` — FastAPI worker app: GET /health (ok + model_loaded), POST /warmup (load model singleton qua synth._get_model), POST /synthesize (synth.synthesize + probe duration từ WAV header). Model singleton nội bộ synth đảm bảo load 1 lần. Import synth guard (try/except) khi cwd sai.
  - `scripts/start_omnivoice_worker.ps1` — launcher: venv OmniVoice + cwd tool root + PYTHONPATH project + PYTHONIOENCODING=utf-8 + port 8791
  - `tests/unit/test_omnivoice_worker.py` — 6 tests (mock synth qua monkeypatch)
- Commands run:
  - `python -m pytest tests/unit/test_omnivoice_worker.py -q` → **6 passed**
  - Verify import thật: chạy `workers.omnivoice_worker.main` bằng OmniVoice venv + cwd tool root → app import OK, synth = synth (model importable)
- Tests: 6 (health ok, warmup loads model, health reflects loaded, synthesize returns WAV + duration, empty text 400, model load error → JSON error clean)
- Result: P3-T01 đạt AC — GET /health = ok; POST /warmup = model loaded.
- Known limitations:
  - Test dùng mock synth (venv dự án không import torch). Real worker chạy bằng OmniVoice venv qua launcher script.
  - `synth._get_model` load model thật tốn vài giây + GPU; warmup preload 1 lần.
- Next eligible task: **P3-T02 — OmniVoice adapter**

### TASK P3-T02 — DONE

- Started: 2026-08-03
- Finished: 2026-08-03
- Files changed:
  - `app/providers/tts/omnivoice.py` — OmniVoiceProvider (TTSProvider protocol): synthesize (POST /synthesize), health (GET /health), warmup (POST /warmup), aclose. `_resolve_output_path` absolute (chống lạc cwd worker). Error types: OmniVoiceError/Unavailable/InputError.
  - `app/providers/tts/__init__.py` — export
  - `scripts/start_omnivoice_worker.ps1` — fix `$Host` reserved → `$ListenHost`
  - `tests/unit/test_tts_omnivoice.py` — 9 tests (mock transport)
- Commands run:
  - Start worker thật bằng OmniVoice venv (launcher) → health `{"status":"ok","model_loaded":false}`
  - `POST /warmup` → `{"status":"loaded","model_loaded":true}` (model CUDA load thật)
  - synthesize qua adapter: scene_001 → dur_ms 3260, scene_002 → dur_ms 2120 (không reload model, worker singleton)
  - ffprobe: pcm_s16le 24000Hz mono 3.26s (khớp dur_ms)
  - fix output path: relative `output/tts_scene_001a.wav` → resolve vào project root (không lạc tool root)
  - `python -m pytest -q` → **153 passed**
- Tests: 9 (synthesize result, sends ref_wav+text+language, second request no reload (no /warmup call), input error 400 → clear detail, worker unreachable, health ok/unavailable, warmup calls worker, runtime_checkable)
- Result: P3-T02 đạt AC — sinh WAV tiếng Việt (ffprobe verify); model load 1 lần (worker singleton); request thứ hai không reload; lỗi input trả JSON rõ (400 detail).
- Known limitations:
  - Worker phải chạy trước khi adapter dùng; nếu worker down → OmniVoiceUnavailable.
  - Integration test cần worker thật (tốn GPU/venv OmniVoice); unit suite dùng mock transport.
- Next eligible task: **P3-T03 — Voice profiles**

### TASK P3-T03 — DONE

- Started: 2026-08-03
- Finished: 2026-08-03
- Files changed:
  - `app/services/voice_profiles.py` — VoiceProfileManager: create_profile (validate file exists + audio ext, SHA-256 hash, upsert, không copy đè), get/list, sync_from_discovery (scan samples dir → profiles, unique id qua slug + sha256[8]), discover_reference_samples, sha256_file, load_voice_presets_json
  - `app/services/__init__.py` — export
  - `tests/unit/test_voice_profiles.py` — 10 tests
- Commands run:
  - sync thật với samples dir → 34 profiles tạo, unique ids (đã fix collision: `ngochuyen (1).wav` vs `.mp3` cùng stem → id thêm sha suffix)
  - `python -m pytest -q` → **163 passed**
- Tests: 10 (validate+hash, missing file raises, unsupported format raises, không copy đè (source untouched, 1 file only), upsert update không duplicate, list, get, get missing raises, discover returns audio, sync idempotent + unique)
- Result: P3-T03 đạt AC — validate file; hash reference (SHA-256); không copy đè; list profile.
- Known limitations:
  - Discovery chỉ quét `_SAMPLE_DIR_CANDIDATES` (hardcode path tool). Nếu tool di chuyển, cập nhật candidates hoặc dùng `config/discovered/omnivoice.json`.
  - Profile id sync = `voice_{stem}_{sha8}` để unique — deterministic, re-run idempotent.
- Next eligible task: **P3-T04 — Vietnamese normalization**

### TASK P3-T04 — DONE

- Started: 2026-08-03
- Finished: 2026-08-03
- Files changed:
  - `config/pronunciation_vi.json` — pronunciation dict (abbreviations, proper_names, currency)
  - `app/services/vi_normalize.py` — ViNormalizer: normalize (tags strip → proper names → abbreviations → percent → money → dates → thousands numbers → URLs → whitespace), _read_number/_read_int/_read_triple (tiếng Việt số đọc), get_normalizer/normalize_vi
  - `app/services/__init__.py` — export
  - `tests/unit/test_vi_normalize.py` — 11 tests
- Commands run:
  - Debug+fix: _PERCENT_RE match sai ('5' thay vì '25' → `\d+`), _MONEY_RE match sai ('0.000' → `\d{1,3}(?:\.\d{3})+`), _read_triple xử lý t='1' (mười/mười một/mười lăm)
  - `python -m pytest -q` → **174 passed**
- Tests: 11 (money 50.000đ + 1.200.000đ, percent 25% + 12.5%, date dd/mm + dd-mm, URL www + https, abbreviations VND + TP HCM, proper names kept, custom pronunciation override, whitespace/punctuation, empty, html tags, config load)
- Result: P3-T04 đạt AC — số tiền; phần trăm; ngày; URL; từ viết tắt; dấu câu; tên riêng override đều test pass.
- Known limitations:
  - `_NUMBER_RE` chỉ đọc số có thousands separator (50.000); số thường "15" giữ nguyên (TTS đọc bình thường).
  - Dictionary cần mở rộng theo nội dung thực tế (config/pronunciation_vi.json).
- Next eligible task: **P3-T05 — TTS scene pipeline**

### TASK P3-T05 — DONE

- Started: 2026-08-03
- Finished: 2026-08-03 (Phase 3 COMPLETE)
- Files changed:
  - `app/services/tts_pipeline.py` — TTSScenePipeline: run (tất cả scenes), generate_scene (normalize narration → cache key sha256 → synthesize qua provider → loudness normalize ffmpeg → persist actual_voice_duration_ms), probe_wav (ffprobe), loudness_normalize (ffmpeg loudnorm, optional), sha256_text
  - `app/services/__init__.py` — export
  - `tests/unit/test_tts_pipeline.py` — 6 tests
- Commands run:
  - `python -m pytest -q` → **180 passed**
- Tests: 6 (all scenes WAV, actual duration updated, rerun cache (no synthesize calls), changed narration regenerates only that scene, cache key derived from narration, empty narration raises)
- Result: P3-T05 đạt AC — tất cả scene có WAV; actual duration cập nhật (ffprobe/loudnorm); rerun dùng cache (sha256 narration, 0 synthesize calls); thay narration chỉ regenerate scene đó.
- Known limitations:
  - Cache key = sha256(normalized narration)[:12]; thay narration → key đổi → regenerate scene đó.
  - Loudness normalize phụ thuộc ffmpeg trên PATH; nếu thiếu → skip (optional).
  - Integration với worker thật cần worker đang chạy (P3-T02 verified rồi).
- Next eligible task: **P4-T01 — Image request/result schemas**

### TASK P4-T01 — DONE

- Started: 2026-08-03
- Finished: 2026-08-03 (Phase 4 first task)
- Files changed:
  - `app/providers/base.py` — `IMAGE_ROLES` tuple (background/subject/foreground/texture/composite); `ImageGenerationRequest.__post_init__` (validate role ∈ IMAGE_ROLES, seed ∈ [0, 2**32−1] hoặc None, candidate_count ≥ 1, aspect_ratio non-empty); `to_dict()`/`from_dict()` cho cả request & result (phục vụ P4-T05 candidate versioning + job persistence). Field bề mặt P4-T01 (prompt/role/reference_images/aspect_ratio/seed/candidate_count/output_path) đã có từ P2-T01, giờ thêm validation + serialize.
  - `tests/unit/test_image_schemas.py` — 29 tests mới
- Commands run:
  - `python -m pytest tests/unit/test_image_schemas.py -q` → **29 passed**
  - `python -m pytest -q` → **209 passed**
- Tests: 29 (request defaults, full fields, role enum accepted per value, invalid role raises (str/bool/int/None), seed None/0/max accepted, seed negative/2**32 raises, candidate_count 0/negative raises, empty aspect raises, request to_dict, request round-trip, request round-trip defaults preserved, result round-trip, result round-trip defaults)
- Result: P4-T01 đạt AC — all fields P4-T01 supported (prompt/role/reference/aspect/seed/candidate/output); validation fail-fast trên role/seed/count/aspect; serialize round-trip cho candidate versioning.
- Known limitations:
  - Field bả đã có từ P2-T01; task này thêm validation nghiêm ngặt + to_dict/from_dict nên không đổi signature `generate(request)`. Adapter code cũ không bị phá.
  - Seed range giới hạn 32-bit non-negative (0..`2**32−1`) — nếu provider khác hỗ trợ seed rộng hơn, nới `_is_valid_seed`.
- Next eligible task: **P4-T02 — FlowKit adapter**

### TASK P4-T03 — DONE

- Started: 2026-08-04
- Finished: 2026-08-04
- Files changed:
  - `app/providers/image/antigravity.py` — AntigravityImageProvider (ImageProvider protocol): generate (POST `/v1beta/models/{model}:generateContent`, `responseModalities:["IMAGE"]`, negative prompt fold vào text, decode inlineData base64 → ghi `output_path` tuyệt đối, normalize ImageGenerationResult với width/height (Pillow) + sha256 + prompt_hash), health (GET /v1/models, lọc image_models), capabilities (text-to-image only, aspect 16:9 fixed, concurrency 1), retry tenacity (429/5xx/transport, max_retries 3), error hierarchy (Auth 401 / NotFound 404 / Validation non-retryable / Retryable). Lưu ý: seed + provider_params.size được pass qua generationConfig nếu có.
  - `app/providers/image/__init__.py` — export adapter + errors
  - `tests/unit/test_image_antigravity.py` — 15 tests (MockTransport + PNG thật base64)
  - `data/probe_antigravity_adapter.py` — tạo rồi xóa (probe tạm)
- Commands run:
  - `python -m pytest tests/unit/test_image_antigravity.py -q` → **15 passed**
  - `python -m pytest -q` → **224 passed**
  - Probe thật: health ok (image_models gồm gemini-3.1-flash-image + gpt-image-2); generate → **JPEG 1376×768 RGB thật**, sha256, file đúng path. Xóa probe file.
- Tests: 15 (generate writes file + normalize dimensions/sha256, sends discovered contract URL+body, negative prompt folded, output_path required, 401 → AuthError, 404 → NotFoundError, no inlineData → ValidationError, invalid base64 → ValidationError, transport error retry→success, 429 retry→success, retries exhausted raises, health ok/unavailable, capabilities, runtime_checkable)
- Result: P4-T03 đạt AC — adapter không crash app; sinh ảnh thật qua CLIProxy (1376×768 JPEG); provider switching bằng config (base_url/model từ settings: `antigravity_image_base_url`/`antigravity_image_model`); normalize result thành ImageGenerationResult chuẩn.
- Known limitations:
  - Aspect KHÔNG điều khiển ở tầng translator (model trả 1408×768 / 1376×768 mặc định) — crop/fit phải làm ở tầng layer/render (P5/P6), đã ghi rõ trong capabilities + discovered/antigravity.json.
  - `seed` gửi trong generationConfig nếu provider hỗ trợ; model gemini-3.1-flash-image có thể ignore.
  - Health dùng GET /v1/models (proxy-wide) chứ không phải route image riêng — kiểm tra service up, không kiểm tra riêng model image.
  - FlowKit vẫn NOT_INSTALLED → nếu `default_image_provider` = flowkit, registry sẽ fallback (chưa implement fallback ở registry — P4-T05 sẽ handle).
- Next eligible task: **P4-T04 — Scene image prompt builder**

### TASK P4-T04 — DONE

- Started: 2026-08-04
- Finished: 2026-08-04
- Files changed:
  - `app/services/scene_image_prompt.py` — SceneImagePromptBuilder (deterministic, KHÔNG gọi LLM): `build(storyboard)` → `{scene_id: [BuiltPrompt,...]}` 5 role/scene (composite, background, subject, foreground, texture); `build_role`, `to_request` (wrap thành ImageGenerationRequest). Continuity: inline style_anchor (`_style_block`) + tái dùng verbatim character description (`_character_block`) mọi scene. Text-safe: `TEXT_SAFE_STUB` (no text/words/letters/numbers/watermark/logo/typography) trong mọi prompt. Foreground thêm `flat` vào negative constraint (overlay mất depth). Composite có `reference_images` từ character.image.
  - `app/services/__init__.py` — export BuiltPrompt + builder + error + TEXT_SAFE_STUB
  - `tests/unit/test_scene_image_prompt.py` — 22 tests mới
- Commands run:
  - `python -m pytest tests/unit/test_scene_image_prompt.py -q` → 22 passed (fixed 1 assert case)
  - `python -m pytest -q` → **246 passed**
- Tests: 22 (all 5 roles per scene, composite first, scene_id/role/aspect on every plan, empty storyboard, missing image_prompt raises, TEXT_SAFE_STUB in every role, background keeps open space, foreground edge overlay + flat, style block present & consistent across scenes, character description verbatim in subject, composite lists characters+locations, composite carries reference image, roles distinct, build_role invalid/missing, to_request wraps + joins negatives)
- Result: P4-T04 đạt AC — không yêu cầu AI tạo chữ (TEXT_SAFE_STUB), prompt có text-safe area (background empty, foreground edge overlay), prompt có continuity (style + verbatim character), prompt role-specific (5 role distinct). Output sẵn sàng thành ImageGenerationRequest cho P4-T05.
- Known limitations:
  - Builder deterministic template-based; chưa dùng motion_prompt (motion tách riêng tầng khác). Chưa có căn cứ foreground khác ngoài template.
  - Aspect mặc định 16:9; config qua constructor arg `aspect_ratio`.
  - Giả định scene có `image_prompt` (đã sinh P2-T05). Nếu thiếu → raise rõ ràng.
- Next eligible task: **P4-T05 — Image generation service**

### TASK P4-T05 — DONE

- Started: 2026-08-04
- Finished: 2026-08-04 (Phase 4 COMPLETE)
- Files changed:
  - `app/services/image_generation.py` — ImageGenerationService: `generate_project(project_id, session)` → ImagePipelineResult. Per-scene processing (mỗi scene xử lý tuần tự, per-role qua JobRunner job — 1 role fail không làm chết scene khác, retry MAX_ATTEMPTS_PER_ROLE=3). Candidate versioning (files `images/{scene}_{role}_{key8}_v{version:03d}.jpg`, regenerate bumps version). Cache theo `role_cache_key(prompt, seed, aspect, provider)` → file v1 tồn tại thì reuse (0 provider call). Fallback: primary provider fail permanent → `fallback_provider` (mặc định antigravity_image). Select candidate: composite newest version → `Scene.selected_image_asset_id` + Asset.selected=True. Persist mỗi ảnh thành Asset row. Project/scene state advance (IMG ES_GENERATNG→IMAGES_READY, scene→IMAGE_READY).
  - `app/services/__init__.py` — export service + dataclasses + role_cache_key
  - `tests/unit/test_image_generation.py` — 6 tests mới
  - `data/smoke_image_service.py` — tạo rồi xóa (smoke tạm)
- Commands run:
  - `python -m pytest tests/unit/test_image_generation.py -q` → 6 passed (fixed 1 test sai model fail-role)
  - `python -m pytest -q` → **252 passed**
  - Smoke thật: Antigravity + storyboard `prj_20260803_2798f1` (5 scenes) → build 5 role prompt/scene đúng, generate composite role thật → **JPEG 1376×768** — builder→service→provider wiring end-to-end pass.
- Tests: 6 (generate toàn project: 10 asset rows + 10 files, role set đầy đủ 5; selected_image_asset_id set + đúng 1 composite selected/scene; fail 1 scene không mất scene khác (scene_001 fail → scenes_ok=1, scene_002 đủ 5 assets); retry transient → success (n>10 calls thử lại); cache reuse → 0 provider call + version giữ nguyên; cache key deterministic)
- Result: P4-T05 đạt AC — generate toàn project; fail 1 scene không mất scene khác; retry; select candidate. Kết hợp P4-T01→P4-T05 xong Phase 4.
- Known limitations:
  - `ImagePipelineResult.generated/cached` đếm xapapxi (recount asset rows version==1; cached không track riêng — reuse cache để nguyên file, không sinh row mới). Nếu cần chính xác, bổ sung bộ đếm ở caller.
  - Concurrency mỗi role = 1 (sequilinear per scene) vì project scripts nhỏ + shared client key; JobRunner hỗ trợ nâng nếu cần.
  - Fallback provider hiện hardcode `FALLBACK_IMAGE_PROVIDER=antigravity_image`; chưa đọc từ config/settings (config-driven switching — đã handle primary qua `provider_name` arg + project.image_provider).
  - Transition project INGESTED→IMAGES_GENERATING bị skip nếu project ở STORYBOARD_VALIDATED (advance > MAX 2) — bằng thiết kế; image state của scene vẫn được set IMAGE_READY.
- Next eligible task: **P5-T01 — Layer package validator**

### TASK P5-T01 — DONE

- Started: 2026-08-04
- Finished: 2026-08-04
- Files changed:
  - `app/services/layer_validator.py` — LayerPackageValidator: validate(layer_package dict role→path) → LayerValidationResult (collect problems, không raise). Checks: image exists+decodable (Pillow loader injectable), role ∈ IMAGE_ROLES, aspect match target (tolerance 10%), alpha expectation (ALPHA_ROLES: subject/foreground/texture/composite phải RGBA; OPAQUE_ROLES: background phải opaque), dimensions (canvas bounds + max side 16384). `validate_or_raise` → LayerPackageValidationError. Helper `parse_aspect('16:9')`.
  - `app/services/__init__.py` — export validator + errors + ALPHA_ROLES + parse_aspect
  - `tests/unit/test_layer_validator.py` — 13 tests mới
- Commands run:
  - `python -m pytest tests/unit/test_layer_validator.py -q` → **13 passed**
  - `python -m pytest -q` → **265 passed**
- Tests: 13 (valid 5-role package passes, validate_or_raise ok, missing image problem, empty package problem, unknown role rejected, alpha roles set, subject RGB→problem, background RGBA→problem, aspect mismatch reported, aspect within tolerance passes, canvas oversize reported, no canvas no limit, validate_or_raise raises, parse_aspect variants)
- Result: P5-T01 đạt AC — validate image; aspect; alpha; role; dimensions. Non-destructive collect-problems design cho orchestrator gom hết lỗi 1 scene.
- Known limitations:
  - Alpha check dùng `"A" in mode.upper()` — chấp nhận RGBA/LA/PA. Không kiểm tra alpha thực tế có pixel transparent hay không (chỉ channel).
  - Aspect chỉ check ratio, không crop/fit (P5-T02 handle normalize). Tolerance 10% vì provider trả kích thước tùy ý (Antigravity 1376×768≈16:9).
  - Loader injectable để test không cần file thật; mặc định Pillow.
- Next eligible task: **P5-T02 — Direct layer workflow**

### TASK P5-T02 — DONE

- Started: 2026-08-04
- Finished: 2026-08-04
- Files changed:
  - `app/services/layer_workflow.py` — LayerWorkflow (Direct layer workflow, Strategy A): `prepare_scene(project_id, scene_id, layer_package, store)` → SceneLayerResult. Validate trước (P5-T01), rồi: normalize canvas (RGBA convert + cover-fit vào canvas + anchor theo role — background full-bleed (0,0), subject/composite bottom-center, texture/foreground centered), trim alpha (crop transparent bbox trên alpha layers), preserve metadata (PNG tEXt Role/Comment/Source), create preview composite (composite background paste + alpha_composite cho alpha layers vào transparent canvas 1920×1080 → `layers/{scene}_preview.png`), asset manifest (`manifests/asset_manifest_{scene}.json`).
  - `app/services/__init__.py` — export workflow + dataclasses
  - `tests/unit/test_layer_workflow.py` — 8 tests mới
- Commands run:
  - `python -m pytest tests/unit/test_layer_workflow.py -q` → 8 passed (fixed preview subdir: `previews` không thuộc PROJECT_SUBDIRS → dùng `layers/`)
  - `python -m pytest -q` → **273 passed**
- Tests: 8 (preview composite đúng size/mode, layer alignment (bg 0,0 full-bleed, subject bottom-center, fg/texture centered), alpha flag trên alpha roles, manifest đầy đủ (5 roles + canvas + preview), normalized layers written disk (RGBA canvas-sized), invalid package rejected, preview có background pixel opaque top-left, metadata Role preserved trong PNG)
- Result: P5-T02 đạt AC — preview composite render đúng (canvas 1920×1080, background opaque, layers aligned); layer alignment đúng theo role anchor; asset manifest đầy đủ (scene_id, canvas, preview path, per-role records với ox/oy/alpha).
- Known limitations:
  - Preview dùng `layers/{scene}_preview.png` (thay vì thư mục `previews/` riêng vì nằm ngoài PROJECT_SUBDIRS allowlist).
  - Cover-fit cắt tràn cạnh (center-crop) — nếu layer quan trọng ở mép, có thể mất nội dung; chưa có option letterbox.
  - Trim alpha cắt theo bbox (tight crop); chưa feather/không xử lý subject che hết frame.
  - Metadata preserve: PNG tEXt (Role/Comment/Source). Chưa copy ICC profile.
- Next eligible task: **P5-T03 — Segmentation fallback**

### TASK P5-T03 — DONE

- Files: `app/services/segmentation.py` (mới), `app/services/layer_workflow.py` (thêm `prepare_composite` Strategy B + `_save_layer` + `_force_opaque` + fix manifest bug), `app/services/__init__.py` (exports), `tests/unit/test_segmentation.py` (mới, 16 tests), `tests/unit/test_layer_workflow.py` (+3 wiring tests).
- `segmentation.py`: `segment_subject` (composite → subject RGBA), `derive_background`/`ensure_background` (opaque bg fallback), `_refine_mask` (threshold + largest connected component), `_feather` (GaussianBlur alpha edge). Backend lazy-load `RembgBackend` (`isnet-general-use`, onnx session lazy, lock-protected) — import module không kéo theo rembg.
- AC đạt: fixture người/vật tạo alpha hợp lệ (test real rembg: blob → subject_found True, alpha max 255); không crash khi không tìm thấy subject (mask rỗng/backend exception → composite fallback); fallback dùng composite layer (subject == full composite, method='fallback').
- LayerWorkflow thêm `prepare_composite(project_id, scene_id, composite_path, store=)` — segmentation thành subject + background, reuse preview/manifest writers, cùng `SceneLayerResult` như `prepare_scene`. Không raise khi thiếu subject.
- Bonus fix: `_write_manifest` trả về `store.write_manifest(...)` là tuple `(path, digest)` — cũ `return path` khiến `manifest_path` thành chuỗi tuple, file vẫn ghi nhưng path sai. Giờ unpack lấy path. Cả `prepare_scene` lẫn `prepare_composite` đều đúng.
- Test count: 292 pass (trước 273, +19).
- Ghi chú: rembg 2.0.76 + onnxruntime + numpy 1.26.4 có sẵn trong venv dự án (không thêm dependency).
- Next eligible task: **P5-T04 — Text-safe layout**

### TASK P5-T04 — DONE

- Files: `app/services/text_layout.py` (mới), `app/services/__init__.py` (exports), `tests/unit/test_text_layout.py` (mới, 32 tests).
- `text_layout.py`: `TextLayoutService.layout(text, canvas_size, placement, font_size, mask=)` → `TextLayoutResult` (box, font_path, font_size, lines, line_boxes, mask_avoided, overflow). Tính vùng an toàn (safe margin, mặc định 96px), tránh che subject khi có mask (thử các anchor theo thứ tự ưu tiên, chọn overlap nhỏ nhất), font fallback theo cmap coverage, greedy word-wrap + hard-break từ dài, co font khi text dài không vừa safe area.
- Font resolution: `resolve_font` dùng fontTools `getBestCmap()` kiểm tra mọi glyph (trừ space) — Arial/Tahoma/Segoe UI phủ đủ tiếng Việt (đã verify cmap trên máy). Candidates: arial, arialbd, tahoma, tahomabd, segoeui, segoeuib, calibri, verdana, times, cour.
- AC đạt: 16:9 (1920×1080) + 9:16 (1080×1920) đều cho box trong frame (parametrize cả 7 placement); tiếng Việt có dấu render được (font_covers True, render thật không tofu); không vượt safe area (co font + wrap, overflow False cả text rất dài).
- Placement anchors: top_left/top_center/top_right/center/bottom_left/bottom_center/bottom_right. Center anchor căn giữa cả chiều ngang/dọc (fix align).
- Test count: 324 pass (trước 292, +32). Không thêm dependency (fontTools 4.63 + PIL có sẵn).
- Next eligible task: **P6-T01 — MotionPlan schema** (Phase 6; dependency P3-T05, P5-T04).

### TASK P6-T01 — DONE

- Files: `app/schemas/motion_plan.py` (mới), `app/schemas/__init__.py` (exports), `tests/unit/test_motion_plan.py` (mới, 22 tests).
- `motion_plan.py`: `build_motion_plan(data)` → `MotionPlan` (frozen dataclass, round-trip qua `to_dict`). Validation: duration_ms required + positive; fps positive; z-order nguyên không âm trong [0, MAX_Z=64) + unique; easing allow-list (linear/ease_in/ease_out/ease_in_out/spring/bounce/overshoot); transition allow-list (none/hard_cut/crossfade/wipe_left/wipe_right/paper_wipe/paper_tear/dip_to_color); transform track dạng `{easing, keyframes}` hoặc bare `[[t,v]]` (times non-decreasing); camera/text_animations/effects validate theo cấu trúc.
- AC đạt: invalid easing fail (validate_easing + cả camera easing); invalid z-order fail (duplicate/out-of-range/non-integer/negative); duration required (thiếu hoặc ≤0 → MotionPlanError); frame_count derived từ `round(duration_ms/1000*fps)` (property, không lưu trong dict — test đã xác nhận).
- Kế thừa style từ storyboard.py: validate qua dataclass + extra checks thay vì jsonschema file riêng.
- Test count: 346 pass (trước 324, +22). Không thêm dependency.
- Next eligible task: **P6-T02 — Motion template library** (12 template; dep P6-T01).

### TASK P6-T02 — DONE

- Files: `app/services/motion_templates.py` (mới), `app/services/__init__.py` (exports), `tests/unit/test_motion_templates.py` (mới, 61 tests).
- Implement đủ 12 template (MASTER_PLAN section 11.2): 01_subject_slide_headline_pop → 12_conclusion_lockup. Registry `_TEMPLATE_BUILDERS` name→builder; mỗi builder nhận (scene_id, duration_ms, seed, canvas) trả dict hợp lệ → `build_template`/`build_template_plan` validate qua P6-T01 ngay khi build.
- Mỗi template: ≥3 independent motion channels (camera + ≥2 layers, mỗi layer ≥1 transform channel) + text_animations → không Ken Burns-only. Deterministic seed (random.Random(seed)) — cùng seed → cùng dict (snapshot AC). Duration scaling: keyframe times là fraction của duration, frame_count tuyến tính. 16:9 + 9:16 (tọa độ theo canvas size).
- Motion bounds (section 11.4): background scale ≤1.06, subject drift ≤4% width, rotation ±3°, foreground drift ≤6%, camera pan ≤3%, jitter 0.2–1.2px. Tests bắt được 2 lỗi thật: 08_photo_stack_shuffle rotation `angle*2` (±6°) và 04_before_after_split subject x 5% — đã sửa.
- AC đạt: snapshot deterministic; template không vượt bounds (test theo từng channel); không Ken Burns-only (≥3 channels + text_animations).
- Test count: 407 pass (trước 346, +61). Không thêm dependency.
- Next eligible task: **P6-T03 — Motion planner service** (kết hợp LLM recommendation + safe template + voice duration + asset availability + preset; dep P2-T05, P6-T02).

### TASK P6-T03 — DONE

- Files: `app/services/motion_planner.py` (mới), `app/services/__init__.py` (exports), `tests/unit/test_motion_planner.py` (mới, 14 tests).
- `MotionPlannerService.plan_scene(SceneMotionContext)` → `MotionPlannerResult`; `plan_project(project_id, scenes)` → `MotionProjectResult` (one bad scene không dừng các scene khác). `SceneMotionContext` gồm scene_id/voice_duration_ms/template_name/seed/canvas_size/available_roles/llm_recommendation.
- Kết hợp: LLM motion recommendation (duck-typed LLMProvider `generate_json`, chỉ chấp nhận template/seed/easing trong allowlist — `_sanitize_overrides` lọc, không bao giờ nhận tên lạ); safe template fallback (scene template unknown hoặc LLM trả tên lạ → `SAFE_TEMPLATE = 01_subject_slide_headline_pop`); voice duration (voice_duration_ms, fallback DEFAULT_VOICE_DURATION_MS=5000); asset availability (`_prune_unavailable_layers` drop layer có asset_role chưa chuẩn bị); preset (force template/duration/seed).
- LLM chỉ chọn grammar + tham số trong allowlist (AC: LLM không tự tạo FFmpeg filter) — response chỉ gồm template/seed/easing, easing áp lên mọi track có easing sẵn rồi re-validate qua P6-T01.
- AC đạt: output đúng schema (mọi plan pass validate_output); unknown template fallback (scene template lạ → fallback; LLM template lạ → discard, giữ scene template); LLM chỉ grammar trong allowlist; all scenes có plan kể cả LLM fail.
- Test count: 421 pass (trước 407, +14). Không thêm dependency.
- Next eligible task: **P6-T04 — FFmpeg motion compiler** (scale/translate/velocity/opacity/reveal/overlay/grain/shadow/text/transition; dep P6-T03).

### TASK P6-T04 — DONE

- Files: `app/services/ffmpeg_compiler.py` (mới), `app/services/__init__.py` (exports), `tests/unit/test_ffmpeg_compiler.py` (mới, 10 tests).
- `MotionCompiler.compile(plan, assets, options, output_path)` → `CompiledMotion` (command list, filter_graph, fps, resolution, frame_count). `build_filter_graph()` xếp layer theo z, per-layer chain (scale/rotate/translate/opacity), overlaid lên base, drawtext text animations, kết thúc `[final]` + transition. `run()` chạy qua injectable runner (subprocess.run, không shell).
- AC đạt:
  - command là argument list (`subprocess.run(cmd)`, không `shell=True` — test đọc source assert không có);
  - no shell=True trong module;
  - Windows path escape đúng: paths chứa space/backslash/colon qua argument list raw, test xác nhận không split (ví dụ `C:\Project Dir\...`);
  - filter graph test: mỗi channel sinh filter hợp lệ, **render thật** với ffmpeg 7.1.1 → MP4 h264 320×180 yuv420p 30fps returncode 0.
- Bug thật bắt & fix trong quá trình: `drawtext` fontfile Windows path cần `'C\:/Windows/...'` (bọc quotes + escape colon); label `[final]` phải là stream cuối để `-map "[final]"` resolve; base phải từ layer z=0 (tránh chain unconnected); `_validate_plan` wrap MotionPlanError → MotionCompilerError.
- Test count: 431 pass (trước 421, +10). Không thêm dependency (ffmpeg có sẵn trên máy).
- Next eligible task: **P6-T05 — Local scene renderer** (render silent scene MP4; AC: đúng FPS/resolution/duration±1 frame, yuv420p, 12 template smoke; dep P6-T04).

### TASK QZ-T01 — Quiz engine v2 consolidation + pilot re-render — DONE

- Started: 2026-09-10
- Finished: 2026-09-12
- Commit: `d2afac6` — feat(quiz): consolidate quiz engine v2 - german locale, multi-mode contract, rights-aware asset policy
- Files changed:
  - `app/services/quiz_engine_v2.py` — nhãn tiếng Đức (is_german: FRAGE / LEICHT / MITTEL / SCHWER / FINAL BOSS / RICHTIGE ANTWORT), tự dò GPU NVENC (h264_nvenc) chống nghẽn pipe trên Windows
  - `app/services/quiz_v2_contract.py` — 7 mode hợp lệ (thêm word_tiles, mystery_box, this_or_that)
  - `app/services/quiz_ai_generator.py` — 6 định dạng + chế độ multi_mode gameshow; luật hình ảnh: người/nhân vật → chibi 2D (an toàn bản quyền), tự nhiên/khoa học → cinematic 3D
  - `app/services/quiz_locales.py` — bộ chuỗi/nhãn tiếng Đức
  - `app/services/quiz_asset_resolver.py` + mới `quiz_asset_policy.py`, `quiz_episode_assets.py`, `quiz_source_review.py` — phân giải ảnh có rights, ngân sách sinh ảnh, thư mục asset theo tập, duyệt nguồn
  - `app/providers/image/antigravity.py` — gửi aspectRatio trong imageConfig (route /v1beta ... generateContent)
  - `app/ui_qt/quiz_json_dialog.py` + mới `quiz_source_dialog.py`; `app/ui_qt/main_window.py`, `app/gui_qt.py` — Multi-Mode Gameshow mặc định + dialog duyệt nguồn
- Commands run (2026-09-12):
  - `python -m pytest tests/unit/test_quiz*.py tests/unit/test_de_football_quiz_spec.py tests/unit/test_football_card_assets.py -q` → **323 passed (64.4s)**
  - `python output/pa1_pilot_multimode12/produce.py` → **208.77s / 6263 frames / decode pass** (ffmpeg null + ffprobe độc lập; render local, 0 gọi AI)
- Products (chờ Boss nghiệm thu nội dung/giọng):
  - `output/de_fussball_30_final/de_fussball_30_final.mp4` — 449.67s, 1920×1080@30, h264_nvenc + AAC stereo (2026-09-11)
  - `output/de_multimode_12/de_multimode_12.mp4` — 209.83s, 12 câu multi-mode (baseline 2026-09-11 22:39)
  - `output/pa1_pilot_multimode12/de_multimode_12.mp4` — 208.77s (pilot sau sửa 2026-09-12) + so sánh side-by-side/khung đôi/SSIM tại `output/pa1_pilot_multimode12/compare/`
- Known limitations:
  - Piper TTS không tất định giữa các lần tổng hợp → tổng thời lượng lệch ~1s/bản khi cache audio lạnh (baseline 209.83s vs pilot 208.77s); trong từng bản render, timeline dựng theo thời lượng thật nên hình/tiếng vẫn khớp
  - Đường ảnh AI phụ thuộc CLIProxy: gpt-image-2 từng HTTP 429 (hết quota); gemini-3.1-flash-image chỉ chạy qua `/v1beta/models/...:generateContent`; gpt-image-1.5 từng bị moderation với prompt tả thực người nổi tiếng (nay dùng chibi, 22/28 rights.json của bộ 30 câu là chibi)
  - Nghiệm thu giọng Đức + native-language của Boss còn treo; chưa publish/push
  - Dòng storyboard/vox (vox_cinematic_engine + pipelines) không có hoạt động source từ 2026-08-19; MASTER_PLAN dừng log ở P6-T04 (P6-T05+ chưa có entry)
- Next eligible task: (a) chạy 1 batch thật sinh câu mới qua đường AI (chốt nghẽn quota/chibi); (b) chốt sống/chết dòng engine cũ; (c) dọn script produce_*/render_* untracked ở root

### TASK QZ-T02 — Canary đường ảnh AI + loại gpt-image-1.5 khỏi quiz allowlist — DONE

- Finished: 2026-09-12 (commit `687dca0`)
- Bằng chứng canary (1 chat + 6 ảnh): `output/qa_ai_batch_20260912_canary1/`
  - `gemini-3.6-flash-high` (chat) OK 9.5s — 3 câu tiếng Đức multi_mode, contract pass
  - `gemini-3.1-flash-image` (Antigravity) OK 1264x848 (13.8s) — moderation/quota KHÔNG còn chặn (khác hôm 11/9)
  - `gpt-image-1.5` (CLIProxy) — route BỎ QUA `size`, cố định 1145x1374 (5:6) ở CẢ 2 request (51.4s / 62.0s) → trượt cổng layout quiz mọi slot
  - `gpt-image-2` (CLIProxy) OK đúng size 1536x1024 (27.3s); quota 429 hôm 11/9 đã hết
  - `grok-imagine-image` OK 1248x832 đúng 3:2 (7.9s) — nhận vai fallback-cuối
  - `gpt-image-2` + chibi người qua ĐƯỜNG POLICY (`resolve_with_policy`) OK 1536x1024 (28.7s), rights `ai_generated` ghi đủ, KHÔNG chữ nhúng (wrapper chống logo/text hoạt động)
- Config sau sửa: provider cliproxy mặc định `gpt-image-2`; fallback `[gpt-image-2, gpt-image-1.5, grok-imagine-image]` (grok cuối, không bao giờ mặc định); quiz allowlist `{gpt-image-2, gemini-3.1-flash-image}`; 2 pin test mới
- Tests: 327 passed (quiz suite + flowkit/provider)
- Known limitations: `gpt-image-1.5` chỉ còn hữu dụng ngoài quiz (route không tôn trọng size); 5 pipeline dòng cũ hardcode 1.5 — chờ chốt dòng cũ; ảnh AI có thể chèn chữ nhúng nếu KHÔNG đi qua wrapper policy (quiz luôn dùng policy + review hình); quota gpt-image-2 nhạy theo thời điểm
- Next eligible task: (a) chốt model chính thức cho kênh khi làm tập mới (28/28 ảnh baseline là gemini, GUI mặc định là gpt-image-2); (b) chốt sống/chết dòng engine cũ; (c) dọn script untracked ở root

### TASK QZ-T03 — Fallback quota an toàn cho ảnh quiz — DONE

- Finished: 2026-09-12 (commit `abf6fa0`)
- Chốt với Boss: model ảnh CHÍNH THỨC của kênh = `gpt-image-2`; hết quota (429) → tự fallback sang `gemini-3.1-flash-image` (an toàn: đúng tỉ lệ 3:2, sạch chữ qua policy); KHÔNG bao giờ rơi vào gpt-image-1.5
- `quiz_asset_policy.py`: `PRIMARY_MODEL`/`FALLBACK_MODEL`/`quota_exhausted()`; fallback chỉ kích hoạt khi lỗi quota; moderation/400 không reroute; sidecar ghi `model` thực đã sinh + `fallback_from` + `fallback_reason=quota`; `valid_record` chấp nhận lineage (re-run với model chính không regen); ASSET_CREDITS in kèm lineage
- Tests: 329 passed (2 test mới: 429 → fallback + tái dùng; moderation → không reroute)
- Known: nếu cả 2 chặng fail → lần chạy lại đòi reconcile ledger (đúng luật unknown-never-retried)
- Next eligible task: (a) chốt sống/chết dòng engine cũ; (b) dọn ~70 mục untracked ở root; (c) tùy chọn 1 call probe grok qua đường policy để thêm chặng-3 fallback

