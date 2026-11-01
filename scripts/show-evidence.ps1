param([Parameter(Mandatory=$true)][string]$Section, [string]$CompletionFile)
$ErrorActionPreference = 'Stop'
$Host.UI.RawUI.WindowTitle = "Ethereum node evidence - $Section"
Clear-Host
Write-Host "Ethereum mainnet node - VPS terminal capture: $Section" -ForegroundColor Cyan
if ($Section -eq 'reference') {
    Write-Host "SSH status and independent mainnet RPC requests from this PC." -ForegroundColor DarkGray
} elseif ($Section -eq 'public') {
    Write-Host "HTTPS and WebSocket requests sent from this PC to the VPS." -ForegroundColor DarkGray
} else {
    Write-Host "Commands are executed over SSH against the school VPS." -ForegroundColor DarkGray
}
Write-Host ""
$repo = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
python (Join-Path $repo 'scripts\terminal_evidence.py') --section $Section
if ($LASTEXITCODE -ne 0) { throw "Evidence command failed: $LASTEXITCODE" }
if ($CompletionFile) { Set-Content -LiteralPath $CompletionFile -Value 'complete' }
Write-Host ""
Write-Host "Live output from the VPS. Press Enter to close." -ForegroundColor DarkGray
Read-Host | Out-Null
