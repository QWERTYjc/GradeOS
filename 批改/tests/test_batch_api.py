"""测试批改 API 的脚本"""
import asyncio
import httpx
import json
from pathlib import Path

async def test_batch_submit():
    """测试批量提交 API"""
    
    # 检查测试文件是否存在
    rubric_file = Path("批改标准.pdf")
    answer_file = Path("学生作答.pdf")
    
    if not rubric_file.exists():
        print(f"❌ 找不到文件: {rubric_file}")
        return
    
    if not answer_file.exists():
        print(f"❌ 找不到文件: {answer_file}")
        return
    
    print(f"✅ 找到测试文件:")
    print(f"   - 批改标准: {rubric_file} ({rubric_file.stat().st_size / 1024:.1f} KB)")
    print(f"   - 学生作答: {answer_file} ({answer_file.stat().st_size / 1024:.1f} KB)")
    
    # 准备文件
    files = {
        "rubrics": ("批改标准.pdf", open(rubric_file, "rb"), "application/pdf"),
        "files": ("学生作答.pdf", open(answer_file, "rb"), "application/pdf"),
    }
    
    data = {
        "exam_id": "test_exam_001",
        "auto_identify": "true"
    }
    
    print("\n📤 发送批改请求到后端...")
    
    async with httpx.AsyncClient(timeout=300.0) as client:
        try:
            response = await client.post(
                "http://127.0.0.1:8001/batch/submit",
                files=files,
                data=data
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"\n✅ 批改任务已提交:")
                print(f"   - batch_id: {result.get('batch_id')}")
                print(f"   - status: {result.get('status')}")
                print(f"   - total_pages: {result.get('total_pages')}")
                print(f"   - estimated_completion_time: {result.get('estimated_completion_time')}s")
                
                batch_id = result.get('batch_id')
                
                # 等待一段时间让批改完成
                print(f"\n⏳ 等待批改完成...")
                await asyncio.sleep(10)
                
                # 查询结果
                print(f"\n📊 查询批改结果...")
                result_response = await client.get(
                    f"http://127.0.0.1:8001/batch/results/{batch_id}"
                )
                
                if result_response.status_code == 200:
                    results = result_response.json()
                    print(f"\n✅ 批改结果:")
                    print(json.dumps(results, indent=2, ensure_ascii=False))
                else:
                    print(f"\n❌ 查询结果失败: {result_response.status_code}")
                    print(result_response.text)
            else:
                print(f"\n❌ 提交失败: {response.status_code}")
                print(response.text)
                
        except Exception as e:
            print(f"\n❌ 请求失败: {e}")
        finally:
            # 关闭文件
            for _, file_tuple in files.items():
                if hasattr(file_tuple[1], 'close'):
                    file_tuple[1].close()

if __name__ == "__main__":
    asyncio.run(test_batch_submit())
