#!/usr/bin/env python3
"""
Celery Worker 热重载启动脚本
"""
import subprocess
import sys
import time
import os
import hashlib
from pathlib import Path

def run_celery():
    """启动 Celery Worker"""
    cmd = [
        'celery', '-A', 'tasks.celery_app',
        'worker', '--loglevel=info', '--concurrency=2'
    ]
    return subprocess.Popen(cmd)

def get_file_hash(filepath):
    """计算文件MD5哈希"""
    try:
        with open(filepath, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()
    except:
        return None

def scan_files(base_path):
    """扫描所有Python文件"""
    hashes = {}
    # 只扫描关键目录
    scan_dirs = ['services', 'ai_models', 'api', 'shared', 'tasks.py', 'main.py', 'config.py']

    for item in scan_dirs:
        full_path = os.path.join(base_path, item)
        if os.path.isfile(full_path) and full_path.endswith('.py'):
            h = get_file_hash(full_path)
            if h:
                hashes[full_path] = h
        elif os.path.isdir(full_path):
            for root, dirs, files in os.walk(full_path):
                dirs[:] = [d for d in dirs if d not in ['__pycache__']]
                for file in files:
                    if file.endswith('.py'):
                        filepath = os.path.join(root, file)
                        h = get_file_hash(filepath)
                        if h:
                            hashes[filepath] = h
    return hashes

print("🚀 Starting Celery Worker with hot reload...")
print("⏳ Scanning files...")

# 初始扫描
file_hashes = scan_files('/app')
print(f"✅ Watching {len(file_hashes)} Python files")

# 启动 Celery
process = run_celery()
print("🟢 Celery Worker started\n")

# 监控循环
try:
    while True:
        time.sleep(4)  # 每4秒检查一次

        changes = []
        new_hashes = scan_files('/app')

        for filepath, new_hash in new_hashes.items():
            if filepath in file_hashes:
                if file_hashes[filepath] != new_hash:
                    changes.append(filepath)
            else:
                # 新文件
                changes.append(filepath)

        # 检查删除的文件
        for filepath in file_hashes:
            if filepath not in new_hashes:
                changes.append(filepath)

        file_hashes = new_hashes

        if changes:
            print(f"\n📝 {len(changes)} file(s) changed:")
            for f in changes[:3]:
                print(f"  - {os.path.basename(f)}")
            if len(changes) > 3:
                print(f"  ... and {len(changes) - 3} more")

            print("🔄 Restarting Celery...")
            process.terminate()
            try:
                process.wait(timeout=5)
            except:
                process.kill()
                process.wait()

            process = run_celery()
            file_hashes = scan_files('/app')  # 重新扫描
            print("✅ Restarted\n")

except KeyboardInterrupt:
    print("\n🛑 Shutting down...")
    process.terminate()
    process.wait()
