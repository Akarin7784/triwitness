<#
.SYNOPSIS
  TriWitness W5-13 外部对照：用 Harbor 在 WSL2 里跑 Terminal-Bench 2.0 的 10 题子集（Agent = TriWitness，deepseek-flash 非思考），打包结果。

.DESCRIPTION
  为什么走 WSL2：Harbor 是 Linux 工具，用 docker compose 起任务容器；TB2 的 verifier 需要联网装依赖。
  前置：WSL2 发行版（如 Ubuntu）+ Docker Desktop 打开该发行版的 WSL integration；WSL 里有 git、curl（uv 缺失会自动装到用户目录）。

  1. 在 WSL 里克隆或更新仓库到 ~/tw-harbor/triwitness（main），uv sync
  2. 取 terminal-bench-2 的固定提交（scripts/harbor_external.py 里的 TB2_SHA），只跑脚本内置的 10 题
  3. harbor run -a triwitness.integrations.harbor_agent:TriWitnessAgent（并发默认 2），出 report.md，连同账本打成 zip，复制到 -OutDir

  DeepSeek 密钥只从本机环境变量 DEEPSEEK_API_KEY 读取，经 WSLENV 透传给 WSL 进程；不写进脚本、文件或结果包。
  北京时间工作日 9-12、14-18 默认不开始（-AllowPeak 可强制）。
  预估花费：10 题约 ¥0.5-2（终端题步数多；以账本实扣为准）；-Smoke 只跑 fix-git 一题，约 ¥0.05-0.2。

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File run-harbor-tb2.ps1 -Smoke
.EXAMPLE
  .\run-harbor-tb2.ps1 -Distro Ubuntu -Concurrency 2
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\windows\run-harbor-tb2.ps1 -Repeats 3 -Tag r2
  第二轮：10 题 × 3 次（约 ¥2）。每次重复一个 Harbor job（WSL 里 ~/tw-harbor/jobs/r2/rep0..rep2），
  中断后重跑同一命令：已完成的 job 跳过、未完成的 harbor jobs resume；结果包只含这一组。

.NOTES
  -Repeats N（默认 1 = 原来的单次运行）；-Tag 是这一组重复的目录名（默认 repeats）。
#>
[CmdletBinding()]
param(
  [string]$Distro = "",
  [string]$RepoUrl = "https://github.com/Akarin7784/triwitness.git",
  [string]$Branch = "main",
  [string]$OutDir = (Join-Path $env:USERPROFILE "tw-harbor-out"),
  [ValidateRange(1, 4)][int]$Concurrency = 2,
  [ValidateRange(1, 10)][int]$Repeats = 1,
  [ValidatePattern('^[A-Za-z0-9_-]*$')][string]$Tag = "",
  [switch]$Smoke,
  [switch]$AllowPeak
)

$ErrorActionPreference = "Stop"
function Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Fail($msg) { Write-Host "错误：$msg" -ForegroundColor Red; exit 1 }

Step "检查环境"
if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) { Fail "找不到 wsl.exe（需要 WSL2：wsl --install）" }
$key = [Environment]::GetEnvironmentVariable("DEEPSEEK_API_KEY", "Process")
if (-not $key) { $key = [Environment]::GetEnvironmentVariable("DEEPSEEK_API_KEY", "User") }
if (-not $key) { Fail "没有 DEEPSEEK_API_KEY 环境变量（用户级或当前会话）" }
$env:DEEPSEEK_API_KEY = $key
# 只透传这一个变量名；值不出现在命令行里
if ($env:WSLENV) { $env:WSLENV = "$($env:WSLENV):DEEPSEEK_API_KEY/u" } else { $env:WSLENV = "DEEPSEEK_API_KEY/u" }

$wslArgs = @()
if ($Distro) { $wslArgs += @("-d", $Distro) }
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$ErrorActionPreference = "Continue"
$outWsl = (& wsl.exe @wslArgs -e wslpath -a "$OutDir" | Out-String).Trim()
$ErrorActionPreference = "Stop"
if (-not $outWsl) { Fail "wslpath 失败：WSL 发行版不可用？（wsl -l -v 查看）" }

$flags = @("--out-win", "'$outWsl'", "--concurrency", "$Concurrency")
if ($Smoke) { $flags += "--smoke" }
if ($Repeats -gt 1) { $flags += @("--repeats", "$Repeats"); if ($Tag) { $flags += @("--tag", $Tag) } }
if ($AllowPeak) { $flags += "--allow-peak" }
$bootstrap = @"
set -e
export TW_REPO_URL='$RepoUrl' TW_BRANCH='$Branch'
src="`$HOME/tw-harbor/triwitness"
if [ ! -d "`$src/.git" ]; then mkdir -p "`$HOME/tw-harbor"; git clone -q --branch '$Branch' '$RepoUrl' "`$src"; fi
git -C "`$src" fetch -q origin '$Branch' && git -C "`$src" checkout -q '$Branch' && git -C "`$src" merge -q --ff-only 'origin/$Branch'
exec bash "`$src/scripts/wsl/run-harbor-tb2.sh" $($flags -join ' ')
"@
Step "在 WSL 里运行 Harbor（日志同时写入 ~/tw-harbor/run.log）"
$ErrorActionPreference = "Continue"
& wsl.exe @wslArgs -e bash -lc ($bootstrap -replace "`r", "")
$rc = $LASTEXITCODE
$ErrorActionPreference = "Stop"
if ($rc -eq 3) { Write-Host "现在是北京时间工作日高峰，未开始；高峰后重跑同一命令" -ForegroundColor Yellow; exit 3 }
$zip = Get-ChildItem -Path $OutDir -Filter "harbor-tb2-*.zip" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if ($zip) { Step "完成（退出码 $rc）。结果包：$($zip.FullName)  ——请把它发回来" } else { Fail "没有生成结果包（退出码 $rc），请把 WSL 里 ~/tw-harbor/run.log 发回来" }
exit $rc
