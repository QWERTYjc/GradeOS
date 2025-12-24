"""监控批量批改进度"""
import requests
import time
import json

batch_id = "160b764e-5247-4569-a706-ffb5c53137e3"

print(f"监控批次: {batch_id}")
print("=" * 80)

last_status = None
iteration = 0

while True:
    iteration += 1
    try:
        response = requests.get(
            f'http://localhost:8001/batch/status/{batch_id}',
            timeout=10
        )
        
        if response.status_code == 200:
            status = response.json()
            
            # 只在状态变化时打印完整信息
            current_status_str = json.dumps(status, ensure_ascii=False, indent=2)
            if current_status_str != last_status:
                print(f"\n[迭代 {iteration}] {time.strftime('%H:%M:%S')}")
                print(current_status_str)
                last_status = current_status_str
            else:
                # 状态未变化，只打印简短信息
                print(f"[迭代 {iteration}] {time.strftime('%H:%M:%S')} - 状态: {status.get('status')} (无变化)", end='\r')
            
            # 检查是否完成
            if status.get('status') in ['COMPLETED', 'FAILED', 'CANCELLED']:
                print(f"\n\n批改流程已结束，最终状态: {status.get('status')}")
                
                # 打印最终结果摘要
                if status.get('results'):
                    results = status['results']
                    print("\n" + "=" * 80)
                    print("最终结果摘要:")
                    print("=" * 80)
                    
                    # 评分细则信息
                    if 'rubric_info' in results:
                        rubric = results['rubric_info']
                        print(f"\n评分细则:")
                        print(f"  题目数: {rubric.get('total_questions', 'N/A')}")
                        print(f"  总分: {rubric.get('total_points', 'N/A')}")
                    
                    # 学生识别信息
                    if 'students' in results:
                        students = results['students']
                        print(f"\n学生识别:")
                        print(f"  识别到的学生数: {len(students)}")
                        for i, student in enumerate(students[:5], 1):  # 只显示前5个
                            print(f"  学生 {i}: {student.get('student_id', 'Unknown')} - "
                                  f"页数: {len(student.get('pages', []))}, "
                                  f"总分: {student.get('total_score', 0)}/{student.get('max_score', 0)}")
                        if len(students) > 5:
                            print(f"  ... 还有 {len(students) - 5} 个学生")
                    
                    # 未识别页面
                    if 'unidentified_pages' in results:
                        unidentified = results['unidentified_pages']
                        if unidentified:
                            print(f"\n未识别页面: {len(unidentified)} 页")
                
                break
        else:
            print(f"\n错误: HTTP {response.status_code}")
            print(response.text)
            break
            
    except requests.exceptions.RequestException as e:
        print(f"\n请求异常: {e}")
        break
    except KeyboardInterrupt:
        print("\n\n用户中断监控")
        break
    
    # 等待 2 秒后再次查询
    time.sleep(2)

print("\n监控结束")
