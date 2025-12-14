"""端到端批改功能测试"""
import os
import asyncio
import base64
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

from src.services.layout_analysis import LayoutAnalysisService
from src.services.gemini_reasoning import GeminiReasoningClient
from src.agents.grading_agent import GradingAgent
from src.models.state import GradingState

def create_test_image(text: str, width: int = 800, height: int = 600) -> bytes:
    """创建测试图像"""
    # 创建白色背景图像
    img = Image.new('RGB', (width, height), color='white')
    draw = ImageDraw.Draw(img)
    
    # 绘制文本
    try:
        # 尝试使用系统字体
        font = ImageFont.truetype("arial.ttf", 40)
    except:
        # 如果找不到字体，使用默认字体
        font = ImageFont.load_default()
    
    # 绘制题目标题
    draw.text((50, 50), "题目 1: 计算题", fill='black', font=font)
    
    # 绘制学生答案
    draw.text((50, 150), text, fill='blue', font=font)
    
    # 绘制一些数学公式样式的内容
    draw.text((50, 250), "解: 1 + 1 = 2", fill='black', font=font)
    draw.text((50, 350), "答: 2", fill='black', font=font)
    
    # 转换为字节
    buffer = BytesIO()
    img.save(buffer, format='JPEG')
    return buffer.getvalue()

async def test_layout_analysis():
    """测试布局分析功能"""
    print("\n" + "="*60)
    print("测试 1: 布局分析 (Gemini 2.5 Flash Lite)")
    print("="*60)
    
    api_key = os.getenv("GEMINI_API_KEY")
    service = LayoutAnalysisService(api_key=api_key)
    
    # 创建测试图像
    print("\n📝 创建测试试卷图像...")
    image_data = create_test_image("学生答案: 1 + 1 = 2")
    print(f"✅ 图像创建成功 ({len(image_data)} 字节)")
    
    try:
        print("\n🔍 调用 Gemini 2.5 Flash Lite 进行页面分割...")
        result = await service.segment_document(
            image_data=image_data,
            submission_id="test_submission_001",
            page_index=0
        )
        
        print(f"\n✅ 布局分析成功！")
        print(f"   - 提交 ID: {result.submission_id}")
        print(f"   - 总页数: {result.total_pages}")
        print(f"   - 识别题目数: {len(result.regions)}")
        
        for region in result.regions:
            print(f"\n   题目 {region.question_id}:")
            print(f"     - 页面索引: {region.page_index}")
            print(f"     - 边界框: ymin={region.bounding_box.ymin}, xmin={region.bounding_box.xmin}")
            print(f"               ymax={region.bounding_box.ymax}, xmax={region.bounding_box.xmax}")
        
        return result
        
    except Exception as e:
        print(f"\n❌ 布局分析失败: {str(e)}")
        return None

async def test_vision_extraction():
    """测试视觉提取功能"""
    print("\n" + "="*60)
    print("测试 2: 视觉提取 (Gemini 2.5 Pro)")
    print("="*60)
    
    api_key = os.getenv("GEMINI_API_KEY")
    client = GeminiReasoningClient(api_key=api_key)
    
    # 创建测试图像
    print("\n📝 创建学生答题图像...")
    image_data = create_test_image("学生答案: 1 + 1 = 2")
    image_b64 = base64.b64encode(image_data).decode('utf-8')
    print(f"✅ 图像创建成功")
    
    rubric = """
评分细则：
1. 正确写出算式 (2分)
2. 计算结果正确 (3分)
总分: 5分
"""
    
    try:
        print("\n🔍 调用 Gemini 2.5 Pro 进行视觉提取...")
        vision_analysis = await client.vision_extraction(
            question_image_b64=image_b64,
            rubric=rubric,
            standard_answer="1 + 1 = 2"
        )
        
        print(f"\n✅ 视觉提取成功！")
        print(f"\n视觉分析结果:")
        print("-" * 60)
        print(vision_analysis[:500] + "..." if len(vision_analysis) > 500 else vision_analysis)
        print("-" * 60)
        
        return vision_analysis
        
    except Exception as e:
        print(f"\n❌ 视觉提取失败: {str(e)}")
        return None

async def test_rubric_mapping(vision_analysis: str):
    """测试评分映射功能"""
    print("\n" + "="*60)
    print("测试 3: 评分映射 (Gemini 2.5 Pro)")
    print("="*60)
    
    api_key = os.getenv("GEMINI_API_KEY")
    client = GeminiReasoningClient(api_key=api_key)
    
    rubric = """
评分细则：
1. 正确写出算式 (2分)
2. 计算结果正确 (3分)
总分: 5分
"""
    
    try:
        print("\n🔍 调用 Gemini 2.5 Pro 进行评分映射...")
        result = await client.rubric_mapping(
            vision_analysis=vision_analysis,
            rubric=rubric,
            max_score=5.0,
            standard_answer="1 + 1 = 2"
        )
        
        print(f"\n✅ 评分映射成功！")
        print(f"\n评分结果:")
        print("-" * 60)
        print(f"初始得分: {result.get('initial_score')}/5.0")
        print(f"\n评分点映射:")
        for item in result.get('rubric_mapping', []):
            print(f"  - {item.get('rubric_point')}")
            print(f"    证据: {item.get('evidence')}")
            print(f"    得分: {item.get('score_awarded')}/{item.get('max_score')}")
        print(f"\n评分理由: {result.get('reasoning', 'N/A')[:200]}...")
        print("-" * 60)
        
        return result
        
    except Exception as e:
        print(f"\n❌ 评分映射失败: {str(e)}")
        return None

