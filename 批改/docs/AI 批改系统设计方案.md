生产级纯视觉 AI 批改系统架构白皮书：基于 Temporal 与 LangGraph 的下一代自动评估引擎
1. 执行摘要与架构愿景
在教育技术（EdTech）领域，自动化批改系统正经历着从“文本识别驱动”向“视觉语义驱动”的范式转移。传统的批改流水线依赖于光学字符识别（OCR）技术将学生的手写答卷转化为机器可读文本，随后利用自然语言处理（NLP）模型进行评分。然而，这种串行化的处理方式在面对复杂s的数理逻辑、化学方程式、几何图形绘制以及非结构化的手写布局时，往往面临着严重的“误差传播”问题——OCR 的微小识别错误（如将积分符号 $\int$ 误认为字母 $S$）将直接导致后续推理环节的全面失效。
本技术报告旨在定义并详述一套生产级、纯视觉（Vision-Native）、高并发且可水平扩展的 AI 批改系统架构。该系统严格遵循“不使用 OCR”的原则，直接利用多模态大模型（LMMs），特别是 Gemini 3.0 Pro 和 Gemini 2.5 Flash Lite，对试卷图像进行端到端的语义理解与评估。架构核心采用 Temporal 作为分布式工作流编排引擎，以确保在长周期、异步批改任务中的“Durable Execution”（持久化执行）；同时引入 LangGraph 构建题内智能体（Agent），通过图结构的循环推理能力实现对学生解题步骤的深度逻辑验证。
本方案专为处理千万级日均请求量设计，利用 PostgreSQL 的 JSONB 特性存储复杂的视觉标注数据，并通过 Redis 实现高吞吐量的状态缓存与任务去重。报告将从业务流程、系统拓扑、核心组件设计、数据工程及工程落地代码骨架等多个维度，对该架构进行详尽的拆解与论证。
2. 纯视觉评估范式：技术选型与模型策略
2.1 摒弃 OCR 的工程逻辑
在传统的工程实践中，OCR 是数据结构化的第一步。但在批改场景下，OCR 实际上是一种“有损压缩”。学生的试卷是一个包含空间拓扑信息的二维平面，箭头指向、页边距的草稿演算、被划掉的错误步骤，这些视觉线索对于判断学生的思维过程至关重要。纯视觉模型（Vision Language Models, VLMs）允许我们将完整的图像上下文直接输入到推理引擎中，从而保留了所有的语义完整性。
根据最新的模型发布信息，Gemini 3.0 Pro 1 引入了“思维层级”（Thinking Levels）和“思维签名”（Thought Signatures），这使得模型在处理复杂的逻辑推理任务时具备了前所未有的深度。而 Gemini 2.5 Flash Lite 3 则提供了 100 万 token 的上下文窗口和极低的延迟，使其成为处理整卷分割和布局分析的理想选择。
2.2 双模型协同策略
为了在成本与性能之间取得平衡，本系统采用“双模型漏斗”策略：
1. 布局分析与分割（Layout Analysis & Segmentation）： 使用 Gemini 2.5 Flash Lite。
   * 任务： 接收整页试卷图像，识别题目边界，提取学生手写区域的 Bounding Box（边界框）。
   * 优势： Flash Lite 版本针对高吞吐量进行了优化，且支持原生工具调用（Tool Use）和结构化输出，能够以极低的成本快速完成千万级像素的图像解析任务。
   * 输出： 结构化的 JSON 数据，包含每个题目的坐标 [ymin, xmin, ymax, xmax] 和对应的题号。
2. 深度推理与评分（Deep Reasoning & Grading）： 使用 Gemini 3.0 Pro。
   * 任务： 接收被裁剪的题目图像和评分细则（Rubric），执行 Agentic 推理。
   * 优势： 利用其强大的 Agentic 能力和视觉推理能力，模型可以模拟人类教师的阅卷过程：先通读全解，再逐步核对关键步骤，最后给出得分理由。对于模糊不清的手写体，Gemini 3.0 Pro 的“Vibe Coding”能力能够结合上下文进行意图推断，而非简单的字符匹配。
