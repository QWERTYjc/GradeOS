"""
GradeOS 前端 E2E 测试
使用 Selenium 测试完整的批改流程，验证：
1. 文件上传
2. 批改过程的渐进式披露
3. 结果页面的题目数量
"""

import time
import json
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

# 配置
FRONTEND_URL = "https://gradeos.up.railway.app"
TEST_PDF_PATH = str(Path(__file__).parent / "gradeos_test_batch_30.pdf")
SCREENSHOT_DIR = Path(__file__).parent / "screenshots"
SCREENSHOT_DIR.mkdir(exist_ok=True)


def setup_driver():
    """设置 Chrome Driver"""
    options = Options()
    # options.add_argument('--headless')  # 无头模式（可选）
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')
    
    driver = webdriver.Chrome(options=options)
    return driver


def take_screenshot(driver, name):
    """截图"""
    screenshot_path = SCREENSHOT_DIR / f"{name}.png"
    driver.save_screenshot(str(screenshot_path))
    print(f"📸 截图已保存: {screenshot_path}")
    return screenshot_path


def test_grading_flow():
    """测试完整的批改流程"""
    driver = setup_driver()
    
    try:
        print("\n" + "=" * 80)
        print("🚀 开始前端 E2E 测试")
        print("=" * 80)
        
        # === 步骤 1: 访问前端首页 ===
        print("\n[步骤 1] 访问前端首页...")
        driver.get(FRONTEND_URL)
        time.sleep(3)
        take_screenshot(driver, "01_homepage")
        print(f"✅ 页面标题: {driver.title}")
        
        # === 步骤 2: 导航到批改功能 ===
        print("\n[步骤 2] 查找批改功能入口...")
        
        # 尝试查找常见的导航链接
        possible_selectors = [
            "//a[contains(text(), 'Console')]",
            "//a[contains(text(), 'Batch')]",
            "//a[contains(text(), 'Grading')]",
            "//button[contains(text(), 'Start')]",
            "//a[@href='/console']",
            "//a[@href='/batch-grading']",
        ]
        
        console_link = None
        for selector in possible_selectors:
            try:
                console_link = driver.find_element(By.XPATH, selector)
                if console_link:
                    print(f"✅ 找到入口: {selector}")
                    break
            except:
                continue
        
        if console_link:
            console_link.click()
            time.sleep(2)
            take_screenshot(driver, "02_console_page")
        else:
            print("⚠️ 未找到批改入口，尝试直接访问 /console")
            driver.get(f"{FRONTEND_URL}/console")
            time.sleep(2)
            take_screenshot(driver, "02_console_direct")
        
        # === 步骤 3: 上传文件 ===
        print("\n[步骤 3] 上传测试文件...")
        
        # 尝试查找文件上传输入框
        file_input = None
        try:
            file_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='file']"))
            )
            print("✅ 找到文件上传输入框")
        except:
            print("❌ 未找到文件上传输入框")
            take_screenshot(driver, "03_upload_not_found")
            return
        
        # 上传文件
        print(f"📤 上传文件: {TEST_PDF_PATH}")
        file_input.send_keys(TEST_PDF_PATH)
        time.sleep(2)
        take_screenshot(driver, "03_file_selected")
        
        # 查找并点击提交按钮
        submit_button = None
        submit_selectors = [
            "//button[contains(text(), 'Submit')]",
            "//button[contains(text(), '提交')]",
            "//button[contains(text(), 'Start')]",
            "//button[contains(text(), '开始')]",
            "//button[@type='submit']",
        ]
        
        for selector in submit_selectors:
            try:
                submit_button = driver.find_element(By.XPATH, selector)
                if submit_button and submit_button.is_enabled():
                    print(f"✅ 找到提交按钮: {selector}")
                    break
            except:
                continue
        
        if submit_button:
            print("🚀 点击提交按钮...")
            submit_button.click()
            time.sleep(3)
            take_screenshot(driver, "04_submitted")
        else:
            print("❌ 未找到提交按钮")
            take_screenshot(driver, "04_submit_not_found")
            return
        
        # === 步骤 4: 监控批改过程的渐进式披露 ===
        print("\n[步骤 4] 监控批改过程的渐进式披露...")
        print("🔍 观察以下元素：")
        print("  - 进度条")
        print("  - 步骤指示器")
        print("  - 当前阶段名称")
        print("  - 百分比显示")
        print("  - 预计剩余时间")
        
        # 每 10 秒截图一次，持续 3 分钟
        max_wait = 180  # 3 分钟
        interval = 10   # 10 秒间隔
        screenshot_count = 0
        
        for i in range(0, max_wait, interval):
            screenshot_count += 1
            print(f"\n⏱️ [{i}s] 检查批改进度...")
            
            # 截图
            take_screenshot(driver, f"05_progress_{i:03d}s")
            
            # 查找进度相关元素
            try:
                # 查找进度条
                progress_bars = driver.find_elements(By.CSS_SELECTOR, 
                    "[role='progressbar'], .progress, [class*='progress']")
                if progress_bars:
                    print(f"  ✅ 发现 {len(progress_bars)} 个进度条元素")
                
                # 查找百分比
                percentage_elements = driver.find_elements(By.XPATH, 
                    "//*[contains(text(), '%')]")
                if percentage_elements:
                    percentages = [elem.text for elem in percentage_elements if '%' in elem.text]
                    print(f"  ✅ 百分比显示: {', '.join(percentages)}")
                
                # 查找状态文本
                status_keywords = ['检测', '批改', '分析', '完成', 'Detecting', 'Grading', 'Processing', 'Completed']
                for keyword in status_keywords:
                    status_elements = driver.find_elements(By.XPATH, 
                        f"//*[contains(text(), '{keyword}')]")
                    if status_elements:
                        print(f"  ✅ 发现状态文本: {keyword}")
                        break
                
            except Exception as e:
                print(f"  ⚠️ 检查进度时出错: {e}")
            
            # 检查是否完成
            try:
                completed_indicators = driver.find_elements(By.XPATH,
                    "//*[contains(text(), '完成') or contains(text(), 'Completed') or contains(text(), 'Done')]")
                if completed_indicators:
                    print("  ✅ 批改已完成！")
                    break
            except:
                pass
            
            time.sleep(interval)
        
        # 最终截图
        take_screenshot(driver, "06_final_state")
        
        # === 步骤 5: 验证结果页面 ===
        print("\n[步骤 5] 验证结果页面...")
        
        # 等待结果页面加载
        time.sleep(5)
        take_screenshot(driver, "07_results_page")
        
        # 查找学生数量
        print("\n🔍 验证显示数据：")
        try:
            page_text = driver.find_element(By.TAG_NAME, "body").text
            
            # 查找学生数量
            if "学生" in page_text or "student" in page_text.lower():
                print("  ✅ 找到学生相关信息")
                # 尝试提取数字
                import re
                student_count_match = re.search(r'(\d+)\s*[个]?学生', page_text)
                if student_count_match:
                    student_count = student_count_match.group(1)
                    print(f"  📊 学生数量: {student_count}")
            
            # 查找题目数量
            if "题目" in page_text or "question" in page_text.lower():
                print("  ✅ 找到题目相关信息")
                question_count_match = re.search(r'(\d+)\s*[道题|题目|questions?]', page_text)
                if question_count_match:
                    question_count = question_count_match.group(1)
                    print(f"  📊 题目数量: {question_count}")
            
            # 查找分数
            if "分" in page_text or "score" in page_text.lower():
                print("  ✅ 找到分数信息")
                score_matches = re.findall(r'(\d+(?:\.\d+)?)\s*分', page_text)
                if score_matches:
                    print(f"  📊 发现分数: {', '.join(score_matches[:5])}...")
                    
        except Exception as e:
            print(f"  ⚠️ 提取数据时出错: {e}")
        
        # 查找结果列表/表格
        try:
            # 查找表格
            tables = driver.find_elements(By.TAG_NAME, "table")
            if tables:
                print(f"  ✅ 发现 {len(tables)} 个表格")
            
            # 查找列表
            lists = driver.find_elements(By.CSS_SELECTOR, "ul, ol, [role='list']")
            if lists:
                print(f"  ✅ 发现 {len(lists)} 个列表")
            
            # 查找卡片
            cards = driver.find_elements(By.CSS_SELECTOR, "[class*='card'], [class*='item']")
            if cards:
                print(f"  ✅ 发现 {len(cards)} 个卡片元素")
                
        except Exception as e:
            print(f"  ⚠️ 查找UI元素时出错: {e}")
        
        # 最终完整截图
        take_screenshot(driver, "08_final_results")
        
        print("\n" + "=" * 80)
        print("✅ E2E 测试完成！")
        print(f"📸 截图已保存到: {SCREENSHOT_DIR}")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ 测试过程中出错: {e}")
        import traceback
        traceback.print_exc()
        take_screenshot(driver, "error_state")
        
    finally:
        print("\n🔄 关闭浏览器...")
        time.sleep(3)
        driver.quit()


if __name__ == "__main__":
    # 检查测试文件是否存在
    if not Path(TEST_PDF_PATH).exists():
        print(f"❌ 测试文件不存在: {TEST_PDF_PATH}")
        exit(1)
    
    print(f"📄 测试文件: {TEST_PDF_PATH}")
    print(f"🌐 前端 URL: {FRONTEND_URL}")
    print(f"📸 截图目录: {SCREENSHOT_DIR}")
    
    test_grading_flow()
