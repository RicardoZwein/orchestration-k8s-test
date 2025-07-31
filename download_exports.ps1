# --------------------------------------------
# Download exported CSV files from Kubernetes
# --------------------------------------------
# Usage:
# > powershell -ExecutionPolicy Bypass -File download_exports.ps1 -job <name> [-n <int>] [-localExportPath <path>]

param (
    [string]$job = $(throw "You must specify a job name via --job=<name>"),
    [int]$n = 0,
    [string]$localExportPath = "$PWD\exports"
)

$remoteExportPath = "/app/data/exports"

# Ensure output directory exists
if (-not (Test-Path $localExportPath)) {
    New-Item -ItemType Directory -Path $localExportPath | Out-Null
    Write-Host "Created local export directory at $localExportPath"
}

# 1. Find Jobs matching CronJob name
$jobNames = kubectl get jobs --sort-by=.metadata.creationTimestamp `
    -o jsonpath="{.items[*].metadata.name}" |
    ForEach-Object { $_ -split '\s+' | Where-Object { $_ -like "$job*" } }

if (-not $jobNames) {
    Write-Host "No jobs found matching '$job'"
    exit 1
}

# 2. Select N most recent jobs (or default to latest)
$selectedJobs = if ($n -le 0) {
    @($jobNames[-1])
} else {
    $jobNames | Select-Object -Last $n
}

# 3. For each job, fetch its pod and copy exports
foreach ($selectedJob in $selectedJobs) {
    Write-Host ""
    Write-Host "Processing job: $selectedJob"

    $podName = kubectl get pods `
        --selector="job-name=$selectedJob" `
        -o jsonpath="{.items[0].metadata.name}" 2>$null

    if (-not $podName) {
        Write-Warning "No pod found for job '$selectedJob'"
        continue
    }

    Write-Host "Found pod: $podName"

    # Prepare temp dir per job
    $tempExportPath = Join-Path $env:TEMP "k8s-export-$($selectedJob)"
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $tempExportPath
    New-Item -ItemType Directory -Path $tempExportPath | Out-Null

    # Convert local path to POSIX for kubectl compatibility
    $posixTempExportPath = $tempExportPath -replace '\\', '/'
    $srcPath = "${podName}:$remoteExportPath"
    $dstPath = "$posixTempExportPath"

    Write-Host "Running: kubectl cp `"$srcPath`" `"$dstPath`""

    try {
        & kubectl cp "$srcPath" "$dstPath" --retries=5
    } catch {
        Write-Warning "❌ Failed to run: kubectl cp `"$srcPath`" `"$dstPath`""
        Write-Error $_
        continue
    }

    # Flatten nested exports/exports if needed
    $nested = Join-Path $tempExportPath "exports"
    if (Test-Path "$nested\exports") {
        Move-Item "$nested\exports\*" "$nested" -Force
        Remove-Item "$nested\exports" -Recurse -Force
    }

    if (-not (Test-Path $nested)) {
        Write-Warning "⚠️ No exports found in pod '$podName'"
        continue
    }

    # Move to final destination with filename prefix
    Get-ChildItem "$nested\*" -File | ForEach-Object {
        $finalPath = Join-Path $localExportPath "$selectedJob-$($_.Name)"
        Copy-Item $_.FullName $finalPath -Force
        Write-Host "✅ Copied: $finalPath"
    }
}

Write-Host ""
Write-Host "✅ Export complete for $($selectedJobs.Count) job(s). Saved to: $localExportPath"