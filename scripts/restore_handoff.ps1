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

# 3. Copy + restore
docker cp $Dump "${Container}:/tmp/restore_full.dump"
docker exec $Container pg_restore -U postgres -d $DbName --no-owner --no-privileges --clean --if-exists /tmp/restore_full.dump
docker exec $Container rm -f /tmp/restore_full.dump
Write-Host "Restore xong vào DB '$DbName'. Chạy verify:"
Write-Host '  $env:PYTHONIOENCODING="utf-8"; .\.venv\Scripts\python.exe scripts\verify_db.py   # kỳ vọng 77 PASS, 0 FAIL'
