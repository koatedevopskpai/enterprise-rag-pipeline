param(
    [string]$ResourceGroup = "rg-ragpipeline-dev2"
)

$ErrorActionPreference = "Stop"

Write-Host "Deleting resource group '$ResourceGroup'..." -ForegroundColor Yellow
az group delete --name $ResourceGroup --yes --no-wait
Write-Host "Delete requested." -ForegroundColor Green
