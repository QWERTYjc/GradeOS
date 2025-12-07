# 实现计划

- [x] 1. 搭建项目结构和核心依赖




  - [x] 1.1 使用 Poetry/uv 包管理器初始化 Python 项目


    - 创建 pyproject.toml，包含依赖：temporalio, langgraph, langchain-google-genai, fastapi, pydantic, psycopg, redis, pdf2image, imagehash
    - 设置 src/ 目录结构：models/, services/, workflows/, agents/, api/
    - _需求：1.1, 1.2_


  - [ ] 1.2 创建核心数据模型和类型定义
    - 实现 Pydantic 模型：SubmissionRequest, SubmissionResponse, BoundingBox, QuestionRegion, GradingState, GradingResult
    - 定义枚举：FileType, SubmissionStatus, ReviewAction
    - _需求：2.2, 3.6, 7.1_



  - [x]* 1.3 编写 BoundingBox 坐标验证的属性测试


    - **属性 1：坐标归一化数学正确性**
    - **验证：需求 2.3**

- [x] 2. 实现坐标归一化工具






  - [ ] 2.1 创建坐标转换函数
    - 实现 `normalize_coordinates(box_1000, img_width, img_height) -> BoundingBox`


    - 实现 `denormalize_coordinates(box_pixel, img_width, img_height) -> List[int]`
    - _需求：2.3_
  - [ ]* 2.2 编写坐标归一化的属性测试
    - **属性 1：坐标归一化数学正确性**
    - **验证：需求 2.3**






- [ ] 3. 实现数据库层



  - [ ] 3.1 创建 PostgreSQL Schema 和迁移
    - 创建 Alembic 迁移：submissions, grading_results, rubrics, langgraph_checkpoints, human_reviews 表
    - 为 agent_trace 和 student_feedback 设置 JSONB 索引
    - _需求：7.1, 7.2, 7.3, 7.5_
  - [ ] 3.2 实现仓储类
    - 创建 SubmissionRepository，包含 CRUD 操作
    - 创建 GradingResultRepository，处理复合键
    - 创建 RubricRepository，支持 exam_id + question_id 查询
    - _需求：7.4, 9.1, 9.2, 9.3_
  - [ ]* 3.3 编写结果持久化完整性的属性测试
    - **属性 13：结果持久化完整性**
    - **验证：需求 7.1, 7.2, 7.3**

- [ ] 4. 实现 Redis 缓存服务

  - [-] 4.1 创建感知哈希计算


    - 使用 imagehash 库实现 `compute_image_hash(image_data: bytes) -> str`
    - 实现 `compute_rubric_hash(rubric_text: str) -> str`
    - _需求：6.1_
  - [ ] 4.2 实现带优雅降级的缓存服务
    - 创建 CacheService 类，包含 get_cached_result, cache_result 方法
    - 实现失败时返回 None 的错误处理
    - 设置缓存条目 TTL 为 30 天
    - _需求：6.2, 6.3, 6.4, 6.5_
  - [ ]* 4.3 编写感知哈希确定性的属性测试
    - **属性 9：感知哈希确定性**
    - **验证：需求 6.1**
  - [ ]* 4.4 编写缓存命中行为的属性测试
    - **属性 10：缓存命中返回缓存结果**
    - **验证：需求 6.2**
  - [ ]* 4.5 编写高置信度缓存的属性测试
    - **属性 11：高置信度结果被缓存**
    - **验证：需求 6.3**
  - [ ]* 4.6 编写缓存失败弹性的属性测试
    - **属性 12：缓存失败不阻塞批改**
    - **验证：需求 6.4**


- [x] 5. 实现限流器



  - [x] 5.1 创建滑动窗口限流器

    - 实现 RateLimiter 类，包含 acquire() 和 get_remaining() 方法
    - 使用 Redis INCR 配合 EXPIRE 实现原子计数
    - _需求：8.3_
  - [ ]* 5.2 编写限流器节流的属性测试
    - **属性 14：限流器节流**
    - **验证：需求 8.3**


- [x] 6. 检查点 - 确保所有测试通过




  - 确保所有测试通过，如有问题请询问用户。

- [x] 7. 实现 Gemini 模型客户端




  - [x] 7.1 创建布局分析客户端 (Gemini 2.5 Flash Lite)


    - 实现 LayoutAnalysisService，包含 segment_document 方法
    - 配置边界框的结构化 JSON 输出
    - 处理空区域检测并标记为需要人工审核
    - _需求：2.1, 2.2, 2.4, 2.5_
  - [x] 7.2 创建深度推理客户端 (Gemini 3.0 Pro)


    - 实现 GeminiReasoningClient，包含 vision_extraction, rubric_mapping, critique 方法
    - 配置 temperature=0.2 以保持一致性
    - _需求：3.2, 3.3, 3.4_




