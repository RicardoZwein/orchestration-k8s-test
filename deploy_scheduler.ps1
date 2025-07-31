# -------------------------------
# BatchOps Scheduler Deployment
# -------------------------------
# Usage:
# > powershell -ExecutionPolicy Bypass -File deploy_scheduler.ps1

# Set working directory to script location (project root)
Set-Location -Path $PSScriptRoot

# Load .env file (required for SCHEDULER_IMAGE)
if (-not (Test-Path ".env")) {
    Write-Error ".env not found in project root"
    exit 1
}

Get-Content .env | ForEach-Object {
    if ($_ -match "^\s*([^#][^=]*)=(.*)$") {
        $key = $matches[1].Trim()
        $value = $matches[2].Trim()
        [System.Environment]::SetEnvironmentVariable($key, $value, "Process")
    }
}

# Build and load runner image
Write-Host "Building runner image on host Docker..."
docker build -t batch-runner:latest -f infra/dockerfile.runner .
Write-Host "Loading runner image into Minikube..."
minikube image load batch-runner:latest

# Set kubectl context (optional safety step)
Write-Host "Switching kubectl context to Minikube..."
kubectl config use-context minikube | Out-Null

# Build and load scheduler image
Write-Host "Building scheduler image on host Docker..."
docker build -t $env:SCHEDULER_IMAGE -f infra/dockerfile.scheduler .
Write-Host "Loading scheduler image into Minikube..."
minikube image load $env:SCHEDULER_IMAGE

# Delete any pre-existing jobs/cronjobs
Write-Host "Deleting previous jobs and cronjobs..."
kubectl delete job --all --ignore-not-found
kubectl delete cronjob --all --ignore-not-found


Write-Host "Applying PV for job exports..."
kubectl apply -f infra/k8s/pv-job-exports.yaml

# Check if the PVC exists before applying it
$pvcExists = kubectl get pvc job-exports-pvc --ignore-not-found

if (-not $pvcExists) {
    Write-Host "Creating job-exports PVC..."
    kubectl apply -f infra/k8s/pvc-job-exports.yaml
} else {
    Write-Host "job-exports PVC already exists."
}



# Apply DB credentials
Write-Host "Applying DB credentials secret..."
kubectl apply -f infra/k8s/db-credentials-secret.yaml

# Apply scheduler job
Write-Host "Applying db-scheduler-job.yaml..."
kubectl apply -f infra/k8s/db-scheduler-job.yaml

# Wait for scheduler job to start and show logs
Start-Sleep -Seconds 10
$schedulerPod = kubectl get pods --selector=job-name=sync-batch-cronjobs -o jsonpath="{.items[0].metadata.name}" 2>$null
if ($schedulerPod) {
    Write-Host "`nLogs from scheduler job:"
    kubectl logs $schedulerPod
} else {
    Write-Warning "No pod found for the scheduler job."
}

Write-Host "`nDone."