-- 添加 rubric_data 和 current_stage 字段到 grading_history 表
-- 执行时间: 2024-02-01
-- 用途: 支持批改标准复核页面从数据库读取 rubric 数据

-- 添加 rubric_data 字段（存储 parsed_rubric）
ALTER TABLE grading_history 
ADD COLUMN IF NOT EXISTS rubric_data JSONB;

-- 添加 current_stage 字段（存储当前批改阶段）
ALTER TABLE grading_history 
ADD COLUMN IF NOT EXISTS current_stage VARCHAR(100);

-- 为 rubric_data 添加索引（可选，提升查询性能）
CREATE INDEX IF NOT EXISTS idx_grading_history_rubric_data 
ON grading_history USING GIN (rubric_data);

-- 为 current_stage 添加索引（可选）
CREATE INDEX IF NOT EXISTS idx_grading_history_current_stage 
ON grading_history (current_stage);

-- 验证字段是否添加成功
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'grading_history' 
  AND column_name IN ('rubric_data', 'current_stage');
