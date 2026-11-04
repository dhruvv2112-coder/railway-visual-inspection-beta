# OnTrack.AI laptop server for Windows 10/11 (draft 1).
# Double-click Start-OnTrack.bat. First run: installs Python 3.11 (per user), the server and its AI models, asks for
# the first sign-in accounts, opens the Windows firewall for port 8000 on private networks, and adds a desktop shortcut.
# Every run: starts the server, advertises it on the Wi-Fi so phones find it, opens a secure internet tunnel so paired
# phones reach it from any network, and opens the connect page.
param(
    [switch]$NonInteractive,          # CI smoke test: default accounts from env, no prompts, no firewall/shortcut
    [int]$Port = 8000,
    [switch]$NoBrowser,
    [switch]$LanOnly,                 # no internet tunnel: phones must be on the same Wi-Fi
    [string]$PublicUrl = ""           # fixed public address (named Cloudflare tunnel, ngrok domain) instead of a quick tunnel
)
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$Root = Split-Path -Parent $PSScriptRoot          # the unzipped OnTrack-Server folder
$Data = Join-Path $env:LOCALAPPDATA "OnTrack"     # database, photos, accounts, Python environment
$Venv = Join-Path $Data "venv"
New-Item -ItemType Directory -Force -Path $Data, (Join-Path $Data "evidence") | Out-Null
try { Start-Transcript -Path (Join-Path $Data "server-setup.log") -Append | Out-Null } catch {}

function Say($msg) { Write-Host ""; Write-Host "  $msg" -ForegroundColor Cyan }
function Ok($msg) { Write-Host "  OK  $msg" -ForegroundColor Green }

Write-Host ""
Write-Host "  OnTrack.AI server" -ForegroundColor White
Write-Host "  -----------------"

# ---- 1. Python 3.11 (OCR needs Python <= 3.12) ------------------------------------------------------------------------
function Find-Python {
    foreach ($v in "3.11", "3.12") {
        try { $p = & py "-$v" -c "import sys;print(sys.executable)" 2>$null; if ($LASTEXITCODE -eq 0 -and $p) { return $p.Trim() } } catch {}
    }
    foreach ($c in "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe", "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
                   "C:\Program Files\Python311\python.exe", "C:\Program Files\Python312\python.exe") {
        if (Test-Path $c) { return $c }
    }
    return $null
}
$Py = Find-Python
if (-not $Py) {
    Say "Installing Python 3.11 (one time, about 30 MB)..."
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        winget install -e --id Python.Python.3.11 --scope user --silent --accept-package-agreements --accept-source-agreements | Out-Host
    } else {
        $inst = Join-Path $env:TEMP "python-3.11.9-amd64.exe"
        Invoke-WebRequest "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe" -OutFile $inst
        Start-Process $inst -Wait -ArgumentList "/quiet", "InstallAllUsers=0", "PrependPath=1", "Include_launcher=1"
    }
    $Py = Find-Python
    if (-not $Py) { throw "Python 3.11 could not be installed. Install it from python.org, then run Start-OnTrack.bat again." }
}
Ok "Python: $Py"

# ---- 2. Server environment (re-installed only when the server version changes) ---------------------------------------
$Backend = Join-Path $Root "server\backend"
$Stamp = Join-Path $Data "installed.txt"
function Get-Sha([string]$path) {
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($sha.ComputeHash([IO.File]::ReadAllBytes($path))) -replace "-", "") } finally { $sha.Dispose() }
}
$ver = Join-Path $Root "VERSION.txt"
$Want = (Get-Sha (Join-Path $Backend "pyproject.toml")) + $(if (Test-Path $ver) { [IO.File]::ReadAllText($ver).Trim() } else { "" })
$VPy = Join-Path $Venv "Scripts\python.exe"
if (-not (Test-Path $VPy) -or -not (Test-Path $Stamp) -or [IO.File]::ReadAllText($Stamp).Trim() -ne $Want) {
    Say "Installing the inspection server (first run takes 3-6 minutes)..."
    if (-not (Test-Path $VPy)) { & $Py -m venv $Venv }
    & $VPy -m pip install --disable-pip-version-check -q --upgrade pip
    & $VPy -m pip install --disable-pip-version-check -q "$Backend[ocr,lan]"
    if ($LASTEXITCODE -ne 0) { throw "Server install failed. Check the internet connection and run again. Log: $Data\server-setup.log" }
    [IO.File]::WriteAllText($Stamp, $Want)
}
Ok "Server installed"

