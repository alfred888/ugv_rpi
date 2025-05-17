#!/usr/bin/env python3
import os
import sys
import time
import signal
import psutil

def find_app_process():
    """查找运行中的app.py进程"""
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if 'python' in proc.info['name'].lower():
                cmdline = proc.info['cmdline']
                if cmdline and 'app.py' in cmdline[-1]:
                    return proc
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None

def kill_process(proc):
    """安全地终止进程"""
    try:
        proc.terminate()
        proc.wait(timeout=5)  # 等待进程终止
    except psutil.TimeoutExpired:
        proc.kill()  # 如果进程没有及时终止，强制结束

def main():
    print("正在停止机器人程序...")
    
    # 查找并终止现有的app.py进程
    proc = find_app_process()
    if proc:
        print(f"找到运行中的app.py进程 (PID: {proc.pid})")
        kill_process(proc)
        print("已成功停止机器人程序")
    else:
        print("未找到运行中的机器人程序")

if __name__ == "__main__":
    main()