#!/bin/bash

# 数据库迁移脚本
# 用于创建批改历史和图片存储表

echo "=========================================="
echo "GradeOS 数据库迁移"
echo "创建批改历史和图片存储表"
echo "=========================================="
echo ""

# 检查环境变量
if [ -z "$DATABASE_URL" ]; then
    echo "❌ 错误: DATABASE_URL 环境变量未设置"
    echo ""
    echo "请设置 DATABASE_URL，例如："
    echo "export DATABASE_URL='postgresql://user:password@localhost:5432/gradeos'"
    echo ""
    exit 1
fi

echo "✅ 数据库连接: $DATABASE_URL"
echo ""

# 执行迁移
echo "📝 执行迁移脚本..."
psql "$DATABASE_URL" -f add_grading_history_tables.sql

if [ $? -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "✅ 迁移成功完成！"
    echo "=========================================="
    echo ""
    echo "已创建以下表："
    echo "  - grading_history (批改历史)"
    echo "  - student_grading_results (学生批改结果)"
    echo "  - grading_page_images (页面图片)"
    echo ""
else
    echo ""
    echo "=========================================="
    echo "❌ 迁移失败"
    echo "=========================================="
    echo ""
    exit 1
fi
