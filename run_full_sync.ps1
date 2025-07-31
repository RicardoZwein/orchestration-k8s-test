# --------------------------------------
# Full Sync: Rebuild, Apply, Sync Jobs
# --------------------------------------
# Usage:
# > powershell -ExecutionPolicy Bypass -File run_full_sync.ps1

# In theory, CI/CD pipelines should call this when anything is pushed to jobs.
# In practice, I can't really do that right now on my local machine.

Set-Location -Path $PSScriptRoot

# Load .env
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

# Make sure Minikube is running
$minikubeStatus = & minikube status --format '{{.Host}}'
if ($minikubeStatus -ne "Running") {
    Write-Host "Starting Minikube..."
    & minikube start
}

# Cleanup jobs and cronjobs
Write-Host "Deleting all jobs and cronjobs..."
kubectl delete job --all --ignore-not-found
kubectl delete cronjob --all --ignore-not-found

# Set Docker environment for Minikube
Write-Host "Setting Docker environment for Minikube..."
& minikube docker-env | Invoke-Expression

# Rebuild and reload runner
Write-Host "Rebuilding batch-runner image..."
docker build -t batch-runner:latest -f infra/dockerfile.runner .
minikube image load batch-runner:latest

# Rebuild and reload scheduler
Write-Host "Rebuilding scheduler image..."
docker build -t $env:SCHEDULER_IMAGE -f infra/dockerfile.scheduler .
minikube image load $env:SCHEDULER_IMAGE

# Apply db-credentials secret
Write-Host "Applying DB credentials secret..."
kubectl apply -f infra/k8s/db-credentials-secret.yaml

# Apply db-scheduler job
Write-Host "Applying db-scheduler-job.yaml..."
kubectl apply -f infra/k8s/db-scheduler-job.yaml

# Wait and show logs for db_scheduler.py
Write-Host "Waiting for db-scheduler job pod..."
Start-Sleep -Seconds 10

$schedulerPod = kubectl get pods --selector=job-name=sync-batch-cronjobs -o jsonpath="{.items[0].metadata.name}" 2>$null
if ($schedulerPod) {
    Write-Host "`nLogs from db_scheduler.py:"
    kubectl logs $schedulerPod
} else {
    Write-Warning "No pod found for the scheduler job."
}

# Trigger one-time sync_jobfiles.py to update DB from jobs/*.yaml
Write-Host "`nRunning sync_jobfiles.py..."
kubectl run sync-jobfiles-now --rm -i --restart=Never --image=batch-runner:latest --image-pull-policy=Never --env="CONN_STR=$env:CONN_STR" -- python sync_jobfiles.py

Write-Host "`nDone."