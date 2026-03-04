# Quick script to free port 8501 and start Streamlit
Write-Host "Freeing port 8501..." -ForegroundColor Yellow

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

# Verify port is free
$stillInUse = Get-NetTCPConnection -LocalPort 8501 -ErrorAction SilentlyContinue
if ($stillInUse) {
    Write-Host "Port 8501 is still in use. Trying alternative port 8502..." -ForegroundColor Red
    Write-Host "Starting Streamlit on port 8502..." -ForegroundColor Green
    .\venvZ\Scripts\streamlit.exe run app\main.py --server.port 8502
} else {
    Write-Host "Port 8501 is free. Starting Streamlit..." -ForegroundColor Green
    .\venvZ\Scripts\streamlit.exe run app\main.py
}
