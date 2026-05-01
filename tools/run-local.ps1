#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Starts all services for local development.

.DESCRIPTION
    This script starts the frontdesk service, faultdesk service, and frontend
    application in parallel for local development and testing.

.EXAMPLE
    .\tools\run-local.ps1
#>

param(
    [switch]$SkipFrontend,
    [switch]$SkipBackend,
    [switch]$Help
)

if ($Help) {
    Get-Help $PSCommandPath -Detailed
    exit 0
}

# Colors for output
$ErrorColor = "Red"
$SuccessColor = "Green"
$InfoColor = "Cyan"
$WarningColor = "Yellow"

function Write-ColorOutput {
    param(
        [string]$Message,
        [string]$Color = "White"
    )
    Write-Host $Message -ForegroundColor $Color
}

function Test-Command {
    param([string]$Command)
    $null = Get-Command $Command -ErrorAction SilentlyContinue
    return $?
}

# Check prerequisites
Write-ColorOutput "Checking prerequisites..." $InfoColor

if (-not (Test-Command "uv")) {
    Write-ColorOutput "ERROR: 'uv' is not installed. Please install it from https://docs.astral.sh/uv/" $ErrorColor
    exit 1
}

if (-not (Test-Command "node")) {
    Write-ColorOutput "ERROR: 'node' is not installed. Please install Node.js from https://nodejs.org/" $ErrorColor
    exit 1
}

Write-ColorOutput "Prerequisites OK" $SuccessColor
Write-ColorOutput ""

# Get repository root
$RepoRoot = Split-Path -Parent $PSScriptPath
$FaultdeskPath = Join-Path $RepoRoot "services\faultdesk"
$FrontdeskPath = Join-Path $RepoRoot "services\frontdesk"
$FrontendPath = Join-Path $RepoRoot "frontend"

# Check environment files
$FaultdeskEnv = Join-Path $FaultdeskPath ".env"
$FrontdeskEnv = Join-Path $FrontdeskPath ".env"

if (-not (Test-Path $FaultdeskEnv)) {
    Write-ColorOutput "WARNING: $FaultdeskEnv not found. Copying from .env.example..." $WarningColor
    $FaultdeskEnvExample = Join-Path $FaultdeskPath ".env.example"
    if (Test-Path $FaultdeskEnvExample) {
        Copy-Item $FaultdeskEnvExample $FaultdeskEnv
        Write-ColorOutput "Please edit $FaultdeskEnv with your Azure credentials" $WarningColor
    }
}

if (-not (Test-Path $FrontdeskEnv)) {
    Write-ColorOutput "WARNING: $FrontdeskEnv not found. Copying from .env.example..." $WarningColor
    $FrontdeskEnvExample = Join-Path $FrontdeskPath ".env.example"
    if (Test-Path $FrontdeskEnvExample) {
        Copy-Item $FrontdeskEnvExample $FrontdeskEnv
        Write-ColorOutput "Please edit $FrontdeskEnv with your Azure credentials" $WarningColor
    }
}

# Install dependencies
Write-ColorOutput "Installing Python dependencies..." $InfoColor
Push-Location $RepoRoot
try {
    & uv sync
    if ($LASTEXITCODE -ne 0) {
        throw "uv sync failed"
    }
} catch {
    Write-ColorOutput "ERROR: Failed to install Python dependencies" $ErrorColor
    Pop-Location
    exit 1
}
Pop-Location

if (-not $SkipFrontend) {
    Write-ColorOutput "Installing frontend dependencies..." $InfoColor
    Push-Location $FrontendPath
    try {
        & npm install
        if ($LASTEXITCODE -ne 0) {
            throw "npm install failed"
        }
    } catch {
        Write-ColorOutput "ERROR: Failed to install frontend dependencies" $ErrorColor
        Pop-Location
        exit 1
    }
    Pop-Location
}

Write-ColorOutput ""
Write-ColorOutput "Starting services..." $SuccessColor
Write-ColorOutput ""

# Array to hold background jobs
$Jobs = @()

# Start faultdesk (must start first, on port 8001)
if (-not $SkipBackend) {
    Write-ColorOutput "Starting faultdesk service on port 8001..." $InfoColor
    Push-Location $FaultdeskPath
    $FaultdeskJob = Start-Job -ScriptBlock {
        param($Path)
        Set-Location $Path
        & uv run uvicorn app.main:app --port 8001 --reload
    } -ArgumentList $FaultdeskPath
    $Jobs += $FaultdeskJob
    Pop-Location
    Write-ColorOutput "Faultdesk service started (Job ID: $($FaultdeskJob.Id))" $SuccessColor

    # Wait a bit for faultdesk to start
    Start-Sleep -Seconds 2

    # Start frontdesk (on port 8000)
    Write-ColorOutput "Starting frontdesk service on port 8000..." $InfoColor
    Push-Location $FrontdeskPath
    $FrontdeskJob = Start-Job -ScriptBlock {
        param($Path)
        Set-Location $Path
        & uv run uvicorn app.main:app --port 8000 --reload
    } -ArgumentList $FrontdeskPath
    $Jobs += $FrontdeskJob
    Pop-Location
    Write-ColorOutput "Frontdesk service started (Job ID: $($FrontdeskJob.Id))" $SuccessColor

    # Wait a bit for frontdesk to start
    Start-Sleep -Seconds 2
}

# Start frontend (on port 5173 by default)
if (-not $SkipFrontend) {
    Write-ColorOutput "Starting frontend on port 5173..." $InfoColor
    Push-Location $FrontendPath
    $FrontendJob = Start-Job -ScriptBlock {
        param($Path)
        Set-Location $Path
        & npm run dev
    } -ArgumentList $FrontendPath
    $Jobs += $FrontendJob
    Pop-Location
    Write-ColorOutput "Frontend started (Job ID: $($FrontendJob.Id))" $SuccessColor
}

Write-ColorOutput ""
Write-ColorOutput "===========================================================" $SuccessColor
Write-ColorOutput "All services started!" $SuccessColor
Write-ColorOutput ""
if (-not $SkipBackend) {
    Write-ColorOutput "  Faultdesk:  http://localhost:8001" $InfoColor
    Write-ColorOutput "  Frontdesk:  http://localhost:8000" $InfoColor
}
if (-not $SkipFrontend) {
    Write-ColorOutput "  Frontend:   http://localhost:5173" $InfoColor
}
Write-ColorOutput ""
Write-ColorOutput "Press Ctrl+C to stop all services" $WarningColor
Write-ColorOutput "===========================================================" $SuccessColor
Write-ColorOutput ""

# Monitor jobs
try {
    while ($true) {
        # Check if any job has failed
        foreach ($Job in $Jobs) {
            if ($Job.State -eq "Failed") {
                Write-ColorOutput "ERROR: Job $($Job.Id) failed" $ErrorColor
                Receive-Job $Job
                throw "Service failed"
            }
        }

        # Show job output
        foreach ($Job in $Jobs) {
            Receive-Job $Job -ErrorAction SilentlyContinue | ForEach-Object {
                Write-Host $_
            }
        }

        Start-Sleep -Seconds 1
    }
} catch {
    Write-ColorOutput ""
    Write-ColorOutput "Stopping all services..." $WarningColor
} finally {
    # Clean up jobs
    foreach ($Job in $Jobs) {
        Stop-Job $Job -ErrorAction SilentlyContinue
        Remove-Job $Job -Force -ErrorAction SilentlyContinue
    }
    Write-ColorOutput "All services stopped" $InfoColor
}
