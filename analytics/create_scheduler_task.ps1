# Create Windows Task Scheduler task for ClipEmpire Analytics Sync
# Run this script as Administrator

param(
    [string]$PythonPath = "C:\Users\kanaw\AppData\Local\Programs\Python\Python310\python.exe",
    [string]$ScriptPath = "C:\Users\kanaw\.openclaw\workspace\ventures\clip_empire\analytics\sync_all.py",
    [string]$LogPath = "C:\Users\kanaw\.openclaw\workspace\ventures\clip_empire\logs\analytics_sync.log"
)

# Check if running as Administrator
$isAdmin = [bool]([System.Security.Principal.WindowsIdentity]::GetCurrent().Groups -match "S-1-5-32-544")
if (-not $isAdmin) {
    Write-Host "Error: This script must be run as Administrator"
    exit 1
}

# Verify paths exist
if (-not (Test-Path $PythonPath)) {
    Write-Host "Error: Python not found at $PythonPath"
    exit 1
}

if (-not (Test-Path $ScriptPath)) {
    Write-Host "Error: Script not found at $ScriptPath"
    exit 1
}

# Ensure log directory exists
$LogDir = Split-Path -Parent $LogPath
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}

# Create the task action
$Action = New-ScheduledTaskAction `
    -Execute $PythonPath `
    -Argument $ScriptPath `
    -WorkingDirectory (Split-Path -Parent $ScriptPath)

# Create the trigger (hourly)
$Trigger = New-ScheduledTaskTrigger `
    -RepetitionInterval (New-TimeSpan -Hours 1) `
    -At "00:00" `
    -Daily

# Create task settings
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries:$false `
    -DontStopIfGoingOnBatteries:$false `
    -Compatibility Win8 `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable

# Register the task
try {
    $TaskName = "ClipEmpire-AnalyticsSync"
    $TaskPath = "\ClipEmpire\"
    
    # Create the full path if it doesn't exist
    $TaskPathExists = Get-ScheduledTask -TaskPath $TaskPath -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($TaskPathExists) {
        Write-Host "Task $TaskName already exists. Updating..."
        Unregister-ScheduledTask -TaskPath $TaskPath -TaskName $TaskName -Confirm:$false
    }
    
    Register-ScheduledTask `
        -TaskName $TaskName `
        -TaskPath $TaskPath `
        -Action $Action `
        -Trigger $Trigger `
        -Settings $Settings `
        -Description "Sync YouTube view counts for Clip Empire every hour" `
        -RunLevel Highest `
        -Force | Out-Null
    
    Write-Host "✓ Task 'ClipEmpire-AnalyticsSync' created successfully"
    Write-Host "  Path: \ClipEmpire\ClipEmpire-AnalyticsSync"
    Write-Host "  Schedule: Every hour"
    Write-Host "  Python: $PythonPath"
    Write-Host "  Script: $ScriptPath"
    Write-Host ""
    Write-Host "To view the task, use: Get-ScheduledTask -TaskName ClipEmpire-AnalyticsSync"
    Write-Host "To test it now, use: Start-ScheduledTask -TaskName ClipEmpire-AnalyticsSync"
    
} catch {
    Write-Host "Error creating task: $_"
    exit 1
}
