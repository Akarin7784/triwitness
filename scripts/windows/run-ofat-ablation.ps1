<#
.SYNOPSIS
  TriWitness W5 OFAT 消融（dev 15 题 × 10 个配置）：一键在本机（Windows + Docker Desktop/WSL2）跑完并打包结果。

.DESCRIPTION
  1. 克隆或更新仓库（默认 %USERPROFILE%\triwitness，main 分支）
  2. docker build 运行镜像 tw-eval-runner（evals/runner/Dockerfile）
  3. docker run：挂载宿主 docker.sock，容器在宿主 Docker 上构建 15 个任务镜像、起断网沙箱，逐个配置跑
     `tw eval run --live`（并发默认 3），只用 deepseek-flash，全部记账本
  4. 出报告（McNemar + Holm + bootstrap），把结果 + 账本打成一个 zip，路径打印在最后

  DeepSeek 密钥只从本机环境变量 DEEPSEEK_API_KEY 读取，经 `docker run -e DEEPSEEK_API_KEY` 透传进容器；
  不写进脚本、镜像、日志或结果包。北京时间工作日 9-12、14-18 默认不开始新配置（-AllowPeak 可强制）。
  中断后重跑同一命令会跳过已完成的题（结果在 -OutDir，账本在 docker 卷 tw-ofat-work）。

  预估花费：-Attempts 1 约 ¥11（10 配置 × 15 题；思考档按 1.5-2.5 倍估）；-Attempts 3 约 ¥33。以账本实扣为准。

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File run-ofat-ablation.ps1
.EXAMPLE
  .\run-ofat-ablation.ps1 -Smoke              # 先冒烟：基线 × 1 道合成题，约 ¥0.02
.EXAMPLE
  .\run-ofat-ablation.ps1 -Only "base,planner" -Attempts 3
#>
[CmdletBinding()]
param(
  [string]$RepoUrl = "https://github.com/Akarin7784/triwitness.git",
  [string]$Branch = "main",
  [string]$RepoDir = (Join-Path $env:USERPROFILE "triwitness"),
  [string]$OutDir = (Join-Path $env:USERPROFILE "tw-ofat-out"),
  [string]$Spec = "evals/ablations/w5-round1.yaml",
  [ValidateRange(1, 8)][int]$Parallel = 3,
  [ValidateRange(1, 5)][int]$Attempts = 1,
  [string]$Only = "",
  [string]$PipIndex = "",
  [switch]$Smoke,
  [switch]$AllowPeak,
  [switch]$NoPull
)

# 原生命令（git/docker）写 stderr 不算失败，一律看 $LASTEXITCODE
$ErrorActionPreference = "Stop"
$Image = "tw-eval-runner"
$Volume = "tw-ofat-work"

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
Step "构建镜像 $Image（首次约 3-8 分钟）"
$buildArgs = @("build", "-f", "evals/runner/Dockerfile", "-t", $Image, "--build-arg", "GIT_SHA=$sha")
if ($PipIndex) { $buildArgs += @("--build-arg", "PIP_INDEX_URL=$PipIndex") }
$buildArgs += "."
Push-Location $RepoDir
try { & docker @buildArgs; if ($LASTEXITCODE -ne 0) { Fail "docker build 失败" } } finally { Pop-Location }

# ---- 3. 运行 ------------------------------------------------------------------
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$runArgs = @($Spec, "--concurrency", "$Parallel", "--attempts", "$Attempts")
if ($Smoke) { $runArgs += @("--only", "base", "--task", "csv-blank-line") }
elseif ($Only) { $runArgs += @("--only", $Only) }
if ($AllowPeak) { $runArgs += "--allow-peak" }

Step "开始运行（并发 $Parallel；全量约 3-6 小时，首次还要构建 15 个任务镜像；可随时 Ctrl+C，重跑续上）"
$started = Get-Date
& docker run --rm --name tw-ofat-ablation `
  -e DEEPSEEK_API_KEY `
  -v //var/run/docker.sock:/var/run/docker.sock `
  -v "${OutDir}:/out" `
  -v "${Volume}:/work" `
  $Image @runArgs
$rc = $LASTEXITCODE
$mins = [int]((Get-Date) - $started).TotalMinutes

# ---- 4. 结果 ------------------------------------------------------------------
$zip = Get-ChildItem -Path $OutDir -Filter "ofat-ablation-*.zip" -ErrorAction SilentlyContinue |
       Sort-Object LastWriteTime -Descending | Select-Object -First 1
Write-Host ""
if ($rc -eq 3) { Write-Host "进入北京时间高峰，已暂停；高峰后重跑本脚本即可续上（已完成的不会重跑）。" -ForegroundColor Yellow }
elseif ($rc -ne 0) { Write-Host "运行返回 $rc，请把下面的 zip（含 run.log）发回分析。" -ForegroundColor Yellow }
if ($zip) {
  Write-Host ("完成（{0} 分钟）。结果包：{1}" -f $mins, $zip.FullName) -ForegroundColor Green
  Write-Host "把这个 zip 发回即可（不含密钥）。报告预览：$OutDir\ofat\report.md"
  Write-Host "任务镜像（tw-task-*）留在本机 Docker 里，续跑 / 重复实验可复用；不需要时 docker image prune -a --filter label=tw.kind=task-image"
} else {
  Write-Host "没有生成结果包，请检查 $OutDir\ofat\run.log" -ForegroundColor Red
}
exit $rc
