# ClipEmpire Data Refresh Task Setup Script
# This script registers the Windows Task Scheduler task for auto-refreshing dashboard data

param(
    [switch]$Force = $false
)

$TaskName = "ClipEmpire-DataRefresh"
$XmlFile = Join-Path -Path (Split-Path -Parent $MyInvocation.MyCommand.Path) -ChildPath "ClipEmpireDataRefresh.xml"

Write-Host "ClipEmpire Data Refresh Task Setup" -ForegroundColor Cyan
Write-Host "===================================="
Write-Host ""

# Check if running as admin
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")

if (-not $isAdmin) {
    Write-Host "ERROR: This script must be run as Administrator" -ForegroundColor Red
    Write-Host "Please run PowerShell as Administrator and try again." -ForegroundColor Red
    exit 1
}

# Check if XML file exists
if (-not (Test-Path $XmlFile)) {
    Write-Host "ERROR: Configuration file not found: $XmlFile" -ForegroundColor Red
    exit 1
}

Write-Host "Task Name: $TaskName" -ForegroundColor Green
Write-Host "Config File: $XmlFile" -ForegroundColor Green
Write-Host ""

# Check if task already exists
$existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue

if ($existingTask -and -not $Force) {
    Write-Host "Task '$TaskName' already exists." -ForegroundColor Yellow
    Write-Host "Use -Force flag to overwrite." -ForegroundColor Yellow
    exit 0
}

if ($existingTask -and $Force) {
    Write-Host "Removing existing task '$TaskName'..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Start-Sleep -Seconds 1
}

# Register the task
try {
    Write-Host "Registering scheduled task..." -ForegroundColor Cyan
    
    $xmlContent = Get-Content $XmlFile -Raw
    Register-ScheduledTask -Xml $xmlContent -TaskName $TaskName -Force | Out-Null
    
    Write-Host "✓ Task registered successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Task Details:" -ForegroundColor Cyan
    Write-Host "  - Task Name: $TaskName" -ForegroundColor Green
    Write-Host "  - Schedule: Every 5 minutes" -ForegroundColor Green
    Write-Host "  - Script: generate_data.py" -ForegroundColor Green
    Write-Host "  - Status: Enabled" -ForegroundColor Green
    Write-Host ""
    
    # Show task info
    $task = Get-ScheduledTask -TaskName $TaskName
    Write-Host "Task State: $(if ($task.State -eq 'Ready') { 'Ready (Enabled)' } else { $task.State })" -ForegroundColor Green
    
} catch {
    Write-Host "ERROR: Failed to register task" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Setup Complete!" -ForegroundColor Green
Write-Host "The dashboard data will refresh automatically every 5 minutes." -ForegroundColor Green
