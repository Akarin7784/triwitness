<#
.SYNOPSIS
  TriWitness W8-01 终测：test 集 35 题 × {单 Executor 基线, 完整流水线 orchestrated-1m} × 1 次，一键在本机跑完并打包。

.DESCRIPTION
  1. 克隆或更新仓库（默认 %USERPROFILE%\triwitness，main 分支）
  2. 磁盘检查（Docker 数据盘剩余 < -MinFreeGB 就不开始）
  3. docker build 运行镜像 tw-eval-runner（evals/runner/Dockerfile）
  4. docker run：挂载宿主 docker.sock，容器在宿主 Docker 上构建 35 个任务镜像、起断网沙箱，
     依次跑 baseline、orchestrated 两臂 `tw eval run --live --suite test --allow-test`（并发默认 3）
  5. 出报告（Resolved@1 + Wilson、¥/题、缓存命中、模型快照、价格表版本、配对 McNemar），
     结果 + 账本打成 zip（超过 24MB 自动拆成多个可独立解压的 part01/part02…），路径打印在最后

  只用 deepseek-flash；评测模式权限全开、不读写记忆；高峰照跑（按高峰价记账）；不设金额上限，只有防失控上限。
  DeepSeek 密钥从本机环境变量 DEEPSEEK_API_KEY 读取，没有就在终端里提示输入（不回显）；
  只放进本进程环境、经 `docker run -e DEEPSEEK_API_KEY` 透传，不写进脚本、镜像、日志或结果包。
  中断（Ctrl+C / 断电）后重跑同一命令：已有 result.json 的题跳过（结果在 -OutDir，账本在 docker 卷 tw-final-work）。

  预估：空闲价约 ¥17（基线约 ¥4 + 流水线约 ¥13）；全程高峰约 ¥34。以账本实扣为准。
  耗时：首次构建 35 个任务镜像约 30-60 分钟；基线约 1.5-2.5 小时，流水线约 2.5-4 小时（并发 3）。

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File run-final-eval.ps1
.EXAMPLE
  .\run-final-eval.ps1 -Smoke                 # 先冒烟：基线 × 1 题（约 ¥0.1，含该题镜像构建）
.EXAMPLE
  .\run-final-eval.ps1 -Arms orchestrated     # 只跑 / 续跑某一臂
.EXAMPLE
  .\run-final-eval.ps1 -Reproduce             # 终测后顺带 W8-05：复现 baseline 臂 1 道最便宜的已解决题并对比（约 ¥0.05-0.2）
.EXAMPLE
  .\run-final-eval.ps1 -ReproduceOnly         # 终测已跑完：只做 W8-05 复现 + 重新打包
.EXAMPLE
  .\run-final-eval.ps1 -BundleOnly            # 不跑，只重新出报告并打包
#>
[CmdletBinding()]
param(
  [string]$RepoUrl = "https://github.com/Akarin7784/triwitness.git",
  [string]$Branch = "main",
  [string]$RepoDir = (Join-Path $env:USERPROFILE "triwitness"),
  [string]$OutDir = (Join-Path $env:USERPROFILE "tw-final-out"),
  [ValidateRange(1, 8)][int]$Parallel = 3,
  [string]$Arms = "baseline,orchestrated",
  [ValidateRange(10, 500)][int]$MinFreeGB = 40,
  [string]$PipIndex = "",
  [switch]$Smoke,
  [switch]$BundleOnly,
  [switch]$Reproduce,
  [switch]$ReproduceOnly,
  [switch]$NoPull
)

# 原生命令（git/docker）写 stderr 不算失败，一律看 $LASTEXITCODE
$ErrorActionPreference = "Stop"
$Image = "tw-eval-runner"
$Volume = "tw-final-work"
$SmokeTask = "swe-ccflow-24"

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

if (-not $BundleOnly) {
  $key = [Environment]::GetEnvironmentVariable("DEEPSEEK_API_KEY", "Process")
  if (-not $key) { $key = [Environment]::GetEnvironmentVariable("DEEPSEEK_API_KEY", "User") }
  if (-not $key) { $key = [Environment]::GetEnvironmentVariable("DEEPSEEK_API_KEY", "Machine") }
  if (-not $key) {
    $sec = Read-Host "没有找到环境变量 DEEPSEEK_API_KEY；请粘贴密钥（不回显，只用于本次运行）" -AsSecureString
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec)
    try { $key = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
    Remove-Variable sec
  }
  if (-not $key) { Fail "没有密钥，退出" }
  $env:DEEPSEEK_API_KEY = $key   # 只放进本进程环境，供 docker -e 透传；不打印、不落盘
  Remove-Variable key
}

