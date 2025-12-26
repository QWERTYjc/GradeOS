# 后端数据库需求文档

## 文档信息
- **项目名称**: AI教育平台后端数据库系统
- **版本**: v1.0
- **创建日期**: 2024-12-18
- **基于文档**: project_api/API接口整合文档.md
- **适用范围**: CTB学生助手系统、教学Agent系统、AI批改平台、移动端扫描系统

## 1. 项目概述

### 1.1 系统背景
基于project_api中的API接口整合文档，设计并实现一个统一的后端数据库系统，支持四大核心系统：

1. **CTB学生助手系统**: G9学段学生学业支持和选科指导
2. **教学Agent系统**: 智能错题分析和学习建议生成  
3. **AI批改平台**: 作业自动批改和可视化展示
4. **移动端扫描系统**: 手机拍照上传和图像处理

### 1.2 技术架构
- **数据库**: PostgreSQL 15+ (主库) + Redis 7+ (缓存)
- **后端框架**: FastAPI + Python 3.11+
- **ORM框架**: SQLAlchemy 2.0+
- **迁移工具**: Alembic
- **AI模型**: OpenRouter Gemini 2.5 Flash Lite
- **部署**: Docker + Kubernetes

### 1.3 设计原则
- **API优先**: 严格按照API接口整合文档设计数据结构
- **数据一致性**: 保证跨系统数据的一致性和完整性
- **高性能**: 支持1000+ QPS并发访问
- **可扩展性**: 支持水平扩展和微服务架构
- **安全性**: 数据加密存储和访问控制

## 2. 数据库架构设计

### 2.1 数据库选型与配置

#### 2.1.1 PostgreSQL主数据库
- 版本: PostgreSQL 15.4+
- 内存: 8GB+
- 存储: SSD 500GB+
- 连接数: 200
- 字符集: UTF-8
- 时区: UTC
- 扩展: uuid-ossp, pg_trgm, btree_gin

#### 2.1.2 Redis缓存数据库
- 版本: Redis 7.2+
- 内存: 4GB+
- 持久化: RDB + AOF
- 集群: 3主3从
- 过期策略: LRU
- 数据库分区: 16个DB

## 3. 核心数据模型设计

### 3.1 用户认证模块

#### 3.1.1 用户表 (users)
| 字段名 | 类型 | 约束 | 说明 |
|-------|------|------|------|
| user_id | VARCHAR(50) | PRIMARY KEY | 用户ID |
| username | VARCHAR(100) | UNIQUE NOT NULL | 用户名 |
| password_hash | VARCHAR(255) | NOT NULL | 密码哈希 |
| email | VARCHAR(200) | UNIQUE | 邮箱 |
| phone | VARCHAR(50) | | 手机号 |
| user_type | VARCHAR(20) | NOT NULL | student/teacher/admin |
| real_name | VARCHAR(100) | | 真实姓名 |
| avatar_url | VARCHAR(500) | | 头像URL |
| status | VARCHAR(20) | DEFAULT 'active' | active/inactive/suspended |
| last_login_at | TIMESTAMP | | 最后登录时间 |
| created_at | TIMESTAMP | DEFAULT NOW() | 创建时间 |
| updated_at | TIMESTAMP | DEFAULT NOW() | 更新时间 |

#### 3.1.2 用户配置表 (user_profiles)
| 字段名 | 类型 | 约束 | 说明 |
|-------|------|------|------|
| profile_id | SERIAL | PRIMARY KEY | 配置ID |
| user_id | VARCHAR(50) | REFERENCES users | 用户ID |
| grade | VARCHAR(20) | | 年级 |
| school | VARCHAR(200) | | 学校 |
| class_id | VARCHAR(100) | | 班级ID |
| subject | VARCHAR(50) | | 科目 |
| preferences | JSONB | DEFAULT '{}' | 偏好设置 |
| learning_style | VARCHAR(50) | | 学习风格 |
| language | VARCHAR(10) | DEFAULT 'zh-CN' | 语言 |
| theme | VARCHAR(20) | DEFAULT 'light' | 主题 |
| notifications | BOOLEAN | DEFAULT TRUE | 通知开关 |

### 3.2 班级管理模块

