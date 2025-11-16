"""
单张图片优化演示脚本
用于演示图片清晰化功能
"""
import os
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# 加载环境变量
from dotenv import load_dotenv
load_dotenv(project_root / '.env.local')

from functions.image_optimization import (
    ImageOptimizer,
    OptimizationSettings,
    QualityChecker
)
from functions.image_optimization.models import OptimizationMode

def optimize_single_image(image_path):
    """优化单张图片"""
    
    if not os.path.exists(image_path):
        print(f"❌ 图片不存在: {image_path}")
        return
    
    print("=" * 70)
    print("🎨 图片优化演示")
    print("=" * 70)
    print(f"\n📷 输入图片: {image_path}")
    
    # 1. 质量检测
    print("\n" + "=" * 70)
    print("📊 步骤1: 图片质量检测")
    print("=" * 70)
    
    checker = QualityChecker()
    
    try:
        report = checker.check_quality(image_path)
        
        print(f"\n质量评分: {report.total_score:.1f}/100")
        print(f"  ├─ 清晰度: {report.clarity_score:.1f}/40 (方差={report.variance:.0f})")
        print(f"  ├─ 倾斜度: {report.tilt_score:.1f}/20 (角度={report.tilt_angle:.1f}°)")
        print(f"  ├─ 背景: {report.background_score:.1f}/20")
        print(f"  └─ 尺寸: {report.size_score:.1f}/20 ({report.width}x{report.height})")
        print(f"\n💡 建议: {report.recommendation}")
        
    except Exception as e:
        print(f"❌ 质量检测失败: {e}")
        return
    
    # 2. 图片优化
    print("\n" + "=" * 70)
    print("✨ 步骤2: 智能优化处理")
    print("=" * 70)
    
    try:
        # 使用智能模式
        settings = OptimizationSettings.get_preset(OptimizationMode.SMART.value)
        optimizer = ImageOptimizer(settings=settings, output_dir="uploads/optimized")
        
        print("\n优化参数:")
        print(f"  ├─ 模式: 智能模式 (推荐)")
        print(f"  ├─ 切边: 开启")
        print(f"  ├─ 矫正: 开启")
        print(f"  ├─ 去模糊: 开启")
        print(f"  ├─ 增强+锐化: 开启")
        print(f"  └─ 方向校正: 开启")
        
        print("\n🔄 正在处理...")
        result = optimizer.optimize_image(image_path, force=True)
        
        if result.success:
            print("\n✅ 优化成功！")
            print(f"\n原图路径: {result.original_path}")
            print(f"优化图路径: {result.optimized_path}")
            
            if result.metadata:
                print(f"\n优化详情:")
                print(f"  ├─ 原始尺寸: {result.metadata.origin_width}x{result.metadata.origin_height}")
                print(f"  ├─ 优化尺寸: {result.metadata.cropped_width}x{result.metadata.cropped_height}")
                print(f"  ├─ 矫正角度: {result.metadata.angle}°")
                print(f"  └─ 处理时间: {result.metadata.duration:.0f}ms")
                
                if result.metadata.quality_scores:
                    scores = result.metadata.quality_scores
                    print(f"\n质量提升:")
                    print(f"  └─ {scores['before']:.1f} → {scores['after']:.1f} (+{scores['improvement']:.1f}分)")
            
            # 文件大小对比
            original_size = os.path.getsize(image_path) / 1024
            if result.optimized_path:
                optimized_size = os.path.getsize(result.optimized_path) / 1024
                print(f"\n文件大小:")
                print(f"  ├─ 原图: {original_size:.1f} KB")
                print(f"  └─ 优化后: {optimized_size:.1f} KB")
            
            print("\n" + "=" * 70)
            print("🎉 优化完成！")
            print("=" * 70)
            print(f"\n💾 优化后的图片已保存至: {result.optimized_path}")
            print(f"\n💡 提示: 运行以下命令查看可视化对比:")
            print(f"   streamlit run streamlit_view_results.py --server.port 8503")
            
        else:
            print(f"\n❌ 优化失败: {result.error_message}")
        
        optimizer.close()
        
    except Exception as e:
        print(f"\n❌ 优化过程出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # 图片路径
    image_path = r"D:\微信图片_20251116164359_54_7.jpg"
    
    # 检查API配置
    app_id = os.getenv('TEXTIN_APP_ID')
    secret_code = os.getenv('TEXTIN_SECRET_CODE')
    
    if not app_id or not secret_code:
        print("❌ 请先配置Textin API凭证")
        print("在 .env.local 文件中添加:")
        print("  TEXTIN_APP_ID=your_app_id")
        print("  TEXTIN_SECRET_CODE=your_secret_code")
    else:
        optimize_single_image(image_path)
