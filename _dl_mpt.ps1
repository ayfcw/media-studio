$ErrorActionPreference = "Stop"
$zip = "C:\Users\24688\dev\mpt_main.zip"
$dst = "C:\Users\24688\dev\MoneyPrinterTurbo"
if (Test-Path $dst) { Remove-Item $dst -Recurse -Force }
if (Test-Path $zip) { Remove-Item $zip -Force }
$url = "https://gh-proxy.com/https://github.com/harry0703/MoneyPrinterTurbo/archive/refs/heads/main.zip"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
Invoke-WebRequest -Uri $url -OutFile $zip -TimeoutSec 600
Write-Output ("downloaded bytes: " + (Get-Item $zip).Length)
Expand-Archive -Path $zip -DestinationPath "C:\Users\24688\dev" -Force
Rename-Item "C:\Users\24688\dev\MoneyPrinterTurbo-main" $dst
Remove-Item $zip -Force
Write-Output "EXTRACT_OK"
