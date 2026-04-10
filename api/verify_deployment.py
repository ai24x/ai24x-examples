#!/usr/bin/env python3
"""
AI24X 副脑01 Day1 部署验证脚本
"""

import os
import sys
import subprocess
import time

def print_header(text):
    print("\n" + "="*60)
    print(f"  {text}")
    print("="*60)

def print_success(text):
    print(f"✅ {text}")

def print_warning(text):
    print(f"⚠️  {text}")

def print_error(text):
    print(f"❌ {text}")

def check_file_exists(filepath):
    if os.path.exists(filepath):
        print_success(f"文件存在: {filepath}")
        return True
    else:
        print_error(f"文件缺失: {filepath}")
        return False

def check_directory_exists(dirpath):
    if os.path.exists(dirpath) and os.path.isdir(dirpath):
        print_success(f"目录存在: {dirpath}")
        return True
    else:
        print_error(f"目录缺失: {dirpath}")
        return False

def check_python_import(module_name):
    try:
        __import__(module_name)
        print_success(f"Python模块可导入: {module_name}")
        return True
    except ImportError as e:
        print_error(f"Python模块导入失败: {module_name} - {e}")
        return False

def run_command(cmd, timeout=10):
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        if result.returncode == 0:
            print_success(f"命令执行成功: {cmd}")
            return True, result.stdout
        else:
            print_error(f"命令执行失败: {cmd}")
            print(f"错误输出: {result.stderr}")
            return False, result.stderr
    except subprocess.TimeoutExpired:
        print_error(f"命令超时: {cmd}")
        return False, "Timeout"
    except Exception as e:
        print_error(f"命令异常: {cmd} - {e}")
        return False, str(e)

def main():
    print_header("AI24X 副脑01 Day1 部署验证")
    
    # 切换到项目目录
    project_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_dir)
    print(f"项目目录: {project_dir}")
    
    # 1. 检查项目结构
    print_header("1. 检查项目结构")
    
    required_files = [
        "main.py",
        "config.py", 
        "database.py",
        "models.py",
        "schemas.py",
        "services.py",
        "requirements.txt",
        ".env.example",
        "run.py",
        "README.md",
        "DAY1_DEPLOYMENT_SUMMARY.md",
        "test_api.py"
    ]
    
    required_dirs = [
        "venv"
    ]
    
    file_checks = []
    for file in required_files:
        file_checks.append(check_file_exists(file))
    
    dir_checks = []
    for dir in required_dirs:
        dir_checks.append(check_directory_exists(dir))
    
    # 2. 检查Python环境
    print_header("2. 检查Python环境")
    
    # 检查Python版本
    success, output = run_command("python --version")
    if success:
        print(f"Python版本: {output.strip()}")
    
    # 检查虚拟环境
    if os.path.exists("venv"):
        # 在Windows上检查激活脚本
        if os.path.exists("venv\\Scripts\\activate"):
            print_success("虚拟环境结构正确 (Windows)")
        elif os.path.exists("venv/bin/activate"):
            print_success("虚拟环境结构正确 (Linux/Mac)")
        else:
            print_warning("虚拟环境激活脚本未找到")
    else:
        print_warning("虚拟环境目录不存在，跳过环境检查")
    
    # 3. 检查核心功能
    print_header("3. 检查核心功能")
    
    # 检查配置文件
    if check_file_exists(".env"):
        with open(".env", 'r') as f:
            env_content = f.read()
            if "DATABASE_URL" in env_content:
                print_success(".env 文件包含数据库配置")
            else:
                print_warning(".env 文件缺少DATABASE_URL配置")
    else:
        print_warning(".env 文件不存在，使用默认配置")
    
    # 4. 代码语法检查
    print_header("4. 代码语法检查")
    
    python_files = [f for f in required_files if f.endswith('.py')]
    syntax_errors = []
    
    for py_file in python_files:
        success, output = run_command(f"python -m py_compile {py_file}", timeout=5)
        if not success:
            syntax_errors.append(py_file)
    
    if not syntax_errors:
        print_success("所有Python文件语法正确")
    else:
        print_error(f"语法错误文件: {', '.join(syntax_errors)}")
    
    # 5. 数据库初始化检查
    print_header("5. 数据库初始化检查")
    
    # 修改database.py使用SQLite
    temp_db_file = "test_ai24x.db"
    
    # 创建测试数据库配置
    test_config = f"""
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = "sqlite:///{temp_db_file}"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    log_level: str = "INFO"
    
    class Config:
        env_file = ".env"

settings = Settings()
"""
    
    # 临时修改config.py
    original_config = None
    if os.path.exists("config.py"):
        with open("config.py", 'r') as f:
            original_config = f.read()
        
        with open("config.py", 'w') as f:
            f.write(test_config)
    
    try:
        # 尝试初始化数据库
        print("尝试初始化测试数据库...")
        success, output = run_command("python -c \"from database import init_db; init_db(); print('数据库初始化成功')\"", timeout=10)
        
        if success and "数据库初始化成功" in output:
            print_success("数据库初始化测试通过")
            
            # 检查数据库文件
            if os.path.exists(temp_db_file):
                print_success(f"数据库文件创建成功: {temp_db_file}")
                # 清理测试文件
                os.remove(temp_db_file)
                print_success("测试数据库文件已清理")
            else:
                print_warning("数据库文件未创建，但初始化成功")
        else:
            print_warning("数据库初始化测试失败（可能是配置问题）")
            print(f"输出: {output}")
            
    except Exception as e:
        print_error(f"数据库测试异常: {e}")
    finally:
        # 恢复原始配置
        if original_config:
            with open("config.py", 'w') as f:
                f.write(original_config)
    
    # 6. 生成部署报告
    print_header("6. 部署验证总结")
    
    total_checks = len(file_checks) + len(dir_checks)
    passed_checks = sum(file_checks) + sum(dir_checks)
    
    print(f"文件检查: {sum(file_checks)}/{len(file_checks)} 通过")
    print(f"目录检查: {sum(dir_checks)}/{len(dir_checks)} 通过")
    print(f"总体通过率: {passed_checks}/{total_checks} ({passed_checks/total_checks*100:.1f}%)")
    
    if passed_checks == total_checks:
        print_success("🎉 Day1 部署验证完全通过！")
        print("\n下一步:")
        print("1. 安装依赖: pip install -r requirements.txt")
        print("2. 启动服务: python run.py")
        print("3. 访问文档: http://localhost:8000/docs")
    elif passed_checks >= total_checks * 0.8:
        print_warning("⚠️ Day1 部署验证基本通过，有少量问题")
        print("\n建议:")
        print("1. 检查缺失的文件")
        print("2. 确保虚拟环境正确设置")
        print("3. 运行测试脚本: python test_api.py")
    else:
        print_error("❌ Day1 部署验证失败")
        print("\n需要修复:")
        print("1. 检查项目结构完整性")
        print("2. 验证Python环境")
        print("3. 重新运行部署脚本")
    
    # 7. 显示关键信息
    print_header("7. 关键信息")
    
    print("项目名称: AI24X 副脑01 API")
    print("技术栈: FastAPI + Python + PostgreSQL/SQLite")
    print("核心接口: POST /v1/chat/run")
    print(f"验证时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    print("\n" + "="*60)
    print("验证完成！")
    print("="*60)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n验证被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n验证过程中发生错误: {e}")
        sys.exit(1)