@echo off
setlocal
chcp 65001 > nul
title GPT-SoVITS Server

cd /d "%~dp0"

echo [1/3] Conda 활성화 스크립트 찾는 중...

:: ============================================================
:: [사용자 설정 영역] 본인의 Conda 경로를 여기에 적으세요.
set "MY_CONDA_PATH=W:\conda\Scripts\activate.bat"
:: ============================================================

:: 1. 사용자 설정 경로 확인
if exist "%MY_CONDA_PATH%" (
    echo [System] 사용자 설정 경로 발견: %MY_CONDA_PATH%
    call "%MY_CONDA_PATH%"
    goto :activate_env
)

:: 2. 일반적인 Anaconda 설치 경로 자동 탐색
set "COMMON_PATH_1=C:\ProgramData\Anaconda3\Scripts\activate.bat"
set "COMMON_PATH_2=%USERPROFILE%\anaconda3\Scripts\activate.bat"
set "COMMON_PATH_3=%USERPROFILE%\miniconda3\Scripts\activate.bat"

if exist "%COMMON_PATH_1%" (
    call "%COMMON_PATH_1%"
    goto :activate_env
)
if exist "%COMMON_PATH_2%" (
    call "%COMMON_PATH_2%"
    goto :activate_env
)
if exist "%COMMON_PATH_3%" (
    call "%COMMON_PATH_3%"
    goto :activate_env
)

:: 3. PATH에 등록된 경우 시도
conda --version >nul 2>&1
if %errorlevel% == 0 (
    echo [System] 시스템 PATH에서 Conda 발견.
    goto :activate_env
)

:: 4. 실패 시 안내 메시지
echo.
echo [Error] Anaconda를 찾을 수 없습니다!
echo -----------------------------------------------------------
echo [해결 방법]
echo 1. 이 배치 파일을 메모장으로 여세요.
echo 2. 'MY_CONDA_PATH' 변수에 아나콘다 설치 경로를 적어주세요.
echo    예: set "MY_CONDA_PATH=C:\MyAnaconda\Scripts\activate.bat"
echo -----------------------------------------------------------
pause
exit /b

:activate_env
echo.
echo [2/3] 가상환경(GPTSoVITS_FINAL) 활성화...
call conda activate GPTSoVITS_FINAL

if %errorlevel% neq 0 (
    echo.
    echo [Error] 가상환경 'GPTSoVITS_FINAL'이 없습니다.
    echo README를 보고 환경을 먼저 생성해주세요.
    pause
    exit /b
)

echo.
echo [3/3] GPT-SoVITS 서버 실행...
python api_v2.py

pause