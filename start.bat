@echo off
echo Starting Roco PvP Helper...
echo.

where py >nul 2>&1 || (
    echo ERROR: py not found. Install Python and ensure 'py' is on PATH.
    exit /b 1
)
where npm >nul 2>&1 || (
    echo ERROR: npm not found. Install Node.js and ensure 'npm' is on PATH.
    exit /b 1
)

:: Kill existing backend (uvicorn on port 8000)
for /f "tokens=5" %%p in ('netstat -aon ^| findstr ":8000 " ^| findstr "LISTENING"') do (
    echo [kill] Found backend on port 8000, PID %%p, terminating...
    taskkill /PID %%p /F >nul 2>&1
)

:: Kill existing frontend (vite on port 5173)
for /f "tokens=5" %%p in ('netstat -aon ^| findstr ":5173 " ^| findstr "LISTENING"') do (
    echo [kill] Found frontend on port 5173, PID %%p, terminating...
    taskkill /PID %%p /F >nul 2>&1
)

:: Also kill by window title in case the process hasn't bound the port yet
for /f "tokens=2" %%p in ('tasklist /FI "WINDOWTITLE eq Roco Backend" /NH 2^>nul ^| findstr /R "[0-9]"') do (
    echo [kill] Found backend window, PID %%p, terminating...
    taskkill /PID %%p /F >nul 2>&1
)
for /f "tokens=2" %%p in ('tasklist /FI "WINDOWTITLE eq Roco Frontend" /NH 2^>nul ^| findstr /R "[0-9]"') do (
    echo [kill] Found frontend window, PID %%p, terminating...
    taskkill /PID %%p /F >nul 2>&1
)

echo.
start "Roco Backend" cmd /k "py -m src.main"
start "Roco Frontend" cmd /k "cd web && npm run dev"

echo.
echo Backend:  http://localhost:8000
echo Frontend: http://localhost:5173
echo.
echo Both servers starting in separate windows.