#### 3.2.1 班级表 (classes)
| 字段名 | 类型 | 约束 | 说明 |
|-------|------|------|------|
| class_id | VARCHAR(100) | PRIMARY KEY | 班级ID |
| class_name | VARCHAR(100) | NOT NULL | 班级名称 |
| teacher_id | VARCHAR(50) | REFERENCES users | 班主任ID |
| grade_level | VARCHAR(20) | | 年级 |
| subject | VARCHAR(50) | | 科目 |
| semester | VARCHAR(20) | | 学期 |
| invite_code | VARCHAR(20) | UNIQUE NOT NULL | 邀请码 |
| student_count | INTEGER | DEFAULT 0 | 学生数量 |
| max_students | INTEGER | DEFAULT 50 | 最大学生数 |
| is_active | BOOLEAN | DEFAULT TRUE | 是否激活 |
| description | TEXT | | 班级描述 |
| created_at | TIMESTAMP | DEFAULT NOW() | 创建时间 |
| updated_at | TIMESTAMP | DEFAULT NOW() | 更新时间 |

#### 3.2.2 学生班级关系表 (student_class_relations)
| 字段名 | 类型 | 约束 | 说明 |
|-------|------|------|------|
| id | SERIAL | PRIMARY KEY | 关系ID |
| student_id | VARCHAR(50) | REFERENCES users | 学生ID |
| class_id | VARCHAR(100) | REFERENCES classes | 班级ID |
| join_date | TIMESTAMP | DEFAULT NOW() | 加入日期 |
| status | VARCHAR(20) | DEFAULT 'active' | 状态 |
| is_admin | BOOLEAN | DEFAULT FALSE | 是否班级管理员 |

### 3.3 作业管理模块

#### 3.3.1 作业表 (assignments)
| 字段名 | 类型 | 约束 | 说明 |
|-------|------|------|------|
| assignment_id | VARCHAR(100) | PRIMARY KEY | 作业ID |
| homework_id | VARCHAR(100) | UNIQUE | 兼容API中的homeworkId |
| class_id | VARCHAR(100) | REFERENCES classes | 班级ID |
| teacher_id | VARCHAR(50) | REFERENCES users | 教师ID |
| title | VARCHAR(200) | NOT NULL | 作业标题 |
| description | TEXT | | 作业描述 |
| subject | VARCHAR(50) | | 科目 |
| total_questions | INTEGER | DEFAULT 0 | 题目总数 |
| max_score | DECIMAL(10,2) | DEFAULT 100 | 满分 |
| status | VARCHAR(20) | DEFAULT 'draft' | draft/published/closed/archived |
| publish_date | TIMESTAMP | | 发布时间 |
| due_date | TIMESTAMP | | 截止时间 |
| allow_late_submission | BOOLEAN | DEFAULT FALSE | 允许迟交 |
| max_attempts | INTEGER | DEFAULT 1 | 最大提交次数 |
| instructions | TEXT | | 作业说明 |
| requirements | TEXT | | 作业要求 |
| attachment_urls | JSONB | DEFAULT '[]' | 附件URL列表 |
| rubric_data | JSONB | DEFAULT '{}' | 评分标准 |
| created_at | TIMESTAMP | DEFAULT NOW() | 创建时间 |
| updated_at | TIMESTAMP | DEFAULT NOW() | 更新时间 |

#### 3.3.2 作业提交表 (assignment_submissions)
| 字段名 | 类型 | 约束 | 说明 |
|-------|------|------|------|
| submission_id | VARCHAR(100) | PRIMARY KEY | 提交ID |
| assignment_id | VARCHAR(100) | REFERENCES assignments | 作业ID |
| student_id | VARCHAR(50) | REFERENCES users | 学生ID |
| attempt_number | INTEGER | DEFAULT 1 | 提交次数 |
| answer_files | JSONB | DEFAULT '[]' | 答案文件列表 |
| submitted_at | TIMESTAMP | DEFAULT NOW() | 提交时间 |
| grading_status | VARCHAR(20) | DEFAULT 'pending' | pending/processing/ai_graded/teacher_reviewed/completed/failed |
| grading_mode | VARCHAR(20) | DEFAULT 'standard' | 批改模式 |
| total_score | DECIMAL(10,2) | | 总分 |
| max_score | DECIMAL(10,2) | | 满分 |
| percentage | DECIMAL(5,2) | | 百分比 |
| grade_level | VARCHAR(10) | | 等级 |
| is_late | BOOLEAN | DEFAULT FALSE | 是否迟交 |
| teacher_comment | TEXT | | 教师评语 |
| teacher_adjusted_score | DECIMAL(10,2) | | 教师调整分数 |
| is_reviewed | BOOLEAN | DEFAULT FALSE | 是否已审核 |
| reviewed_at | TIMESTAMP | | 审核时间 |
| submit_time | TIMESTAMP | DEFAULT NOW() | 兼容API中的submitTime |
| created_at | TIMESTAMP | DEFAULT NOW() | 创建时间 |
| updated_at | TIMESTAMP | DEFAULT NOW() | 更新时间 |

