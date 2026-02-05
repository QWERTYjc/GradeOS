-- GradeOS 数据库初始化脚本
-- 基于 后端数据库需求文档_基于API整合.md

-- 启用扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "btree_gin";

-- ============ 用户认证模块 ============

CREATE TABLE IF NOT EXISTS users (
    user_id VARCHAR(50) PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    email VARCHAR(200) UNIQUE,
    phone VARCHAR(50),
    user_type VARCHAR(20) NOT NULL CHECK (user_type IN ('student', 'teacher', 'admin')),
    real_name VARCHAR(100),
    avatar_url VARCHAR(500),
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'suspended')),
    last_login_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_profiles (
    profile_id SERIAL PRIMARY KEY,
    user_id VARCHAR(50) REFERENCES users(user_id) ON DELETE CASCADE,
    grade VARCHAR(20),
    school VARCHAR(200),
    class_id VARCHAR(100),
    subject VARCHAR(50),
    preferences JSONB DEFAULT '{}',
    learning_style VARCHAR(50),
    language VARCHAR(10) DEFAULT 'zh-CN',
    theme VARCHAR(20) DEFAULT 'light',
    notifications BOOLEAN DEFAULT TRUE
);

-- ============ 班级管理模块 ============

CREATE TABLE IF NOT EXISTS classes (
    class_id VARCHAR(100) PRIMARY KEY,
    class_name VARCHAR(100) NOT NULL,
    teacher_id VARCHAR(50) REFERENCES users(user_id),
    grade_level VARCHAR(20),
    subject VARCHAR(50),
    semester VARCHAR(20),
    invite_code VARCHAR(20) UNIQUE NOT NULL,
    student_count INTEGER DEFAULT 0,
    max_students INTEGER DEFAULT 50,
    is_active BOOLEAN DEFAULT TRUE,
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS student_class_relations (
    id SERIAL PRIMARY KEY,
    student_id VARCHAR(50) REFERENCES users(user_id) ON DELETE CASCADE,
    class_id VARCHAR(100) REFERENCES classes(class_id) ON DELETE CASCADE,
    join_date TIMESTAMP DEFAULT NOW(),
    status VARCHAR(20) DEFAULT 'active',
    is_admin BOOLEAN DEFAULT FALSE,
    UNIQUE(student_id, class_id)
);

-- ============ 作业管理模块 ============

CREATE TABLE IF NOT EXISTS assignments (
    assignment_id VARCHAR(100) PRIMARY KEY,
    homework_id VARCHAR(100) UNIQUE,
    class_id VARCHAR(100) REFERENCES classes(class_id),
    teacher_id VARCHAR(50) REFERENCES users(user_id),
    title VARCHAR(200) NOT NULL,
    description TEXT,
    subject VARCHAR(50),
    total_questions INTEGER DEFAULT 0,
    max_score DECIMAL(10,2) DEFAULT 100,
    status VARCHAR(20) DEFAULT 'draft' CHECK (status IN ('draft', 'published', 'closed', 'archived')),
    publish_date TIMESTAMP,
    due_date TIMESTAMP,
    allow_late_submission BOOLEAN DEFAULT FALSE,
    max_attempts INTEGER DEFAULT 1,
    instructions TEXT,
    requirements TEXT,
    attachment_urls JSONB DEFAULT '[]',
    rubric_data JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);


CREATE TABLE IF NOT EXISTS assignment_submissions (
    submission_id VARCHAR(100) PRIMARY KEY,
    assignment_id VARCHAR(100) REFERENCES assignments(assignment_id),
    student_id VARCHAR(50) REFERENCES users(user_id),
    attempt_number INTEGER DEFAULT 1,
    answer_files JSONB DEFAULT '[]',
    submitted_at TIMESTAMP DEFAULT NOW(),
    grading_status VARCHAR(20) DEFAULT 'pending' CHECK (grading_status IN ('pending', 'processing', 'ai_graded', 'teacher_reviewed', 'completed', 'failed')),
    grading_mode VARCHAR(20) DEFAULT 'standard',
    total_score DECIMAL(10,2),
    max_score DECIMAL(10,2),
    percentage DECIMAL(5,2),
    grade_level VARCHAR(10),
    is_late BOOLEAN DEFAULT FALSE,
    teacher_comment TEXT,
    teacher_adjusted_score DECIMAL(10,2),
    is_reviewed BOOLEAN DEFAULT FALSE,
    reviewed_at TIMESTAMP,
    submit_time TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- ============ AI 批改模块 ============

CREATE TABLE IF NOT EXISTS grading_tasks (
    task_id VARCHAR(100) PRIMARY KEY,
    submission_id VARCHAR(100) REFERENCES assignment_submissions(submission_id),
    student_id VARCHAR(50) REFERENCES users(user_id),
    subject VARCHAR(50),
    total_questions INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'cancelled')),
    ai_model VARCHAR(100) DEFAULT 'google/gemini-3-flash-preview',
    processing_mode VARCHAR(20) DEFAULT 'standard',
    confidence_score DECIMAL(5,4),
    processing_time_ms INTEGER,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS grading_results (
    result_id SERIAL PRIMARY KEY,
    task_id VARCHAR(100) REFERENCES grading_tasks(task_id),
    question_id VARCHAR(100) NOT NULL,
    question_no INTEGER,
    score DECIMAL(10,2) NOT NULL,
    max_score DECIMAL(10,2) NOT NULL,
    is_correct BOOLEAN,
    feedback TEXT,
    strategy VARCHAR(50),
    confidence DECIMAL(5,4),
    error_type VARCHAR(50),
    suggestion TEXT,
    correct_answer TEXT,
    annotations JSONB DEFAULT '{}',
    coordinates JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============ 错题分析模块 ============

CREATE TABLE IF NOT EXISTS error_records (
    error_id VARCHAR(100) PRIMARY KEY,
    analysis_id VARCHAR(100) UNIQUE,
    student_id VARCHAR(50) REFERENCES users(user_id),
    question_id VARCHAR(100),
    subject VARCHAR(50),
    question_type VARCHAR(50),
    original_question JSONB DEFAULT '{}',
    student_answer TEXT,
    student_solution_steps JSONB DEFAULT '[]',
    correct_answer TEXT,
    error_type VARCHAR(50),
    error_severity VARCHAR(20) CHECK (error_severity IN ('high', 'medium', 'low')),
    root_cause TEXT,
    knowledge_points JSONB DEFAULT '[]',
    knowledge_gaps JSONB DEFAULT '[]',
    detailed_analysis JSONB DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS learning_recommendations (
    recommendation_id VARCHAR(100) PRIMARY KEY,
    student_id VARCHAR(50) REFERENCES users(user_id),
    analysis_id VARCHAR(100) REFERENCES error_records(analysis_id),
    recommendation_type VARCHAR(50),
    content TEXT,
    resources JSONB DEFAULT '[]',
    immediate_actions JSONB DEFAULT '[]',
    practice_exercises JSONB DEFAULT '[]',
    learning_strategies JSONB DEFAULT '[]',
    learning_path JSONB DEFAULT '{}',
    priority INTEGER DEFAULT 1,
    status VARCHAR(20) DEFAULT 'pending',
    feedback_rating INTEGER CHECK (feedback_rating BETWEEN 1 AND 5),
    feedback_comment TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP
);

-- ============ 知识图谱模块 ============

CREATE TABLE IF NOT EXISTS knowledge_points (
    concept_id VARCHAR(100) PRIMARY KEY,
    concept_name VARCHAR(200) NOT NULL,
    point_name VARCHAR(200) NOT NULL,
    subject VARCHAR(50),
    chapter VARCHAR(100),
    difficulty VARCHAR(20) CHECK (difficulty IN ('easy', 'medium', 'hard')),
    difficulty_level INTEGER CHECK (difficulty_level BETWEEN 1 AND 5),
    description TEXT,
    parent_point_id VARCHAR(100),
    prerequisites JSONB DEFAULT '[]',
    related_points JSONB DEFAULT '[]',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS student_knowledge_mastery (
    mastery_id SERIAL PRIMARY KEY,
    student_id VARCHAR(50) REFERENCES users(user_id),
    concept_id VARCHAR(100) REFERENCES knowledge_points(concept_id),
    mastery_level DECIMAL(5,4) DEFAULT 0.0,
    correct_count INTEGER DEFAULT 0,
    total_count INTEGER DEFAULT 0,
    last_assignment_id VARCHAR(100),
    last_score DECIMAL(10,2),
    last_evaluated_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(student_id, concept_id)
);

-- ============ 统计分析模块 ============

CREATE TABLE IF NOT EXISTS class_statistics (
    stat_id VARCHAR(100) PRIMARY KEY,
    class_id VARCHAR(100) REFERENCES classes(class_id),
    assignment_id VARCHAR(100) REFERENCES assignments(assignment_id),
    class_name VARCHAR(100),
    total_students INTEGER,
    submitted_count INTEGER,
    graded_count INTEGER,
    average_score DECIMAL(10,2),
    max_score DECIMAL(10,2),
    min_score DECIMAL(10,2),
    median_score DECIMAL(10,2),
    pass_rate DECIMAL(5,4),
    score_distribution JSONB DEFAULT '{}',
    common_errors JSONB DEFAULT '[]',
    error_distribution JSONB DEFAULT '[]',
    knowledge_mastery JSONB DEFAULT '{}',
    teaching_suggestions JSONB DEFAULT '[]',
    generated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS system_logs (
    log_id SERIAL PRIMARY KEY,
    user_id VARCHAR(50),
    action VARCHAR(100),
    resource_type VARCHAR(50),
    resource_id VARCHAR(100),
    ip_address INET,
    user_agent TEXT,
    request_data JSONB DEFAULT '{}',
    response_status INTEGER,
    processing_time_ms INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============ OpenBoard 论坛模块 ============

-- 论坛表
CREATE TABLE IF NOT EXISTS forums (
    forum_id VARCHAR(100) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    creator_id VARCHAR(50) REFERENCES users(user_id),
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'active', 'rejected')),
    rejection_reason TEXT,
    post_count INTEGER DEFAULT 0,
    last_activity_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 帖子表
CREATE TABLE IF NOT EXISTS forum_posts (
    post_id VARCHAR(100) PRIMARY KEY,
    forum_id VARCHAR(100) REFERENCES forums(forum_id) ON DELETE CASCADE,
    title VARCHAR(200) NOT NULL,
    content TEXT NOT NULL,
    images JSONB DEFAULT '[]',  -- 图片数组，存储 base64 或 URL
    author_id VARCHAR(50) REFERENCES users(user_id),
    reply_count INTEGER DEFAULT 0,
    is_deleted BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 回复表
CREATE TABLE IF NOT EXISTS forum_replies (
    reply_id VARCHAR(100) PRIMARY KEY,
    post_id VARCHAR(100) REFERENCES forum_posts(post_id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    author_id VARCHAR(50) REFERENCES users(user_id),
    is_deleted BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 管理日志表
CREATE TABLE IF NOT EXISTS forum_mod_logs (
    log_id VARCHAR(100) PRIMARY KEY,
    moderator_id VARCHAR(50) REFERENCES users(user_id),
    action VARCHAR(50) NOT NULL,
    target_type VARCHAR(20) NOT NULL,
    target_id VARCHAR(100) NOT NULL,
    reason TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 用户论坛状态表（封禁状态）
CREATE TABLE IF NOT EXISTS forum_user_status (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(50) REFERENCES users(user_id),
    is_banned BOOLEAN DEFAULT FALSE,
    banned_at TIMESTAMP,
    banned_by VARCHAR(50) REFERENCES users(user_id),
    ban_reason TEXT,
    UNIQUE(user_id)
);

-- ============ 索引 ============

CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_type_status ON users(user_type, status);
CREATE INDEX IF NOT EXISTS idx_classes_teacher_id ON classes(teacher_id);
CREATE INDEX IF NOT EXISTS idx_classes_invite_code ON classes(invite_code);
CREATE INDEX IF NOT EXISTS idx_assignments_class_id ON assignments(class_id);
CREATE INDEX IF NOT EXISTS idx_assignments_due_date ON assignments(due_date);
CREATE INDEX IF NOT EXISTS idx_submissions_assignment_student ON assignment_submissions(assignment_id, student_id);
CREATE INDEX IF NOT EXISTS idx_grading_tasks_status ON grading_tasks(status);
CREATE INDEX IF NOT EXISTS idx_error_records_student ON error_records(student_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_points_subject ON knowledge_points(subject);

-- OpenBoard 索引
CREATE INDEX IF NOT EXISTS idx_forums_status ON forums(status);
CREATE INDEX IF NOT EXISTS idx_forums_creator ON forums(creator_id);
CREATE INDEX IF NOT EXISTS idx_forum_posts_forum ON forum_posts(forum_id);
CREATE INDEX IF NOT EXISTS idx_forum_posts_author ON forum_posts(author_id);
CREATE INDEX IF NOT EXISTS idx_forum_replies_post ON forum_replies(post_id);
CREATE INDEX IF NOT EXISTS idx_forum_user_status_user ON forum_user_status(user_id);

-- 全文搜索索引
CREATE INDEX IF NOT EXISTS idx_forum_posts_title_gin ON forum_posts USING gin(to_tsvector('simple', title));
CREATE INDEX IF NOT EXISTS idx_forum_posts_content_gin ON forum_posts USING gin(to_tsvector('simple', content));

-- ============ 初始数据 ============

-- 插入演示用户
INSERT INTO users (user_id, username, password_hash, user_type, real_name, status) VALUES
    ('t-001', 'teacher', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.S6GgrMYRnML4Gy', 'teacher', 'Demo Teacher', 'active'),
    ('s-001', 'student', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.S6GgrMYRnML4Gy', 'student', 'Demo Student', 'active')
ON CONFLICT (user_id) DO NOTHING;

-- 插入演示班级
INSERT INTO classes (class_id, class_name, teacher_id, invite_code, student_count) VALUES
    ('c-001', 'Advanced Physics 2024', 't-001', 'PHY24A', 32),
    ('c-002', 'Mathematics Grade 11', 't-001', 'MTH11B', 28)
ON CONFLICT (class_id) DO NOTHING;

-- 插入学生班级关系
INSERT INTO student_class_relations (student_id, class_id) VALUES
    ('s-001', 'c-001')
ON CONFLICT (student_id, class_id) DO NOTHING;

COMMIT;
