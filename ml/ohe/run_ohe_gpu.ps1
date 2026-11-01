<#
  OHE detector + anomaly training on the Windows laptop GPU (RTX 5070), full public data, results pushed to GitHub.

  One line at a time in normal PowerShell:
    Set-ExecutionPolicy -Scope Process Bypass
    git -C $HOME\rvi-bench pull -q        # if rvi-bench exists; otherwise the script clones it
    & $HOME\rvi-bench\ml\ohe\run_ohe_gpu.ps1
  (first time, if rvi-bench does not exist:  git clone https://github.com/dhruvv2112-coder/railway-visual-inspection-beta $HOME\rvi-bench )

  Steps: CUDA PyTorch (cu128, needed for RTX 50-series) -> prepare data (CPLID, powerline, synthetic, EPDCL poles +
  vegetation, RailFOD23 6.5 GB, VPMBGI, corrosion; up to 3000 train images per source) -> anomaly branch ->
  YOLO11s, 60 epochs, 800 px on the GPU -> ONNX + backend adapter check. Results (reports, logs, ONNX) are pushed to
  branch 'local-ohe-gpu' after each step. Re-running resumes: downloads are cached; -Fresh rebuilds the dataset.
  Needs ~25 GB free disk, NVIDIA driver 570+, Python 3.11/3.12 ("py" launcher), Git. Time ~3-4 h.
#>
param([int]$Epochs = 60, [int]$ImgSz = 800, [string]$Model = "yolo11s.pt", [int]$Cap = 3000, [int]$EvalCap = 400,
      [string]$Workdir = "$HOME\rvi-bench", [switch]$Fresh)
$ErrorActionPreference = "Continue"
$Repo = "https://github.com/dhruvv2112-coder/railway-visual-inspection-beta"
function Say($m, $c = "Cyan") { Write-Host "[$(Get-Date -Format HH:mm)] $m" -ForegroundColor $c }

if (-not (Test-Path "$Workdir\.git")) { git clone $Repo $Workdir }
Set-Location $Workdir
git fetch -q origin main; git checkout -q main; git reset -q --hard origin/main
$Data = "$Workdir\.cache\ohe"; $Rep = "$Workdir\reports-ohe-gpu"; $Logs = "$Workdir\logs-ohe-gpu"
New-Item -ItemType Directory -Force -Path $Data, $Rep, $Logs | Out-Null
if ($Fresh -and (Test-Path "$Data\ohe_yolo")) { Remove-Item -Recurse -Force "$Data\ohe_yolo" }

function Publish($stage) {
  $pub = Join-Path $env:TEMP "rvi-ohe-pub"; if (Test-Path $pub) { Remove-Item -Recurse -Force $pub }
  New-Item -ItemType Directory -Path "$pub\reports", "$pub\logs" | Out-Null
  Copy-Item "$Rep\*" "$pub\reports" -Recurse -ErrorAction SilentlyContinue
  Copy-Item "$Logs\*" "$pub\logs" -ErrorAction SilentlyContinue
  Copy-Item "$Data\ohe_yolo\manifest.json" "$pub\reports" -ErrorAction SilentlyContinue
  Push-Location $pub
  git init -q -b local-ohe-gpu
  $gpu = (nvidia-smi --query-gpu=name --format=csv,noheader 2>$null | Select-Object -First 1)
  "$(git -C $Workdir rev-parse HEAD) $stage $gpu" | Out-File STATUS -Encoding utf8
  git add -A; git -c user.name=dhruvv2112-coder -c user.email=315002824+dhruvv2112-coder@users.noreply.github.com commit -qm "OHE GPU run: $stage"
  git push -q -f $Repo HEAD:local-ohe-gpu
  if ($LASTEXITCODE) { Say "Could not push (sign in to GitHub when the window asks, then re-run)" Yellow } else { Say "Pushed to branch local-ohe-gpu ($stage)" Green }
  Pop-Location
}
function Step($name, [scriptblock]$body) {
  Say "=== $name ==="
  & $body 2>&1 | ForEach-Object { "$_" } | Tee-Object -FilePath "$Logs\$name.log"
  Publish $name
}

# ---- Python env with CUDA PyTorch
$venv = "$Workdir\ml\ohe\.venv"; $py = "$venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
  $base = (py -3.12 -c "import sys;print(sys.executable)" 2>$null); if (-not $base) { $base = (py -3.11 -c "import sys;print(sys.executable)") }
  & $base -m venv $venv
}
Step "setup" {
  & $py -m pip install -q --upgrade pip
  & $py -m pip install -q torch torchvision --index-url https://download.pytorch.org/whl/cu128
  & $py -m pip install -q -r ml\ohe\requirements.txt fastapi sqlmodel pydantic-settings python-multipart
  & $py -c "import torch;print('torch',torch.__version__,'cuda',torch.cuda.is_available(),torch.cuda.get_device_name(0) if torch.cuda.is_available() else '')"
}
$cuda = (& $py -c "import torch;print(torch.cuda.is_available())")
if ($cuda -ne "True") { Say "CUDA not available in PyTorch - check the NVIDIA driver (570+). Stopping." Red; exit 1 }

$env:OHE_DATA = $Data; $env:RVI_REPORTS = $Rep; $env:HF_HUB_DISABLE_PROGRESS_BARS = "1"; $env:PYTHONUTF8 = "1"
$env:OHE_CAP_PER_SOURCE = "$Cap"; $env:OHE_EVAL_CAP_PER_SOURCE = "$EvalCap"; $env:OHE_CAP_OVERRIDES = ""
$env:OHE_DEVICE = "0"; $env:OHE_EPOCHS = "$Epochs"; $env:OHE_IMGSZ = "$ImgSz"; $env:OHE_MODEL = $Model; $env:OHE_BATCH = "-1"
Set-Location "$Workdir\ml\ohe"
if (-not (Test-Path "$Data\ohe_yolo\data.yaml")) { Step "prepare" { & $py prepare_data.py } } else { Say "dataset exists - skipping prepare (use -Fresh to rebuild)" DarkGray }
Step "anomaly" { & $py anomaly.py }
Step "detector" { & $py train_detector.py }
Step "verify_onnx" { & $py verify_onnx.py $Rep "$Data\ohe_yolo" }
Say "Done. Results are on GitHub branch local-ohe-gpu; the ONNX model is in $Rep" Green