### 3.4 AI批改模块

#### 3.4.1 批改任务表 (grading_tasks)
| 字段名 | 类型 | 约束 | 说明 |
|-------|------|------|------|
| task_id | VARCHAR(100) | PRIMARY KEY | 任务ID |
| submission_id | VARCHAR(100) | REFERENCES assignment_submissions | 提交ID |
| student_id | VARCHAR(50) | REFERENCES users | 学生ID |
| subject | VARCHAR(50) | | 科目 |
| total_questions | INTEGER | DEFAULT 0 | 题目总数 |
| status | VARCHAR(20) | DEFAULT 'pending' | pending/processing/completed/failed/cancelled |
| ai_model | VARCHAR(100) | DEFAULT 'google/gemini-2.5-flash-lite' | AI模型 |
| processing_mode | VARCHAR(20) | DEFAULT 'standard' | 处理模式 |
| confidence_score | DECIMAL(5,4) | | 置信度 |
| processing_time_ms | INTEGER | | 处理时间(毫秒) |
| error_message | TEXT | | 错误信息 |
| created_at | TIMESTAMP | DEFAULT NOW() | 创建时间 |
| completed_at | TIMESTAMP | | 完成时间 |

#### 3.4.2 批改结果表 (grading_results)
| 字段名 | 类型 | 约束 | 说明 |
|-------|------|------|------|
| result_id | SERIAL | PRIMARY KEY | 结果ID |
| task_id | VARCHAR(100) | REFERENCES grading_tasks | 任务ID |
| question_id | VARCHAR(100) | NOT NULL | 题目ID |
| question_no | INTEGER | | 题目序号 |
| score | DECIMAL(10,2) | NOT NULL | 得分 |
| max_score | DECIMAL(10,2) | NOT NULL | 满分 |
| is_correct | BOOLEAN | | 是否正确 |
| feedback | TEXT | | 反馈 |
| strategy | VARCHAR(50) | | 批改策略 |
| confidence | DECIMAL(5,4) | | 置信度 |
| error_type | VARCHAR(50) | | 错误类型 |
| suggestion | TEXT | | 建议 |
| correct_answer | TEXT | | 正确答案 |
| annotations | JSONB | DEFAULT '{}' | 标注信息 |
| coordinates | JSONB | DEFAULT '{}' | 坐标信息 |
| created_at | TIMESTAMP | DEFAULT NOW() | 创建时间 |

### 3.5 错题分析模块 (教学Agent系统)

#### 3.5.1 错题记录表 (error_records)
| 字段名 | 类型 | 约束 | 说明 |
|-------|------|------|------|
| error_id | VARCHAR(100) | PRIMARY KEY | 错题ID |
| analysis_id | VARCHAR(100) | UNIQUE | 分析ID |
| student_id | VARCHAR(50) | REFERENCES users | 学生ID |
| question_id | VARCHAR(100) | | 题目ID |
| subject | VARCHAR(50) | | 科目 |
| question_type | VARCHAR(50) | | 选择题/填空题/解答题 |
| original_question | JSONB | DEFAULT '{}' | 原题信息 |
| student_answer | TEXT | | 学生答案 |
| student_solution_steps | JSONB | DEFAULT '[]' | 解题步骤 |
| correct_answer | TEXT | | 正确答案 |
| error_type | VARCHAR(50) | | 错误类型 |
| error_severity | VARCHAR(20) | | high/medium/low |
| root_cause | TEXT | | 根本原因 |
| knowledge_points | JSONB | DEFAULT '[]' | 知识点 |
| knowledge_gaps | JSONB | DEFAULT '[]' | 知识漏洞 |
| detailed_analysis | JSONB | DEFAULT '{}' | 详细分析 |
| metadata | JSONB | DEFAULT '{}' | 元数据 |
| created_at | TIMESTAMP | DEFAULT NOW() | 创建时间 |

