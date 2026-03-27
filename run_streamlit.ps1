# Always uses project venv Python (avoids a global `streamlit` on PATH from another install).
$ErrorActionPreference = "Stop"
$py = Join-Path $PSScriptRoot "venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $py)) {
    throw "venv not found at $py — create with: py -3.11 -m venv venv"
}
$main = Join-Path $PSScriptRoot "app\main.py"
$which = & $py -c "import sys; print(sys.executable)"
Write-Host "Using: $which" -ForegroundColor Cyan

$port = 8501
for ($i = 0; $i -lt $args.Count; $i++) {
    if ($args[$i] -eq "--server.port" -and ($i + 1) -lt $args.Count) {
        $port = [int]$args[$i + 1]
        break
    }
}
$url = "http://127.0.0.1:$port/"
Write-Host ""
Write-Host "  App URL (open manually if the browser does not start): $url" -ForegroundColor Yellow
Write-Host ""

# Open default browser once Streamlit is listening (Streamlit sometimes does not launch the browser on Windows).
$openCmd = @"
for (`$i = 0; `$i -lt 120; `$i++) {
  if (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) {
    Start-Process '$url'
    exit 0
  }
  Start-Sleep -Milliseconds 500
}
exit 1
"@
Start-Process -FilePath "powershell.exe" -ArgumentList @(
    "-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden", "-Command", $openCmd
) | Out-Null

& $py -m streamlit run $main @args
