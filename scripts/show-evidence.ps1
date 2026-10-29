param([Parameter(Mandatory=$true)][string]$Section)
$ErrorActionPreference = 'Stop'
$Host.UI.RawUI.WindowTitle = "Ethereum node evidence - $Section"
Clear-Host
Write-Host "Ethereum mainnet node - VPS terminal capture: $Section" -ForegroundColor Cyan
Write-Host "Commands are executed over SSH against the school VPS." -ForegroundColor DarkGray
Write-Host ""
$repo = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
python (Join-Path $repo 'scripts\terminal_evidence.py') --section $Section
Write-Host ""
Write-Host "Live output from the VPS. Press Enter to close." -ForegroundColor DarkGray
Read-Host | Out-Null
