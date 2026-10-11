<#
.SYNOPSIS
  TriWitness W4-14 评审者消融：一键在本机（Windows + Docker Desktop/WSL2）跑完并打包结果。

.DESCRIPTION
  1. 克隆或更新仓库（默认 %USERPROFILE%\triwitness，main 分支）
  2. docker build 实验镜像（构建时下载 20 个基线源码包）
  3. docker run：容器内并发跑 4 个评审臂 × 40 题（默认并发 4），只用 deepseek-flash，走账本
  4. 评分并把结果 + 账本打成一个 zip，路径打印在最后

  DeepSeek 密钥只从本机环境变量 DEEPSEEK_API_KEY 读取，经 `docker run -e DEEPSEEK_API_KEY` 透传进容器；
  不写进脚本、镜像、日志或结果包。北京时间工作日 9-12、14-18 默认不跑（-AllowPeak 可强制）。
  中断后重跑同一命令会跳过已完成的题（结果在 -OutDir，账本在 docker 卷 tw-ablation-work）。

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File run-reviewer-ablation.ps1
.EXAMPLE
  .\run-reviewer-ablation.ps1 -Smoke            # 先冒烟：2 题 × 4 臂，约 ¥0.1
.EXAMPLE
  .\run-reviewer-ablation.ps1 -Parallel 3 -Repeats 2
#>
[CmdletBinding()]
param(
  [string]$RepoUrl = "https://github.com/Akarin7784/triwitness.git",
  [string]$Branch = "main",
  [string]$RepoDir = (Join-Path $env:USERPROFILE "triwitness"),
  [string]$OutDir = (Join-Path $env:USERPROFILE "tw-ablation-out"),
  [ValidateRange(1, 8)][int]$Parallel = 4,
  [ValidateRange(1, 5)][int]$Repeats = 1,
  [string]$Arms = "same,adversarial,checklist_t03,checklist_t10",
  [string]$Items = "",
  [string]$PipIndex = "",
  [switch]$Smoke,
  [switch]$AllowPeak,
  [switch]$NoPull
)

# 原生命令（git/docker）写 stderr 不算失败，一律看 $LASTEXITCODE
$ErrorActionPreference = "Stop"
$Image = "tw-reviewer-ablation"
$Volume = "tw-ablation-work"

function Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Fail($msg) { Write-Host "错误：$msg" -ForegroundColor Red; exit 1 }

# ---- 0. 前置检查 -------------------------------------------------------------
Step "检查环境"
foreach ($cmd in @("git", "docker")) {
  if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) { Fail "找不到 $cmd，请先安装并加入 PATH" }
}
$ErrorActionPreference = "Continue"
docker info --format "{{.ServerVersion}}" *> $null
$dockerOk = ($LASTEXITCODE -eq 0)
$ErrorActionPreference = "Stop"
if (-not $dockerOk) { Fail "Docker 没在运行（请先启动 Docker Desktop，WSL2 后端）" }
$key = [Environment]::GetEnvironmentVariable("DEEPSEEK_API_KEY", "Process")
if (-not $key) { $key = [Environment]::GetEnvironmentVariable("DEEPSEEK_API_KEY", "User") }
if (-not $key) { $key = [Environment]::GetEnvironmentVariable("DEEPSEEK_API_KEY", "Machine") }
if (-not $key) { Fail "没有找到环境变量 DEEPSEEK_API_KEY（在“系统属性 → 环境变量”里设置后重开终端）" }
$env:DEEPSEEK_API_KEY = $key   # 只放进本进程环境，供 docker -e 透传；不打印
Remove-Variable key

$bj = [System.TimeZoneInfo]::ConvertTimeBySystemTimeZoneId([DateTime]::UtcNow, "China Standard Time")
$peak = ($bj.DayOfWeek -ne "Saturday" -and $bj.DayOfWeek -ne "Sunday") -and
        (($bj.Hour -ge 9 -and $bj.Hour -lt 12) -or ($bj.Hour -ge 14 -and $bj.Hour -lt 18))
