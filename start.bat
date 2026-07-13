@echo off
cd /d "%~dp0"

if not exist venv (
    echo Creating virtual environment, this may take a moment...
    py -3.12 -m venv venv
    if errorlevel 1 (
        echo Could not create the environment using "py -3.12".
        echo Please make sure Python 3.12 is installed and try again.
        pause
        exit /b 1
    )
    call venv\Scripts\activate.bat
    echo Installing dependencies, this can take a couple of minutes...
    pip install -r requirements.txt
) else (
    call venv\Scripts\activate.bat
)

echo.
echo Starting the server...
echo Once you see "Uvicorn running on http://127.0.0.1:8000", open that
echo address in your browser.
echo To stop the server, close this window or press Ctrl+C.
echo.

uvicorn app.main:app --reload

pause
