"""重置日志文件为 UTF-8 编码"""
from datetime import datetime
import time

log_file = "batch_grading.log"

# 等待文件解锁
max_retries = 5
for i in range(max_retries):
    try:
        # 尝试以写入模式打开（会清空文件）
        with open(log_file, 'w', encoding='utf-8-sig') as f:  # utf-8-sig 会添加 BOM
            f.write(f"# GradeOS 批改日志 - 重置时间: {datetime.now().isoformat()}\n")
            f.write("# 编码: UTF-8 with BOM\n\n")
        print(f"✅ 成功重置日志文件为 UTF-8 编码（带 BOM）")
        break
    except PermissionError:
        if i < max_retries - 1:
            print(f"⏳ 文件被锁定，等待 1 秒后重试... ({i+1}/{max_retries})")
            time.sleep(1)
        else:
            print(f"❌ 无法访问日志文件，请手动关闭占用该文件的程序")
            print(f"   提示：可能是文本编辑器或日志查看器打开了该文件")