#### 3.5.2 学习建议表 (learning_recommendations)
| 字段名 | 类型 | 约束 | 说明 |
|-------|------|------|------|
| recommendation_id | VARCHAR(100) | PRIMARY KEY | 建议ID |
| student_id | VARCHAR(50) | REFERENCES users | 学生ID |
| analysis_id | VARCHAR(100) | REFERENCES error_records | 分析ID |
| recommendation_type | VARCHAR(50) | | 建议类型 |
| content | TEXT | | 建议内容 |
| resources | JSONB | DEFAULT '[]' | 学习资源 |
| immediate_actions | JSONB | DEFAULT '[]' | 即时行动 |
| practice_exercises | JSONB | DEFAULT '[]' | 练习题 |
| learning_strategies | JSONB | DEFAULT '[]' | 学习策略 |
| learning_path | JSONB | DEFAULT '{}' | 学习路径 |
| priority | INTEGER | DEFAULT 1 | 优先级 |
| status | VARCHAR(20) | DEFAULT 'pending' | 状态 |
| feedback_rating | INTEGER | | 反馈评分1-5 |
| feedback_comment | TEXT | | 反馈评论 |
| created_at | TIMESTAMP | DEFAULT NOW() | 创建时间 |
| expires_at | TIMESTAMP | | 过期时间 |

### 3.6 选科指导模块 (G9专属)

#### 3.6.1 科目信息表 (subjects)
| 字段名 | 类型 | 约束 | 说明 |
|-------|------|------|------|
| subject_id | VARCHAR(50) | PRIMARY KEY | 科目ID |
| subject_name | VARCHAR(100) | NOT NULL | 科目名称 |
| subject_type | VARCHAR(20) | | core/elective |
| difficulty_level | INTEGER | | 难度1-5 |
| description | TEXT | | 描述 |
| learning_content | TEXT | | 学习内容 |
| assessment_method | TEXT | | 评核方式 |
| workload_estimate | INTEGER | | 学习压力评估 |
| info | JSONB | DEFAULT '{}' | 科目详情 |
| prerequisites | JSONB | DEFAULT '[]' | 先修科目 |
| career_paths | JSONB | DEFAULT '[]' | 职业方向 |
| created_at | TIMESTAMP | DEFAULT NOW() | 创建时间 |
| updated_at | TIMESTAMP | DEFAULT NOW() | 更新时间 |

#### 3.6.2 选科组合表 (subject_combinations)
| 字段名 | 类型 | 约束 | 说明 |
|-------|------|------|------|
| combo_id | VARCHAR(100) | PRIMARY KEY | 组合ID |
| combo_name | VARCHAR(200) | | 组合名称 |
| subjects | JSONB | NOT NULL | 科目列表 |
| difficulty_rating | INTEGER | | 难度评级1-5 |
| suitable_majors | JSONB | DEFAULT '[]' | 适合专业 |
| advantages | TEXT | | 优势 |
| disadvantages | TEXT | | 劣势 |
| competition_level | INTEGER | | 竞争强度1-5 |
| created_at | TIMESTAMP | DEFAULT NOW() | 创建时间 |

#### 3.6.3 升学要求表 (admission_requirements)
| 字段名 | 类型 | 约束 | 说明 |
|-------|------|------|------|
| requirement_id | VARCHAR(100) | PRIMARY KEY | 要求ID |
| major_id | VARCHAR(100) | | 专业ID |
| uni_id | VARCHAR(100) | | 大学ID |
| university_name | VARCHAR(200) | | 大学名称 |
| major_name | VARCHAR(200) | | 专业名称 |
| required_subjects | JSONB | DEFAULT '[]' | 必选科目 |
| preferred_subjects | JSONB | DEFAULT '[]' | 优先科目 |
| min_grades | JSONB | DEFAULT '[]' | 最低等级要求 |
| application_tips | TEXT | | 申请建议 |
| subject_type | VARCHAR(20) | | 核心/选修 |
| last_updated | TIMESTAMP | DEFAULT NOW() | 最后更新 |
| data_source | VARCHAR(100) | DEFAULT 'JUPAS' | 数据来源 |

### 3.7 移动端扫描模块

