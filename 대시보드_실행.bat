@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 공정별 불량률 대시보드

echo ============================================================
echo   공정별 불량률 취합·분석 대시보드
echo ============================================================
echo.

REM Node.js 설치 확인
node --version >nul 2>&1
if errorlevel 1 (
  echo [오류] Node.js가 설치되어 있지 않습니다.
  echo        https://nodejs.org 에서 Node.js LTS를 먼저 설치하세요.
  echo.
  pause
  exit /b 1
)

echo [1/2] 필요한 패키지 확인·설치 중... (처음 1회만 시간이 걸립니다)
call npm install
echo.
echo [2/2] 대시보드를 실행합니다. 잠시 후 브라우저가 자동으로 열립니다.
echo        종료하려면 이 창에서 Ctrl + C 를 누르거나 창을 닫으세요.
echo.

call npm run dev

pause