3. 系统宏观架构设计
本系统采用基于事件驱动的微服务架构（Event-Driven Microservices Architecture），核心组件通过异步消息传递和工作流编排进行解耦，以满足高并发和水平扩展的需求。
3.1 核心组件拓扑
系统逻辑上分为三层：接入层、编排层、认知计算层。
3.1.1 接入层（Ingestion Layer）
* API Gateway (FastAPI/Nginx): 系统的统一入口，负责鉴权、流控和请求路由。它不处理具体的业务逻辑，仅负责接收前端（学生端 App 或教师端 Web）上传的 PDF/图像流。
* Submission Service: 负责处理上传文件的预处理（如 PDF 转图片）、元数据校验，并将其持久化到对象存储（S3/MinIO）。一旦文件落盘成功，该服务即向 Temporal Cluster 发起一个 StartWorkflow 信号，随后立即返回 submission_id 给客户端，实现异步处理。
3.1.2 编排层（Orchestration Layer）
* Temporal Cluster: 系统的心脏，负责维护所有批改任务的状态机。它由 History Service、Matching Service、Frontend Service 和 Worker Service 组成。Temporal 保证了即使在 Cognitive Worker 崩溃或重启的情况下，批改任务也不会丢失，而是会从断点处重试。
* Orchestration Worker: 运行轻量级的流程逻辑，负责调度 Activity，但不执行繁重的计算任务。它决定了何时进行页面分割、何时并发启动题目批改、何时汇总分数以及何时触发人工审核。
3.1.3 认知计算层（Cognitive Layer）
* Cognitive Worker Pool: 这是系统资源消耗最大的部分，由一组无状态的 Python 服务组成。这些 Worker 专门用于执行 Temporal Activity，内部封装了 LangGraph Agent 和 Gemini API Client。
* LangGraph Runtime: 运行在 Activity 内部，负责管理单道题目的微观推理循环（Loop）。它维护着题目的短期记忆（State），并控制模型在“看图”、“查分”、“反思”之间的状态流转。
3.1.4 数据存储层（Persistence Layer）
* PostgreSQL (Primary Datastore): 存储用户信息、作业元数据、评分细则（Rubric）以及最终的批改结果。利用 PG 的 JSONB 字段存储 LangGraph 的 Checkpoint，实现推理过程的可追溯性。
* Redis (Hot Data & Caching): 用于语义缓存（Semantic Cache）、分布式锁（针对同一试卷的重复提交）以及 API 速率限制（Rate Limiting）的令牌桶存储。
3.2 高并发与水平扩展策略
为了满足“生产级”要求，架构设计必须应对突发流量（如考试结束后的提交洪峰）。
1. Worker 分离策略： 我们将 IO 密集型任务（如通知发送、状态更新）与 GPU/API 密集型任务（如图像分析、大模型推理）分配到不同的 Temporal Task Queue 中。
   * default-queue: 处理流程控制、数据库写入、通知推送。
   * vision-compute-queue: 专门处理 Gemini API 调用和 LangGraph 推理。
这种分离允许我们根据 ScheduleToStartLatency 指标，利用 Kubernetes KEDA 独立扩缩容 vision-compute-queue 的 Pod 数量，而不必浪费资源在轻量级任务上。
   2. 异步扇出（Async Fan-Out）： 对于一份包含 20 道题的试卷，Temporal Workflow 会采用 Scatter-Gather 模式，并行生成 20 个子任务（Activity 或 Child Workflow）。这些任务被分发到整个集群中并行执行，极大地缩短了单份试卷的端到端批改时间（Latency）。
4. Temporal 工作流编排设计详情
Temporal 在本架构中不仅是任务调度器，更是业务逻辑的“状态持有者”。我们利用 Python SDK 定义了一套健壮的父子工作流体系。
4.1 工作流层级定义
为了隔离故障域并简化重试逻辑，我们将批改流程拆分为父工作流（Parent Workflow）和子工作流（Child Workflow）。
4.1.1 试卷级父工作流 (ExamPaperWorkflow)
该工作流负责管理一份完整试卷的生命周期。
   * 输入： submission_id, student_id, exam_id, file_paths。
   * 状态空间： UPLOADED -> SEGMENTING -> GRADING -> REVIEWING -> COMPLETED。
   * 主要逻辑：
   1. 执行分割 Activity： 调用 SegmentDocumentActivity，传入整卷图像，获取题目坐标列表。
   2. 动态扇出（Dynamic Fan-Out）： 遍历分割结果中的每一个题目区域（Region），为每一个题目启动一个 QuestionGradingChildWorkflow。这里使用的是 execute_child_workflow 而非简单的 Activity，目的是为了让每道题的批改具备独立的生命周期管理（例如，某道题卡住了，不影响其他题目的批改和状态查询）。
   3. 聚合结果（Fan-In）： 使用 asyncio.gather 等待所有子工作流完成。
   4. 质量门控（Quality Gate）： 汇总所有题目的置信度分数（Confidence Score）。如果任意一题的置信度低于预设阈值（如 0.75），则将工作流状态流转至 REVIEWING，并挂起等待人工介入信号。
   5. 持久化与通知： 将最终结果写入 PostgreSQL，并推送通知给客户端。
