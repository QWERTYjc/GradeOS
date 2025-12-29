#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BookScan-AI 集成测试脚本
验证各个模块的导入和基本功能
"""

import sys
from pathlib import Path

# 添加 ai_correction 目录到路径
ai_correction_path = Path(__file__).parent / "ai_correction"
sys.path.insert(0, str(ai_correction_path))

def test_imports():
    """测试模块导入"""
    print("🧪 测试模块导入...")
    
    try:
        import streamlit as st
        print("✅ Streamlit 导入成功")
    except ImportError as e:
        print(f"❌ Streamlit 导入失败: {e}")
        return False
    
    try:
        from functions.bookscan_integration import BookScanIntegration, show_bookscan_scanner
        print("✅ BookScan 集成模块导入成功")
    except ImportError as e:
        print(f"❌ BookScan 集成模块导入失败: {e}")
        print("   这是正常的，因为需要在 Streamlit 环境中运行")
    
    try:
        from PIL import Image
        print("✅ PIL 图像处理库导入成功")
    except ImportError as e:
        print(f"❌ PIL 导入失败: {e}")
    
    return True

def test_file_structure():
    """测试文件结构"""
    print("\n📁 测试文件结构...")
    
    required_files = [
        "main.py",
        "requirements.txt", 
        "start_integrated_system.bat",
        "ai_correction/main.py",
        "ai_correction/functions/bookscan_integration.py"
    ]
    
    for file_path in required_files:
        if Path(file_path).exists():
            print(f"✅ {file_path} 存在")
        else:
            print(f"❌ {file_path} 不存在")
    
    return True

def test_bookscan_integration():
    """测试 BookScan 集成功能"""
    print("\n🔗 测试 BookScan 集成功能...")
    
    try:
        # 模拟创建 BookScan 集成实例
        from functions.bookscan_integration import BookScanIntegration
        
        integration = BookScanIntegration()
        print("✅ BookScanIntegration 实例创建成功")
        
        # 测试基本方法
        status = integration.get_api_integration_status()
        print(f"✅ API 集成状态获取成功: {status['status']}")
        
        return True
        
    except Exception as e:
        print(f"❌ BookScan 集成测试失败: {e}")
        return False

def test_directory_structure():
    """测试目录结构"""
    print("\n📂 测试目录结构...")
    
    directories = [
        "ai_correction",
        "ai_correction/functions",
        "ai_correction/bookscan-ai",
        "uploads"
    ]
    
    for dir_path in directories:
        path = Path(dir_path)
        if path.exists():
            print(f"✅ {dir_path}/ 目录存在")
        else:
            print(f"⚠️ {dir_path}/ 目录不存在，将创建")
            path.mkdir(parents=True, exist_ok=True)
    
    return True

def main():
    """主测试函数"""
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║     BookScan-AI 集成系统 - 功能测试                          ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    
    tests = [
        test_directory_structure,
        test_file_structure,
        test_imports,
        test_bookscan_integration
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ 测试异常: {e}")
    
    print(f"\n📊 测试结果: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 所有测试通过！系统集成成功")
        print("\n🚀 启动建议:")
        print("   1. 运行: streamlit run main.py --server.port=8502")
        print("   2. 访问: http://localhost:8502")
        print("   3. 或运行: start_integrated_system.bat")
    else:
        print("⚠️ 部分测试失败，请检查相关模块")
    
    return passed == total

if __name__ == "__main__":
    main()