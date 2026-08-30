$ErrorActionPreference = "Stop"
Set-StrictMode -Version 2.0

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

$LogDirectory = Join-Path $ProjectRoot "logs"
New-Item -ItemType Directory -Force -Path $LogDirectory | Out-Null
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogPath = Join-Path $LogDirectory ("piomas_osi_refresh_{0}.log" -f $Timestamp)
$LastLogPointer = Join-Path $ProjectRoot "PIOMAS_OSI_REFRESH_LAST_LOG.txt"
Set-Content -LiteralPath $LastLogPointer -Value $LogPath -Encoding UTF8

$TranscriptStarted = $false
$ExitCode = 0

function Invoke-PythonChecked {
    param(
        [Parameter(Mandatory = $true)] [string[]]$Arguments,
        [Parameter(Mandatory = $true)] [string]$FailureMessage
    )
    Write-Host ("> {0} {1}" -f $script:Python, ($Arguments -join " ")) -ForegroundColor DarkGray
    & $script:Python @Arguments
    $NativeExitCode = $LASTEXITCODE
    if ($NativeExitCode -ne 0) {
        throw "$FailureMessage Exit code: $NativeExitCode."
    }
}

function Assert-ExistingCoreEvidence {
    $Required = @(
        "data\validation\sea_ice_fixed_mask\N_03_fixed_mask.csv",
        "data\validation\sea_ice_fixed_mask\N_09_fixed_mask.csv",
        "data\validation\sea_ice_fixed_mask\MODEL_OBSERVATION_OPERATOR.npz",
        "data\validation\sea_ice_physical\cryosat2_rdeft4_monthly.csv",
        "data\validation\sea_ice_physical\cryosat2_rdeft4_operator.npz",
        "data\validation\sea_ice_physical\icesat2_is2sitmogr4_monthly.csv",
        "data\validation\sea_ice_physical\icesat2_is2sitmogr4_operator.npz"
    )
    $Missing = @()
    foreach ($Relative in $Required) {
        if (-not (Test-Path -LiteralPath (Join-Path $ProjectRoot $Relative))) {
            $Missing += $Relative
        }
    }
    if ($Missing.Count -gt 0) {
        throw ("Incomplete extraction: required pre-existing G02202/CryoSat/ICESat evidence is missing:`n  " + ($Missing -join "`n  ") + "`nExtract this ZIP to a short folder such as C:\EGCM_ARCTIC_READY and run again.")
    }
}

try {
    try {
        Start-Transcript -LiteralPath $LogPath -Force | Out-Null
        $TranscriptStarted = $true
    } catch {
        Write-Host "WARNING: PowerShell transcript could not be started: $($_.Exception.Message)" -ForegroundColor Yellow
    }

    Write-Host "============================================================"
    Write-Host "EGCM ARCTIC VALIDATION FINAL REFRESH: 2026-08-09"
    Write-Host "Self-contained short-path build"
    Write-Host "No Earthdata credentials are required."
    Write-Host "Log: $LogPath"
    Write-Host "============================================================"
    Write-Host ""

    Assert-ExistingCoreEvidence

    if (Get-Command py -ErrorAction SilentlyContinue) {
        $script:Python = "py"
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        $script:Python = "python"
    } else {
        throw "Python was not found on PATH."
    }

    Write-Host "Installing/confirming validation dependencies (including pytest)..."
    Invoke-PythonChecked -Arguments @("-m", "pip", "install", "-r", "requirements-validation-data.txt") -FailureMessage "Dependency installation failed."

    Write-Host ""
    Write-Host "Refreshing corrected PIOMAS + OSI SAF evidence..."
    Invoke-PythonChecked -Arguments @("tools/acquire_arctic_validation_stack.py", "--refresh-piomas-osi") -FailureMessage "PIOMAS/OSI SAF refresh failed."

    Write-Host ""
    Write-Host "Running data-processing regression tests..."
    Invoke-PythonChecked -Arguments @("-m", "pytest", "-q", "tests/test_2026_arctic_data_processing_repairs.py") -FailureMessage "Data-processing regression tests failed."

    Write-Host ""
    Write-Host "Verifying complete core-five stack..."
    Invoke-PythonChecked -Arguments @("-c", "import arctic_validation_stack as a; s=a.validation_stack_status(); assert s.get('core_five_calibration_validation_stack_complete') is True, s; print('CORE FIVE COMPLETE:', ', '.join(s['available_sources']))") -FailureMessage "Core-five validation stack is incomplete."

    Write-Host ""
    Write-Host "Exporting corrected validation evidence..."
    Invoke-PythonChecked -Arguments @("tools/export_arctic_validation_bundle.py", "--allow-missing-ice-age", "--output", "ARCTIC_VALIDATION_DATA_BUNDLE_CORRECTED.zip") -FailureMessage "Corrected bundle export failed."

    $BundlePath = Join-Path $ProjectRoot "ARCTIC_VALIDATION_DATA_BUNDLE_CORRECTED.zip"
    if (-not (Test-Path -LiteralPath $BundlePath)) {
        throw "Refresh completed but ARCTIC_VALIDATION_DATA_BUNDLE_CORRECTED.zip was not created."
    }

    Write-Host ""
    Write-Host "SUCCESS: corrected core-five Arctic validation bundle created." -ForegroundColor Green
    Write-Host "Bundle: $BundlePath" -ForegroundColor Green
    Write-Host "Log:    $LogPath"
} catch {
    $ExitCode = 1
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Red
    Write-Host "ARCTIC VALIDATION FINAL REFRESH FAILED" -ForegroundColor Red
    Write-Host "============================================================" -ForegroundColor Red
    Write-Host ("Error: {0}" -f $_.Exception.Message) -ForegroundColor Red
    if ($_.InvocationInfo) {
        if ($_.InvocationInfo.ScriptName) { Write-Host ("Script: {0}" -f $_.InvocationInfo.ScriptName) -ForegroundColor Red }
        if ($_.InvocationInfo.ScriptLineNumber) { Write-Host ("Line:   {0}" -f $_.InvocationInfo.ScriptLineNumber) -ForegroundColor Red }
        if ($_.InvocationInfo.Line) { Write-Host ("Code:   {0}" -f $_.InvocationInfo.Line.Trim()) -ForegroundColor Red }
    }
    if ($_.ScriptStackTrace) {
        Write-Host ""
        Write-Host "PowerShell stack trace:" -ForegroundColor Red
        Write-Host $_.ScriptStackTrace -ForegroundColor Red
    }
    Write-Host ""
    Write-Host "Full log:" -ForegroundColor Yellow
    Write-Host "  $LogPath" -ForegroundColor Yellow
} finally {
    if ($TranscriptStarted) {
        try { Stop-Transcript | Out-Null } catch {}
    }
}

exit $ExitCode