#### 3.7.1 扫描会话表 (scan_sessions)
| 字段名 | 类型 | 约束 | 说明 |
|-------|------|------|------|
| session_id | VARCHAR(100) | PRIMARY KEY | 会话ID |
| user_id | VARCHAR(50) | REFERENCES users | 用户ID |
| exam_id | VARCHAR(100) | | 考试ID |
| student_id | VARCHAR(50) | | 学生ID |
| status | VARCHAR(20) | DEFAULT 'active' | active/completed/expired/cancelled |
| created_time | TIMESTAMP | DEFAULT NOW() | 创建时间 |
| completed_at | TIMESTAMP | | 完成时间 |
| expires_at | TIMESTAMP | | 过期时间 |

#### 3.7.2 图片处理表 (image_processing)
| 字段名 | 类型 | 约束 | 说明 |
|-------|------|------|------|
| image_id | VARCHAR(100) | PRIMARY KEY | 图片ID |
| session_id | VARCHAR(100) | REFERENCES scan_sessions | 会话ID |
| original_filename | VARCHAR(255) | | 原始文件名 |
| original_path | VARCHAR(500) | | 原始路径 |
| optimized_path | VARCHAR(500) | | 优化后路径 |
| file_size_bytes | INTEGER | | 文件大小 |
| processing_status | VARCHAR(20) | DEFAULT 'pending' | pending/processing/processed/failed |
| ocr_result | JSONB | DEFAULT '{}' | OCR结果 |
| optimization_params | JSONB | DEFAULT '{}' | 优化参数 |
| upload_time | TIMESTAMP | DEFAULT NOW() | 上传时间 |
| processed_time | TIMESTAMP | | 处理完成时间 |
| status | VARCHAR(20) | DEFAULT 'pending' | 状态 |

### 3.8 知识图谱模块

#### 3.8.1 知识点表 (knowledge_points)
| 字段名 | 类型 | 约束 | 说明 |
|-------|------|------|------|
| concept_id | VARCHAR(100) | PRIMARY KEY | 知识点ID |
| concept_name | VARCHAR(200) | NOT NULL | 知识点名称 |
| point_name | VARCHAR(200) | NOT NULL | 知识点名称 |
| subject | VARCHAR(50) | | 科目 |
| chapter | VARCHAR(100) | | 章节 |
| difficulty | VARCHAR(20) | | easy/medium/hard |
| difficulty_level | INTEGER | | 难度1-5 |
| description | TEXT | | 描述 |
| parent_point_id | VARCHAR(100) | | 父知识点ID |
| prerequisites | JSONB | DEFAULT '[]' | 先修知识点 |
| related_points | JSONB | DEFAULT '[]' | 相关知识点 |
| created_at | TIMESTAMP | DEFAULT NOW() | 创建时间 |

#### 3.8.2 学生知识掌握表 (student_knowledge_mastery)
| 字段名 | 类型 | 约束 | 说明 |
|-------|------|------|------|
| mastery_id | SERIAL | PRIMARY KEY | 掌握ID |
| student_id | VARCHAR(50) | REFERENCES users | 学生ID |
| concept_id | VARCHAR(100) | REFERENCES knowledge_points | 知识点ID |
| mastery_level | DECIMAL(5,4) | DEFAULT 0.0 | 掌握程度0-1 |
| correct_count | INTEGER | DEFAULT 0 | 正确次数 |
| total_count | INTEGER | DEFAULT 0 | 总次数 |
| last_assignment_id | VARCHAR(100) | | 最后作业ID |
| last_score | DECIMAL(10,2) | | 最后得分 |
| last_evaluated_at | TIMESTAMP | | 最后评估时间 |
| created_at | TIMESTAMP | DEFAULT NOW() | 创建时间 |
| updated_at | TIMESTAMP | DEFAULT NOW() | 更新时间 |

### 3.9 统计分析模块

#### 3.9.1 班级统计表 (class_statistics)
| 字段名 | 类型 | 约束 | 说明 |
|-------|------|------|------|
| stat_id | VARCHAR(100) | PRIMARY KEY | 统计ID |
| class_id | VARCHAR(100) | REFERENCES classes | 班级ID |
| assignment_id | VARCHAR(100) | REFERENCES assignments | 作业ID |
| class_name | VARCHAR(100) | | 班级名称 |
| total_students | INTEGER | | 学生总数 |
| submitted_count | INTEGER | | 已提交数 |
| graded_count | INTEGER | | 已批改数 |
| average_score | DECIMAL(10,2) | | 平均分 |
| max_score | DECIMAL(10,2) | | 最高分 |
| min_score | DECIMAL(10,2) | | 最低分 |
| median_score | DECIMAL(10,2) | | 中位数 |
| pass_rate | DECIMAL(5,4) | | 及格率 |
| score_distribution | JSONB | DEFAULT '{}' | 分数分布 |
| common_errors | JSONB | DEFAULT '[]' | 常见错误 |
| error_distribution | JSONB | DEFAULT '[]' | 错误分布 |
| knowledge_mastery | JSONB | DEFAULT '{}' | 知识掌握情况 |
| teaching_suggestions | JSONB | DEFAULT '[]' | 教学建议 |
| generated_at | TIMESTAMP | DEFAULT NOW() | 生成时间 |

