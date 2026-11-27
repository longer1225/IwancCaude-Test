<#
.SYNOPSIS
    起两份隔离实例（7438 / 7439）用于测试，或按记录清理。

.DESCRIPTION
    对应《测试计划》6.1（环境与数据安全）与 2.3（已知限制）。
    1. 在 runs/evidence/<日期>/ 建隔离目录，导出 6+1 个 IWAN_* 变量；
    2. 双实例时把仓库复制到 runs/instance-b/ 并改其 .env 端口为 7439；
    3. 起 daemon、打印 core status、写 instances.json；
    4. -Stop 时按记录停止并清理。

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File docs\lab2-test\scripts\start-two-instances.ps1
.EXAMPLE
    powershell -ExecutionPolicy Bypass -File docs\lab2-test\scripts\start-two-instances.ps1 -Stop
#>
[CmdletBinding()]
param(
    [switch]$Single,
    [switch]$Stop,
    [int]$PortA = 7438,
    [int]$PortB = 7439
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$stamp = Get-Date -Format 'yyyy-MM-dd'
$evidence = Join-Path $repoRoot "runs\evidence\$stamp"
$record = Join-Path $evidence 'instances.json'
$instanceB = Join-Path $repoRoot 'runs\instance-b'

function Assert-PortFree {
    param([int]$Port)
    $busy = $false
    try {
        $c = New-Object System.Net.Sockets.TcpClient
        $c.Connect('127.0.0.1', $Port)
        $busy = $c.Connected
        $c.Close()
    } catch { $busy = $false }
    if ($busy) { throw "端口 $Port 已被占用：先停掉占用它的进程，或换端口（-PortA/-PortB）" }
}

function Stop-Recorded {
    if (-not (Test-Path $record)) { Write-Host '没有 instances.json 记录，跳过停止' -ForegroundColor Yellow; return }
    $items = Get-Content $record -Raw -Encoding UTF8 | ConvertFrom-Json
    foreach ($it in $items) {
        Write-Host ("停止 {0}（端口 {1}）..." -f $it.dir, $it.port) -ForegroundColor Cyan
        Push-Location $it.dir
        try { & uv run iwan core stop } catch { Write-Host ("  跳过：{0}" -f $_.Exception.Message) -ForegroundColor Yellow }
        Pop-Location
    }
    if (Test-Path $instanceB) { Remove-Item $instanceB -Recurse -Force -ErrorAction SilentlyContinue }
    Remove-Item $record -Force -ErrorAction SilentlyContinue
    Write-Host '已停止并清理' -ForegroundColor Green
}

if ($Stop) { Stop-Recorded; return }

New-Item -ItemType Directory -Force -Path $evidence | Out-Null
$dirs = @{
    trace   = Join-Path $evidence 'trace'
    memory  = Join-Path $evidence 'memory'
    sessions= Join-Path $evidence 'sessions'
    plugins = Join-Path $evidence 'plugins'
}
foreach ($d in $dirs.Values) { New-Item -ItemType Directory -Force -Path $d | Out-Null }
$policy  = Join-Path $evidence 'policy.toml'
$trust   = Join-Path $evidence 'trust.toml'
$secrets = Join-Path $evidence 'secrets.env'

# 隔离变量：本脚本进程内生效，并被 start 出的 daemon 继承
$env:IWAN_TRACE_FILE   = Join-Path $dirs.trace 'daemon.jsonl'
$env:IWAN_MEMORY_DIR   = $dirs.memory
$env:IWAN_SESSIONS_DIR = $dirs.sessions
$env:IWAN_PLUGINS_DIR  = $dirs.plugins
$env:IWAN_POLICY_FILE  = $policy
$env:IWAN_TRUST_FILE   = $trust
$env:IWAN_SECRETS_FILE = $secrets
$env:IWAN_SPEECH_PREWARM = '0'
if (-not $env:DEEPSEEK_API_KEY) {
    $env:DEEPSEEK_API_KEY = 'test-key-not-validated'
    $env:IWAN_LLM_BASE_URL = 'http://127.0.0.1:9'
    Write-Host '未检测到 Key，已使用假 Key + 死端点（离线链路）' -ForegroundColor Yellow
}

Write-Host ("隔离目录：{0}" -f $evidence) -ForegroundColor Cyan

$records = @()

# ---- 实例 A（当前仓库，端口取 .env 的 7438）----
Assert-PortFree -Port $PortA
Push-Location $repoRoot
try {
    & uv run iwan core start
    & uv run iwan core status
} finally { Pop-Location }
$records += [pscustomobject]@{ dir = $repoRoot; port = $PortA; role = 'A' }

# ---- 实例 B（仓库副本，端口 7439）----
if (-not $Single) {
    Assert-PortFree -Port $PortB
    if (Test-Path $instanceB) { Remove-Item $instanceB -Recurse -Force }
    Write-Host ('复制仓库副本到 {0}（首次较慢）...' -f $instanceB) -ForegroundColor Cyan
    & robocopy $repoRoot $instanceB /E /XD .git runs gui\node_modules .venv __pycache__ .mypy_cache .ruff_cache .pytest_cache /NFL /NDL /NJH /NJS /NP | Out-Null

    $envFile = Join-Path $instanceB '.env'
    (Get-Content $envFile -Encoding UTF8) -replace '^IWAN_PORT=.*$', "IWAN_PORT=$PortB" |
        Set-Content $envFile -Encoding UTF8
    Push-Location $instanceB
    try {
        & uv sync --quiet
        & uv run iwan core start
        & uv run iwan core status
    } finally { Pop-Location }
    $records += [pscustomobject]@{ dir = $instanceB; port = $PortB; role = 'B' }
}

$records | ConvertTo-Json | Set-Content $record -Encoding UTF8
Write-Host ''
Write-Host '起好了：' -ForegroundColor Green
$records | Format-Table role, port, dir -AutoSize
Write-Host ('验证 BUG-2：cd {0}; uv run iwan core stop; cd {1}; uv run iwan core status（应仍 running）' -f $instanceB, $repoRoot) -ForegroundColor Cyan
Write-Host ('清理：本脚本加 -Stop' -f $null) -ForegroundColor Cyan
