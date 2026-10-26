# Continuous Integration and Security Scan Monitor
# This script runs end-to-end integration tests and security scans.
# It monitors the git repository for new commits and re-runs the tests automatically.
# When phase 16 is verified (assumed true), it stops monitoring and creates a summary.

$repoPath = "d:\\GNW\\perplexity-browser-api"
$logDir = Join-Path $repoPath "ci_logs"
if (-Not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }

function Run-Tests {
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $logFile = Join-Path $logDir "tests_$timestamp.log"
    Write-Output "[INFO] Starting integration tests at $timestamp" | Tee-Object -FilePath $logFile
    # Example: run pytest (adjust command as needed)
    Push-Location $repoPath
    try {
        $testResult = & pytest --junitxml=report.xml 2>&1
        $testResult | Tee-Object -FilePath $logFile -Append
        Write-Output "[INFO] Tests completed" | Tee-Object -FilePath $logFile -Append
    } finally { Pop-Location }
    return $logFile
}

function Run-SecurityScan {
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $logFile = Join-Path $logDir "security_$timestamp.log"
    Write-Output "[INFO] Starting security scan at $timestamp" | Tee-Object -FilePath $logFile
    # Placeholder: invoke a security scanning tool (e.g., bandit, safety)
    Push-Location $repoPath
    try {
        $scanResult = & bandit -r . 2>&1
        $scanResult | Tee-Object -FilePath $logFile -Append
        Write-Output "[INFO] Security scan completed" | Tee-Object -FilePath $logFile -Append
    } finally { Pop-Location }
    return $logFile
}

function Check-Phase16 {
    # Placeholder: determine if phase 16 is verified.
    # Assuming a file flag exists.
    $flagPath = Join-Path $repoPath "phase16_done.txt"
    return (Test-Path $flagPath)
}

function Create-Summary {
    $summaryPath = Join-Path $repoPath "continuous_integration_summary.md"
    $logs = Get-ChildItem $logDir -Filter "*.log" | Sort-Object LastWriteTime
    $content = "# Continuous Integration Summary\n\n" +
               "## Test and Scan Log Files\n"
    foreach ($log in $logs) {
        $relative = $log.FullName.Substring($repoPath.Length + 1).Replace('\\', '/')
        $content += "- [$($log.Name)]($relative)\n"
    }
    Set-Content -Path $summaryPath -Value $content -Encoding UTF8
    Write-Output "[INFO] Summary written to $summaryPath"
}

# Main monitoring loop
$lastCommit = ""
while ($true) {
    $currentCommit = git -C $repoPath rev-parse HEAD
    if ($currentCommit -ne $lastCommit) {
        Write-Output "[INFO] Detected new commit $currentCommit"
        $lastCommit = $currentCommit
        Run-Tests | Out-Null
        Run-SecurityScan | Out-Null
    }
    if (Check-Phase16) {
        Write-Output "[INFO] Phase 16 verified. Stopping monitor."
        break
    }
    Start-Sleep -Seconds 30
}
Create-Summary
