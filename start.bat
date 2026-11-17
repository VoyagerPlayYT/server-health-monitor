@echo off
chcp 65001 > nul
title Server and PC Health Monitor Dashboard
echo ========================================================
echo   Server and PC Health Monitor Dashboard (Live Telemetry)
echo ========================================================
echo [INFO] Запуск веб-панели мониторинга на http://localhost:8002 ...
start http://localhost:8002
python -m uvicorn main:app --host 0.0.0.0 --port 8002
pause