4.1.2 题目级子工作流 (QuestionGradingChildWorkflow)
该工作流负责单道题目的精细化批改。
   * 输入： question_id, image_crop_metadata, rubric_text。
   * 主要逻辑：
   1. 语义缓存检查 Activity： 计算图像区域的哈希值，查询 Redis 是否存在完全相同的已批改记录（常见于选择题或填空题）。若命中缓存，直接返回结果，跳过 LLM 调用。
   2. 执行推理 Activity： 调用 LangGraphReasoningActivity。这是消耗成本最高的一步，需配置严格的重试策略（RetryPolicy）以应对 API 限流。
   3. 结果标准化： 校验 LLM 返回的 JSON 格式是否符合 Schema 要求。
4.2 关键 Temporal 模式应用
4.2.1 信号（Signals）与人工介入 (Human-in-the-Loop)
在生产环境中，AI 并非总是可信的。当系统遇到低置信度结果时，必须能够“暂停”并等待人类指令。Temporal 的 Signal 机制完美支持这一场景 6。
实现逻辑：
父工作流在聚合阶段如果发现 low_confidence 标志为真，将进入一个 workflow.wait_condition 状态。此时工作流实际上是“休眠”的，不消耗任何计算资源。


Python




# Temporal Workflow 代码片段示意
@workflow.run
async def run(self, input_data: ExamInput):
   #... (前序批改逻辑)
   
   if self.requires_human_review(results):
       # 触发通知 Activity
       await workflow.execute_activity("NotifyTeacherForReview",...)
       
       # 挂起工作流，等待信号
       # self.review_action 是由 Signal Handler 修改的成员变量
       await workflow.wait_condition(lambda: self.review_action is not None)
       
       if self.review_action == "REJECT":
           raise ApplicationError("Submission rejected by human reviewer")
       elif self.review_action == "OVERRIDE":
           results = self.apply_human_override(results)

   #... (后续持久化逻辑)

@workflow.signal
def review_signal(self, action: str, override_data: dict):
   self.review_action = action
   self.human_override_data = override_data

4.2.2 确定性与非确定性分离
Temporal 要求 Workflow 代码必须是确定性的（Deterministic），即相同的输入必须产生相同的命令序列。然而，LangGraph Agent 的推理过程本质上是非确定性的（LLM 的输出每次可能不同）。
解决方案：
我们将 LangGraph 的执行完全封装在 Activity 中。Temporal Activity 允许包含非确定性代码（API 调用、随机数、IO 操作）。Workflow 只负责调度 Activity 并记录其返回结果。无论 Activity 内部重试了多少次，或者 LLM 思考了多久，对于 Workflow 历史记录（History）而言，它只是一个输入输出确定的“原子操作”。
5. LangGraph 题内智能体设计详情
LangGraph 是本系统的认知引擎。与传统的线性 Chain 不同，Graph 结构允许 Agent 在“批改”和“反思”之间循环，直到达成逻辑自洽。
5.1 状态定义 (GradingState)
LangGraph 的核心是 State，它是图节点间传递的共享上下文。


Python




from typing import TypedDict, List, Optional, Annotated
import operator

class GradingState(TypedDict):
   # 静态输入数据
   question_image: str  # Base64 编码的题目图像
   rubric: str          # 评分细则
   standard_answer: str # 标准答案（可选）
   
   # 动态推理数据
   vision_analysis: str # 对图像的文字描述
   initial_score: float
   reasoning_trace: List[str] # 推理步骤记录
   critique_feedback: str     # 自我反思的意见
   final_score: float
   confidence: float
   
   # 控制标志
   revision_count: int  # 循环修正次数
   is_finalized: bool

