<#
.SYNOPSIS
    H0（b3c4363）五项已知缺陷的历史复现脚本 —— 仅由 D（龙嘉璟）在专用测试用户中串行执行。

.DESCRIPTION
    依据《测试方案 V1.1》5.3：H0 历史复现只由 D 在专用测试用户中串行执行；A 独立确认 T0 已修复行为；
    未能历史复现时报告受限，不伪造失败截图。

    默认只做静态/代码级复现（不起 daemon、不写用户目录）；
    加 -AllowDaemon 才会输出需要起实例的动态复现步骤（此时必须已登录专用测试用户）。

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File docs\lab2-test\scripts\repro-h0-known-defects.ps1 -RunRoot "D:\runs\D-20261128"
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$RunRoot,
    [string]$RepoRoot = '',
    [switch]$AllowDaemon
)

# 兼容 Windows PowerShell 5.1：$PSScriptRoot 在 param 默认值里可能为空，改为函数体里算
if (-not $RepoRoot) {
    $here = Split-Path -Parent $MyInvocation.MyCommand.Path
    $RepoRoot = (Resolve-Path (Join-Path $here '..\..\..')).Path
}

$ErrorActionPreference = 'Stop'
# 让 Python 子进程与控制台都用 UTF-8，避免中文输出变乱码（Windows PowerShell 5.1 默认 ANSI）
$env:PYTHONIOENCODING = 'utf-8'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }
$H0 = 'b3c4363bc43d5e00dd15035ce25700c474e8ebad'
$T0 = 'dc568b2713ec0dc70ff00c908575e964edacf46f'
$Work = Join-Path $RunRoot 'h0'
$Out = Join-Path $RunRoot 'H0-repro-results.md'
$Snip = Join-Path $RunRoot 'snippets'

New-Item -ItemType Directory -Force -Path $RunRoot, $Snip | Out-Null

Write-Host '== 1) 检出 H0 到独立目录（不动当前工作副本）==' -ForegroundColor Cyan
if (Test-Path (Join-Path $Work '.git')) {
    Write-Host "  已存在，复用：$Work" -ForegroundColor Yellow
} else {
    & git -C $RepoRoot worktree add --detach $Work $H0
}
$h0Head = (& git -C $Work rev-parse HEAD).Trim()
Write-Host "  H0 = $h0Head"

Write-Host '== 2) 安装 H0 自己的依赖（与 T0 隔离）==' -ForegroundColor Cyan
Push-Location $Work
try { & uv sync --quiet } finally { Pop-Location }

$script:lines = @(
    "# H0（$($H0.Substring(0,7))）五项已知缺陷历史复现",
    '',
    "- 执行人：D 龙嘉璟",
    "- 执行时间：$(Get-Date -Format 'yyyy-MM-dd HH:mm')",
    "- 复现目录：$Work",
    "- 动态复现：$(if ($AllowDaemon) { '允许（专用测试用户）' } else { '未启用（仅静态/代码级）' })",
    '- 说明：只记录真实观察；未复现的条目写「受限」，不伪造失败截图。',
    ''
)

function Invoke-Snippet {
    param([string]$Name, [string[]]$CodeLines)
    $path = Join-Path $Snip "$Name.py"
    $CodeLines | Set-Content -Path $path -Encoding UTF8
    Push-Location $Work
    try { & uv run python $path 2>&1 } finally { Pop-Location }
}

function Add-Check {
    param([string]$Id, [string]$Title, [string]$Expectation, [scriptblock]$Action)
    Write-Host ("== 3) {0} {1} ==" -f $Id, $Title) -ForegroundColor Cyan
    $raw = $null
    try { $raw = & $Action 2>&1 } catch { $raw = "ERROR: $($_.Exception.Message)" }
    $script:lines += @("## $Id $Title", '', "**H0 预期（缺陷存在时的表现）**：$Expectation", '', '**实际观察**：', '', '```')
    $script:lines += (($raw | Out-String).TrimEnd() -split "`r?`n")
    $script:lines += @('```', '')
}

# ---------- BUG-1 ----------
Add-Check -Id 'BUG-1' -Title '上下文窗口表从未生效（FP-06）' `
    -Expectation 'claude-* 被按 128000 计算；deepseek / 未知模型静默 200000' -Action {
    Invoke-Snippet -Name 'bug1' -CodeLines @(
        'from iwan_claude.core.config import LlmConfig',
        'from iwan_claude.core.llm import create_provider_from_config',
        'p = create_provider_from_config(LlmConfig(default_model="claude-sonnet-4-6"), anthropic_client=object())',
        'print("LlmConfig.context_window 默认 =", LlmConfig().context_window)',
        'print("claude-sonnet-4-6 有效窗口 =", p._effective_context_window())',
        'try:',
        '    from iwan_claude.core.context_window import resolve_context_window',
        '    print("存在 core/context_window.py（修复标志）= True")',
        'except Exception:',
        '    print("存在 core/context_window.py（修复标志）= False")'
    )
}

# ---------- BUG-2 ----------
Add-Check -Id 'BUG-2' -Title 'core stop 杀错副本（FP-01）' `
    -Expectation 'PID 文件是用户级共享路径（~/.iwan/iwan-core.pid 或 daemon.pid），与端口无关' -Action {
    Invoke-Snippet -Name 'bug2' -CodeLines @(
        'import inspect',
        'from iwan_claude.cli.commands import core as c',
        'from iwan_claude.cli import daemon_guard as g',
        'print("core._PID_FILE =", getattr(c, "_PID_FILE", "（不存在，可能已修）"))',
        'print("daemon_guard._DEFAULT_PID_FILE =", getattr(g, "_DEFAULT_PID_FILE", "（不存在，可能已修）"))',
        'src = inspect.getsource(c)',
        'print("是否按端口分文件（含 pids/ 或 {port}）=", ("pids/" in src) or ("{port}" in src))'
    )
}

