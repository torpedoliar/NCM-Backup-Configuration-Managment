$ServiceName = "NCMv4Backend"
if (Get-Service -Name $ServiceName -ErrorAction SilentlyContinue) {
  Stop-Service -Name $ServiceName -Force
  sc.exe delete $ServiceName | Out-Null
}