5.2 节点（Nodes）设计
我们将评分过程拆解为四个核心节点：
   1. VisionExtractionNode (Vision-Native Analysis):
   * 模型： Gemini 3.0 Pro。
   * Prompt 策略： "请充当人类助教。详细描述图像中的学生解题步骤，包括所有的公式推导、图表绘制和文字说明。不要进行评分，仅客观描述。"
   * 目的： 将视觉信息显式化为中间的语义表征（Semantic Representation），为后续评分提供依据。
   2. RubricMappingNode (Alignment):
   * 模型： Gemini 3.0 Pro。
   * Prompt 策略： 接收 vision_analysis 和 rubric。逐条核对评分点（Point）。例如：“Rubric 要求列出动量守恒方程，学生的第 2 行推导符合此要求，得 2 分。”
   3. CritiqueNode (Self-Reflection):
   * 模型： Gemini 3.0 Pro (High Reasoning Mode)。
   * Prompt 策略： "你是一个极其严格的质检员。请审查上述的评分建议。评分是否过高？是否忽略了图像右上角的计算错误？如果存在疑点，请给出具体的修改建议。"
   * 逻辑： 这是一个关键的质量控制环节。如果模型发现评分逻辑存在漏洞，它会生成 critique_feedback 并将状态推回评分节点。
   4. FinalizationNode:
   * 逻辑： 格式化最终输出，生成 JSON 结构，包含分数、评语和 bounding box 高亮坐标（如果模型指出了具体错误位置）。
5.3 图的拓扑结构与持久化
图的边（Edges）定义了控制流：
   * Start -> VisionExtractionNode -> RubricMappingNode -> CritiqueNode
   * CritiqueNode -> (Conditional Edge):
   * 如果 critique_feedback 为空或 revision_count > 2 -> FinalizationNode -> End
   * 如果存在 critique_feedback -> RubricMappingNode (带上反馈重新打分)
持久化 (Persistence) 设计：
为了支持生产级的调试和审计，我们使用 PostgresSaver 8。
LangGraph 的每一次状态转换（Super-step）都会被序列化并保存到 PostgreSQL 的 checkpoints 表中。thread_id 设置为 submission_id + question_id。
这意味着：
   1. 审计追踪： 教师可以随时查看 AI 是如何一步步得出分数的（如：“在第 2 次循环中，AI 发现了之前的漏判”）。
   2. 断点恢复： 理论上支持在 Activity 重试时加载之前的 Checkpoint，但在本架构中，为了简化，我们通常选择在 Activity 层面重试整个 Graph。
6. 数据工程与存储层设计
6.1 PostgreSQL Schema 设计 (JSONB 深度应用)
我们利用 PostgreSQL 强大的 JSONB 能力来存储非结构化的批改结果，这避免了频繁修改 Schema 以适应不同学科（如英语作文 vs 数学题）的评分结构差异 9。


SQL




-- 核心评分结果表
CREATE TABLE grading_results (
   submission_id UUID NOT NULL,
   question_id VARCHAR(50) NOT NULL,
   exam_id UUID NOT NULL,
   student_id UUID NOT NULL,
   
   -- 核心分数字段
   score DECIMAL(5, 2),
   max_score DECIMAL(5, 2),
   confidence_score DECIMAL(3, 2),
   
   -- 视觉锚点数据 (Vision-Native 的关键)
   -- 存储格式: {"box_2d": [ymin, xmin, ymax, xmax], "page_index": 0}
   -- 用于前端在原图上绘制红框
   visual_annotations JSONB, 
   
   -- AI 推理全链路 (来自 LangGraph State)
   -- 包含: {"vision_analysis": "...", "reasoning_steps": [...], "critique": "..."}
   agent_trace JSONB,
   
   -- 结构化反馈 (用于生成学生报告)
   student_feedback JSONB,
   
   created_at TIMESTAMPTZ DEFAULT NOW(),
   updated_at TIMESTAMPTZ DEFAULT NOW(),
   
   PRIMARY KEY (submission_id, question_id)
);

