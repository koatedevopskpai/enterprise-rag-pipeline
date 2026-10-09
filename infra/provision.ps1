param(
    [string]$ResourceGroup = "rg-ragpipeline-dev2",
    [string]$Location = "eastus",
    [string]$BaseName = "ragpipeline",
    [string]$DeploymentName = "ragpipeline-base",
    [string]$ChatModel = "",
    [string]$ChatVersion = "",
    [string]$ChatSku = "",
    [string]$EmbeddingModel = "text-embedding-3-large",
    [string]$EmbeddingVersion = "1",
    [int]$ChatCapacity = 50,
    [int]$EmbeddingCapacity = 50,
    [string]$Environment = "dev",
    [string]$Owner = "koatedevopskpai",
    [string]$CostCenter = "personal",
    [string]$ExpiresOn = (Get-Date).AddDays(30).ToString("yyyy-MM-dd"),
    [int]$ConflictWaitSeconds = 10,
    [switch]$WriteEnv
)

$ErrorActionPreference = "Continue"
$Bar = "=" * 64

function Section($text) {
    Write-Host ""
    Write-Host $Bar -ForegroundColor DarkGray
    Write-Host $text -ForegroundColor Cyan
    Write-Host $Bar -ForegroundColor DarkGray
}

function Get-ChatSku($name) {
    return 'GlobalStandard'
}

function Get-Suffix {
    return (-join ((97..122) + (48..57) | Get-Random -Count 6 | ForEach-Object { [char]$_ }))
}

