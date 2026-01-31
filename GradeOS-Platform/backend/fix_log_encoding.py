"""修复日志文件编码问题"""
import os
import shutil
from datetime import datetime

# 日志文件路径
log_file = "batch_grading.log"

if os.path.exists(log_file):
    # 备份旧日志文件
    backup_file = f"batch_grading.log.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(log_file, backup_file)
    print(f"✅ 已备份旧日志文件到: {backup_file}")
    
    # 删除旧日志文件
    os.remove(log_file)
    print(f"✅ 已删除旧日志文件: {log_file}")

# 创建新的 UTF-8 编码的日志文件
with open(log_file, 'w', encoding='utf-8') as f:
    f.write(f"# GradeOS 批改日志 - 创建时间: {datetime.now().isoformat()}\n")
    f.write("# 编码: UTF-8\n\n")

print(f"✅ 已创建新的 UTF-8 编码日志文件: {log_file}")
print("\n现在可以重启后端服务了！")
