"""批量提交 API 测试脚本

测试新的批量提交 API 端点，包括：
- 同步批改
- 异步批改
- 状态查询
- WebSocket 实时推送
"""

import asyncio
import json
from pathlib import Path
from typing import Optional

import aiohttp
import websockets


API_BASE_URL = "http://localhost:8000"
WS_BASE_URL = "ws://localhost:8000"
API_KEY = "AIzaSyD5D9_uYqcRgyivexpVq5iPvqL6uKD85QE"


async def test_sync_grading():
    """测试同步批改 API"""
    print("\n" + "=" * 70)
    print("测试 1: 同步批改 API")
    print("=" * 70)
    
    rubric_path = Path("批改标准.pdf")
    answer_path = Path("学生作答.pdf")
    
    if not rubric_path.exists() or not answer_path.exists():
        print("❌ 缺少必要文件")
        return None
    
    try:
        async with aiohttp.ClientSession() as session:
            with open(rubric_path, "rb") as rubric_file, \
                 open(answer_path, "rb") as answer_file:
                
                form_data = aiohttp.FormData()
                form_data.add_field("rubric_file", rubric_file, filename="rubric.pdf")
                form_data.add_field("answer_file", answer_file, filename="answer.pdf")
                form_data.add_field("api_key", API_KEY)
                form_data.add_field("total_score", "105")
                form_data.add_field("total_questions", "19")
                
                print("\n📤 发送请求...")
                async with session.post(
                    f"{API_BASE_URL}/batch/grade-sync",
                    data=form_data
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        print("✅ 批改完成！")
                        print(f"\n📊 批改结果:")
                        print(f"   总学生数: {result['total_students']}")
                        
                        for student in result["students"]:
                            print(f"\n   【{student['name']}】")
                            print(f"      页面范围: 第 {student['page_range']['start']} - {student['page_range']['end']} 页")
                            print(f"      总分: {student['total_score']} / {student['max_score']}")
                            print(f"      得分率: {student['percentage']}%")
                            print(f"      批改题数: {student['questions_graded']}")
                            
                            # 显示前 3 题的详情
                            print(f"      题目详情 (前 3 题):")
                            for detail in student["details"][:3]:
                                print(f"         第 {detail['question_id']} 题: {detail['score']}/{detail['max_score']} 分")
                                for point in detail["scoring_points"]:
                                    print(f"            - {point['point']}: {point['score']} 分")
                        
                        return result
                    else:
                        error = await response.text()
                        print(f"❌ 请求失败: {response.status}")
                        print(f"   错误: {error}")
                        return None
    
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        return None


async def test_async_grading():
    """测试异步批改 API"""
    print("\n" + "=" * 70)
    print("测试 2: 异步批改 API")
    print("=" * 70)
    
    rubric_path = Path("批改标准.pdf")
    answer_path = Path("学生作答.pdf")
    
    if not rubric_path.exists() or not answer_path.exists():
        print("❌ 缺少必要文件")
        return None
    
    try:
        async with aiohttp.ClientSession() as session:
            with open(rubric_path, "rb") as rubric_file, \
                 open(answer_path, "rb") as answer_file:
                
                form_data = aiohttp.FormData()
                form_data.add_field("exam_id", "exam_2025_test_001")
                form_data.add_field("rubric_file", rubric_file, filename="rubric.pdf")
                form_data.add_field("answer_file", answer_file, filename="answer.pdf")
                form_data.add_field("api_key", API_KEY)
                form_data.add_field("auto_identify", "true")
                
                print("\n📤 发送异步批改请求...")
                async with session.post(
                    f"{API_BASE_URL}/batch/submit",
                    data=form_data
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        batch_id = result["batch_id"]
                        print("✅ 批改任务已提交！")
                        print(f"\n📋 任务信息:")
                        print(f"   批次 ID: {batch_id}")
                        print(f"   状态: {result['status']}")
                        print(f"   总页数: {result['total_pages']}")
                        print(f"   预计完成时间: {result['estimated_completion_time']} 秒")
                        
                        return batch_id
                    else:
                        error = await response.text()
                        print(f"❌ 请求失败: {response.status}")
                        print(f"   错误: {error}")
                        return None
    
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        return None


async def test_status_query(batch_id: str):
    """测试状态查询 API"""
    print("\n" + "=" * 70)
    print("测试 3: 状态查询 API")
    print("=" * 70)
    
    try:
        async with aiohttp.ClientSession() as session:
            print(f"\n📤 查询批次 {batch_id} 的状态...")
            async with session.get(
                f"{API_BASE_URL}/batch/status/{batch_id}"
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    print("✅ 状态查询成功！")
                    print(f"\n📊 批次状态:")
                    print(f"   批次 ID: {result['batch_id']}")
                    print(f"   考试 ID: {result['exam_id']}")
                    print(f"   状态: {result['status']}")
                    print(f"   总学生数: {result['total_students']}")
                    print(f"   已完成: {result['completed_students']}")
                    print(f"   未识别页数: {result['unidentified_pages']}")
                else:
                    error = await response.text()
                    print(f"❌ 查询失败: {response.status}")
                    print(f"   错误: {error}")
    
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")


async def test_websocket(batch_id: str):
    """测试 WebSocket 实时推送"""
    print("\n" + "=" * 70)
    print("测试 4: WebSocket 实时推送")
    print("=" * 70)
    
    try:
        ws_url = f"{WS_BASE_URL}/batch/ws/{batch_id}"
        print(f"\n🔌 连接到 WebSocket: {ws_url}")
        
        async with websockets.connect(ws_url) as websocket:
            print("✅ WebSocket 连接成功！")
            print("\n📡 等待消息...")
            
            # 接收消息（最多 30 秒）
            try:
                while True:
                    message = await asyncio.wait_for(
                        websocket.recv(),
                        timeout=30
                    )
                    data = json.loads(message)
                    
                    if data["type"] == "progress":
                        print(f"   进度: {data['percentage']}% - {data.get('student_name', 'N/A')}")
                    elif data["type"] == "completed":
                        print(f"   ✅ 批改完成！")
                        break
                    elif data["type"] == "error":
                        print(f"   ❌ 错误: {data.get('error', 'Unknown error')}")
                        break
            
            except asyncio.TimeoutError:
                print("   ⏱️  等待超时（30 秒）")
    
    except Exception as e:
        print(f"❌ WebSocket 测试失败: {str(e)}")


async def main():
    """主测试函数"""
    print("\n" + "=" * 70)
    print("批量提交 API 测试套件")
    print("=" * 70)
    
    # 测试 1: 同步批改
    result = await test_sync_grading()
    
    # 测试 2: 异步批改
    batch_id = await test_async_grading()
    
    if batch_id:
        # 测试 3: 状态查询
        await test_status_query(batch_id)
        
        # 测试 4: WebSocket 实时推送
        await test_websocket(batch_id)
    
    print("\n" + "=" * 70)
    print("✅ 所有测试完成！")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
