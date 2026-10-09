param(
    [string]$ResourceGroup = "rg-ragpipeline-dev3",
    [string]$Location = "westus3",
    [string]$AppName = "enterprise-rag-api2",
    [string]$EnvName = "enterprise-rag-api2-env",
    [string]$AcrName = "ca2eceda24baacr",
    [string]$AppInsightsName = "enterprise-rag-ai",
    [string]$ImageName = "enterprise-rag-api",
    [string]$ImageTag = "v1"
)

$ErrorActionPreference = "Continue"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$Bar = "=" * 64

function Section($text) {
    Write-Host ""
    Write-Host $Bar -ForegroundColor DarkGray
    Write-Host $text -ForegroundColor Cyan
    Write-Host $Bar -ForegroundColor DarkGray
}

$Repo = Split-Path $PSScriptRoot -Parent
$envPath = Join-Path $Repo ".env"
if (-not (Test-Path -LiteralPath $envPath)) {
    Write-Host "FAIL: .env not found. Run infra/provision.ps1 -WriteEnv first." -ForegroundColor Red
    exit 1
}

$cfg = @{}
Get-Content -LiteralPath $envPath | ForEach-Object {
    if ($_ -match '^\s*([^#=]+)=(.*)$') { $cfg[$matches[1].Trim()] = $matches[2].Trim() }
}
function Get-Cfg($key) { if ($cfg.ContainsKey($key)) { return $cfg[$key] } return "" }

Section "Application Insights"
$conn = az monitor app-insights component show --app $AppInsightsName --resource-group $ResourceGroup --query connectionString -o tsv 2>$null
if (-not $conn) {
    $conn = az monitor app-insights component create `
        --app $AppInsightsName --resource-group $ResourceGroup --location $Location `
        --application-type web --query connectionString -o tsv
}
Write-Host "App Insights configured: $([bool]$conn)"

Section "Container registry"
$acr = az acr show --name $AcrName --resource-group $ResourceGroup --query name -o tsv 2>$null
if (-not $acr) {
    az acr create --name $AcrName --resource-group $ResourceGroup --location $Location --sku Basic --admin-enabled true --output none
}
$server = az acr show --name $AcrName --query loginServer -o tsv
Write-Host "ACR: $server"

Section "Build image (remote ACR build)"
az acr build --registry $AcrName --image "$ImageName`:$ImageTag" $Repo
if ($LASTEXITCODE -ne 0) { Write-Host "FAIL: image build failed." -ForegroundColor Red; exit 1 }

$acrUser = az acr credential show --name $AcrName --query username -o tsv
$acrPass = az acr credential show --name $AcrName --query "passwords[0].value" -o tsv

Section "Container Apps environment"
$envExists = az containerapp env show --name $EnvName --resource-group $ResourceGroup --query name -o tsv 2>$null
if (-not $envExists) {
    az containerapp env create --name $EnvName --resource-group $ResourceGroup --location $Location --output none
}

Section "Create/update container app (scale-to-zero)"
$envVars = @(
    "AZURE_OPENAI_ENDPOINT=$(Get-Cfg 'AZURE_OPENAI_ENDPOINT')",
    "AZURE_OPENAI_API_KEY=$(Get-Cfg 'AZURE_OPENAI_API_KEY')",
    "AZURE_OPENAI_API_VERSION=$(Get-Cfg 'AZURE_OPENAI_API_VERSION')",
    "MODEL_DEPLOYMENT_NAME=$(Get-Cfg 'MODEL_DEPLOYMENT_NAME')",
    "EMBEDDING_DEPLOYMENT_NAME=$(Get-Cfg 'EMBEDDING_DEPLOYMENT_NAME')",
    "EMBEDDING_DIMENSIONS=$(Get-Cfg 'EMBEDDING_DIMENSIONS')",
    "SEARCH_ENDPOINT=$(Get-Cfg 'SEARCH_ENDPOINT')",
    "SEARCH_KEY=$(Get-Cfg 'SEARCH_KEY')",
    "SEARCH_INDEX_NAME=$(Get-Cfg 'SEARCH_INDEX_NAME')",
    "APPLICATIONINSIGHTS_CONNECTION_STRING=$conn"
)

az containerapp create `
    --name $AppName `
    --resource-group $ResourceGroup `
    --environment $EnvName `
    --image "$server/$ImageName`:$ImageTag" `
    --registry-server $server `
    --registry-username $acrUser `
    --registry-password $acrPass `
    --target-port 8000 `
    --ingress external `
    --min-replicas 0 `
    --max-replicas 2 `
    --env-vars $envVars
if ($LASTEXITCODE -ne 0) { Write-Host "FAIL: container app create failed." -ForegroundColor Red; exit 1 }

$fqdn = az containerapp show --name $AppName --resource-group $ResourceGroup --query "properties.configuration.ingress.fqdn" -o tsv

Section "Done"
Write-Host "URL    : https://$fqdn" -ForegroundColor Green
Write-Host "Health : https://$fqdn/health" -ForegroundColor Green
Write-Host "Ask    : https://$fqdn/ask?q=Which%20items%20are%20not%20refundable" -ForegroundColor Green
Write-Host ""
Write-Host "Teardown: powershell -ExecutionPolicy Bypass -File .\infra\teardown.ps1 -ResourceGroup $ResourceGroup" -ForegroundColor Yellow
