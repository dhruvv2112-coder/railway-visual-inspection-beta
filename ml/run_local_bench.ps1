<#
  Run the speech (ASR) and defect-detector benchmarks on a Windows laptop with an NVIDIA GPU
  (ProArt P16, RTX 5070 Laptop). Results are pushed to the branch 'local-bench-results' so the
  Solution Design Report can be generated from them.

  Requirements: Git, Python 3.11 or 3.12 (python.org installer, "py" launcher), NVIDIA driver 570+.
  Usage (PowerShell, from any folder):
    Set-ExecutionPolicy -Scope Process Bypass
    .\run_local_bench.ps1                     # asr + detector
    .\run_local_bench.ps1 -Suites detector    # one suite
  Disk: ~12 GB (PyTorch CUDA, models, datasets). Time: ~45-90 min, most of it downloads.
#>
param(
  [string]$Suites = "asr,detector",
  [string]$Workdir = "$HOME\rvi-bench",
  [string]$Branch = "fix/quality-gate-ocr"
)
$ErrorActionPreference = "Continue"   # native tools write progress to stderr; we check exit codes instead
function Check($what) { if ($LASTEXITCODE -ne 0) { Write-Host "FAILED: $what" -ForegroundColor Red; exit 1 } }
$Repo = "https://github.com/dhruvv2112-coder/railway-visual-inspection-beta"

# 1. Code
if (-not (Test-Path "$Workdir\.git")) { git clone --depth 1 -b $Branch $Repo $Workdir; Check "git clone" }
Set-Location $Workdir
git fetch --depth 1 origin $Branch; git checkout -q $Branch; git reset -q --hard "origin/$Branch"

# 2. Python environment with CUDA PyTorch (Blackwell / sm_120 needs CUDA 12.8 builds)
$py = (py -3.12 -c "import sys;print(sys.executable)" 2>$null); if (-not $py) { $py = (py -3.11 -c "import sys;print(sys.executable)") }
if (-not (Test-Path ".venv")) { & $py -m venv .venv }
. .\.venv\Scripts\Activate.ps1
python -m pip install -q --upgrade pip
python -m pip install -q torch torchvision --index-url https://download.pytorch.org/whl/cu128; Check "PyTorch CUDA install"
python -m pip install -q -r ml\requirements-bench.txt; Check "benchmark packages"
python -c "import torch;assert torch.cuda.is_available(),'CUDA not available';print('GPU:',torch.cuda.get_device_name(0))"; Check "CUDA check (update NVIDIA driver to 570+)"

# faster-whisper (CTranslate2) uses the cuBLAS/cuDNN DLLs shipped inside the torch wheel
$torchLib = python -c "import torch,os;print(os.path.join(os.path.dirname(torch.__file__),'lib'))"
$env:PATH = "$torchLib;$env:PATH"

# 3. Run
$env:RVI_DEVICE = "cuda"
$env:RVI_REPORTS = "$Workdir\reports"; $env:RVI_DATA = "$Workdir\.cache\rvi"
$env:FT_EPOCHS = "30"; $env:FT_FRACTION = "1.0"; $env:FT_IMGSZ = "640"; $env:ZS_N = "400"; $env:ASR_N = "100"
$env:PYTHONUTF8 = "1"
New-Item -ItemType Directory -Force -Path reports, logs | Out-Null
Push-Location ml\bench
foreach ($s in $Suites.Split(",")) {
  $script = @{ asr = "bench_asr.py"; detector = "bench_detector.py" }[$s.Trim()]
  Write-Host "=== $s ===" -ForegroundColor Cyan
  python $script 2>&1 | Tee-Object -FilePath "..\..\logs\$($s.Trim()).log"
}
Pop-Location

# 4. Publish results (reports + logs only; no models or data)
$pub = Join-Path $env:TEMP "rvi-pub"; if (Test-Path $pub) { Remove-Item -Recurse -Force $pub }
New-Item -ItemType Directory -Path $pub | Out-Null
Copy-Item -Recurse reports, logs $pub
Get-ChildItem "$pub\reports" -Include *.onnx -Recurse | Remove-Item
Push-Location $pub
git init -q -b local-bench-results
"$(git -C $Workdir rev-parse HEAD) local-gpu $(python -c "import torch;print(torch.cuda.get_device_name(0))")" | Out-File STATUS -Encoding utf8
git add -A; git -c user.name=dhruvv2112-coder -c user.email=315002824+dhruvv2112-coder@users.noreply.github.com commit -qm "Local GPU benchmark results"
git push -q -f $Repo HEAD:local-bench-results; Check "git push (sign in to GitHub when prompted)"
Pop-Location
Write-Host "Done. Results pushed to branch local-bench-results." -ForegroundColor Green
