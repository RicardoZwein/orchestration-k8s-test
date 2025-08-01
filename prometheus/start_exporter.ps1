# > powershell -ExecutionPolicy Bypass -File start_exporter.ps1

# Set working directory to script location
Set-Location -Path $PSScriptRoot

# Paths
$driverZipUrl = "https://public.dhe.ibm.com/ibmdl/export/pub/software/data/db2/drivers/odbc_cli/ntx64_odbc_cli.zip"
$driverFolder = "..\infra\db2_driver"
$driverBin = Join-Path $driverFolder "clidriver\bin"
$zipPath = "$env:TEMP\db2_driver.zip"

# 1. Install Python dependencies (only missing ones)
Write-Host "Ensuring Python dependencies from prometheus-requirements.txt..."
pip install -r "$PSScriptRoot\prometheus-requirements.txt"

# 2. Install IBM DB2 CLI driver if not already there
if (-not (Test-Path $driverBin)) {
    Write-Host "Downloading IBM DB2 CLI driver..."
    Invoke-WebRequest -Uri $driverZipUrl -OutFile $zipPath

    Write-Host "Extracting driver to: $driverFolder"
    Expand-Archive -Path $zipPath -DestinationPath $driverFolder -Force

    Remove-Item $zipPath
    Write-Host "DB2 driver installed locally"
} else {
    Write-Host "DB2 driver already installed - skipping"
}

# 3. Launch metrics exporter
Write-Host "Starting Prometheus exporter on http://localhost:9123 ..."
uvicorn metrics_exporter:app --host 0.0.0.0 --port 9123