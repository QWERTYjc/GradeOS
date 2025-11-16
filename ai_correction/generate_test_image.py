"""生成测试图片"""
from PIL import Image, ImageDraw, ImageFont
import os

def create_test_image():
    """创建一张测试图片（模拟学生作业）"""
    # 创建白色背景图片
    width, height = 800, 600
    img = Image.new('RGB', (width, height), color='white')
    draw = ImageDraw.Draw(img)
    
    # 添加背景噪点（模拟拍照背景）
    for i in range(0, width, 50):
        for j in range(0, height, 50):
            draw.rectangle([i, j, i+40, j+40], fill=(245, 245, 245))
    
    # 添加主要内容区域（模拟作业纸）
    margin = 100
    draw.rectangle([margin, margin, width-margin, height-margin], 
                   fill='white', outline='black', width=3)
    
    # 添加文字内容
    try:
        font = ImageFont.truetype("arial.ttf", 24)
    except:
        font = ImageFont.load_default()
    
    text_content = [
        "数学作业",
        "",
        "1. 计算题：",
        "   (1) 3 + 5 = 8",
        "   (2) 12 - 7 = 5",
        "",
        "2. 应用题：",
        "   小明有10个苹果...",
        "   答：还剩6个苹果"
    ]
    
    y_position = margin + 30
    for line in text_content:
        draw.text((margin + 20, y_position), line, fill='black', font=font)
        y_position += 35
    
    # 添加倾斜效果（模拟拍照角度问题）
    img = img.rotate(5, expand=True, fillcolor='lightgray')
    
    # 保存图片
    output_path = "temp/uploads/test_homework.jpg"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    img.save(output_path, quality=75)
    print(f"✅ 测试图片已生成: {output_path}")
    return output_path

if __name__ == "__main__":
    create_test_image()
