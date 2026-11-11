@echo off
chcp 65001 >nul
echo ===================================================
echo   Chrome Profile Portable Vault - בניית קובץ EXE
echo ===================================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python לא מותקן או לא נוסף ל-PATH במחשב.
    pause
    exit /b 1
)

echo [1/3] התקנת pyinstaller...
pip install pyinstaller

echo.
echo [2/3] בניית קובץ EXE עצמאי ונייד (Portable Single File)...
pyinstaller ChromeVault.spec

if errorlevel 1 (
    echo.
    echo [ERROR] הבנייה נכשלה.
    pause
    exit /b 1
)

echo.
echo [3/3] העתקת קובץ ההרצה ChromeVault.exe לתיקייה הראשית...
copy /Y dist\ChromeVault.exe . >nul

echo.
echo ===================================================
echo   הקובץ ChromeVault.exe נוצר בהצלחה!
echo   ניתן להעתיק אותו ישירות לדיסק-און-קי (USB).
echo ===================================================
pause
