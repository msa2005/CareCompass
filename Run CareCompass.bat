@echo off
setlocal
title CareCompass launcher

cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo Python was not found. Install Python 3.11 or newer, then try again.
  pause
  exit /b 1
)

where node >nul 2>nul
if errorlevel 1 (
  echo Node.js was not found. Install Node.js 20 or newer, then try again.
  pause
  exit /b 1
)

where npm >nul 2>nul
if errorlevel 1 (
  echo npm was not found. Reinstall Node.js with npm included, then try again.
  pause
  exit /b 1
)

if not exist ".env" (
  echo The project .env file is missing.
  echo Copy .env.example to .env, add your Supabase credentials, then run this file again.
  pause
  exit /b 1
)

if not exist "web\.env.local" copy "web\.env.example" "web\.env.local" >nul

python -c "import fastapi, uvicorn, supabase, groq, pandas, joblib, sklearn" >nul 2>nul
if errorlevel 1 (
  echo Installing the CareCompass API packages. This may take a few minutes...
  python -m pip install -r api\requirements.txt
  if errorlevel 1 (
    echo API package installation failed. Check your internet connection and try again.
    pause
    exit /b 1
  )
)

if exist "web\node_modules\next\dist\bin\next" if exist "web\node_modules\react\package.json" goto start_services

echo Installing the CareCompass web packages. This may take a few minutes...
pushd web
call npm install
if errorlevel 1 (
  popd
  echo Web package installation failed. Check your internet connection and try again.
  pause
  exit /b 1
)
popd

:start_services
echo Starting the CareCompass API and web app...
netstat -ano | findstr /C:":8000" | findstr /C:"LISTENING" >nul
if errorlevel 1 (
  start "CareCompass API" /D "%~dp0" cmd /k "python -m uvicorn api.main:app --host 127.0.0.1 --port 8000"
) else echo CareCompass API is already running on port 8000.

netstat -ano | findstr /C:":3000" | findstr /C:"LISTENING" >nul
if errorlevel 1 (
  start "CareCompass Web" /D "%~dp0web" cmd /k "node node_modules/next/dist/bin/next dev --hostname 127.0.0.1 --port 3000"
) else echo CareCompass web app is already running on port 3000.

echo Waiting for the web app to start...
timeout /t 6 /nobreak >nul
start "" "http://127.0.0.1:3000"
echo CareCompass is opening in your browser.
endlocal