# 磁盘：Docker Desktop 的 WSL2 虚拟盘默认在系统盘（%LOCALAPPDATA%\Docker）
$drive = (Split-Path -Qualifier $env:LOCALAPPDATA).TrimEnd(":")
$freeGB = [math]::Round((Get-PSDrive -Name $drive).Free / 1GB, 1)
Write-Host ("Docker 数据盘 {0}: 剩余 {1} GB（要求 ≥ {2} GB）" -f $drive, $freeGB, $MinFreeGB)
if (-not $BundleOnly -and $freeGB -lt $MinFreeGB) {
  Fail ("磁盘剩余 {0} GB 不足 {1} GB：先清理（docker image prune -a --filter label=tw.kind=task-image 可删旧任务镜像），或加 -MinFreeGB 调低" -f $freeGB, $MinFreeGB)
}

$bj = [System.TimeZoneInfo]::ConvertTimeBySystemTimeZoneId([DateTime]::UtcNow, "China Standard Time")
$peak = ($bj.DayOfWeek -ne "Saturday" -and $bj.DayOfWeek -ne "Sunday") -and
        (($bj.Hour -ge 9 -and $bj.Hour -lt 12) -or ($bj.Hour -ge 14 -and $bj.Hour -lt 18))
if ($peak) { Write-Host ("提示：现在是北京时间 {0:HH:mm}，DeepSeek 高峰价（约 2 倍），照跑、照实记账。" -f $bj) -ForegroundColor Yellow }

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
Write-Host "commit $sha（终测冻结在这个提交；续跑请保持同一提交，或加 -NoPull）"

# ---- 2. 构建镜像 --------------------------------------------------------------
Step "构建镜像 $Image（首次约 3-8 分钟）"
$buildArgs = @("build", "-f", "evals/runner/Dockerfile", "-t", $Image, "--build-arg", "GIT_SHA=$sha")
if ($PipIndex) { $buildArgs += @("--build-arg", "PIP_INDEX_URL=$PipIndex") }
$buildArgs += "."
Push-Location $RepoDir
try { & docker @buildArgs; if ($LASTEXITCODE -ne 0) { Fail "docker build 失败" } } finally { Pop-Location }

# ---- 3. 运行 ------------------------------------------------------------------
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$common = @("--rm", "--name", "tw-final-eval", "-v", "${OutDir}:/out", "-v", "${Volume}:/work")
$started = Get-Date
if ($BundleOnly) {
  Step "只出报告并打包"
  & docker run @common --entrypoint bash $Image -c `
    "cd /app && uv run --no-sync python scripts/final_eval.py report --out /out/final && uv run --no-sync python scripts/final_eval.py bundle --out /out/final --dest /out"
  $rc = $LASTEXITCODE
} else {
  $envArgs = @()
  if ($Reproduce -or $ReproduceOnly) { $envArgs += @("-e", "TW_REPRODUCE=1") }
  if ($ReproduceOnly) { $envArgs += @("-e", "TW_SKIP_RUN=1") }
  $runArgs = @("--concurrency", "$Parallel")
  if ($Smoke) { $runArgs += @("--arms", "baseline", "--task", $SmokeTask) }
  else { $runArgs += @("--arms", $Arms) }
  if ($ReproduceOnly) { Step "只做 W8-05 复现（baseline 臂 1 题）并重新打包" } else {
  Step "开始运行（臂 $Arms；并发 $Parallel；全量约 4-7 小时，含首次构建 35 个任务镜像；可随时 Ctrl+C，重跑同一命令续上）" }
  & docker run @common @envArgs `
    -e DEEPSEEK_API_KEY `
    -v //var/run/docker.sock:/var/run/docker.sock `
    --entrypoint bash $Image /app/scripts/windows/final-entry.sh @runArgs
  $rc = $LASTEXITCODE
}
$mins = [int]((Get-Date) - $started).TotalMinutes

# ---- 4. 结果 ------------------------------------------------------------------
$stamp = Get-ChildItem -Path $OutDir -Filter "final-eval-*.zip" -ErrorAction SilentlyContinue |
         Sort-Object LastWriteTime -Descending | Select-Object -First 1
Write-Host ""
if ($rc -ne 0) { Write-Host "运行返回 $rc（部分题可能未完成）。重跑同一命令可续跑；也可先把下面的 zip（含 run.log）发回分析。" -ForegroundColor Yellow }
if ($stamp) {
  $prefix = ($stamp.Name -replace "-part\d+[ab]?\.zip$", "" -replace "\.zip$", "")
  $zips = Get-ChildItem -Path $OutDir -Filter "$prefix*.zip" | Sort-Object Name
  Write-Host ("完成（{0} 分钟）。结果包（不含密钥），全部发回：" -f $mins) -ForegroundColor Green
  foreach ($z in $zips) { Write-Host ("  {0}  ({1:N1} MB)" -f $z.FullName, ($z.Length / 1MB)) }
  Write-Host "报告预览：$OutDir\final\report.md"
  if (Test-Path "$OutDir\final\reproduce\reproduce.md") { Write-Host "W8-05 复现对比：$OutDir\final\reproduce\reproduce.md" }
  Write-Host "任务镜像（tw-task-*）留在本机 Docker，续跑可复用；不需要时 docker image prune -a --filter label=tw.kind=task-image"
} else {
  Write-Host "没有生成结果包，请检查 $OutDir\final\run.log" -ForegroundColor Red
}
exit $rc