#### 3.9.2 系统日志表 (system_logs)
| 字段名 | 类型 | 约束 | 说明 |
|-------|------|------|------|
| log_id | SERIAL | PRIMARY KEY | 日志ID |
| user_id | VARCHAR(50) | | 用户ID |
| action | VARCHAR(100) | | 操作类型 |
| resource_type | VARCHAR(50) | | 资源类型 |
| resource_id | VARCHAR(100) | | 资源ID |
| ip_address | INET | | IP地址 |
| user_agent | TEXT | | 用户代理 |
| request_data | JSONB | DEFAULT '{}' | 请求数据 |
| response_status | INTEGER | | 响应状态码 |
| processing_time_ms | INTEGER | | 处理时间(毫秒) |
| created_at | TIMESTAMP | DEFAULT NOW() | 创建时间 |

---

## 4. API接口与数据库映射

### 4.1 用户认证接口映射

| API接口 | 数据库操作 | 涉及表 |
|--------|----------|-------|
| POST /api/auth/login | SELECT + UPDATE | users, user_profiles |
| GET /api/user/info | SELECT | users, user_profiles |

### 4.2 班级管理接口映射

| API接口 | 数据库操作 | 涉及表 |
|--------|----------|-------|
| GET /api/class/my | SELECT | classes, student_class_relations, users |
| POST /api/class/join | INSERT + UPDATE | student_class_relations, classes |
| GET /api/teacher/classes | SELECT | classes |
| POST /api/teacher/classes | INSERT | classes |

### 4.3 作业管理接口映射

| API接口 | 数据库操作 | 涉及表 |
|--------|----------|-------|
| GET /api/homework/list | SELECT | assignments, assignment_submissions |
| GET /api/homework/detail/{id} | SELECT | assignments |
| POST /api/homework/create | INSERT | assignments |
| POST /api/homework/submit | INSERT | assignment_submissions |
| GET /api/homework/result | SELECT | assignment_submissions, grading_tasks, grading_results |

### 4.4 错题分析接口映射

| API接口 | 数据库操作 | 涉及表 |
|--------|----------|-------|
| POST /api/v1/analysis/submit-error | INSERT | error_records |
| POST /api/v1/recommendation/generate | INSERT | learning_recommendations |
| GET /api/v1/diagnosis/report/{id} | SELECT | error_records, student_knowledge_mastery |
| POST /api/v1/feedback/submit | INSERT | feedback_submissions |

### 4.5 选科指导接口映射

| API接口 | 数据库操作 | 涉及表 |
|--------|----------|-------|
| GET /api/G9admission/student/concept | SELECT | subjects |
| GET /api/G9admission/student/combos | SELECT | subject_combinations |
| GET /api/G9admission/student/requirement | SELECT | admission_requirements |

### 4.6 移动端扫描接口映射

| API接口 | 数据库操作 | 涉及表 |
|--------|----------|-------|
| POST /api/scan/session/create | INSERT | scan_sessions |
| GET /api/scan/session/{id} | SELECT | scan_sessions, image_processing |
| DELETE /api/scan/session/{id} | DELETE | scan_sessions |
| POST /api/scan/submit | INSERT | image_processing |

---

## 5. 索引设计

### 5.1 主要索引列表

| 表名 | 索引名 | 索引字段 | 索引类型 |
|-----|-------|---------|---------|
| users | idx_users_username | username | UNIQUE |
| users | idx_users_type_status | user_type, status | BTREE |
| classes | idx_classes_teacher_id | teacher_id | BTREE |
| classes | idx_classes_invite_code | invite_code | UNIQUE |
| student_class_relations | idx_scr_student_class | student_id, class_id | UNIQUE |
| assignments | idx_assignments_class_id | class_id | BTREE |
| assignments | idx_assignments_due_date | due_date | BTREE |
| assignment_submissions | idx_submissions_assignment_student | assignment_id, student_id | BTREE |
| grading_tasks | idx_grading_tasks_status | status | BTREE |
| error_records | idx_error_records_student | student_id | BTREE |
| knowledge_points | idx_knowledge_points_subject | subject | BTREE |