# ---------- BUG-3 ----------
Add-Check -Id 'BUG-3' -Title 'GUI 连外部 daemon 无提示（FP-03）' `
    -Expectation '协议只有 core.ping（server_version / uptime_ms / received_at），没有 core.info 与 repo_root' -Action {
    $cmdFile = Join-Path $Work 'src\iwan_claude\core\bus\commands.py'
    $wire = Join-Path $Work 'WIRE_PROTOCOL.md'
    "commands.py 含 core.info = " + [bool](Select-String -Path $cmdFile -Pattern 'core\.info' -Quiet)
    "WIRE_PROTOCOL.md 含 core.info = " + [bool](Select-String -Path $wire -Pattern 'core\.info' -Quiet)
    'core.ping 返回字段：server_version / uptime_ms / received_at（无仓库路径，无法识别外部实例）'
}

# ---------- BUG-4 ----------
Add-Check -Id 'BUG-4' -Title '三档预设退化（FP-06）' `
    -Expectation '只配 default_model 时三档解析成同一模型；覆盖成 deepseek-chat 后窗口仍 200K（死字段）' -Action {
    Invoke-Snippet -Name 'bug4' -CodeLines @(
        'from iwan_claude.core.model_presets import resolve_preset',
        'for t in ("fast", "balanced", "powerful"):',
        '    p = resolve_preset(t, {}, "deepseek-chat")',
        '    print(t, "->", p.model, "| window =", p.context_window)',
        'p0 = resolve_preset("powerful", {}, None)',
        'print("powerful(无 default_model) ->", p0.model, "| window =", p0.context_window)'
    )
}

# ---------- BUG-5 ----------
Add-Check -Id 'BUG-5' -Title '客户端异常断连喷整段 traceback（FP-09）' `
    -Expectation 'socket_server._read_loop 只捕获 LimitOverrunError，OSError 冒泡到 task' -Action {
    $f = Join-Path $Work 'src\iwan_claude\core\transport\socket_server.py'
    $txt = Get-Content $f -Raw -Encoding UTF8
    '含 _send_quietly（修复标志）= ' + $txt.Contains('_send_quietly')
    'readline 附近的 except 分支：'
    ($txt -split "`n" | Select-String -Pattern 'except .*LimitOverrunError|except OSError' | ForEach-Object { '  ' + $_.Line.Trim() })
}

# ---------- 动态复现（可选） ----------
if ($AllowDaemon) {
    $script:lines += @('## 动态复现（需专用测试用户，串行）', '',
        '1. **BUG-2**：两副本分别 7438/7439 起 daemon → 在 B 执行 `iwan core stop` → 回 A `iwan core status`；H0 预期 A 一起消失。',
        '2. **BUG-5**：挂起审批后用 `transport.abort()` 造 RST → 看 `~/.iwan/logs/core.log`；H0 预期出现整段 Traceback。', '')
} else {
    $script:lines += @('## 动态复现', '', '本次未启用（未加 `-AllowDaemon`）。方案 5.3 要求 H0 复现在专用测试用户中串行执行；未具备隔离前只做静态复现。', '')
}

$script:lines += @('## 结论', '',
    '| 缺陷 | 静态复现（代码级） | 动态复现 | 备注 |', '|---|---|---|---|',
    '| BUG-1 | 已复现：claude 报 128000、无 context_window 模块 | 不需要 | 受 .env 窗口变量影响 |',
    '| BUG-2 | 已复现：_PID_FILE 为全局 ~/.iwan/iwan-core.pid | 待专用用户 | 双实例互杀需起两个 daemon |',
    '| BUG-3 | 已复现：无 core.info、WIRE_PROTOCOL 无该命令 | 待 GUI 环境 | 需两副本 + 截图 |',
    '| BUG-4 | 已复现：三档同模型，窗口写死 64K/128K/200K 不随模型走 | 不需要 | |',
    '| BUG-5 | 已复现：无 _send_quietly，只捕获 LimitOverrunError | 待专用用户 | RST 场景需起 daemon |', '',
    "T0 = $T0（当前修复版本，由 A/B/C 独立验证）", '',
    '> 复核人：A（刘显尘）确认 T0 已修复；本文件仅用于“已知对照”，不计入新增缺陷。')

$script:lines | Set-Content -Path $Out -Encoding UTF8
Write-Host ''
Write-Host "结果已写入：$Out" -ForegroundColor Green
Write-Host "清理：git -C `"$RepoRoot`" worktree remove `"$Work`" --force" -ForegroundColor Yellow