async def test_critique(vision_analysis: str, rubric_mapping: dict):
    """测试自我反思功能"""
    print("\n" + "="*60)
    print("测试 4: 自我反思 (Gemini 2.5 Pro)")
    print("="*60)
    
    api_key = os.getenv("GEMINI_API_KEY")
    client = GeminiReasoningClient(api_key=api_key)
    
    rubric = """
评分细则：
1. 正确写出算式 (2分)
2. 计算结果正确 (3分)
总分: 5分
"""
    
    try:
        print("\n🔍 调用 Gemini 2.5 Pro 进行自我反思...")
        result = await client.critique(
            vision_analysis=vision_analysis,
            rubric=rubric,
            rubric_mapping=rubric_mapping.get('rubric_mapping', []),
            initial_score=rubric_mapping.get('initial_score', 0),
            max_score=5.0,
            standard_answer="1 + 1 = 2"
        )
        
        print(f"\n✅ 自我反思成功！")
        print(f"\n反思结果:")
        print("-" * 60)
        print(f"需要修正: {result.get('needs_revision')}")
        print(f"置信度: {result.get('confidence')}")
        if result.get('critique_feedback'):
            print(f"反馈: {result.get('critique_feedback')[:200]}...")
        else:
            print(f"反馈: 无需修正")
        print("-" * 60)
        
        return result
        
    except Exception as e:
        print(f"\n❌ 自我反思失败: {str(e)}")
        return None

async def test_full_grading_agent():
    """测试完整的批改智能体"""
    print("\n" + "="*60)
    print("测试 5: 完整批改智能体 (LangGraph + Gemini)")
    print("="*60)
    
    api_key = os.getenv("GEMINI_API_KEY")
    
    # 创建测试图像
    print("\n📝 创建学生答题图像...")
    image_data = create_test_image("学生答案: 1 + 1 = 2")
    image_b64 = base64.b64encode(image_data).decode('utf-8')
    print(f"✅ 图像创建成功")
    
    # 创建批改智能体
    print("\n🤖 初始化批改智能体...")
    reasoning_client = GeminiReasoningClient(api_key=api_key)
    agent = GradingAgent(reasoning_client=reasoning_client)
    print(f"✅ 智能体初始化成功")
    
    # 准备输入参数
    rubric = """
评分细则：
1. 正确写出算式 (2分)
2. 计算结果正确 (3分)
总分: 5分
"""
    standard_answer = "1 + 1 = 2"
    max_score = 5.0
    
    try:
        print("\n🚀 开始批改流程...")
        print("   步骤: 视觉提取 → 评分映射 → 自我反思 → 最终化")
        
        # 运行智能体
        final_state = await agent.run(
            question_image=image_b64,
            rubric=rubric,
            max_score=max_score,
            standard_answer=standard_answer
        )
        
        print(f"\n✅ 批改完成！")
        print(f"\n批改结果:")
        print("=" * 60)
        print(f"最终得分: {final_state['final_score']}/{final_state['max_score']}")
        print(f"置信度: {final_state['confidence']:.2f}")
        print(f"修正次数: {final_state['revision_count']}")
        print(f"\n学生反馈:")
        print("-" * 60)
        print(final_state['student_feedback'][:500] + "..." if len(final_state['student_feedback']) > 500 else final_state['student_feedback'])
        print("-" * 60)
        
        print(f"\n推理轨迹 ({len(final_state['reasoning_trace'])} 步):")
        for i, trace in enumerate(final_state['reasoning_trace'], 1):
            print(f"  {i}. {trace[:100]}...")
        
        return final_state
        
    except Exception as e:
        print(f"\n❌ 批改失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

async def main():
    """主测试函数"""
    print("\n" + "🎯" * 30)
    print("AI 批改系统 - 端到端功能测试")
    print("🎯" * 30)
    
    # 检查 API Key
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("\n❌ 错误: 未找到 GEMINI_API_KEY 环境变量")
        print("请确保 .env 文件存在并包含有效的 API Key")
        return
    
    print(f"\n✅ API Key 已加载: {api_key[:20]}...")
    
    # 测试 1: 布局分析
    layout_result = await test_layout_analysis()
    
    # 测试 2: 视觉提取
    vision_analysis = await test_vision_extraction()
    
    # 初始化变量
    rubric_mapping = None
    critique_result = None
    
    if vision_analysis:
        # 测试 3: 评分映射
        rubric_mapping = await test_rubric_mapping(vision_analysis)
        
        if rubric_mapping:
            # 测试 4: 自我反思
            critique_result = await test_critique(vision_analysis, rubric_mapping)
    
    # 测试 5: 完整批改智能体
    final_result = await test_full_grading_agent()
    
    # 总结
    print("\n" + "="*60)
    print("测试总结")
    print("="*60)
    print(f"✅ 布局分析: {'通过' if layout_result else '失败'}")
    print(f"✅ 视觉提取: {'通过' if vision_analysis else '失败'}")
    print(f"✅ 评分映射: {'通过' if rubric_mapping else '失败'}")
    print(f"✅ 自我反思: {'通过' if critique_result else '失败'}")
    print(f"✅ 完整批改: {'通过' if final_result else '失败'}")
    
    if final_result:
        print(f"\n🎉 所有测试通过！批改系统运行正常！")
        print(f"\n最终批改结果:")
        print(f"  - 得分: {final_result['final_score']}/{final_result['max_score']}")
        print(f"  - 置信度: {final_result['confidence']:.2%}")
        print(f"  - 修正次数: {final_result['revision_count']}")
    else:
        print(f"\n⚠️ 部分测试失败，请检查错误信息")

if __name__ == "__main__":
    asyncio.run(main())
