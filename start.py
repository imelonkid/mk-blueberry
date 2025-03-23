#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
PaperTrans 启动脚本 - Python版本
支持Windows/macOS/Linux系统
"""

import os
import sys
import time
import signal
import subprocess
import webbrowser
import platform
from pathlib import Path
import argparse

# 设置颜色输出（如果支持）
try:
    import colorama
    colorama.init()
    
    def print_color(text, color):
        colors = {
            'red': colorama.Fore.RED,
            'green': colorama.Fore.GREEN,
            'yellow': colorama.Fore.YELLOW,
            'blue': colorama.Fore.BLUE,
            'reset': colorama.Fore.RESET
        }
        print(f"{colors.get(color, '')}{text}{colors.get('reset', '')}")
except ImportError:
    def print_color(text, color):
        print(text)

# 获取当前脚本目录
SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR / "backend"
LOG_FILE = SCRIPT_DIR / "papertrans.log"
PID_FILE = SCRIPT_DIR / ".papertrans.pid"
PORT = 8000

# 尝试加载.env文件中的配置
def load_env_file():
    env_file = SCRIPT_DIR / ".env"
    if env_file.exists():
        print_color("从.env文件加载配置...", 'blue')
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()
        return True
    return False

# 解析命令行参数
def parse_arguments():
    parser = argparse.ArgumentParser(description="启动PaperTrans PDF翻译服务")
    parser.add_argument('--port', type=int, help="指定要使用的端口号")
    return parser.parse_args()

# 打印欢迎信息
def print_welcome():
    print_color("""
  _____                      _______                    
 |  __ \                    |__   __|                   
 | |__) |__ _ _ __   ___ _ __  | |_ __ __ _ _ __  ___  
 |  ___/ _` | '_ \ / _ \ '__| | | '__/ _` | '_ \/ __| 
 | |  | (_| | |_) |  __/ |    | | | | (_| | | | \__ \ 
 |_|   \__,_| .__/ \___|_|    |_|_|  \__,_|_| |_|___/ 
            | |                                        
            |_|                                        
    """, 'blue')
    print_color("PDF论文翻译工具 - 启动脚本\n", 'green')

# 检查依赖
def check_requirements():
    if not (BACKEND_DIR / "PDFMathTranslate").exists():
        print_color("错误: 未找到 PDFMathTranslate 工具", 'red')
        print_color("请确认 PDFMathTranslate 已下载到 backend 目录", 'yellow')
        return False
        
    if not (BACKEND_DIR / "pdf_translator_bridge.py").exists():
        print_color("错误: 未找到 pdf_translator_bridge.py 文件", 'red')
        return False
        
    return True

# 检查已运行的进程
def check_running_process():
    if PID_FILE.exists():
        pid = int(PID_FILE.read_text().strip())
        try:
            # 检查进程是否运行
            if platform.system() == "Windows":
                subprocess.check_output(f"tasklist /FI \"PID eq {pid}\"", shell=True)
                # 如果没有抛出异常，表示进程存在
                print_color(f"PaperTrans 服务已经在运行 (PID: {pid})", 'yellow')
                print_color(f"访问地址: http://localhost:{PORT}", 'green')
                print_color("如需重启，请先停止当前服务", 'yellow')
                return True
            else:
                os.kill(pid, 0)  # 这不会真正发送信号，只会检查进程是否存在
                print_color(f"PaperTrans 服务已经在运行 (PID: {pid})", 'yellow')
                print_color(f"访问地址: http://localhost:{PORT}", 'green')
                print_color("如需重启，请先停止当前服务", 'yellow')
                return True
        except (subprocess.CalledProcessError, OSError, ProcessLookupError):
            print_color("发现过期的PID文件，正在清理...", 'yellow')
            PID_FILE.unlink(missing_ok=True)
    
    return False

# 启动服务
def start_service():
    print_color("启动PDF翻译后端服务...", 'blue')
    
    try:
        # 确保目录存在
        (BACKEND_DIR / "uploads").mkdir(exist_ok=True)
        (BACKEND_DIR / "translated").mkdir(exist_ok=True)
        
        # 设置API密钥（如果.env中未设置则提示配置）
        if "DEEPSEEK_API_KEY" not in os.environ:
            print_color("未在.env中找到DEEPSEEK_API_KEY，请在.env文件中配置", 'yellow')
            
        if "OPENAI_API_KEY" not in os.environ:
            # 如果设置了DEEPSEEK_API_KEY，同时将其用于OPENAI_API_KEY
            if "DEEPSEEK_API_KEY" in os.environ:
                print_color("未设置OPENAI_API_KEY，使用DEEPSEEK_API_KEY作为替代", 'yellow')
                os.environ["OPENAI_API_KEY"] = os.environ["DEEPSEEK_API_KEY"]
            else:
                print_color("未在.env中找到OPENAI_API_KEY，请在.env文件中配置", 'yellow')
        
        # 构建命令
        if platform.system() == "Windows":
            cmd = [
                sys.executable,
                str(BACKEND_DIR / "pdf_translator_bridge.py"),
                "--port", str(PORT)
            ]
            # 使用CREATE_NEW_CONSOLE创建新控制台窗口
            process = subprocess.Popen(
                cmd,
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
        else:
            # 对于Unix系统，将输出重定向到日志文件
            log_file = open(LOG_FILE, "w")
            cmd = [
                sys.executable,
                str(BACKEND_DIR / "pdf_translator_bridge.py"),
                "--port", str(PORT)
            ]
            process = subprocess.Popen(
                cmd,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                start_new_session=True  # 使进程独立于当前会话
            )
        
        # 保存PID
        PID_FILE.write_text(str(process.pid))
        
        # 等待服务启动
        print_color("等待服务启动...", 'yellow')
        time.sleep(3)
        
        # 检查服务是否成功启动
        try:
            if platform.system() == "Windows":
                subprocess.check_output(f"tasklist /FI \"PID eq {process.pid}\"", shell=True)
                service_running = True
            else:
                os.kill(process.pid, 0)
                service_running = True
        except:
            service_running = False
            
        if service_running:
            print_color(f"PDF翻译服务已成功启动 (PID: {process.pid})", 'green')
            if platform.system() != "Windows":
                print_color(f"日志文件: {LOG_FILE}", 'yellow')
            
            print_color("\n服务已启动!", 'green')
            url = f"http://localhost:{PORT}/translate.html"
            print_color(f"请在浏览器中访问: {url}", 'blue')
            
            # 自动打开浏览器
            try:
                webbrowser.open(url)
            except:
                print_color("无法自动打开浏览器，请手动访问上述地址", 'yellow')
                
            return True
        else:
            print_color("启动服务失败", 'red')
            if platform.system() != "Windows":
                print_color(f"请检查日志文件: {LOG_FILE}", 'yellow')
            return False
            
    except Exception as e:
        print_color(f"启动服务时出错: {str(e)}", 'red')
        return False

def main():
    global PORT
    
    # 加载.env文件
    load_env_file()
    
    # 解析命令行参数
    args = parse_arguments()
    
    # 优先级: 命令行参数 > 环境变量 > 默认值
    if args.port:
        PORT = args.port
    elif 'PORT' in os.environ:
        try:
            PORT = int(os.environ['PORT'])
            print_color(f"使用端口: {PORT}", 'blue')
        except ValueError:
            print_color(f"环境变量PORT值 '{os.environ['PORT']}' 无效，使用默认端口 {PORT}", 'yellow')
    
    print_welcome()
    
    if not check_requirements():
        sys.exit(1)
        
    if check_running_process():
        sys.exit(0)
        
    if start_service():
        print_color("\n要停止服务，请运行 stop.py 脚本或关闭服务窗口", 'yellow')
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main() 