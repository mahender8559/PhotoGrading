@echo off
setlocal
cd /d "%~dp0"

py -3.14 --version >nul 2>&1
if errorlevel 1 (
    echo Compatible Python was not found (need Python 3.14 or 3.11).
    echo Install Python 3.14 from https://www.python.org/downloads/release/python-31410/ (recommended), or Python 3.11.
    echo Install the Python Launcher / Python install manager too, then run this file again.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    %PY_CMD% -m venv .venv
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
