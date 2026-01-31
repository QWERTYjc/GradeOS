-- 添加 rubric 字段到 grading_history 表
-- 用于存储评分标准（解析后的 JSON 格式）

ALTER TABLE grading_history 
ADD COLUMN IF NOT EXISTS rubric JSONB DEFAULT '{}';

-- 添加索引（用于搜索评分标准）
CREATE INDEX IF NOT EXISTS idx_grading_history_rubric ON grading_history USING GIN (rubric);

-- 添加注释
COMMENT ON COLUMN grading_history.rubric IS '评分标准（解析后的 JSON 格式，包含题目、分值、评分细则等）';

-- 验证修改
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'grading_history' 
  AND column_name = 'rubric';

COMMIT;