---

## 6. 缓存策略 (Redis)

### 6.1 缓存键设计

| 缓存键模式 | 数据类型 | TTL | 说明 |
|-----------|---------|-----|------|
| user:{user_id} | Hash | 1h | 用户信息缓存 |
| session:{token} | String | 24h | 会话Token |
| class:{class_id} | Hash | 30m | 班级信息缓存 |
| homework:list:{user_id} | List | 5m | 作业列表缓存 |
| stats:{class_id}:{homework_id} | Hash | 10m | 统计数据缓存 |
| knowledge:{subject} | Hash | 1d | 知识点缓存 |
| admission:{major_id} | Hash | 1d | 升学要求缓存 |

### 6.2 缓存更新策略

- **写穿透**: 写入数据库后立即更新缓存
- **读穿透**: 缓存未命中时从数据库读取并写入缓存
- **定时刷新**: 统计数据每10分钟自动刷新
- **主动失效**: 数据更新时主动删除相关缓存

---

## 7. 安全设计

### 7.1 数据加密
- 密码使用bcrypt哈希存储
- 敏感数据使用AES-256加密
- 传输层使用TLS 1.3

### 7.2 访问控制
- 基于角色的访问控制(RBAC)
- JWT Token认证，有效期24小时
- API请求频率限制：100次/分钟

### 7.3 数据隐私
- 学生姓名、学校等隐私信息脱敏
- 仅保留匿名标识(studentId, classId)
- 日志中不记录敏感信息

---

## 8. 性能指标

### 8.1 目标指标
| 指标 | 目标值 |
|-----|-------|
| 响应时间 | < 200ms (P95) |
| 并发连接 | 1000+ |
| QPS | 1000+ |
| 可用性 | 99.9% |
| 数据库连接池 | 20-50 |

### 8.2 优化策略
- 读写分离：主库写入，从库读取
- 连接池：使用SQLAlchemy连接池
- 查询优化：避免N+1查询，使用JOIN
- 分页查询：大数据量使用游标分页

---

## 9. 部署架构

### 9.1 Docker配置
- PostgreSQL: postgres:15-alpine
- Redis: redis:7-alpine
- FastAPI: python:3.11-slim

### 9.2 环境变量
- DATABASE_URL: PostgreSQL连接字符串
- REDIS_URL: Redis连接字符串
- JWT_SECRET: JWT签名密钥
- AI_API_KEY: AI模型API密钥

---

## 10. 数据库表总览

| 序号 | 表名 | 说明 | 所属模块 |
|-----|-----|------|---------|
| 1 | users | 用户表 | 用户认证 |
| 2 | user_profiles | 用户配置表 | 用户认证 |
| 3 | classes | 班级表 | 班级管理 |
| 4 | student_class_relations | 学生班级关系表 | 班级管理 |
| 5 | assignments | 作业表 | 作业管理 |
| 6 | assignment_submissions | 作业提交表 | 作业管理 |
| 7 | grading_tasks | 批改任务表 | AI批改 |
| 8 | grading_results | 批改结果表 | AI批改 |
| 9 | error_records | 错题记录表 | 错题分析 |
| 10 | learning_recommendations | 学习建议表 | 错题分析 |
| 11 | subjects | 科目信息表 | 选科指导 |
| 12 | subject_combinations | 选科组合表 | 选科指导 |
| 13 | admission_requirements | 升学要求表 | 选科指导 |
| 14 | scan_sessions | 扫描会话表 | 移动端扫描 |
| 15 | image_processing | 图片处理表 | 移动端扫描 |
| 16 | knowledge_points | 知识点表 | 知识图谱 |
| 17 | student_knowledge_mastery | 学生知识掌握表 | 知识图谱 |
| 18 | class_statistics | 班级统计表 | 统计分析 |
| 19 | system_logs | 系统日志表 | 统计分析 |

---

**文档版本**: v1.0  
**最后更新**: 2025-12-18  
**基于文档**: project_api/API接口整合文档.md