- [x] 8. 实现 LangGraph 批改智能体






  - [ ] 8.1 定义 GradingState TypedDict
    - 包含所有字段：question_image, rubric, vision_analysis, rubric_mapping, initial_score, reasoning_trace, critique_feedback, final_score, confidence, revision_count, is_finalized
    - _需求：3.1_


  - [ ] 8.2 实现图节点
    - 创建 vision_extraction_node：调用 Gemini 3.0 Pro 描述学生解答
    - 创建 rubric_mapping_node：将评分点映射到证据


    - 创建 critique_node：审查评分并生成反馈
    - 创建 finalization_node：格式化最终输出
    - _需求：3.2, 3.3, 3.4_
  - [ ] 8.3 构建带条件边的图
    - 设置入口点为 vision_extraction_node
    - 添加边：vision -> rubric_mapping -> critique
    - 添加条件边：如果有反馈且 revision_count < 3 -> rubric_mapping，否则 -> finalization
    - _需求：3.5_
  - [ ] 8.4 配置 PostgresSaver 用于检查点
    - 设置检查点持久化，thread_id = submission_id + question_id
    - _需求：3.7_
  - [ ]* 8.5 编写智能体执行完整性的属性测试
    - **属性 2：智能体执行完整性**
    - **验证：需求 3.1, 3.2, 3.3, 3.6**
  - [ ]* 8.6 编写修正循环终止的属性测试
    - **属性 3：智能体修正循环终止**
    - **验证：需求 3.5**
  - [ ]* 8.7 编写检查点持久化的属性测试
    - **属性 4：状态转换时检查点持久化**
    - **验证：需求 3.7**

- [ ] 9. 检查点 - 确保所有测试通过
  - 确保所有测试通过，如有问题请询问用户。

- [ ] 10. 实现 Temporal Activities
  - [ ] 10.1 创建 SegmentDocumentActivity
    - 封装 LayoutAnalysisService 调用
    - 返回包含题目区域的 SegmentationResult
    - _需求：2.1, 2.2_
  - [ ] 10.2 创建 GradeQuestionActivity
    - 首先检查语义缓存
    - 缓存未命中时调用 LangGraph 智能体
    - 缓存高置信度结果
    - 返回 GradingResult
    - _需求：3.1, 6.2, 6.3_
  - [ ] 10.3 创建 NotifyTeacherActivity
    - 当工作流进入 REVIEWING 状态时发送通知
    - _需求：5.2_
  - [ ] 10.4 创建 PersistResultsActivity
    - 将批改结果保存到 PostgreSQL
    - 更新提交状态
    - _需求：7.1, 4.6_

- [ ] 11. 实现 Temporal 工作流
  - [ ] 11.1 创建 QuestionGradingChildWorkflow（子工作流）
    - 执行 GradeQuestionActivity，配置重试策略（最多 3 次）
    - 返回 GradingResult
    - _需求：4.4_
  - [ ] 11.2 创建 ExamPaperWorkflow（父工作流）
    - 执行 SegmentDocumentActivity
    - 使用 asyncio.gather 为每道题目扇出子工作流
    - 聚合结果并计算总分
    - 检查置信度阈值，必要时转换到 REVIEWING 状态
    - 处理审核信号（APPROVE, OVERRIDE, REJECT）
    - 持久化最终结果
    - _需求：4.1, 4.2, 4.3, 5.1, 5.3, 5.4, 5.5_
  - [ ]* 11.3 编写扇出数量的属性测试
    - **属性 5：扇出数量匹配题目数量**
    - **验证：需求 4.2**
  - [ ]* 11.4 编写分数聚合的属性测试
    - **属性 6：分数聚合正确性**
    - **验证：需求 4.3**
  - [ ]* 11.5 编写低置信度审核触发的属性测试
    - **属性 7：低置信度触发审核状态**
    - **验证：需求 5.1**
  - [ ]* 11.6 编写信号处理的属性测试
    - **属性 8：信号处理状态转换**
    - **验证：需求 5.3, 5.4, 5.5**

- [ ] 12. 检查点 - 确保所有测试通过
  - 确保所有测试通过，如有问题请询问用户。

