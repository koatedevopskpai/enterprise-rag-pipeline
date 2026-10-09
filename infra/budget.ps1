param(
    [decimal]$Amount = 25,
    [string]$BudgetName = "ai103-portfolio-monthly"
)

$ErrorActionPreference = "Continue"
$start = (Get-Date -Day 1).ToString("yyyy-MM-dd")
$end = (Get-Date).AddYears(2).ToString("yyyy-MM-dd")

Write-Host "Creating subscription budget '$BudgetName' of $Amount per month (from $start) ..."

az consumption budget create `
    --budget-name $BudgetName `
    --category Cost `
    --amount $Amount `
    --time-grain Monthly `
    --start-date $start `
    --end-date $end `
    --output none

if ($LASTEXITCODE -eq 0) {
    Write-Host "Budget created." -ForegroundColor Green
    Write-Host "Add alert thresholds (e.g., 50/80/100%) in the portal:" -ForegroundColor Yellow
    Write-Host "  Cost Management + Billing > Cost Management > Budgets > $BudgetName"
} else {
    Write-Host "Budget creation failed. You can create it in the portal instead." -ForegroundColor Yellow
}
