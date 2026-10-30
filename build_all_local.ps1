<#
  Build and test EVERYTHING on the Windows laptop (ProArt P16, RTX 5070) and push the results to GitHub.

  Stages (each is skipped next time once it has passed; -Force re-runs all):
    1 tools     JDK 17, Android SDK (platform 35, build-tools 35), Gradle 8.11.1 – installed under rvi-bench\.tools
    2 backend   ruff + pytest (FastAPI backend)
    3 android   debug APK, unit tests, lint, screenshots (Roborazzi)  -> APK copied to your Desktop
    4 bench     model benchmarks on the GPU via ml\run_local_bench.ps1 (detector, asr, quality, dedup, translation, ocr)
  After every stage the logs and results are pushed to the branch 'local-bench-results'.

  Usage (normal PowerShell, one line at a time):
    git -C $HOME\rvi-bench pull -q            # skip if rvi-bench does not exist yet
    Set-ExecutionPolicy -Scope Process Bypass
    & $HOME\rvi-bench\build_all_local.ps1      # or: -Stages backend,android   |   -Force
  Requirements already on the laptop: Git, Python 3.11/3.12 ("py" launcher), NVIDIA driver 570+, winget.
  Disk ~20 GB. Time ~2–3 h first run (downloads + 30-epoch detector training).
#>
param(
  [string]$Stages = "tools,backend,android,bench",
  [string]$Workdir = "$HOME\rvi-bench",
  [string]$Branch = "main",
  [switch]$Force
)
$ErrorActionPreference = "Continue"
$Repo = "https://github.com/dhruvv2112-coder/railway-visual-inspection-beta"
$Tools = "$Workdir\.tools"; $Out = "$Workdir\local-build"
function Say($m, $c = "Cyan") { Write-Host "[$(Get-Date -Format HH:mm)] $m" -ForegroundColor $c }

# ---- code
if (-not (Test-Path "$Workdir\.git")) { git clone -b $Branch $Repo $Workdir; if ($LASTEXITCODE) { Say "FAILED: git clone" Red; exit 1 } }
Set-Location $Workdir
git fetch -q origin $Branch; git checkout -q $Branch; git reset -q --hard "origin/$Branch"
New-Item -ItemType Directory -Force -Path $Out, "$Out\logs", $Tools, reports, logs | Out-Null

function Done($n) { (Test-Path "$Out\$n.ok") -and -not $Force }
function Stage($name, [scriptblock]$body) {
  if ($Stages -notmatch $name) { return }
  if (Done $name) { Say "=== $($name): already passed, skipping ===" DarkGray; return }
  Say "=== $name ==="
  $global:StageFailed = $false
  & $body 2>&1 | ForEach-Object { "$_" } | Tee-Object -FilePath "$Out\logs\$name.log"
  if ($global:StageFailed) { Say "FAILED: $name – see local-build\logs\$name.log" Red }
  else { "$(Get-Date -Format o)" | Out-File "$Out\$name.ok"; Say "$name passed" Green }
  Publish
}
function Need($ok, $what) { if (-not $ok) { Write-Output "ERROR: $what"; $global:StageFailed = $true } }

function Publish {
  $pub = Join-Path $env:TEMP "rvi-pub"; if (Test-Path $pub) { Remove-Item -Recurse -Force $pub }
  New-Item -ItemType Directory -Path $pub | Out-Null
  foreach ($d in "reports", "logs", "local-build") { if (Test-Path "$Workdir\$d") { Copy-Item -Recurse "$Workdir\$d" $pub } }
  Get-ChildItem $pub -Include *.onnx, *.pt, *.apk -Recurse | Remove-Item -Force
  Push-Location $pub
  git init -q -b local-bench-results
  $gpu = (nvidia-smi --query-gpu=name --format=csv,noheader 2>$null | Select-Object -First 1)
  "$(git -C $Workdir rev-parse HEAD) local-gpu $gpu" | Out-File STATUS -Encoding utf8
  git add -A; git -c user.name=dhruvv2112-coder -c user.email=315002824+dhruvv2112-coder@users.noreply.github.com commit -qm "Local build and benchmark results"
  git push -q -f $Repo HEAD:local-bench-results
  if ($LASTEXITCODE) { Say "Could not push results (sign in to GitHub when prompted)" Yellow } else { Say "Results pushed to branch local-bench-results" Green }
  Pop-Location
}

