@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

rem ============================================================
rem  WaveLogic MSO - Nuitka build for the launcher exe ONLY
rem  The Streamlit runtime is shipped as normal Python
rem  (make_runtime_bundle.ps1), NOT compiled into the exe.
rem ============================================================

set "ROOT=%~dp0"
set "SRC=%ROOT%src"
set "VENV_PY=%ROOT%..\.venv\Scripts\python.exe"
if not exist "%VENV_PY%" set "VENV_PY=python"

set APP_NAME=WaveLogicMSO
set MAIN_FILE=launcher.py
set LAUNCHER_VERSION=1.0.2

set BUILD_JOBS=%NUMBER_OF_PROCESSORS%
if not defined BUILD_JOBS set BUILD_JOBS=4
if %BUILD_JOBS% gtr 8 set BUILD_JOBS=8

set EXCLUDE_MODULES=unittest,test,pytest,_pytest,doctest,pdb,pdbpp
set EXCLUDE_MODULES=%EXCLUDE_MODULES%,setuptools,pip,distutils,pkg_resources
set EXCLUDE_MODULES=%EXCLUDE_MODULES%,email.mime,http.server,xmlrpc

echo.
echo [1/2] cleaning previous output...
if exist "%ROOT%dist\launcher.dist" rd /s /q "%ROOT%dist\launcher.dist"
if exist "%ROOT%dist\launcher.build" rd /s /q "%ROOT%dist\launcher.build"

echo.
echo [2/2] running Nuitka (%BUILD_JOBS% jobs)...
pushd "%SRC%"

"%VENV_PY%" -m nuitka --standalone ^
    --mingw64 --assume-yes-for-downloads ^
    --windows-console-mode=disable ^
    --company-name="Kishan J." ^
    --product-name="WaveLogic MSO" ^
    --product-version="%LAUNCHER_VERSION%" ^
    --file-version="%LAUNCHER_VERSION%" ^
    --file-description="WaveLogic MSO launcher %LAUNCHER_VERSION%" ^
    --windows-icon-from-ico=wavelogic_logo.ico ^
    --enable-plugin=tk-inter ^
    --jobs=%BUILD_JOBS% ^
    --enable-plugin=anti-bloat ^
    --noinclude-pytest-mode=nofollow ^
    --noinclude-setuptools-mode=nofollow ^
    --nofollow-import-to=%EXCLUDE_MODULES% ^
    --output-dir=%ROOT%dist ^
    --remove-output ^
    %MAIN_FILE%

set RC=%ERRORLEVEL%
popd

if %RC% neq 0 (
    echo.
    echo Build FAILED with code %RC%
    exit /b %RC%
)

echo.
echo Compile OK - launcher written to %ROOT%dist\launcher.dist\launcher.exe
endlocal