- [ ] 13. 实现提交服务
  - [ ] 13.1 创建 PDF 转图像功能
    - 使用 pdf2image 实现 convert_pdf_to_images，dpi=300
    - 处理多页 PDF
    - _需求：1.1_
  - [ ] 13.2 创建文件验证
    - 验证图像格式（JPEG, PNG, WEBP）
    - 验证文件大小限制
    - 为无效格式返回描述性错误消息
    - _需求：1.2, 1.5_
  - [ ] 13.3 实现提交处理器
    - 将图像保存到对象存储（S3/MinIO）
    - 在数据库中创建提交记录
    - 异步启动 Temporal 工作流
    - 立即返回 submission_id
    - _需求：1.3, 1.4_

- [ ] 14. 实现评分细则服务
  - [ ] 14.1 创建评分细则 CRUD 操作
    - 实现 create_rubric, get_rubric, update_rubric, delete_rubric
    - 将评分细则链接到 exam_id 和 question_id
    - _需求：9.1, 9.2_
  - [ ] 14.2 实现评分细则更新时的缓存失效
    - 更新时删除匹配 rubric_hash 的缓存条目
    - _需求：9.4_
  - [ ] 14.3 实现缺失评分细则检测
    - 将没有评分细则的题目标记为需要手动配置
    - _需求：9.5_
  - [ ]* 14.4 编写评分细则缓存失效的属性测试
    - **属性 15：评分细则更新使缓存失效**
    - **验证：需求 9.4**
  - [ ]* 14.5 编写缺失评分细则处理的属性测试
    - **属性 16：缺失评分细则标记题目**
    - **验证：需求 9.5**

- [ ] 15. 实现 FastAPI 端点
  - [ ] 15.1 创建提交端点
    - POST /api/v1/submissions - 上传并提交批改
    - GET /api/v1/submissions/{submission_id} - 获取提交状态
    - GET /api/v1/submissions/{submission_id}/results - 获取批改结果
    - _需求：1.3, 7.4_
  - [ ] 15.2 创建评分细则端点
    - POST /api/v1/rubrics - 创建评分细则
    - GET /api/v1/rubrics/{exam_id}/{question_id} - 获取评分细则
    - PUT /api/v1/rubrics/{rubric_id} - 更新评分细则
    - _需求：9.1, 9.2_
  - [ ] 15.3 创建审核端点
    - POST /api/v1/reviews/{submission_id}/signal - 发送审核信号
    - GET /api/v1/reviews/{submission_id}/pending - 获取待审核项
    - _需求：5.3, 5.4, 5.5_
  - [ ] 15.4 添加限流中间件
    - 对所有端点应用限流器
    - 节流时返回 429 和 retry-after 头
    - _需求：8.3_

- [ ] 16. 实现质量控制流水线
  - [ ] 16.1 创建黄金数据集验证
    - 加载 500 份标注样本
    - 在样本上运行批改流水线
    - _需求：10.1_
  - [ ] 16.2 实现指标计算
    - 计算皮尔逊相关系数
    - 计算科恩 Kappa 系数
    - _需求：10.2_
  - [ ] 16.3 实现部署门控
    - 如果相关系数 < 0.9 或 Kappa < 0.8 则阻止部署
    - _需求：10.3_
  - [ ]* 16.4 编写质量控制阈值阻止的属性测试
    - **属性 17：质量控制阈值阻止部署**
    - **验证：需求 10.3**

- [ ] 17. 创建 Temporal Worker 入口点
  - [ ] 17.1 创建编排 Worker
    - 注册 ExamPaperWorkflow 和 QuestionGradingChildWorkflow
    - 连接到 default-queue
    - _需求：4.1_
  - [ ] 17.2 创建认知 Worker
    - 注册所有 Activities
    - 连接到 vision-compute-queue
    - 配置并发限制
    - _需求：4.1_

- [ ] 18. 创建 Docker 和 Kubernetes 配置
  - [ ] 18.1 创建 Dockerfile
    - 为 API 服务创建 Dockerfile
    - 为 Temporal Workers 创建 Dockerfile
    - _需求：8.1_
  - [ ] 18.2 创建 Kubernetes 清单
    - 为 API、提交服务、Workers 创建 Deployment
    - 创建 Service 和 Ingress
    - 为认知 Workers 创建 KEDA ScaledObject
    - _需求：8.1, 8.2_

- [ ] 19. 最终检查点 - 确保所有测试通过
  - 确保所有测试通过，如有问题请询问用户。