# ---- 1 tools
Stage "tools" {
  $jdk = Get-ChildItem "C:\Program Files\Microsoft\jdk-17*" -Directory -ErrorAction SilentlyContinue | Select-Object -First 1
  if (-not $jdk) {
    winget install --id Microsoft.OpenJDK.17 -e --silent --accept-package-agreements --accept-source-agreements
    $jdk = Get-ChildItem "C:\Program Files\Microsoft\jdk-17*" -Directory -ErrorAction SilentlyContinue | Select-Object -First 1
  }
  Need $jdk "JDK 17 not found after winget install"
  $sdk = "$Tools\android-sdk"; $sdkm = "$sdk\cmdline-tools\latest\bin\sdkmanager.bat"
  if (-not (Test-Path $sdkm)) {
    $zip = "$Tools\cmdline-tools.zip"
    Invoke-WebRequest "https://dl.google.com/android/repository/commandlinetools-win-11076708_latest.zip" -OutFile $zip
    Expand-Archive $zip "$Tools\cmd-tmp" -Force
    New-Item -ItemType Directory -Force "$sdk\cmdline-tools" | Out-Null
    Move-Item "$Tools\cmd-tmp\cmdline-tools" "$sdk\cmdline-tools\latest" -Force
  }
  $env:JAVA_HOME = $jdk.FullName
  ("y`n" * 30) | & $sdkm --sdk_root=$sdk --licenses | Out-Null
  & $sdkm --sdk_root=$sdk "platform-tools" "platforms;android-35" "build-tools;35.0.0"
  Need (Test-Path "$sdk\platforms\android-35") "Android platform 35 not installed"
  if (-not (Test-Path "$Tools\gradle-8.11.1\bin\gradle.bat")) {
    Invoke-WebRequest "https://services.gradle.org/distributions/gradle-8.11.1-bin.zip" -OutFile "$Tools\gradle.zip"
    Expand-Archive "$Tools\gradle.zip" $Tools -Force
  }
  Need (Test-Path "$Tools\gradle-8.11.1\bin\gradle.bat") "Gradle not installed"
}

$jdk = Get-ChildItem "C:\Program Files\Microsoft\jdk-17*" -Directory -ErrorAction SilentlyContinue | Select-Object -First 1
if ($jdk) { $env:JAVA_HOME = $jdk.FullName; $env:PATH = "$($jdk.FullName)\bin;$env:PATH" }
$env:ANDROID_HOME = "$Tools\android-sdk"

# ---- 2 backend
Stage "backend" {
  $py = (py -3.12 -c "import sys;print(sys.executable)" 2>$null); if (-not $py) { $py = (py -3.11 -c "import sys;print(sys.executable)") }
  Push-Location backend
  if (-not (Test-Path ".venv")) { & $py -m venv .venv }
  & .\.venv\Scripts\python.exe -m pip install -q --upgrade pip
  & .\.venv\Scripts\python.exe -m pip install -q -e ".[dev]"; Need ($LASTEXITCODE -eq 0) "backend install"
  & .\.venv\Scripts\ruff.exe check app tests; Need ($LASTEXITCODE -eq 0) "ruff"
  New-Item -ItemType Directory -Force "$Out\tests" | Out-Null
  & .\.venv\Scripts\pytest.exe -q -rA --junitxml="$Out\tests\backend-tests.xml"; Need ($LASTEXITCODE -eq 0) "pytest"
  Pop-Location
}

# ---- 3 android
Stage "android" {
  $sdkEsc = ($env:ANDROID_HOME -replace '\\', '\\') -replace ':', '\:'
  "sdk.dir=$sdkEsc" | Out-File android\local.properties -Encoding ascii
  Push-Location android
  & "$Tools\gradle-8.11.1\bin\gradle.bat" --no-daemon --continue :app:assembleDebug :app:testDebugUnitTest :app:lintDebug :app:recordRoborazziDebug
  Need ($LASTEXITCODE -eq 0) "gradle build/tests"
  Pop-Location
  New-Item -ItemType Directory -Force "$Out\tests\android", "$Out\screens" | Out-Null
  Copy-Item android\app\build\test-results\testDebugUnitTest\*.xml "$Out\tests\android" -ErrorAction SilentlyContinue
  Copy-Item android\app\build\outputs\roborazzi\*.png "$Out\screens" -ErrorAction SilentlyContinue
  $apk = Get-ChildItem android\app\build\outputs\apk\debug\*.apk -ErrorAction SilentlyContinue | Select-Object -First 1
  Need $apk "APK not produced"
  if ($apk) { Copy-Item $apk.FullName "$([Environment]::GetFolderPath('Desktop'))\RVI-Inspect-debug.apk" -Force; Write-Output "APK copied to Desktop\RVI-Inspect-debug.apk" }
}

# ---- 4 benchmarks (GPU)
if ($Stages -match "bench") {
  Say "=== bench (GPU) ==="
  $suites = "detector,asr,quality,dedup,translation,ocr"
  if ($Force) { & "$Workdir\ml\run_local_bench.ps1" -Suites $suites -Branch $Branch -Force } else { & "$Workdir\ml\run_local_bench.ps1" -Suites $suites -Branch $Branch }
  Publish
}

Say "All requested stages finished. Summary:" Green
foreach ($n in "tools", "backend", "android") { if ($Stages -match $n) { Say ("  {0,-8} {1}" -f $n, $(if (Test-Path "$Out\$n.ok") { "passed" } else { "NOT passed – see local-build\logs\$n.log" })) } }
Get-ChildItem "$Workdir\reports\*.json" -ErrorAction SilentlyContinue | ForEach-Object { Say ("  bench    " + $_.BaseName) }
