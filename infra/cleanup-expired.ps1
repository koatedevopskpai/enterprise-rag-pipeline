param(
    [string]$TagName = "expiresOn",
    [switch]$Delete
)

$ErrorActionPreference = "Continue"
$Bar = "=" * 64
$today = (Get-Date).ToString("yyyy-MM-dd")

Write-Host $Bar -ForegroundColor DarkGray
Write-Host "Expired resource groups (tag $TagName <= $today)" -ForegroundColor Cyan
Write-Host $Bar -ForegroundColor DarkGray

$groups = az group list --query "[].{name:name, tags:tags}" -o json | ConvertFrom-Json
$expired = @()
foreach ($g in $groups) {
    $exp = $g.tags.$TagName
    if ($exp -and $exp -le $today) {
        $expired += [pscustomobject]@{ Name = $g.name; ExpiresOn = $exp }
    }
}

if ($expired.Count -eq 0) {
    Write-Host "No expired resource groups." -ForegroundColor Green
    exit 0
}

$expired | Format-Table -AutoSize

if ($Delete) {
    foreach ($g in $expired) {
        Write-Host "Deleting $($g.Name) ..." -ForegroundColor Yellow
        az group delete --name $g.Name --yes --no-wait
    }
    Write-Host "Delete requested." -ForegroundColor Green
} else {
    Write-Host "Dry run. Re-run with -Delete to remove the groups above." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Schedule daily cleanup with Task Scheduler:" -ForegroundColor Cyan
Write-Host '  schtasks /create /tn "ai103-cleanup" /tr "powershell -ExecutionPolicy Bypass -File <path>\cleanup-expired.ps1 -Delete" /sc daily /st 09:00'