# ---- 3. Settings, secret key and accounts ---------------------------------------------------------------------------------
$SecretFile = Join-Path $Data "secret.txt"
if (-not (Test-Path $SecretFile)) {
    $b = New-Object byte[] 32; [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b)
    Set-Content -Path $SecretFile -Value ([Convert]::ToBase64String($b))
}
$env:RVI_SECRET_KEY = (Get-Content $SecretFile -Raw).Trim()
$env:RVI_DATABASE_URL = "sqlite:///" + ((Join-Path $Data "ontrack.db") -replace "\\", "/")
$env:RVI_EVIDENCE_DIR = Join-Path $Data "evidence"
$env:RVI_USERS_FILE = Join-Path $Data "users.yaml"
$env:RVI_MODEL_DIR = Join-Path $Root "models"
$env:RVI_APP_DIR = Join-Path $Data "app"
$env:RVI_APP_IMPORT_DIR = Join-Path $Root "app"
$env:RVI_AUTH_MODE = "token"
$env:RVI_MDNS = "true"
$env:RVI_PORT = "$Port"
$env:RVI_SERVER_NAME = "OnTrack.AI server"
$env:RVI_RELAY_FILE = Join-Path $Data "relay.json"

# ---- 3b. Internet access: Cloudflare quick tunnel (outbound HTTPS only, no account, no router changes) --------------
if (-not $LanOnly -and -not $PublicUrl) {
    $Cf = Join-Path $Data "cloudflared.exe"
    if (-not (Test-Path $Cf)) {
        Say "Downloading the secure tunnel (cloudflared, one time, about 60 MB)..."
        try {
            [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
            Invoke-WebRequest "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe" -OutFile "$Cf.part"
            Move-Item -Force "$Cf.part" $Cf
        } catch { Write-Host "  Tunnel download failed; continuing on Wi-Fi only. ($_)" -ForegroundColor Yellow }
    }
    if (Test-Path $Cf) { $env:RVI_TUNNEL = "cloudflare"; $env:RVI_CLOUDFLARED_PATH = $Cf; Ok "Internet tunnel ready" }
} elseif ($PublicUrl) {
    $env:RVI_PUBLIC_URL = $PublicUrl; Ok "Fixed internet address: $PublicUrl"
}

function Add-User($id, $role, $pin, $name) {
    Push-Location $Backend
    try { & $VPy -m app.ohe.auth add $id $role $pin $name | Out-Host } finally { Pop-Location }
}
function Read-Pin($label) {
    while ($true) {
        $s = Read-Host "  $label PIN (4 to 8 digits)" -AsSecureString
        $p = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($s))
        if ($p -match '^\d{4,8}$') { return $p }
        Write-Host "  Use 4 to 8 digits." -ForegroundColor Yellow
    }
}
if (-not (Test-Path $env:RVI_USERS_FILE)) {
    if ($NonInteractive) {
        Add-User "PT-0001" "Patrol" "1234" "Patroller"
        Add-User "SSE-0001" "SSE" "4321" "Reviewer"
    } else {
        Say "Create the first sign-in accounts (you can add more later with Add-User.bat)."
        $pid1 = Read-Host "  Patroller ID (for the phone)  [PT-0001]"; if (-not $pid1) { $pid1 = "PT-0001" }
        $pn1 = Read-Host "  Patroller name                [Patroller]"; if (-not $pn1) { $pn1 = "Patroller" }
        Add-User $pid1 "Patrol" (Read-Pin "Patroller") $pn1
        $sid1 = Read-Host "  Reviewer (SSE) ID             [SSE-0001]"; if (-not $sid1) { $sid1 = "SSE-0001" }
        $sn1 = Read-Host "  Reviewer name                 [Reviewer]"; if (-not $sn1) { $sn1 = "Reviewer" }
        Add-User $sid1 "SSE" (Read-Pin "Reviewer") $sn1
    }
}
Ok "Accounts: $env:RVI_USERS_FILE"

