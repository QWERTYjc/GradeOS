# 数据库迁移指南

## 添加批改页面图像表

本迁移会创建 `grading_page_images` 表，用于存储批改过程中的页面图像。

### 方法 1: 使用 Python 脚本（推荐）

1. 确保已设置数据库环境变量：

```bash
# Windows PowerShell
$env:DATABASE_URL="postgresql://postgres:postgres@localhost:5432/ai_grading"

# Windows CMD
set DATABASE_URL=postgresql://postgres:postgres@localhost:5432/ai_grading

# Linux/Mac
export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/ai_grading"
```

2. 运行迁移脚本：

```bash
cd GradeOS-Platform/backend
python scripts/migrate_add_images.py
```

### 方法 2: 使用批处理脚本（Windows）

1. 编辑 `scripts/migrate_images.bat`，修改数据库连接信息：
   - PGHOST（主机地址）
   - PGPORT（端口）
   - PGDATABASE（数据库名）
   - PGUSER（用户名）

2. 双击运行 `migrate_images.bat`

3. 输入数据库密码

### 方法 3: 直接使用 psql

```bash
# 连接到数据库
psql -h localhost -p 5432 -U postgres -d ai_grading

# 执行 SQL 文件
\i scripts/create_image_table.sql

# 或者一行命令
psql -h localhost -p 5432 -U postgres -d ai_grading -f scripts/create_image_table.sql
```

### 验证迁移

连接到数据库并检查表是否创建成功：

```sql
-- 查看表结构
\d grading_page_images

-- 查看索引
\di grading_page_images*

-- 查看外键约束
SELECT conname, conrelid::regclass, confrelid::regclass
FROM pg_constraint
WHERE conname LIKE '%grading_page_images%';
```

### 回滚迁移

如果需要删除表：

```sql
DROP TABLE IF EXISTS grading_page_images CASCADE;
```

## 常见问题

### Q: 提示"数据库不可用（降级模式）"

**A:** 检查以下几点：
1. 数据库服务是否运行
2. DATABASE_URL 是否正确设置
3. 数据库连接信息是否正确
4. 防火墙是否阻止连接

### Q: 提示"外键约束失败"

**A:** 确保 `grading_history` 表已存在。如果不存在，先运行主数据库初始化脚本：

```bash
psql -f scripts/init_database.sql
```

### Q: 表已存在

**A:** SQL 脚本使用了 `IF NOT EXISTS`，重复运行不会报错。如果需要重建表：

```sql
DROP TABLE IF EXISTS grading_page_images CASCADE;
```

然后重新运行迁移脚本。
