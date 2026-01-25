@echo off
echo Starting EPS Bot (Unified)...

:: Check if npx is available
where npx >nul 2>nul
if %errorlevel% neq 0 (
    echo Error: Node.js/npx is not installed or not in PATH.
    echo Please install Node.js to use this unified starter.
    pause
    exit /b
)

:: Open browser after a short delay (in a separate process so it doesn't block)
start "" cmd /c "timeout /t 4 >nul && start http://localhost:5173"

:: Run backend and frontend concurrently in this single window
:: -k: kill others if one dies
npx -y concurrently -k -n "BACKEND,FRONTEND" -c "blue,green" "cd server && uvicorn app.main:app --reload" "cd client && npm run dev"

pause