function New-ModelDeployment($depName, $modelName, $modelVersion, $sku, $capacity) {
    for ($i = 1; $i -le 5; $i++) {
        Write-Host "  deploying $depName <- $modelName ($modelVersion) sku=$sku capacity=$capacity [attempt $i]" -ForegroundColor Yellow
        $out = az cognitiveservices account deployment create `
            --name $script:accountName `
            --resource-group $script:ResourceGroup `
            --deployment-name $depName `
            --model-name $modelName `
            --model-version $modelVersion `
            --model-format OpenAI `
            --sku-name $sku `
            --sku-capacity $capacity `
            --only-show-errors 2>&1 | Out-String
        if ($LASTEXITCODE -eq 0) { return $true }
        if ($out -match 'RequestConflict|being performed|background operation|ServiceDeleting') {
            Start-Sleep -Seconds $script:ConflictWaitSeconds
            continue
        }
        Write-Host $out
        return $false
    }
    return $false
}

$Repo = Split-Path $PSScriptRoot -Parent
$Template = Join-Path $PSScriptRoot "main.bicep"

Section "Provision resources"
Write-Host "Resource group : $ResourceGroup"
Write-Host "Location       : $Location"

az group create --name $ResourceGroup --location $Location --output none
if ($LASTEXITCODE -ne 0) { Write-Host "FAIL: could not create resource group" -ForegroundColor Red; exit 1 }

Section "Resolve account and search names"
$accountName = az cognitiveservices account list --resource-group $ResourceGroup --query "[?kind=='AIServices'].name | [0]" -o tsv 2>$null
$searchName = az search service list --resource-group $ResourceGroup --query "[0].name" -o tsv 2>$null

$suffix = Get-Suffix
if (-not $accountName) { $accountName = "$BaseName-$suffix".ToLower() }
if (-not $searchName) { $searchName = "$BaseName-search-$suffix".ToLower() }

Write-Host "AI account     : $accountName"
Write-Host "Search service : $searchName"

Section "Deploy base (account + search)"
az bicep install --only-show-errors
$baseOk = $false
for ($i = 1; $i -le 5; $i++) {
    Write-Host "  base deploy attempt $i" -ForegroundColor Yellow
    $baseOut = az deployment group create `
        --resource-group $ResourceGroup `
        --name $DeploymentName `
        --template-file $Template `
        --parameters location=$Location accountName=$accountName searchName=$searchName environment=$Environment owner=$Owner costCenter=$CostCenter projectName=enterprise-rag-pipeline expiresOn=$ExpiresOn `
        --only-show-errors 2>&1 | Out-String
    if ($LASTEXITCODE -eq 0) { $baseOk = $true; break }
    if ($baseOut -match 'RequestConflict|being performed|background operation|ServiceDeleting') {
        Start-Sleep -Seconds $ConflictWaitSeconds
        continue
    }
    Write-Host $baseOut
    break
}
if (-not $baseOk) {
    Write-Host "FAIL: base deployment failed." -ForegroundColor Red
    Write-Host "If the account is mid-operation, wait a minute and re-run." -ForegroundColor Yellow
    exit 1
}

Section "Discover chat models in $Location"
$models = @()
$raw = az cognitiveservices model list --location $Location -o json 2>$null
if ($LASTEXITCODE -eq 0 -and $raw) { $models = $raw | ConvertFrom-Json }

$candidates = @()
if ($ChatModel) {
    $sku = $ChatSku
    if (-not $sku) { $sku = Get-ChatSku $ChatModel }
    $candidates += [pscustomobject]@{ Name = $ChatModel; Version = $ChatVersion; Sku = $sku }
} else {
    foreach ($p in @("gpt-4.1-mini", "gpt-5-mini", "gpt-5.4-mini", "gpt-4o-mini", "gpt-4o")) {
        $m = $models | Where-Object { $_.model.name -eq $p } | Select-Object -First 1
        if ($m) { $candidates += [pscustomobject]@{ Name = $m.model.name; Version = $m.model.version; Sku = (Get-ChatSku $m.model.name) } }
    }
}
$candidates | ForEach-Object { Write-Host "  - $($_.Name) ($($_.Version)) sku=$($_.Sku)" }

Section "Create embedding deployment"
$embDep = $EmbeddingModel.ToLower()
$embOk = New-ModelDeployment $embDep $EmbeddingModel $EmbeddingVersion "Standard" $EmbeddingCapacity
if (-not $embOk) { Write-Host "FAIL: embedding deployment failed." -ForegroundColor Red; exit 1 }

Section "Create chat deployment (trying candidates)"
$chatDep = ""
$chatOk = $false
foreach ($c in $candidates) {
    $dep = ($c.Name -replace '\.', '-')
    if (New-ModelDeployment $dep $c.Name $c.Version $c.Sku $ChatCapacity) {
        $chatDep = $dep
        $chatOk = $true
        Write-Host "Chat deployment ready: $chatDep" -ForegroundColor Green
        break
    }
    Write-Host "  $($c.Name) not usable; trying next." -ForegroundColor Yellow
}
if (-not $chatOk) {
    Write-Host "FAIL: no chat model could be deployed in $Location." -ForegroundColor Red
    Write-Host "List options: az cognitiveservices model list -l $Location -o table" -ForegroundColor Yellow
    exit 1
}

Section "Read endpoints and keys"
$openaiEndpoint = "https://$accountName.openai.azure.com"
$searchEndpoint = "https://$searchName.search.windows.net"
$aiKey = az cognitiveservices account keys list --name $accountName --resource-group $ResourceGroup --query "key1" -o tsv
$searchKey = az search admin-key show --service-name $searchName --resource-group $ResourceGroup --query "primaryKey" -o tsv

if ($WriteEnv) {
    $envPath = Join-Path $Repo ".env"
    $content = @"
AZURE_OPENAI_ENDPOINT=$openaiEndpoint
AZURE_OPENAI_API_KEY=$aiKey
AZURE_OPENAI_API_VERSION=2024-10-21
MODEL_DEPLOYMENT_NAME=$chatDep
EMBEDDING_DEPLOYMENT_NAME=$embDep
EMBEDDING_DIMENSIONS=3072
SEARCH_ENDPOINT=$searchEndpoint
SEARCH_KEY=$searchKey
SEARCH_INDEX_NAME=enterprise-docs
CHUNK_SIZE=800
CHUNK_OVERLAP=100
RETRIEVE_TOP_K=5
"@
    [System.IO.File]::WriteAllText($envPath, $content, (New-Object System.Text.UTF8Encoding($false)))
    Write-Host "Wrote $envPath" -ForegroundColor Green
}

Section "Done"
Write-Host "Chat deployment      : $chatDep"
Write-Host "Embedding deployment : $embDep"
Write-Host "Teardown: powershell -ExecutionPolicy Bypass -File .\infra\teardown.ps1" -ForegroundColor Yellow
