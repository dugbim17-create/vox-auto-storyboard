# Auto Storyboard Vox

Tool chạy local trên Windows: nhận kịch bản văn bản → tự động tạo video hoàn chỉnh
(storyboard → image → VoxStyle layered motion → voice → final MP4).

## Nguồn sự thật

- `MASTER_PLAN_AUTO_STORYBOARD_VOX_WORKFLOW.md` — kiến trúc & task plan (bắt buộc đọc trước khi sửa code).
- `MASTER_PROGRESS.md` — trạng thái thực thi từng task.
- Code hiện tại trong repository.

## Quy tắc thực thi

- Chỉ thực thi một task ID tại một thời điểm.
- Không hard-code venv path, port, model ID, token, URL service.
- CLIProxy & OmniVoice đã cài — phải discovery đường dẫn/cổng thực tế, không cài lại.
- OmniVoice chạy bằng venv có sẵn, bọc thành worker riêng.
- FlowKit & Antigravity đi qua provider adapter.
- Local FFmpeg layered renderer là bắt buộc; image-to-video chỉ là quality tier.
- Phải viết/chạy test và đạt acceptance criteria trước khi báo DONE.
- Service local không hoạt động → đánh dấu BLOCKED kèm lệnh tái hiện, không giả lập.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
Copy-Item .env.example .env   # rồi điền giá trị thực
```

## Test

```powershell
python -m pytest
```

## Cấu trúc

Xem `MASTER_PLAN` section 4. Orchestrator nằm trong `app/`, worker TTS trong `workers/omnivoice_worker/`,
test trong `tests/` (unit / integration / e2e), project data trong `projects/`.
