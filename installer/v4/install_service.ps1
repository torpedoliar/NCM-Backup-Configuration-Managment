param(
  [Parameter(Mandatory=$true)][string]$InstallDir,
  [string]$PythonExe = "python"
)
$ServiceName = "NCMv4Backend"
$Args = "-m app_v4.service.windows_service"
New-Service -Name $ServiceName -BinaryPathName "`"$PythonExe`" $Args" -DisplayName "NCM v4 Backend" -StartupType Automatic
Start-Service -Name $ServiceName