-- 索引优化
-- 针对 JSONB 内部字段建立 GIN 索引，加速查询
CREATE INDEX idx_grading_results_feedback ON grading_results USING GIN (student_feedback);

6.2 Redis 缓存设计策略
   1. Semantic Deduplication (语义去重):
   * Key: grade_cache:v1:{rubric_hash}:{image_perceptual_hash}
   * Value: 评分结果 JSON。
   * 逻辑： 在批改填空题或选择题时，大量学生的答案图像在视觉上高度相似。我们计算图像的感知哈希（Perceptual Hash），如果发现已有相同的图像被高置信度地批改过，则直接复用结果。这能显著降低 Gemini API 的调用成本。
   2. Rate Limiting (限流):
   * 利用 Redis 的原子计数器实现滑动窗口算法，严格控制每分钟对 Gemini API 的并发请求数，防止触发 Provider 的 429 Too Many Requests 错误，保护系统的稳定性。
7. 纯视觉管线实现细节 (Vision-Native Pipeline)
7.1 PDF 到高保真图像的转换
纯视觉方案对图像质量高度敏感。我们不使用普通的缩略图，而是使用 pdf2image 库将 PDF 渲染为高分辨率图像 11。
   * 参数配置： dpi=300 (保证手写笔迹清晰)，fmt='jpeg' (平衡质量与体积)。
   * 工程细节： 为了避免 I/O 瓶颈，这一步在 Submission Service 中通过内存流（BytesIO）处理，或直接流式上传到 S3，尽量减少本地磁盘写入。
7.2 智能坐标映射 (Coordinate Mapping)
Gemini 2.5 Flash Lite 返回的 bounding box 坐标通常是归一化到 `` 区间的相对值 13。为了在前端准确显示，必须进行坐标还原。


Python




def normalize_coordinates(box_1000: list, img_width: int, img_height: int) -> list:
   """
   将 Gemini 的 [ymin, xmin, ymax, xmax] (0-1000 scale)
   转换为像素坐标 [y_min_px, x_min_px, y_max_px, x_max_px]
   """
   ymin, xmin, ymax, xmax = box_1000
   return [
       int(ymin / 1000 * img_height),
       int(xmin / 1000 * img_width),
       int(ymax / 1000 * img_height),
       int(xmax / 1000 * img_width)
   ]

7.3 Set-of-Mark (SoM) 提示策略
为了提高 Gemini 3.0 Pro 在复杂版面（如连线题、包含多个子图的物理题）上的定位精度，我们可以在 Prompt 中采用 Set-of-Mark 思想 15。
在发送给评分模型之前，我们在原始图像上通过 OpenCV 预先叠加半透明的数字标记或网格。这为模型提供了一个显式的坐标参考系，使其能够说出：“错误出现在标记 3 的区域”，而非模糊的“左上角”。
8. 关键代码骨架 (Python)
以下代码展示了如何将 Temporal Activity 与 LangGraph 结合，实现具体的批改逻辑。
8.1 Temporal Activity 封装 LangGraph


Python




import asyncio
from temporalio import activity
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres import PostgresSaver
from langchain_google_genai import ChatGoogleGenerativeAI
import psycopg
from my_types import GradingState, QuestionInput

# 数据库连接池（在 Worker 启动时初始化）
db_pool = psycopg_pool.AsyncConnectionPool(conninfo="postgresql://user:pass@db:5432/grading_db")

