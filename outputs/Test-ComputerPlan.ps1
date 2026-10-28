[CmdletBinding()]
param(
    [string]$Model = $env:GNW_COMPUTER_PLAN_MODEL,
    [string]$BaseUri = 'http://127.0.0.1:8010',
    [ValidateRange(5, 120)]
    [int]$TimeoutSec = 75
)

$ErrorActionPreference = 'Stop'
if ([string]::IsNullOrWhiteSpace($Model)) {
    # Example shown in the gateway guide; access depends on the account's enabled catalog.
    $Model = 'perplexity/kimi-k3'
}
$BaseUri = $BaseUri.TrimEnd('/')

function Write-JsonResult($Value) {
    Write-Output ($Value | ConvertTo-Json -Depth 8)
}

# /health is local-only and does not call Perplexity.
try {
    $health = Invoke-WebRequest -Method Get -Uri "$BaseUri/health" -TimeoutSec 5 -UseBasicParsing
    if ([int]$health.StatusCode -ne 200) {
        Write-JsonResult ([ordered]@{
            outcome = 'BLOCKED'
            phase = 'local_gateway_health'
            http_status = [int]$health.StatusCode
            gateway_post_attempted = $false
            message = 'Local gateway health check did not return HTTP 200; no plan request was sent.'
        })
        exit 2
    }
} catch {
    Write-JsonResult ([ordered]@{
        outcome = 'BLOCKED'
        phase = 'local_gateway_health'
        http_status = $null
        gateway_post_attempted = $false
        message = 'Could not reach the local gateway. Start it and rerun this script.'
        detail = $_.Exception.Message
    })
    exit 2
}

$task = 'Smoke test only: provide one safe, manual checklist item for inspecting the visible Computer-mode controls. Do not submit a prompt, change settings, run code, or claim to have acted.'
$requestBody = @{
    model = $Model
    task = $task
} | ConvertTo-Json -Depth 4 -Compress

try {
    # Exactly one POST: this sends the generic task to the official Perplexity API
    # if the gateway has a configured API key. No automatic retry is performed.
    $response = Invoke-WebRequest -Method Post -Uri "$BaseUri/v1/computer/plan" `
        -ContentType 'application/json' -Body $requestBody -TimeoutSec $TimeoutSec -UseBasicParsing
    $statusCode = [int]$response.StatusCode
    $data = $response.Content | ConvertFrom-Json
} catch {
    $statusCode = $null
    $errorBody = $null
    if ($_.Exception.Response) {
        try { $statusCode = [int]$_.Exception.Response.StatusCode } catch { }
        try {
            $stream = $_.Exception.Response.GetResponseStream()
            if ($stream) {
                $reader = New-Object System.IO.StreamReader($stream)
                $errorBody = $reader.ReadToEnd()
                $reader.Dispose()
            }
        } catch { }
    }
    if ([string]::IsNullOrWhiteSpace($errorBody) -and $_.ErrorDetails) {
        $errorBody = $_.ErrorDetails.Message
    }
    if ([string]::IsNullOrWhiteSpace($errorBody)) {
        $errorBody = $_.Exception.Message
    }
    Write-JsonResult ([ordered]@{
        outcome = 'FAIL'
        phase = 'plan_request'
        http_status = $statusCode
        gateway_post_attempted = $true
        model = $Model
        message = $errorBody
        note = 'One POST was attempted; no retry was made. Check the status and API-key/model configuration before any new attempt.'
    })
    exit 1
}

$checks = [ordered]@{
    mode_is_plan_only = ($data.mode -eq 'computer_task_plan_only')
    status_requires_review = ($data.status -eq 'pending_human_review')
    executed_is_false = ($data.executed -eq $false)
    approval_required_is_true = ($data.approval_required -eq $true)
    output_marked_untrusted = ($data.untrusted_model_output -eq $true)
    plan_text_present = (-not [string]::IsNullOrWhiteSpace([string]$data.plan_text))
}
$allPassed = $true
foreach ($checkName in $checks.Keys) {
    if (-not $checks[$checkName]) { $allPassed = $false }
}
$outcome = if ($allPassed) { 'PASS' } else { 'FAIL' }
Write-JsonResult ([ordered]@{
    outcome = $outcome
    http_status = $statusCode
    model = $Model
    checks = $checks
    response = $data
})
if (-not $allPassed) { exit 1 }
exit 0
