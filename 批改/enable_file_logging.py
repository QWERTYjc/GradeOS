"""启用文件日志"""
import logging

# 配置文件日志
file_handler = logging.FileHandler('batch_grading.log', mode='w', encoding='utf-8')
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
))

# 添加到根日志器
root_logger = logging.getLogger()
root_logger.addHandler(file_handler)
root_logger.setLevel(logging.INFO)

print("文件日志已启用: batch_grading.log")
