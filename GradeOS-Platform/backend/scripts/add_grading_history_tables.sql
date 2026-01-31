-- 添加批改历史和图片存储表
-- 用于存储批改历史记录和页面图片

-- ============ 批改历史表 ============

CREATE TABLE IF NOT EXISTS grading_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id VARCHAR(100) UNIQUE NOT NULL,
    class_ids JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'completed', 'imported', 'revoked', 'failed')),
    total_students INTEGER DEFAULT 0,
    average_score DECIMAL(10,2),
    result_data JSONB DEFAULT '{}'
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_grading_history_batch_id ON grading_history(batch_id);
CREATE INDEX IF NOT EXISTS idx_grading_history_created_at ON grading_history(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_grading_history_status ON grading_history(status);
CREATE INDEX IF NOT EXISTS idx_grading_history_class_ids ON grading_history USING GIN (class_ids);

-- 注释
COMMENT ON TABLE grading_history IS '批改历史记录表';
COMMENT ON COLUMN grading_history.batch_id IS '批次 ID（唯一标识）';
COMMENT ON COLUMN grading_history.class_ids IS '关联的班级 ID 列表（JSON 数组）';
COMMENT ON COLUMN grading_history.result_data IS '批改结果数据（JSON 格式）';

-- ============ 学生批改结果表 ============

CREATE TABLE IF NOT EXISTS student_grading_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    grading_history_id UUID NOT NULL REFERENCES grading_history(id) ON DELETE CASCADE,
    student_key VARCHAR(200) NOT NULL,
    class_id VARCHAR(100),
    student_id VARCHAR(50),
    score DECIMAL(10,2),
    max_score DECIMAL(10,2),
    summary TEXT,
    self_report TEXT,
    result_data JSONB DEFAULT '{}',
    imported_at TIMESTAMP,
    revoked_at TIMESTAMP,
    UNIQUE(grading_history_id, student_key)
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_student_results_history ON student_grading_results(grading_history_id);
CREATE INDEX IF NOT EXISTS idx_student_results_student_key ON student_grading_results(student_key);
CREATE INDEX IF NOT EXISTS idx_student_results_class_id ON student_grading_results(class_id);
CREATE INDEX IF NOT EXISTS idx_student_results_student_id ON student_grading_results(student_id);

-- 注释
COMMENT ON TABLE student_grading_results IS '学生批改结果表';
COMMENT ON COLUMN student_grading_results.student_key IS '学生标识（姓名或学号）';
COMMENT ON COLUMN student_grading_results.result_data IS '详细批改结果（JSON 格式）';
COMMENT ON COLUMN student_grading_results.self_report IS '自我审查报告';

-- ============ 批改页面图片表 ============

CREATE TABLE IF NOT EXISTS grading_page_images (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    grading_history_id UUID NOT NULL REFERENCES grading_history(id) ON DELETE CASCADE,
    student_key VARCHAR(200) NOT NULL,
    page_index INTEGER NOT NULL,
    image_data BYTEA NOT NULL,
    image_format VARCHAR(10) DEFAULT 'png',
    created_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT unique_page_image UNIQUE (grading_history_id, student_key, page_index)
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_page_images_history ON grading_page_images(grading_history_id);
CREATE INDEX IF NOT EXISTS idx_page_images_student ON grading_page_images(grading_history_id, student_key);
CREATE INDEX IF NOT EXISTS idx_page_images_created_at ON grading_page_images(created_at DESC);

-- 注释
COMMENT ON TABLE grading_page_images IS '批改页面图片存储表';
COMMENT ON COLUMN grading_page_images.image_data IS '图片二进制数据（PNG/JPG 格式）';
COMMENT ON COLUMN grading_page_images.page_index IS '页码（从 0 开始）';
COMMENT ON COLUMN grading_page_images.image_format IS '图片格式（png, jpg, webp）';

-- ============ 统计信息 ============

-- 查看表大小
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE tablename IN ('grading_history', 'student_grading_results', 'grading_page_images')
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

COMMIT;
