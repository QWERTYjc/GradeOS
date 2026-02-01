@echo off
REM Windows 批处理脚本：执行数据库迁移

echo 开始数据库迁移：添加批改页面图像表...
echo.

REM 检查 psql 是否可用
where psql >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo 错误: 未找到 psql 命令
    echo 请确保 PostgreSQL 已安装并添加到 PATH
    pause
    exit /b 1
)

REM 设置数据库连接信息（根据实际情况修改）
set PGHOST=localhost
set PGPORT=5432
set PGDATABASE=ai_grading
set PGUSER=postgres

echo 连接到数据库: %PGDATABASE%@%PGHOST%:%PGPORT%
echo.

REM 执行 SQL 文件
psql -f "%~dp0create_image_table.sql"

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ✓ 数据库迁移成功！
    echo   - 已创建 grading_page_images 表
    echo   - 已创建相关索引
) else (
    echo.
    echo ✗ 数据库迁移失败
)

echo.
pause
