"""
测试 payload 中的 answer_images 是否正确
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

# 模拟一个简单的 payload
test_payload = {
    "batch_id": "test_001",
    "exam_id": "exam_001",
    "rubric_images": [b"fake_rubric_image_data"],
    "answer_images": [b"fake_answer_image_data_1", b"fake_answer_image_data_2"],
    "api_key": "test_key",
    "inputs": {
        "rubric": "test rubric",
        "auto_identify": True,
        "manual_boundaries": [],
        "expected_students": 1,
        "enable_review": False,
        "grading_mode": "auto",
    }
}

print("=" * 60)
print("Payload 结构检查")
print("=" * 60)

print(f"\n1. payload keys: {list(test_payload.keys())}")
print(f"2. answer_images type: {type(test_payload['answer_images'])}")
print(f"3. answer_images length: {len(test_payload['answer_images'])}")
print(f"4. answer_images[0] type: {type(test_payload['answer_images'][0])}")
print(f"5. answer_images[0] length: {len(test_payload['answer_images'][0])}")

# 检查是否为空
if not test_payload.get("answer_images"):
    print("\n❌ answer_images 为空或不存在!")
else:
    print(f"\n✓ answer_images 存在且有 {len(test_payload['answer_images'])} 个元素")

# 检查 intake_node 的逻辑
answer_images = test_payload.get("answer_images", [])
if not answer_images:
    print("\n❌ intake_node 会抛出 ValueError: 未提供答题图像")
else:
    print(f"\n✓ intake_node 检查通过，有 {len(answer_images)} 张图片")
