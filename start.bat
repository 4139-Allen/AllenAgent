@echo off
cd /d "%~dp0"

echo ================================
echo  Allen Agent - 启动前后端
echo ================================

start "Allen Backend" cmd /c "cd /d %CD%\backend && python main.py"
start "Allen Frontend" cmd /c "cd /d %CD%\frontend && npm run dev"

echo 后端: http://localhost:8000
echo 前端: http://localhost:5173
echo.
echo 关闭窗口即停止服务。
pause
