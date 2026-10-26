# Audit script for Windows PC
# This script collects system information, installed software, services, scheduled tasks, environment variables, disk usage, and network configuration.
# Output is written to audit_report.md in the same folder.

$reportPath = Join-Path -Path (Split-Path -Parent $MyInvocation.MyCommand.Path) -ChildPath "audit_report.md"

function Write-SectionHeader($title) {
    Add-Content -Path $reportPath -Value "## $title`n"
}

# Clear previous report
if (Test-Path $reportPath) { Remove-Item $reportPath }

# Transcript for full console output
$transcriptPath = Join-Path -Path (Split-Path -Parent $MyInvocation.MyCommand.Path) -ChildPath "audit_transcript.txt"
Start-Transcript -Path $transcriptPath -NoClobber


# OS and hardware info
Write-SectionHeader "OS & Hardware"
Get-CimInstance Win32_OperatingSystem | Select-Object Caption, Version, BuildNumber, OSArchitecture | Format-List | Out-String | Add-Content -Path $reportPath
Get-CimInstance Win32_ComputerSystem | Select-Object Manufacturer, Model, TotalPhysicalMemory | Format-List | Out-String | Add-Content -Path $reportPath

# CPU info
Write-SectionHeader "CPU"
Get-CimInstance Win32_Processor | Select-Object Name, NumberOfCores, NumberOfLogicalProcessors, MaxClockSpeed | Format-List | Out-String | Add-Content -Path $reportPath

# Disk usage
Write-SectionHeader "Disk Usage"
Get-PSDrive -PSProvider 'FileSystem' | Select-Object Name, @{Name='Free(GB)';Expression={"{0:N2}" -f ($_.Free/1GB)}}, @{Name='Used(GB)';Expression={"{0:N2}" -f (($_.Used)/1GB)}}, @{Name='Total(GB)';Expression={"{0:N2}" -f ($_.Free + $_.Used)/1GB}} | Format-Table | Out-String | Add-Content -Path $reportPath

# Installed programs (via registry)
Write-SectionHeader "Installed Programs"
$programs = Get-ItemProperty HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\* , HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\* | Where-Object { $_.DisplayName } | Select-Object DisplayName, DisplayVersion, Publisher, InstallDate | Sort-Object DisplayName
$programs | Format-Table -AutoSize | Out-String | Add-Content -Path $reportPath

# Services status
Write-SectionHeader "Services (Running)"
Get-Service | Where-Object {$_.Status -eq 'Running'} | Select-Object Name, DisplayName, Status | Format-Table -AutoSize | Out-String | Add-Content -Path $reportPath

# Scheduled tasks
Write-SectionHeader "Scheduled Tasks"
Get-ScheduledTask | Select-Object TaskName, State, NextRunTime | Format-Table -AutoSize | Out-String | Add-Content -Path $reportPath

# Environment variables
Write-SectionHeader "Environment Variables"
Get-ChildItem Env: | Sort-Object Name | Format-Table -AutoSize | Out-String | Add-Content -Path $reportPath

# PATH entries
Write-SectionHeader "PATH Entries"
$env:Path -split ';' | ForEach-Object { "- $_" } | Add-Content -Path $reportPath

# Network adapters
Write-SectionHeader "Network Adapters"
Get-NetAdapter | Select-Object Name, InterfaceDescription, Status, LinkSpeed | Format-Table -AutoSize | Out-String | Add-Content -Path $reportPath

# Firewall rules (enabled)
Write-SectionHeader "Firewall Rules (Enabled)"
Get-NetFirewallRule -ErrorAction SilentlyContinue | Where-Object { $_.Enabled -eq 'True' } | Select-Object Name, Direction, Action, Profile | Format-Table -AutoSize | Out-String | Add-Content -Path $reportPath

# Common developer tools versions
Write-SectionHeader "Developer Tools Versions"
$tools = @('git','python','node','npm','dotnet','java')
foreach ($tool in $tools) {
    $ver = & $tool --version 2>$null
    if ($LASTEXITCODE -eq 0) {
        Add-Content -Path $reportPath -Value "- ${tool}: ${ver}"
    }
}

Write-Host "Audit complete. Report saved to $reportPath"
