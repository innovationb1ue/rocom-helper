@echo off
echo Starting Roco PvP Helper...
echo.

where py >nul 2>&1 || (
    echo ERROR: py not found. Install Python and ensure 'py' is on PATH.
    exit /b 1
)

:: Double-clicked .bat files do not inherit an activated Anaconda environment.
:: Add the selected Python runtime's DLL paths so modules such as ssl can load.
set "PYTHON_PREFIX="
for /f "usebackq delims=" %%d in (`py -c "import sys; print(sys.prefix)" 2^>nul`) do set "PYTHON_PREFIX=%%d"
if not defined PYTHON_PREFIX (
    echo ERROR: Could not detect Python runtime prefix.
    exit /b 1
)
if exist "%PYTHON_PREFIX%\Library\bin" set "PATH=%PYTHON_PREFIX%\Library\bin;%PATH%"
if exist "%PYTHON_PREFIX%\DLLs" set "PATH=%PYTHON_PREFIX%\DLLs;%PATH%"
if exist "%PYTHON_PREFIX%\Scripts" set "PATH=%PYTHON_PREFIX%\Scripts;%PATH%"

py -c "import ssl" >nul 2>&1 || (
    echo ERROR: Python ssl module failed to load.
    echo        Python prefix: %PYTHON_PREFIX%
    echo        If this is Anaconda, repair the environment or run from Anaconda Prompt.
    exit /b 1
)

where npm >nul 2>&1 || (
    echo ERROR: npm not found. Install Node.js and ensure 'npm' is on PATH.
    exit /b 1
)

:: Kill existing backend (uvicorn on port 18731)
for /f "tokens=5" %%p in ('netstat -aon ^| findstr ":18731 " ^| findstr "LISTENING"') do (
    echo [kill] Found backend on port 18731, PID %%p, terminating...
    taskkill /PID %%p /F >nul 2>&1
)

:: Kill existing frontend (vite on port 18732)
for /f "tokens=5" %%p in ('netstat -aon ^| findstr ":18732 " ^| findstr "LISTENING"') do (
    echo [kill] Found frontend on port 18732, PID %%p, terminating...
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
echo Backend:  http://localhost:18731
echo Frontend: http://localhost:18732
echo.
echo Both servers starting in separate windows.
