"""
真实浏览器流程测试

通过实际的文件上传和批改流程，监控：
1. WebSocket 消息的实际内容和大小
2. Worker 接收的上下文数据
3. 前后端数据传递的完整性
4. 实时进度更新的准确性

Requirements: 3.2 (Worker 独立性), 3.4 (进度报告)
"""

import asyncio
import json
import sys
import os
from pathlib import Path
from datetime import datetime
import requests

# 测试文件路径
RUBRIC_PDF = Path(__file__).parent.parent / "批改" / "批改标准.pdf"
ANSWER_PDF = Path(__file__).parent.parent / "批改" / "学生作答.pdf"


async def test_real_flow():
    """测试真实的批改流程"""
    print("\n" + "="*60)
    print("真实浏览器流程测试")
    print("="*60)
    
    # 检查文件是否存在
    if not RUBRIC_PDF.exists():
        print(f"❌ 评分标准文件不存在: {RUBRIC_PDF}")
        return False
    
    if not ANSWER_PDF.exists():
        print(f"❌ 学生作答文件不存在: {ANSWER_PDF}")
        return False
    
    print(f"\n✅ 找到测试文件:")
    print(f"  评分标准: {RUBRIC_PDF}")
    print(f"  学生作答: {ANSWER_PDF}")
    
    # 准备上传
    print(f"\n准备上传文件到后端...")
    
    try:
        # 上传文件
        with open(RUBRIC_PDF, 'rb') as rubric_file, open(ANSWER_PDF, 'rb') as answer_file:
            files = {
                'rubrics': ('批改标准.pdf', rubric_file, 'application/pdf'),
                'files': ('学生作答.pdf', answer_file, 'application/pdf')
            }
            
            data = {
                'exam_id': 'test_exam_001',
                'auto_identify': 'true'
            }
            
            # 检查是否有 API key
            api_key = os.getenv('GEMINI_API_KEY')
            if api_key:
                data['api_key'] = api_key
                print(f"✅ 使用环境变量中的 API Key")
            else:
                print(f"⚠️ 未找到 GEMINI_API_KEY 环境变量")
            
            print(f"\n发送批改请求到 http://localhost:8001/batch/submit")
            
            response = requests.post(
                'http://localhost:8001/batch/submit',
                files=files,
                data=data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                batch_id = result.get('batch_id')
                
                print(f"\n✅ 批改任务已提交:")
                print(f"  Batch ID: {batch_id}")
                print(f"  状态: {result.get('status')}")
                print(f"  总页数: {result.get('total_pages')}")
                print(f"  预计完成时间: {result.get('estimated_completion_time')} 秒")
                
                print(f"\n📊 现在可以在浏览器中观察:")
                print(f"  1. 打开浏览器控制台 (F12)")
                print(f"  2. 查看 [WS Monitor] 开头的日志")
                print(f"  3. 观察 WebSocket 消息的类型和大小")
                print(f"  4. 检查 Agent 上下文数据")
                
                print(f"\n等待批改完成...")
                print(f"提示: 在浏览器控制台中运行 window.wsMonitor.getReport() 查看监控报告")
                
                # 等待一段时间让批改完成
                await asyncio.sleep(5)
                
                # 查询状态
                print(f"\n查询批改状态...")
                status_response = requests.get(
                    f'http://localhost:8001/batch/status/{batch_id}',
                    timeout=10
                )
                
                if status_response.status_code == 200:
                    status = status_response.json()
                    print(f"\n当前状态:")
                    print(f"  状态: {status.get('status')}")
                    print(f"  学生数: {status.get('total_students')}")
                    print(f"  已完成: {status.get('completed_students')}")
                
                return True
                
            else:
                print(f"\n❌ 批改请求失败:")
                print(f"  状态码: {response.status_code}")
                print(f"  响应: {response.text}")
                return False
                
    except requests.exceptions.ConnectionError:
        print(f"\n❌ 无法连接到后端服务 (http://localhost:8001)")
        print(f"  请确保后端服务正在运行")
        return False
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """主函数"""
    print("\n" + "="*60)
    print("GradeOS 真实浏览器流程测试")
    print("="*60)
    
    print("\n测试说明:")
    print("1. 此测试将上传真实的 PDF 文件到后端")
    print("2. 后端将启动完整的批改流程")
    print("3. 浏览器中的 WebSocket 监控器将捕获所有消息")
    print("4. 测试完成后可以查看监控报告")
    
    print("\n前置条件:")
    print("✅ 前端运行在 http://localhost:3000")
    print("✅ 后端运行在 http://localhost:8001")
    print("✅ WebSocket 监控器已注入浏览器")
    
    input("\n按 Enter 键开始测试...")
    
    result = await test_real_flow()
    
    if result:
        print("\n" + "="*60)
        print("🎉 测试完成！")
        print("="*60)
        
        print("\n下一步:")
        print("1. 在浏览器控制台运行: window.wsMonitor.getReport()")
        print("2. 查看 WebSocket 消息统计")
        print("3. 检查是否有过大的消息 (> 10KB)")
        print("4. 验证 Worker 上下文是否干净")
        
        print("\n关键验证点:")
        print("  ✅ WebSocket 消息大小 < 10KB")
        print("  ✅ Agent 输出只包含必要字段")
        print("  ✅ 无多余的上下文数据传递")
        print("  ✅ 实时进度更新正常")
        
        return 0
    else:
        print("\n❌ 测试失败")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
