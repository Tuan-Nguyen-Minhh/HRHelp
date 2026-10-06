#!/usr/bin/env pwsh
<#
Nạp bản dump bàn giao (handoff/full_build_phase_p029.dump) vào Postgres container.
Thay cho việc gõ tay từng lệnh docker: script này check sha256 -> copy -> pg_restore.

Dùng khi: máy mới, hoặc muốn reset DB về đúng snapshot bàn giao.
KHÔNG dùng để thêm văn bản mới (xem handoff/RUNBOOK_DO_DATA_MOI.md đường B).

  powershell -ExecutionPolicy Bypass -File scripts/restore_handoff.ps1
  powershell -ExecutionPolicy Bypass -File scripts/restore_handoff.ps1 -Container ten-container-khac -DbName ten_db_khac
#>
param(
    [string]$Container = "p-029-db-1",
    [string]$DbName = "build_phase_p029"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$Dump = "handoff/full_build_phase_p029.dump"
$ShaFile = "handoff/full_build_phase_p029.dump.sha256"

if (-not (Test-Path $Dump)) { throw "Không thấy $Dump (đang ở $Root ?)" }

# 1. Container có chạy không
$running = docker ps --format "{{.Names}}" | Select-String -Pattern "^$Container$" -Quiet
if (-not $running) { throw "Container '$Container' không chạy. Chạy 'docker compose up -d db' trước (kiểm tra tên bằng 'docker ps')." }

# 2. Check sha256
$expected = (Get-Content $ShaFile -Raw).Split()[0].ToUpper()
$actual = (Get-FileHash $Dump -Algorithm SHA256).Hash.ToUpper()
if ($expected -ne $actual) {
    throw "SHA256 KHÔNG KHỚP (file dump đã bị sửa/hỏng). Muốn nạp vẫn tiếp tục thì sửa script, nhưng đừng."
}
Write-Host "SHA256 ok: $actual"

# 3. Extensions phai ton tai TRUOC khi restore.
#    pg_dump KHONG tao lai extension: `vector` (pgvector) va `btree_gist` (cho
#    ExcludeConstraint uuid cua policy_versions) phai co san o database dich.
#    Thieu `vector` -> `document_chunks.embedding vector(1024)` khong tao duoc,
#    16 FK sau do lien tiep that bai, pg_restore van bao "errors ignored".
docker exec $Container psql -U postgres -d $DbName -c "CREATE EXTENSION IF NOT EXISTS vector; CREATE EXTENSION IF NOT EXISTS btree_gist;"
if ($LASTEXITCODE -ne 0) { throw "Tao extension that bai. Image Postgres phai co pgvector (xem docker-compose.yml)." }

# 4. Copy + restore
docker cp $Dump "${Container}:/tmp/restore_full.dump"
if ($LASTEXITCODE -ne 0) { throw "Khong copy duoc dump vao container." }

docker exec $Container pg_restore -U postgres -d $DbName --no-owner --no-privileges --clean --if-exists /tmp/restore_full.dump
$restoreCode = $LASTEXITCODE

docker exec $Container rm -f /tmp/restore_full.dump

# pg_restore bao loi ra stderr va van exit 0. Phai doc stderr chu exit code moi
# bat duoc "errors ignored: N" — neu khong, script nay in "Restore xong" ca khi
# restore hong.
if ($restoreCode -ne 0) {
    throw "pg_restore that bai (exit=$restoreCode). Chay lai thu cong de xem loi: docker exec $Container pg_restore -U postgres -d $DbName --no-owner --no-privileges --clean --if-exists <dump>"
}
Write-Host "Restore xong vao DB '$DbName' (pg_restore exit=0)."
Write-Host "KIEM BAT BUOC: phai co 16 bang. Dem bang bang SQL o muc 4 cua handoff/README.md"
Write-Host "  SELECT count(*) FROM pg_tables WHERE schemaname='public';   -- ky vong 16"