# ---- 4. Firewall (private networks only) and desktop shortcut -----------------------------------------------------------
if (-not $NonInteractive) {
    $rule = Get-NetFirewallRule -DisplayName "OnTrack.AI server" -ErrorAction SilentlyContinue
    if (-not $rule) {
        Say "Windows will ask once to let phones on your Wi-Fi reach this laptop (port $Port, private networks only)."
        $cmd = "New-NetFirewallRule -DisplayName 'OnTrack.AI server' -Direction Inbound -Protocol TCP -LocalPort $Port -Action Allow -Profile Private,Domain; " +
               "New-NetFirewallRule -DisplayName 'OnTrack.AI discovery' -Direction Inbound -Protocol UDP -LocalPort 5353 -Action Allow -Profile Private,Domain"
        try { Start-Process powershell -Verb RunAs -Wait -WindowStyle Hidden -ArgumentList "-NoProfile", "-Command", $cmd } catch {
            Write-Host "  Firewall not changed (permission refused). Phones may not connect until port $Port is allowed." -ForegroundColor Yellow }
    }
    $pub = Get-NetConnectionProfile -ErrorAction SilentlyContinue | Where-Object { $_.NetworkCategory -eq "Public" }
    if ($pub) {
        Write-Host ""
        Write-Host "  Your network '$($pub[0].Name)' is set to Public, which blocks phones." -ForegroundColor Yellow
        Write-Host "  If this is your own or office Wi-Fi: Settings > Network & internet > Wi-Fi > $($pub[0].Name) > Private network." -ForegroundColor Yellow
    }
    $lnk = Join-Path ([Environment]::GetFolderPath("Desktop")) "OnTrack.AI Server.lnk"
    if (-not (Test-Path $lnk)) {
        $ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut($lnk)
        $s.TargetPath = Join-Path $Root "Start-OnTrack.bat"; $s.WorkingDirectory = $Root
        $ico = Join-Path $Root "setup\ontrack.ico"; if (Test-Path $ico) { $s.IconLocation = $ico }
        $s.Save()
        Ok "Desktop shortcut added"
    }
}

# ---- 5. Start ----------------------------------------------------------------------------------------------------------
$ips = @()
try {
    $ips = [System.Net.Dns]::GetHostAddresses([System.Net.Dns]::GetHostName()) | Where-Object {
        $_.AddressFamily -eq "InterNetwork" -and $_.IPAddressToString -notmatch '^(127\.|169\.254\.)' } | ForEach-Object { $_.IPAddressToString }
} catch {}
Say "Starting. Phones on the same Wi-Fi find this laptop automatically."
foreach ($ip in $ips) { Write-Host "     http://${ip}:$Port/" -ForegroundColor White }
Write-Host "  Connect page: http://localhost:$Port/ohe/connect     Reviewer: http://localhost:$Port/ohe/review"
if ($env:RVI_TUNNEL -or $env:RVI_PUBLIC_URL) { Write-Host "  Internet: the connect page shows the HTTPS address. Phones paired once find it from any network." }
Write-Host "  Keep this window open. Close it (or press Ctrl+C) to stop the server."
try { Stop-Transcript | Out-Null } catch {}
if (-not $NoBrowser) {
    Start-Job -ScriptBlock { param($p) Start-Sleep 6; Start-Process "http://localhost:$p/ohe/connect" } -ArgumentList $Port | Out-Null
}
Push-Location $Backend
try { & $VPy -m uvicorn app.main:app --host 0.0.0.0 --port $Port } finally { Pop-Location }
