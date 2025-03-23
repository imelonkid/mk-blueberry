#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
PaperTrans 停止脚本 - Python版本
支持Windows/macOS/Linux系统
"""

import os
import sys
import time
import signal
import subprocess
import platform
from pathlib import Path

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
PID_FILE = SCRIPT_DIR / ".papertrans.pid"

def stop_service():
    print_color("停止 PaperTrans 服务...", 'blue')
    
    # 检查PID文件是否存在
    if not PID_FILE.exists():
        print_color("未找到PID文件，服务可能未运行", 'yellow')
        return True
    
    try:
        # 读取PID
        pid = int(PID_FILE.read_text().strip())
        
        # 检查进程是否存在
        process_exists = False
        try:
            if platform.system() == "Windows":
                # 在Windows上检查进程
                output = subprocess.check_output(f"tasklist /FI \"PID eq {pid}\"", shell=True).decode()
                process_exists = str(pid) in output
            else:
                # 在Unix上检查进程
                os.kill(pid, 0)  # 不会发送信号，只检查进程是否存在
                process_exists = True
        except (subprocess.CalledProcessError, OSError, ProcessLookupError):
            process_exists = False
        
        if not process_exists:
            print_color(f"进程 {pid} 不存在，可能已停止", 'yellow')
            PID_FILE.unlink(missing_ok=True)
            return True
        
        # 停止进程
        print_color(f"停止进程 {pid}...", 'blue')
        
        try:
            if platform.system() == "Windows":
                # 在Windows上终止进程
                subprocess.run(f"taskkill /PID {pid} /F", shell=True, check=True)
            else:
                # 在Unix上发送SIGTERM信号
                os.kill(pid, signal.SIGTERM)
                
                # 等待进程终止
                max_wait = 10
                for i in range(max_wait):
                    try:
                        os.kill(pid, 0)
                        print_color(f"等待进程停止 ({i+1}/{max_wait})...", 'yellow')
                        time.sleep(1)
                    except OSError:
                        break
                
                # 如果进程仍在运行，强制终止
                try:
                    os.kill(pid, 0)
                    print_color("进程未能正常停止，尝试强制终止...", 'red')
                    os.kill(pid, signal.SIGKILL)
                    time.sleep(1)
                except OSError:
                    pass
        except Exception as e:
            print_color(f"停止进程时出错: {str(e)}", 'red')
            print_color(f"请手动终止进程 {pid}", 'yellow')
            return False
        
        # 最终检查进程是否已停止
        try:
            if platform.system() == "Windows":
                output = subprocess.check_output(f"tasklist /FI \"PID eq {pid}\"", shell=True).decode()
                if str(pid) in output:
                    print_color(f"无法停止进程 {pid}", 'red')
                    print_color(f"请手动终止进程", 'yellow')
                    return False
            else:
                os.kill(pid, 0)
                print_color(f"无法停止进程 {pid}", 'red')
                print_color(f"请手动运行: kill -9 {pid}", 'yellow')
                return False
        except (subprocess.CalledProcessError, OSError, ProcessLookupError):
            # 进程已成功停止
            pass
        
        print_color("服务已成功停止", 'green')
        PID_FILE.unlink(missing_ok=True)
        return True
        
    except Exception as e:
        print_color(f"停止服务时出错: {str(e)}", 'red')
        return False

def main():
    if stop_service():
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()