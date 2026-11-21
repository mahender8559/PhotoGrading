@echo off
setlocal
cd /d "%~dp0"

REM Prefer Python 3.14; fall back to the CI-tested Python 3.11.
py -3.14 --version >nul 2>&1
if not errorlevel 1 (
    set "PY_CMD=py -3.14"
) else (
    py -3.11 --version >nul 2>&1
    if not errorlevel 1 (
        set "PY_CMD=py -3.11"
    ) else (
        echo Compatible Python was not found. This project currently targets Python 3.14 or 3.11.
        echo Python 3.15 is not yet part of our tested setup because the OpenCV wheel support
        echo currently lists Python versions only through 3.14.
        echo.
        echo Install Python 3.14 from:
        echo https://www.python.org/downloads/release/python-31410/
        echo Install Python 3.14 using the standard Windows installer from that page.
        echo Then open a NEW terminal and confirm with: py -3.14 --version
        echo Finally double-click this file again.
        pause
        exit /b 1
    )
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment using %PY_CMD%...
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
