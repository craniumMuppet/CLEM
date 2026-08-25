$ErrorActionPreference = "Stop"
Set-StrictMode -Version 2.0

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

$LogDirectory = Join-Path $ProjectRoot "logs"
New-Item -ItemType Directory -Force -Path $LogDirectory | Out-Null
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogPath = Join-Path $LogDirectory ("arctic_validation_acquisition_{0}.log" -f $Timestamp)
$LastLogPointer = Join-Path $ProjectRoot "ARCTIC_ACQUISITION_LAST_LOG.txt"
Set-Content -LiteralPath $LastLogPointer -Value $LogPath -Encoding UTF8

$TranscriptStarted = $false
try {
    Start-Transcript -LiteralPath $LogPath -Force | Out-Null
    $TranscriptStarted = $true
} catch {
    Write-Host "WARNING: PowerShell transcript could not be started: $($_.Exception.Message)" -ForegroundColor Yellow
}

$ExitCode = 0
$TokenSetHere = $false

function Convert-SecureStringToPlainText([Security.SecureString]$SecureValue) {
    $Ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureValue)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($Ptr)
    } finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($Ptr)
    }
}

function Invoke-PythonChecked {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,
        [Parameter(Mandatory = $true)]
        [string]$FailureMessage
    )

    Write-Host ("> {0} {1}" -f $script:Python, ($Arguments -join " ")) -ForegroundColor DarkGray
    & $script:Python @Arguments
    $NativeExitCode = $LASTEXITCODE
    if ($NativeExitCode -ne 0) {
        throw "$FailureMessage Exit code: $NativeExitCode."
    }
}

try {
    Write-Host "============================================================"
    Write-Host "EGCM ARCTIC ACQUISITION BUILD: CORE5-NONBLOCKING-2026-08-08"
    Write-Host "CRASH-LOGGING LAUNCHER: 2026-08-08"
    Write-Host "This run is being logged to:"
    Write-Host "  $LogPath"
    Write-Host "============================================================"
    Write-Host ""

    if (Get-Command py -ErrorAction SilentlyContinue) {
        $script:Python = "py"
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        $script:Python = "python"
    } else {
        throw "Python was not found on PATH."
    }

    # Earthdata Cloud products use a user token.
    if (-not $env:EARTHDATA_TOKEN) {
        Write-Host "NASA Earthdata Cloud access requires a user token."
        Write-Host "The token is read securely and kept only in this PowerShell process."
        $SecureToken = Read-Host "Paste your Earthdata token" -AsSecureString
        $env:EARTHDATA_TOKEN = Convert-SecureStringToPlainText $SecureToken
        $TokenSetHere = $true
        if (-not $env:EARTHDATA_TOKEN) {
            throw "EARTHDATA_TOKEN was empty."
        }
    }

    Write-Host ""
    Write-Host "NSIDC-0611 sea-ice age is no longer a hard acquisition blocker." -ForegroundColor Yellow
    Write-Host "The five core products will be acquired and exported even if the legacy ice-age archive is unavailable." -ForegroundColor Yellow
    Write-Host "The final scientific report will keep the ice-age structural diagnostic explicitly pending." -ForegroundColor Yellow

    Write-Host ""
    Write-Host "Installing Arctic validation data dependencies..."
    Invoke-PythonChecked -Arguments @("-m", "pip", "install", "-r", "requirements-validation-data.txt") -FailureMessage "Dependency installation failed."

    Write-Host ""
    Write-Host "Acquiring the five core Arctic validation sources (NSIDC-0611 remains optional)..."
    Write-Host "Existing valid raw files are reused. Credentials are not written into the project."
    Invoke-PythonChecked -Arguments @("tools/acquire_arctic_validation_stack.py", "--all") -FailureMessage "Arctic validation acquisition failed."

    Write-Host ""
    Write-Host "Exporting processed evidence only..."
    Invoke-PythonChecked -Arguments @("tools/export_arctic_validation_bundle.py", "--allow-missing-ice-age") -FailureMessage "Validation bundle export failed."

    $BundlePath = Join-Path $ProjectRoot "ARCTIC_VALIDATION_DATA_BUNDLE.zip"
    if (-not (Test-Path -LiteralPath $BundlePath)) {
        throw "The acquisition commands completed but ARCTIC_VALIDATION_DATA_BUNDLE.zip was not created."
    }

    Write-Host ""
    Write-Host "Done: ARCTIC_VALIDATION_DATA_BUNDLE.zip (core five complete; ice-age diagnostic may be pending)" -ForegroundColor Green
    Write-Host "Bundle: $BundlePath"
    Write-Host "Log:    $LogPath"
} catch {
    $ExitCode = 1
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Red
    Write-Host "ARCTIC VALIDATION ACQUISITION FAILED" -ForegroundColor Red
    Write-Host "============================================================" -ForegroundColor Red
    Write-Host ("Error: {0}" -f $_.Exception.Message) -ForegroundColor Red

    if ($_.InvocationInfo) {
        if ($_.InvocationInfo.ScriptName) {
            Write-Host ("Script: {0}" -f $_.InvocationInfo.ScriptName) -ForegroundColor Red
        }
        if ($_.InvocationInfo.ScriptLineNumber) {
            Write-Host ("Line:   {0}" -f $_.InvocationInfo.ScriptLineNumber) -ForegroundColor Red
        }
        if ($_.InvocationInfo.Line) {
            Write-Host ("Code:   {0}" -f $_.InvocationInfo.Line.Trim()) -ForegroundColor Red
        }
    }

    if ($_.ScriptStackTrace) {
        Write-Host ""
        Write-Host "PowerShell stack trace:" -ForegroundColor Red
        Write-Host $_.ScriptStackTrace -ForegroundColor Red
    }

    Write-Host ""
    Write-Host "The full console transcript is saved here:" -ForegroundColor Yellow
    Write-Host "  $LogPath" -ForegroundColor Yellow
} finally {
    if ($TokenSetHere) {
        Remove-Item Env:EARTHDATA_TOKEN -ErrorAction SilentlyContinue
    }

    if ($TranscriptStarted) {
        try {
            Stop-Transcript | Out-Null
        } catch {
            # Do not hide the original acquisition result if transcript shutdown fails.
        }
    }
}

exit $ExitCode