if ($peak -and -not $AllowPeak) { Fail ("现在是北京时间 {0:HH:mm}（工作日高峰 9-12 / 14-18），不跑。高峰后再试，或加 -AllowPeak" -f $bj) }

# ---- 1. 克隆 / 更新仓库 -------------------------------------------------------
Step "准备仓库 $RepoDir"
if (-not (Test-Path (Join-Path $RepoDir ".git"))) {
  git -c core.autocrlf=false clone --branch $Branch $RepoUrl $RepoDir
  if ($LASTEXITCODE -ne 0) { Fail "git clone 失败" }
} elseif (-not $NoPull) {
  git -C $RepoDir fetch origin $Branch
  if ($LASTEXITCODE -ne 0) { Fail "git fetch 失败" }
  git -C $RepoDir checkout $Branch
  git -C $RepoDir merge --ff-only "origin/$Branch"
  if ($LASTEXITCODE -ne 0) { Fail "本地 $Branch 有改动，无法快进；请处理后重试（或加 -NoPull）" }
}
$sha = (git -C $RepoDir rev-parse --short HEAD).Trim()
Write-Host "commit $sha"

# ---- 2. 构建镜像 --------------------------------------------------------------
Step "构建镜像 $Image（首次约 5-15 分钟：装依赖 + 下载 20 个基线源码包）"
$buildArgs = @("build", "-f", "evals/reviewer/Dockerfile", "-t", $Image, "--build-arg", "GIT_SHA=$sha")
if ($PipIndex) { $buildArgs += @("--build-arg", "PIP_INDEX_URL=$PipIndex") }
$buildArgs += "."
Push-Location $RepoDir
try { & docker @buildArgs; if ($LASTEXITCODE -ne 0) { Fail "docker build 失败" } } finally { Pop-Location }

# ---- 3. 运行 ------------------------------------------------------------------
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$runArgs = @("--arms", $Arms, "--repeats", "$Repeats", "--parallel", "$Parallel")
if ($Smoke) { $runArgs += @("--items", "d01-defect,d01-clean") }
elseif ($Items) { $runArgs += @("--items", $Items) }
if ($AllowPeak) { $runArgs += "--allow-peak" }

Step "开始运行（并发 $Parallel；全量 160 次评审预计 2-4 小时；可随时 Ctrl+C，重跑续上）"
$started = Get-Date
& docker run --rm --name tw-reviewer-ablation `
  -e DEEPSEEK_API_KEY `
  -v "${OutDir}:/out" `
  -v "${Volume}:/work" `
  --cpus 8 --memory 12g `
  $Image @runArgs
$rc = $LASTEXITCODE
$mins = [int]((Get-Date) - $started).TotalMinutes

# ---- 4. 结果 ------------------------------------------------------------------
$zip = Get-ChildItem -Path $OutDir -Filter "reviewer-ablation-*.zip" -ErrorAction SilentlyContinue |
       Sort-Object LastWriteTime -Descending | Select-Object -First 1
Write-Host ""
if ($rc -eq 3) { Write-Host "进入北京时间高峰，已暂停；高峰后重跑本脚本即可续上（已完成的不会重跑）。" -ForegroundColor Yellow }
elseif ($rc -ne 0) { Write-Host "运行返回 $rc，请把下面的 zip（含 run.log）发回分析。" -ForegroundColor Yellow }
if ($zip) {
  Write-Host ("完成（{0} 分钟）。结果包：{1}" -f $mins, $zip.FullName) -ForegroundColor Green
  Write-Host "把这个 zip 发回即可（不含密钥）。报告预览：$OutDir\ablation\report.md"
} else {
  Write-Host "没有生成结果包，请检查 $OutDir\ablation\run.log" -ForegroundColor Red
}
exit $rc
