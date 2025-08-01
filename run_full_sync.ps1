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

# Rebuild and reload runner
Write-Host "Rebuilding batch-runner image..."
docker build --no-cache -t batch-runner:latest -f infra/dockerfile.runner .
minikube image load batch-runner:latest


# Rebuild and reload scheduler
Write-Host "Rebuilding scheduler image..."
docker build --no-cache -t $env:SCHEDULER_IMAGE -f infra/dockerfile.scheduler .
minikube image load $env:SCHEDULER_IMAGE


# Set Docker environment for Minikube
Write-Host "Setting Docker environment for Minikube..."
& minikube docker-env | Invoke-Expression

# Apply RBAC resources first
Write-Host "Applying RBAC resources..."
kubectl apply -f infra/k8s/scheduler-service-account.yaml
kubectl apply -f infra/k8s/scheduler-role.yaml  
kubectl apply -f infra/k8s/scheduler-role-binding.yaml

# Give RBAC a moment to propagate
Start-Sleep -Seconds 5

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
kubectl apply -f infra/k8s/temp-sync-jobs.yaml

# Wait for job completion
Write-Host "Waiting for sync job to complete..."
kubectl wait --for=condition=complete job/sync-jobfiles-now --timeout=300s

# Show logs
$syncPod = kubectl get pods --selector=job-name=sync-jobfiles-now -o jsonpath="{.items[0].metadata.name}" 2>$null
if ($syncPod) {
    Write-Host "`nLogs from sync_jobfiles.py:"
    kubectl logs $syncPod
} else {
    Write-Warning "No pod found for the sync job."
}

# Cleanup
kubectl delete job sync-jobfiles-now

Write-Host "`nDone."