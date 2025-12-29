"""
上传文件并监控 Worker 上下文

直接上传文件到后端，然后通过浏览器监控 WebSocket 消息
"""

import requests
import time
import os
from pathlib import Path

# 测试文件路径
RUBRIC_PDF = Path(__file__).parent.parent / "批改" / "批改标准.pdf"
ANSWER_PDF = Path(__file__).parent.parent / "批改" / "学生作答.pdf"

def main():
    print("\n" + "="*60)
    print("上传文件并监控 Worker 上下文")
    print("="*60)
    
    # 检查文件
    if not RUBRIC_PDF.exists():
        print(f"❌ 找不到文件: {RUBRIC_PDF}")
        return
    
    if not ANSWER_PDF.exists():
        print(f"❌ 找不到文件: {ANSWER_PDF}")
        return
    
    print(f"\n✅ 找到测试文件")
    print(f"  评分标准: {RUBRIC_PDF.name} ({RUBRIC_PDF.stat().st_size / 1024:.1f} KB)")
    print(f"  学生作答: {ANSWER_PDF.name} ({ANSWER_PDF.stat().st_size / 1024:.1f} KB)")
    
    # 获取 API Key
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print(f"\n⚠️ 警告: 未设置 GEMINI_API_KEY 环境变量")
        print(f"  批改可能会失败")
    else:
        print(f"\n✅ 已设置 API Key")
    
    print(f"\n准备上传文件...")
    
    try:
        # 打开文件
        with open(RUBRIC_PDF, 'rb') as rubric_file, open(ANSWER_PDF, 'rb') as answer_file:
            files = {
                'rubrics': ('批改标准.pdf', rubric_file, 'application/pdf'),
                'files': ('学生作答.pdf', answer_file, 'application/pdf')
            }
            
            data = {
                'exam_id': 'browser_test_001',
                'auto_identify': 'true'
            }
            
            if api_key:
                data['api_key'] = api_key
            
            print(f"\n📤 发送请求到 http://localhost:8001/batch/submit")
            
            response = requests.post(
                'http://localhost:8001/batch/submit',
                files=files,
                data=data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                batch_id = result.get('batch_id')
                
                print(f"\n✅ 批改任务已提交!")
                print(f"  Batch ID: {batch_id}")
                print(f"  状态: {result.get('status')}")
                print(f"  总页数: {result.get('total_pages')}")
                print(f"  预计时间: {result.get('estimated_completion_time')} 秒")
                
                print(f"\n" + "="*60)
                print(f"📊 浏览器监控指南")
                print(f"="*60)
                print(f"\n1. 打开浏览器 (http://localhost:3000/console)")
                print(f"2. 按 F12 打开开发者工具")
                print(f"3. 切换到 Console 标签")
                print(f"4. 查看 [WS Monitor] 开头的日志")
                print(f"\n关键监控点:")
                print(f"  • WebSocket 消息类型和大小")
                print(f"  • Agent 上下文数据 (agent_update 消息)")
                print(f"  • 批次完成信息 (batch_completed 消息)")
                print(f"  • 跨页题目检测 (cross_page_detected 消息)")
                print(f"  • 学生分割结果 (students_identified 消息)")
                
                print(f"\n运行以下命令查看监控报告:")
                print(f"  window.wsMonitor.getReport()")
                
                print(f"\n等待批改完成 (约 {result.get('estimated_completion_time', 30)} 秒)...")
                
                # 轮询状态
                for i in range(10):
                    time.sleep(3)
                    try:
                        status_resp = requests.get(
                            f'http://localhost:8001/batch/status/{batch_id}',
                            timeout=5
                        )
                        if status_resp.status_code == 200:
                            status = status_resp.json()
                            print(f"  [{i*3}s] 状态: {status.get('status')}, "
                                  f"学生数: {status.get('total_students')}, "
                                  f"已完成: {status.get('completed_students')}")
                            
                            if status.get('status') in ['COMPLETED', 'FAILED']:
                                break
                    except:
                        pass
                
                print(f"\n" + "="*60)
                print(f"✅ 测试完成!")
                print(f"="*60)
                
                print(f"\n下一步:")
                print(f"1. 在浏览器控制台运行: window.wsMonitor.getReport()")
                print(f"2. 检查消息统计:")
                print(f"   • totalMessages: 总消息数")
                print(f"   • totalSize: 总数据大小")
                print(f"   • messageTypes: 各类型消息统计")
                print(f"   • largeMessages: 过大的消息 (> 10KB)")
                
                print(f"\n验证要点:")
                print(f"  ✅ 所有消息 < 10KB")
                print(f"  ✅ Agent 输出只包含 score, maxScore, feedback, questionResults")
                print(f"  ✅ 无多余的上下文数据")
                print(f"  ✅ 工作流节点按顺序执行")
                
            else:
                print(f"\n❌ 请求失败:")
                print(f"  状态码: {response.status_code}")
                print(f"  响应: {response.text[:500]}")
                
    except requests.exceptions.ConnectionError:
        print(f"\n❌ 无法连接到后端 (http://localhost:8001)")
        print(f"  请确保后端服务正在运行:")
        print(f"  cd GradeOS-Platform/backend")
        print(f"  uvicorn src.api.main:app --reload --port 8001")
        
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
