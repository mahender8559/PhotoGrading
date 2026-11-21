@echo off
setlocal
cd /d "%~dp0"

py -3.11 --version >nul 2>&1
if errorlevel 1 (
    echo Python 3.11 was not found.
    echo Install Python 3.11 from https://www.python.org/downloads/windows/
    echo Make sure the Python Launcher is installed, then run this file again.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    py -3.11 -m venv .venv
    if errorlevel 1 goto failed
)

call ".venv\Scripts\activate.bat"
echo Installing or updating dependencies...
python -m pip install --upgrade pip
if errorlevel 1 goto failed
python -m pip install -r requirements.txt
if errorlevel 1 goto failed

echo Starting PhotoGrading...
python -m streamlit run app.py
goto end

:failed
echo.
echo Setup failed. Check the error above.
pause
exit /b 1

:end
endlocal
