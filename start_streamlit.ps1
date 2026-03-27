# Quick script to free port 8501 and start Streamlit without relying on
# fragile Windows launcher executables that may point to an old venv path.
# Target: Python 3.11.x (use `py -3.11` — resolves to 3.11.6 on this machine).
$PreferredPyLauncherArgs = @("-3.11")

Write-Host "Freeing port 8501..." -ForegroundColor Yellow

function Invoke-WithProjectPython {
    param(
        [string]$PythonCommand,
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$PassArgs
    )
    if ($PythonCommand -eq "py -3.11") {
        & py @PreferredPyLauncherArgs @PassArgs
    } else {
        & $PythonCommand @PassArgs
    }
}

function Get-ProjectPython {
    $venvPython = Join-Path $PSScriptRoot "venv\Scripts\python.exe"
    if (Test-Path $venvPython) {
        try {
            $null = & $venvPython --version 2>&1
            $majMin = & $venvPython -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>&1
            if ($majMin -ne "3.11") {
                Write-Host "WARNING: venv is Python $majMin, not 3.11. LangChain/Pydantic need Python < 3.14; recreate with: py -3.11 -m venv venv --clear" -ForegroundColor Yellow
            }
            return $venvPython
        } catch {
            Write-Host "Existing venv Python is broken; falling back to py -3.11." -ForegroundColor Yellow
        }
    }

    $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        return "py -3.11"
    }

    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCmd) {
        return $pythonCmd.Source
    }

    throw "No usable Python interpreter was found."
}

function Show-ActivePython([string]$PythonCommand) {
    # Single-quoted Python snippet so PowerShell does not treat [0] as its own syntax.
    $verSnippet = 'import sys; print("Executable:", sys.executable); print("Version:", sys.version.split()[0])'
    Write-Host "--- Active Python for Streamlit ---" -ForegroundColor Cyan
    if ($PythonCommand -eq "py -3.11") {
        Invoke-WithProjectPython -PythonCommand $PythonCommand -PassArgs @("-c", $verSnippet)
    } else {
        & $PythonCommand -c $verSnippet
    }
    Write-Host "-----------------------------------" -ForegroundColor Cyan
}

function Start-Streamlit([string]$PythonCommand, [int]$Port) {
    Write-Host "Starting Streamlit on port $Port..." -ForegroundColor Green
    Invoke-WithProjectPython -PythonCommand $PythonCommand -PassArgs @("-m", "streamlit", "run", "app\main.py", "--server.port", "$Port")
}

# Kill processes using port 8501
$connections = Get-NetTCPConnection -LocalPort 8501 -ErrorAction SilentlyContinue
if ($connections) {
    $connections | ForEach-Object {
        $processId = $_.OwningProcess
        Write-Host "Stopping process $processId using port 8501..." -ForegroundColor Yellow
        Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 2
}

# Kill all Streamlit processes
Get-Process | Where-Object {$_.ProcessName -like "*streamlit*"} | ForEach-Object {
    Write-Host "Stopping Streamlit process $($_.Id)..." -ForegroundColor Yellow
    Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
}

Start-Sleep -Seconds 1

$pythonCommand = Get-ProjectPython
Show-ActivePython -PythonCommand $pythonCommand

# Verify port is free
$stillInUse = Get-NetTCPConnection -LocalPort 8501 -ErrorAction SilentlyContinue
if ($stillInUse) {
    Write-Host "Port 8501 is still in use. Trying alternative port 8502..." -ForegroundColor Red
    Start-Streamlit -PythonCommand $pythonCommand -Port 8502
} else {
    Start-Streamlit -PythonCommand $pythonCommand -Port 8501
}
