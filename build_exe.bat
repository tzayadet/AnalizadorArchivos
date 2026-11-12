@echo off
setlocal EnableExtensions
title Analizador de Archivos PRO - Generador de EXE
color 0A

REM Always work from the directory containing this script.
pushd "%~dp0"
if errorlevel 1 (
    echo [ERROR] No se pudo acceder al directorio del proyecto.
    exit /b 1
)

echo ============================================================
echo   Analizador de Archivos PRO - Generador de EXE portable
echo ============================================================
echo.
echo Este script debe ejecutarse en Windows, con Python instalado.
echo Descarga Python desde https://www.python.org/downloads/
echo IMPORTANTE: marca "Add Python to PATH" durante la instalacion.
echo.
pause

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] No se encontro Python en PATH.
    popd
    pause
    exit /b 1
)

set "BUILD_DIR=%TEMP%\AnalizadorArchivosPRO_build_%RANDOM%_%RANDOM%"
set "DIST_DIR=%~dp0dist"

echo.
echo [1/4] Creando entorno virtual aislado...
if not exist "venv_build\Scripts\python.exe" (
    python -m venv venv_build
    if errorlevel 1 (
        echo [ERROR] No se pudo crear el entorno virtual.
        popd
        pause
        exit /b 1
    )
)

call "venv_build\Scripts\activate.bat"
if errorlevel 1 (
    echo [ERROR] No se pudo activar el entorno virtual.
    popd
    pause
    exit /b 1
)

echo.
echo [2/4] Instalando PyInstaller...
python -m pip install --upgrade pip
if errorlevel 1 goto BUILD_FAILED
python -m pip install pyinstaller
if errorlevel 1 goto BUILD_FAILED

echo.
echo [3/4] Generando el ejecutable en un directorio temporal...
python -m PyInstaller --onefile --windowed --clean --noconfirm ^
  --name "AnalizadorDeArchivosPRO" ^
  --distpath "%BUILD_DIR%\dist" ^
  --workpath "%BUILD_DIR%\work" ^
  --specpath "%BUILD_DIR%\spec" ^
  "analizador_archivos.py"
if errorlevel 1 goto BUILD_FAILED

if not exist "%BUILD_DIR%\dist\AnalizadorDeArchivosPRO.exe" (
    echo [ERROR] PyInstaller no genero el ejecutable esperado.
    goto BUILD_FAILED
)

echo.
echo [4/4] Copiando el ejecutable sin sobrescribir archivos existentes...
if not exist "%DIST_DIR%\." mkdir "%DIST_DIR%"
if errorlevel 1 goto BUILD_FAILED

set "OUTPUT_NAME=AnalizadorDeArchivosPRO"
set /a SUFFIX=2
:CHECK_OUTPUT
if exist "%DIST_DIR%\%OUTPUT_NAME%.exe" (
    set "OUTPUT_NAME=AnalizadorDeArchivosPRO_%SUFFIX%"
    set /a SUFFIX+=1
    goto CHECK_OUTPUT
)

move "%BUILD_DIR%\dist\AnalizadorDeArchivosPRO.exe" "%DIST_DIR%\%OUTPUT_NAME%.exe" >nul
if errorlevel 1 goto BUILD_FAILED

if exist "%BUILD_DIR%\." rmdir /s /q "%BUILD_DIR%"

echo.
echo ============================================================
echo   LISTO: dist\%OUTPUT_NAME%.exe
echo   El directorio de origen y los .spec existentes no se han tocado.
echo ============================================================
popd
pause
exit /b 0

:BUILD_FAILED
echo.
echo [ERROR] El proceso de compilacion ha fallado.
echo Los archivos del proyecto no se han eliminado.
if exist "%BUILD_DIR%\." rmdir /s /q "%BUILD_DIR%"
popd
pause
exit /b 1
