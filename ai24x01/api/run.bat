@echo off
REM AI24X 副脑01 API 启动脚本 (Windows)

echo ========================================
echo   AI24X 副脑01 API 服务启动
echo ========================================

REM 激活虚拟环境
call venv\Scripts\activate.bat

REM 检查环境变量文件
if not exist .env (
    echo [警告] 未找到 .env 文件，使用默认配置
    echo 请复制 .env.example 为 .env 并配置数据库连接
)

REM 启动服务
python run.py

pause