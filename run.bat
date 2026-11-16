@echo off
REM CREATEchat one-command launcher (Windows).
REM Backend: http://127.0.0.1:8000   Frontend: http://localhost:5173
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo CREATEchat - OPAH prototype
echo ----------------------------------------

where python >nul 2>nul
if errorlevel 1 (
  echo [X] Python is required. Install Python 3.10+ and tick "Add to PATH".
  exit /b 1
)
where node >nul 2>nul
if errorlevel 1 (
  echo [X] Node.js is required. Install Node.js 18+ from https://nodejs.org
  exit /b 1
)
where npm >nul 2>nul
if errorlevel 1 (
  echo [X] npm is required and ships with Node.js.
  exit /b 1
)

if not exist "backend\.venv" (
  echo - Creating the Python virtual environment
  python -m venv backend\.venv
  if errorlevel 1 exit /b 1
)
set "PY=%CD%\backend\.venv\Scripts\python.exe"

"%PY%" -c "import fastapi, uvicorn, openai, pypdf, multipart, dotenv" >nul 2>nul
if errorlevel 1 (
  echo - Installing backend dependencies
  "%PY%" -m pip install --upgrade pip >nul
  "%PY%" -m pip install -r backend\requirements.txt
) else (
  echo - Backend dependencies already installed
)

if not exist "frontend\node_modules" (
  echo - Installing frontend dependencies
  pushd frontend
  call npm install --no-audit --no-fund
  popd
) else (
  echo - Frontend dependencies already installed
)

if not exist ".env" (
  echo - Creating .env from .env.example
  copy /y ".env.example" ".env" >nul
)

findstr /b /r "^OPENAI_API_KEY=." .env >nul 2>nul
if errorlevel 1 findstr /b /r "^OPENAI_API_KEY=." backend\.env >nul 2>nul
if errorlevel 1 (
  echo - No OPENAI_API_KEY yet - chat replies stay disabled until you add one
) else (
  echo - Model key found
)

echo - Starting the FastAPI backend
start "CREATEchat backend" /min cmd /c ""%PY%" -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000"

echo - Starting the React frontend
start "CREATEchat frontend" /min cmd /c "cd /d "%CD%\frontend" && npm run dev"

timeout /t 6 /nobreak >nul

echo.
echo ----------------------------------------
echo   CREATEchat is running
echo.
echo   Frontend  http://localhost:5173
echo   Backend   http://127.0.0.1:8000
echo   API docs  http://127.0.0.1:8000/docs
echo.
echo   Demo accounts: clt_001 (Maya), clt_002 (Jordan), clt_003 (Sam)
echo   Add OPENAI_API_KEY to .env for live assistant replies.
echo   Close the two minimized windows to stop the servers.
echo ----------------------------------------
start "" http://localhost:5173
endlocal
