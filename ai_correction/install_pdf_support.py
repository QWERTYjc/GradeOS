#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
安装 PDF 和 Word 支持库
"""

import subprocess
import sys

def install_packages():
    """安装必要的包"""
    packages = [
        'PyPDF2',
        'python-docx'
    ]
    
    for package in packages:
        print(f"正在安装 {package}...")
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', package])
            print(f"✅ {package} 安装成功")
        except Exception as e:
            print(f"❌ {package} 安装失败: {e}")

if __name__ == '__main__':
    install_packages()
    print("\n所有包安装完成！")

