@echo off
setlocal

set "SKIP_PYINSTALLER=0"
for %%A in (%*) do (
	if /I "%%~A"=="-n" set "SKIP_PYINSTALLER=1"
)

set "APP_VERSION_FILE=app_version.py"
set "APP_VERSION_BACKUP=app_version.py.bak"

if exist "%APP_VERSION_FILE%" copy /y "%APP_VERSION_FILE%" "%APP_VERSION_BACKUP%" >nul

for /f "usebackq tokens=2 delims== " %%v in (`findstr /r /c:"^[ ]*version[ ]*=" pyproject.toml`) do set "APP_VERSION=%%~v"
if "%APP_VERSION%"=="" set "APP_VERSION=0.0.0"

echo Build versione: %APP_VERSION%

> "%APP_VERSION_FILE%" echo APP_VERSION = "%APP_VERSION%"

if "%SKIP_PYINSTALLER%"=="0" (
	pyinstaller main.py --noconsole --onefile --name "Gestione Inventario" --icon static\icon.ico
	if exist "Gestione Inventario.spec" del /f "Gestione Inventario.spec"
	if exist ".\build\" rmdir /s /q .\build\
)

where ISCC >nul 2>nul
set "ISCC_EXE="
set "ISS_FILE=inno-setup\gestione_inventario-setup.iss"

if defined ISCC_PATH if exist "%ISCC_PATH%" set "ISCC_EXE=%ISCC_PATH%"
if not defined ISCC_EXE if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC_EXE=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC_EXE if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC_EXE=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not defined ISCC_EXE if %errorlevel% equ 0 set "ISCC_EXE=ISCC"

if not exist "%ISS_FILE%" (
	echo File .iss non trovato: %ISS_FILE%
	echo Controlla il percorso del progetto o il nome del file Inno Setup.
	goto :eof
)

if defined ISCC_EXE (
	"%ISCC_EXE%" /DMyAppVersion=%APP_VERSION% "%ISS_FILE%"
) else (
	echo ISCC non trovato nel PATH ne nelle cartelle standard.
	echo Installa Inno Setup 6 oppure imposta ISCC_PATH con il percorso completo di ISCC.exe.
	echo Esempio: set "ISCC_PATH=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
)

if exist "%APP_VERSION_BACKUP%" (
	move /y "%APP_VERSION_BACKUP%" "%APP_VERSION_FILE%" >nul
)