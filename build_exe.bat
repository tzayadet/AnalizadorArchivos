@echo off
setlocal
title Analizador de Archivos PRO - Generador de EXE
color 0A

echo ============================================================
echo   Analizador de Archivos PRO - Generador de EXE portable
echo ============================================================
echo.
echo Este script debe ejecutarse en Windows, con Python instalado.
echo Descarga Python (si no lo tienes) desde https://www.python.org/downloads/
echo IMPORTANTE al instalar Python: marca la casilla "Add Python to PATH".
echo.
pause

REM --- Comprobar que Python está disponible ---
where python >nul 2>nul
if errorlevel 1 (
    echo.
    echo [ERROR] No se encontro "python" en el PATH del sistema.
    echo Instala Python desde https://www.python.org/downloads/
    echo y vuelve a ejecutar este script.
    echo.
    pause
    exit /b 1
)

echo.
echo [1/4] Creando entorno virtual aislado (venv_build)...
python -m venv venv_build
call venv_build\Scripts\activate.bat

echo.
echo [2/4] Actualizando pip e instalando PyInstaller...
python -m pip install --upgrade pip >nul
pip install pyinstaller

echo.
echo [3/4] Generando el ejecutable portable (un unico archivo .exe, sin consola)...
REM  --onefile     -> un solo .exe portable (no necesita instalar nada en el PC destino)
REM  --windowed    -> sin ventana de consola negra detras de la GUI
REM  --name        -> nombre del ejecutable final
REM  --clean       -> limpia cache de compilaciones anteriores
pyinstaller --onefile --windowed --clean --name "AnalizadorDeArchivosPRO" analizador_archivos.py

echo.
echo [4/4] Limpiando archivos temporales de compilacion...
rmdir /s /q build >nul 2>nul
del /q AnalizadorDeArchivosPRO.spec >nul 2>nul

echo.
echo ============================================================
echo   LISTO. Tu ejecutable portable esta en:
echo   dist\AnalizadorDeArchivosPRO.exe
echo.
echo   Puedes copiar ese unico archivo .exe a cualquier PC con
echo   Windows y funcionara sin instalar Python ni nada mas
echo   (standalone / portable).
echo ============================================================
echo.
pause
