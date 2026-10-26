# Deploy the World No 1 Personal Agent artefacts
# -------------------------------------------------
# This script copies the artefacts you listed from your Downloads folder
# into a deployment folder (by default "deployment" under the current
# workspace) and grants **Everyone** full control on the copied files.
# Adjust `$TargetDir` if you want the artefacts placed elsewhere.

# ----- Configuration -------------------------------------------------
$TargetDir = "d:/GNW/perplexity-browser-api/deployment"

# Ensure target folder exists
if (-Not (Test-Path $TargetDir)) {
    New-Item -ItemType Directory -Path $TargetDir -Force | Out-Null
}

# List of source artefacts (absolute paths)
$Sources = @(
    "C:\\Users\\asisy\\Downloads\\World_No1_Personal_Agent_Test_Evidence_20261025.txt",
    "C:\\Users\\asisy\\Downloads\\World_No1_Personal_Agent_Red_Team_Test_Plan.md",
    "C:\\Users\\asisy\\Downloads\\World_No1_Personal_Agent_Benchmark_20261025.json",
    "C:\\Users\\asisy\\Downloads\\World_No1_Agent_Workflow_Scaling_Spotcheck_20261025.json",
    "C:\\Users\\asisy\\Downloads\\World_No1_Personal_Agent_Final_Verification_20261025.md",
    "C:\\Users\\asisy\\Downloads\\World_No1_Personal_Agent_Baseline_Audit.md"
)

# ----- Copy artefacts ------------------------------------------------
foreach ($src in $Sources) {
    $fileName = Split-Path $src -Leaf
    $dest = Join-Path $TargetDir $fileName

    Write-Host "Copying `$src` → `$dest`"
    Copy-Item -Path $src -Destination $dest -Force
}

# ----- Grant Everyone full control -----------------------------------
Write-Host "Setting full control for Everyone on `$TargetDir` contents"
icacls $TargetDir /grant Everyone:F /T

Write-Host "\nDeployment complete. All artefacts are in `$TargetDir` with full permissions."
