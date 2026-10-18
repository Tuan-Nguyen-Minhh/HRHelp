# Đóng góp cho P-029 — HR Help

Cảm ơn bạn đã quan tâm. Quy trình review:

| Phần | Đường dẫn | Ai duyệt |
|------|-----------|----------|
| Code | `src/`, `tests/`, `scripts/`, Dockerfile… | Maintainer bất kỳ |
| Tài liệu dự án | `docs/`, `ARCHITECTURE.md`, `eval/`… | Maintainer bất kỳ |

## Quy trình

1. Fork repo, tạo nhánh từ `main`: `git checkout -b feat/ten-thay-doi`
2. Commit theo [Conventional Commits](https://www.conventionalcommits.org/):
   `feat:`, `fix:`, `docs:`, `chore:`, `test:`, `refactor:`
3. Chạy kiểm tra trước khi push:
   ```bash
   ruff check .
   pytest
   ```
4. Mở PR vào `main`. CI (`.github/workflows/ci.yml`) phải xanh.

## Không commit thông tin bí mật

Tuyệt đối không commit API key, token, hay credential — kể cả trong
`.env.example`, comment, hay file docs.

- `.env.example` chỉ chứa **placeholder** (ví dụ `your-api-key-here`).
- Giá trị thật đặt trong `.env` — file này đã nằm trong `.gitignore`.
- Nếu lỡ commit, đọc [SECURITY.md](SECURITY.md): key coi như đã lộ và **phải
  được xoay (rotate)**, xoá commit thôi là chưa đủ.

## Báo lỗi

Mở issue kèm: môi trường (OS, Python version), các bước tái hiện, log lỗi.

Lỗ hổng bảo mật thì **không** mở issue công khai — làm theo [SECURITY.md](SECURITY.md).

## Quy tắc ứng xử

Tham gia repo này đồng nghĩa với việc bạn đồng ý tuân thủ
[Quy tắc ứng xử](CODE_OF_CONDUCT.md).
