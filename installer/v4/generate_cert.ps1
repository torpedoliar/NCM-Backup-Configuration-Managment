param(
  [Parameter(Mandatory=$true)][string]$CertPath,
  [Parameter(Mandatory=$true)][string]$Password
)
$cert = New-SelfSignedCertificate -DnsName @("localhost", $env:COMPUTERNAME) -CertStoreLocation "Cert:\CurrentUser\My" -NotAfter (Get-Date).AddYears(5)
$secure = ConvertTo-SecureString -String $Password -Force -AsPlainText
Export-PfxCertificate -Cert $cert -FilePath $CertPath -Password $secure | Out-Null