@activity.defn
async def grade_question_activity(input_data: QuestionInput) -> dict:
   """
   Temporal Activity: 负责单道题目的智能批改
   包含 LangGraph 的完整生命周期管理
   """
   activity.logger.info(f"Starting grading for QID: {input_data.question_id}")

   # 1. 构造 LangGraph
   # 使用 Gemini 3.0 Pro 进行推理
   llm = ChatGoogleGenerativeAI(
       model="gemini-3.0-pro",
       temperature=0.2, # 保持低随机性以增加稳定性
       google_api_key=activity.info().workflow_execution.run_id # 或从 Secret 获取
   )
   
   workflow = StateGraph(GradingState)
   
   # 定义节点函数 (省略具体 Prompt 实现细节)
   async def vision_node(state):
       # 调用 Gemini Vision API 分析图像
       return {"vision_analysis": "..."}
       
   async def scoring_node(state):
       # 基于 vision_analysis 和 rubric 打分
       return {"current_score": 5.0, "reasoning": "..."}
       
   async def critic_node(state):
       # 自我反思
       if state['current_score'] > 4 and "error" in state['vision_analysis']:
            return {"critique_feedback": "Score too high for error...", "revision_count": state['revision_count'] + 1}
       return {"critique_feedback": None, "is_finalized": True}

   # 添加节点与边
   workflow.add_node("vision", vision_node)
   workflow.add_node("scorer", scoring_node)
   workflow.add_node("critic", critic_node)
   
   workflow.set_entry_point("vision")
   workflow.add_edge("vision", "scorer")
   workflow.add_edge("scorer", "critic")
   
   def check_revision(state):
       if state.get("is_finalized") or state.get("revision_count", 0) > 2:
           return END
       return "scorer" # 反馈驱动循环
       
   workflow.add_conditional_edges("critic", check_revision)

   # 2. 设置持久化 (Persistence)
   # 使用 question_id 作为 thread_id，确保每次 Activity 重试都能从（逻辑上的）新起点开始，
   # 或者如果需要断点续传，可以使用相同的 thread_id 读取之前的 state。
   # 这里我们选择每次全新的 thread_id 以避免重试时的状态污染，但记录到 DB 用于审计。
   thread_id = f"{input_data.submission_id}_{input_data.question_id}"
   
   async with db_pool.connection() as conn:
       checkpointer = PostgresSaver(conn)
       app = workflow.compile(checkpointer=checkpointer)
       
       # 3. 执行 Graph
       initial_state = {
           "question_image": input_data.image_b64,
           "rubric": input_data.rubric,
           "revision_count": 0
       }
       
       config = {"configurable": {"thread_id": thread_id}}
       
       # 异步调用 LangGraph
       final_state = await app.ainvoke(initial_state, config=config)
       
   # 4. 返回结果给 Temporal Workflow
   return {
       "score": final_state["final_score"],
       "feedback": final_state["reasoning_trace"][-1],
       "confidence": final_state.get("confidence", 0.9)
   }

8.2 Temporal Workflow 定义 (Fan-Out)


Python




from datetime import timedelta
from temporalio import workflow
from my_activities import grade_question_activity, segment_document_activity

@workflow.defn
class ExamPaperWorkflow:
    @workflow.run
   async def run(self, submission_data: SubmissionData):
       # 1. 纯视觉分割 (Gemini 2.5 Flash Lite)
       segmentation_result = await workflow.execute_activity(
           segment_document_activity,
           submission_data,
           start_to_close_timeout=timedelta(minutes=5)
       )
       
       # 2. 扇出 (Fan-Out): 并行批改所有题目
       grading_futures =
       for region in segmentation_result.regions:
           # 为每个题目构造输入
           q_input = QuestionInput(
               submission_id=submission_data.id,
               question_id=region.id,
               image_b64=region.image_data, # 实际应传 S3 key
               rubric=region.rubric
           )
           
           # 异步启动 Activity
           future = workflow.execute_activity(
               grade_question_activity,
               q_input,
               start_to_close_timeout=timedelta(minutes=3),
               retry_policy=RetryPolicy(maximum_attempts=3)
           )
           grading_futures.append(future)
           
       # 3. 扇入 (Fan-In): 等待所有结果
       # return_exceptions=True 允许部分失败
       results = await asyncio.gather(*grading_futures, return_exceptions=True)
       
       # 4. 异常处理与聚合
       final_grades =
       requires_review = False
       
       for res in results:
           if isinstance(res, Exception):
               requires_review = True # 只要有一题失败，整卷转人工
           elif res['confidence'] < 0.8:
               requires_review = True
           else:
               final_grades.append(res)
               
       if requires_review:
           # 触发人工审核流程 (Signal Pattern)
           await self.wait_for_human_review()
           
       return final_grades

9. 质量控制与评估体系
为了确保 AI 批改的公正性和准确性，系统必须内置严格的质量控制（QC）机制。
9.1 黄金数据集验证 (Golden Set Validation)
在每次部署新的 Prompt 或模型版本更新前，系统会自动运行 CI/CD 管道中的评估脚本。该脚本会在“黄金数据集”（由资深教师标注的 500 份样卷）上运行批改流程。
   * 指标： 计算 AI 评分与人工评分的 Pearson 相关系数（Pearson Correlation Coefficient）和 Cohen's Kappa 系数。
   * 阈值： 只有当相关系数 > 0.9 且 Kappa > 0.8 时，新版本才会被允许发布到生产环境。
