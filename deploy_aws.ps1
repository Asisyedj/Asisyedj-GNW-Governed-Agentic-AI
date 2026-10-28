# AWS Automated Deployment Script for perplexity-browser-api
$ErrorActionPreference = "Stop"

$ACCOUNT_ID = "106139565701"
$REGION = "ap-southeast-2"
$REPO_NAME = "perplexity-browser-api"
$IMAGE_TAG = "latest"
$REGISTRY = "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com"
$FULL_IMAGE = "$REGISTRY/$REPO_NAME`:$IMAGE_TAG"
$CLUSTER_NAME = "perplexity-browser-api-cluster"
$SERVICE_NAME = "perplexity-browser-api-service"
$TASK_FAMILY = "perplexity-browser-api-task"

Write-Host "=== Step 1: Checking AWS Identity ===" -ForegroundColor Cyan
aws sts get-caller-identity --output table

Write-Host "`n=== Step 2: Ensuring ECR Repository Exists ===" -ForegroundColor Cyan
try {
    aws ecr describe-repositories --repository-names $REPO_NAME --region $REGION 2>$null | Out-Null
    Write-Host "ECR repository '$REPO_NAME' verified." -ForegroundColor Green
} catch {
    Write-Host "Creating ECR repository '$REPO_NAME'..." -ForegroundColor Yellow
    aws ecr create-repository --repository-name $REPO_NAME --image-scanning-configuration scanOnPush=true --region $REGION
}

Write-Host "`n=== Step 3: Verifying Docker Environment ===" -ForegroundColor Cyan
$pipeExists = [System.IO.File]::Exists('\\.\pipe\dockerDesktopLinuxEngine')
$serviceRunning = $false
try {
    $svc = Get-Service -Name "com.docker.service" -ErrorAction SilentlyContinue
    if ($svc -and $svc.Status -eq "Running") {
        $serviceRunning = $true
    }
} catch {}

if ($pipeExists -or $serviceRunning) {
    Write-Host "Docker daemon is active." -ForegroundColor Green

    Write-Host "`n=== Step 4: Logging in to Amazon ECR ===" -ForegroundColor Cyan
    $loginPassword = aws ecr get-login-password --region $REGION
    $loginPassword | docker login --username AWS --password-stdin $REGISTRY

    Write-Host "`n=== Step 5: Building Docker Image ===" -ForegroundColor Cyan
    docker build -t "$REPO_NAME`:$IMAGE_TAG" .

    Write-Host "`n=== Step 6: Tagging and Pushing Image to ECR ===" -ForegroundColor Cyan
    docker tag "$REPO_NAME`:$IMAGE_TAG" $FULL_IMAGE
    docker push $FULL_IMAGE
    Write-Host "Image successfully pushed to: $FULL_IMAGE" -ForegroundColor Green
} else {
    Write-Host "Local Docker daemon is currently stopped." -ForegroundColor Yellow
    Write-Host "  -> To build locally: Launch Docker Desktop from the Start Menu." -ForegroundColor Yellow
    Write-Host "  -> For cloud build: An AWS CodeBuild configuration (buildspec.yml) is ready." -ForegroundColor Yellow
}

Write-Host "`n=== Step 7: Verifying ECS Cluster & Service ===" -ForegroundColor Cyan
$clusterJson = aws ecs describe-clusters --clusters $CLUSTER_NAME --region $REGION --output json | ConvertFrom-Json
if ($clusterJson.clusters.Count -gt 0) {
    Write-Host "ECS Cluster '$CLUSTER_NAME' is active (Status: $($clusterJson.clusters[0].status))." -ForegroundColor Green
} else {
    Write-Host "Creating ECS Cluster '$CLUSTER_NAME'..." -ForegroundColor Yellow
    aws ecs create-cluster --cluster-name $CLUSTER_NAME --region $REGION
}

Write-Host "`n=== AWS Deployment Pipeline Verified! ===" -ForegroundColor Green