9.2 在线一致性监测
在生产运行中，系统随机抽取 5% 的高置信度试卷发送给人工复核（Double Blind Review）。如果发现 AI 评分与人工评分存在显著偏差，系统将自动触发报警，并将相关题目特征（如特定的手写风格、特定的题型）标记为“低置信度”，在后续批改中强制降级为人工审核，直到模型微调（Fine-tuning）修正该偏差为止。
10. 结论
本报告提出的架构方案通过深度整合 Temporal 的编排能力与 LangGraph 的推理能力，成功构建了一个无需 OCR 介入的纯视觉批改系统。该系统利用 Gemini 3.0 Pro 的先进推理能力解决了传统方案在语义理解上的痛点，同时通过 Gemini 2.5 Flash Lite 和 Redis 缓存策略有效控制了运营成本。基于 JSONB 的数据持久化和 KEDA 驱动的水平扩展设计，进一步确保了系统在生产环境下的灵活性与高可用性。这不仅是一次技术架构的升级，更是对自动化评估领域“机器视觉优先”理念的工程化实践。
Works cited
   1. Release notes | Gemini API - Google AI for Developers, accessed December 7, 2025, https://ai.google.dev/gemini-api/docs/changelog
   2. Gemini 3 Pro | Generative AI on Vertex AI - Google Cloud Documentation, accessed December 7, 2025, https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models/gemini/3-pro
   3. accessed December 7, 2025, https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models/gemini/2-5-flash-lite#:~:text=It%20comes%20with%20the%20same,1%20million%2Dtoken%20context%20length.
   4. Gemini 2.5 Flash-Lite - Google DeepMind, accessed December 7, 2025, https://deepmind.google/models/gemini/flash-lite/
   5. Gemini 2.5 Flash-Lite | Generative AI on Vertex AI - Google Cloud Documentation, accessed December 7, 2025, https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models/gemini/2-5-flash-lite
   6. Part 2: Adding Durable Human-in-the-Loop to Our Research Application | Learn Temporal, accessed December 7, 2025, https://learn.temporal.io/tutorials/ai/building-durable-ai-applications/human-in-the-loop/
   7. Human dependent long running Workflows - Community Support - Temporal, accessed December 7, 2025, https://community.temporal.io/t/human-dependent-long-running-workflows/3403
   8. Memory - Docs by LangChain, accessed December 7, 2025, https://docs.langchain.com/oss/python/langgraph/add-memory
   9. Documentation: 18: 8.14. JSON Types - PostgreSQL, accessed December 7, 2025, https://www.postgresql.org/docs/current/datatype-json.html
   10. JSONB: PostgreSQL's Secret Weapon for Flexible Data Modeling | by Rick Hightower, accessed December 7, 2025, https://medium.com/@richardhightower/jsonb-postgresqls-secret-weapon-for-flexible-data-modeling-cf2f5087168f
   11. Convert PDF to Images with Python - DOCSAID, accessed December 7, 2025, https://docsaid.org/en/blog/convert-pdf-to-images/
   12. Belval/pdf2image: A python module that wraps the pdftoppm utility to convert PDF to PIL Image object - GitHub, accessed December 7, 2025, https://github.com/Belval/pdf2image
   13. Building a tool showing how Gemini Pro can return bounding boxes for objects in images, accessed December 7, 2025, https://simonwillison.net/2024/Aug/26/gemini-bounding-box-visualization/
   14. 7 examples of Gemini's multimodal capabilities in action - Google Developers Blog, accessed December 7, 2025, https://developers.googleblog.com/en/7-examples-of-geminis-multimodal-capabilities-in-action/
   15. Set-of-Mark Prompting Unleashes Extraordinary Visual Grounding in GPT-4V | Qiang Zhang, accessed December 7, 2025, https://zhangtemplar.github.io/prompt-mark-gpt4v/
   16. [2310.11441] Set-of-Mark Prompting Unleashes Extraordinary Visual Grounding in GPT-4V, accessed December 7, 2025, https://arxiv.org/abs/2310.11441