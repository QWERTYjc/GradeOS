# Requirements Document

## Introduction

批改工作流系统重构 v2 是 GradeOS 平台的核心功能升级，旨在实现一个支持人机交互的智能批改工作流。该系统采用双阶段批改（视觉模型+文本模型）、工作流暂停态设计、SQLite 持久化存储，并与现有班级系统深度集成。核心目标是让老师能够一键触发批改，在关键节点进行人工审核和修正，最终生成高质量的批改结果和学生总结。

## Glossary

- **Grading_Workflow_System**: 批改工作流系统，负责协调整个批改流程的执行
- **Workflow_State**: 工作流状态，包括 running、waiting_for_human、completed、failed
- **Pause_Point**: 暂停点，工作流需要人工介入的检查点，包括 rubric_review（评分标准检查）和 grading_review（批改结果检查）
- **Vision_Model**: 视觉模型，用于从图片中提取内容并进行初步批改
- **Text_Model**: 文本模型，用于深度批改和生成详细评语
- **Grading_Self_Report**: 批改自白，AI 生成的批改过程说明，用于辅助用户查漏补缺
- **Student_Summary**: 学生总结，针对每个学生生成的批改结果摘要
- **Student_Boundary**: 学生边界，用于在批量图片中识别不同学生答卷的分隔信息
- **Rubric**: 评分标准，定义题目的评分规则和得分点
- **LLM_Client**: 统一的大语言模型客户端，支持 OpenRouter 适配
- **SQLite_Database**: 轻量级数据库，用于持久化工作流状态和批改结果

## Requirements

### Requirement 1

**User Story:** As a teacher, I want to upload student answer images and trigger one-click grading, so that I can efficiently grade multiple students' work without manual intervention.

#### Acceptance Criteria

1. WHEN a teacher uploads images with student boundary information THEN the Grading_Workflow_System SHALL preprocess images to JPEG format and initiate the grading workflow
2. WHEN the grading workflow starts THEN the Grading_Workflow_System SHALL parse the rubric from uploaded materials and extract scoring criteria
3. WHEN images are preprocessed THEN the Grading_Workflow_System SHALL validate image format and quality before proceeding
4. WHEN a teacher clicks the one-click grading button THEN the Grading_Workflow_System SHALL create a new grading history record and begin processing

### Requirement 2

**User Story:** As a teacher, I want to review and modify the parsed rubric before grading proceeds, so that I can ensure the scoring criteria are accurate.

#### Acceptance Criteria

1. WHEN the rubric parsing completes THEN the Grading_Workflow_System SHALL enter WAITING_FOR_HUMAN state at the rubric_review Pause_Point
2. WHILE the workflow is at rubric_review Pause_Point THEN the Grading_Workflow_System SHALL display the parsed rubric for teacher review
3. WHEN a teacher modifies the rubric THEN the Grading_Workflow_System SHALL allow re-parsing of selected questions
4. WHEN a teacher confirms the rubric THEN the Grading_Workflow_System SHALL resume workflow execution and proceed to student grading
5. WHILE waiting for human review THEN the Grading_Workflow_System SHALL persist workflow state to SQLite_Database without timeout

### Requirement 3

**User Story:** As a teacher, I want the system to grade students in parallel using a two-stage model approach, so that grading is both fast and accurate.

#### Acceptance Criteria

1. WHEN rubric is confirmed THEN the Grading_Workflow_System SHALL split students by boundary and create parallel grading workers
2. WHEN a grading worker processes a student THEN the Vision_Model SHALL extract content from images and perform initial grading
3. WHEN initial grading completes THEN the Text_Model SHALL perform deep grading with detailed feedback
4. WHEN deep grading completes THEN the Grading_Workflow_System SHALL generate a Grading_Self_Report for each student
5. WHEN all parallel workers complete THEN the Grading_Workflow_System SHALL aggregate results and proceed to review

### Requirement 4

**User Story:** As a teacher, I want to review grading results and make corrections before finalizing, so that I can ensure grading quality and fix any AI mistakes.

#### Acceptance Criteria

1. WHEN all student grading completes THEN the Grading_Workflow_System SHALL enter WAITING_FOR_HUMAN state at the grading_review Pause_Point
2. WHILE at grading_review Pause_Point THEN the Grading_Workflow_System SHALL display grading results with Grading_Self_Report for each student
3. WHEN a teacher modifies a grading result THEN the Grading_Workflow_System SHALL update the student's score and feedback
4. WHEN a teacher confirms all results THEN the Grading_Workflow_System SHALL generate Student_Summary for each student
5. WHEN results are confirmed THEN the Grading_Workflow_System SHALL mark workflow as completed and persist final results

### Requirement 5

**User Story:** As a teacher, I want to import grading results into the class system, so that students can view their grades and I can track class performance.

#### Acceptance Criteria

1. WHEN grading workflow completes THEN the Grading_Workflow_System SHALL provide option to import results to class system
2. WHEN importing to class THEN the Grading_Workflow_System SHALL map student_key to student_id using provided mapping
3. WHEN import succeeds THEN the Grading_Workflow_System SHALL update student_grading_results with class_id and student_id
4. WHEN a teacher requests class grading history THEN the Grading_Workflow_System SHALL return all grading records for that class
5. WHEN a teacher revokes imported results THEN the Grading_Workflow_System SHALL mark results as revoked and update status

### Requirement 6

**User Story:** As a teacher, I want to view grading history and resume interrupted workflows, so that I can manage ongoing and past grading sessions.

#### Acceptance Criteria

1. WHEN a teacher views grading history THEN the Grading_Workflow_System SHALL display all grading_history records with status
2. WHEN a workflow is in WAITING_FOR_HUMAN state THEN the Grading_Workflow_System SHALL allow resuming from the saved Pause_Point
3. WHEN resuming a workflow THEN the Grading_Workflow_System SHALL restore state_data from SQLite_Database and continue execution
4. WHEN a workflow fails THEN the Grading_Workflow_System SHALL persist error state and allow retry or manual intervention

### Requirement 7

**User Story:** As a developer, I want a unified LLM client that supports OpenRouter, so that I can easily switch between different AI models.

#### Acceptance Criteria

1. WHEN the LLM_Client is initialized THEN the Grading_Workflow_System SHALL load configuration from backend/src/config/llm.py
2. WHEN making LLM requests THEN the LLM_Client SHALL route requests through OpenRouter with configured model
3. WHEN parsing rubric THEN the LLM_Client SHALL handle ScoringPoint extraction with proper error handling
4. WHEN generating grading feedback THEN the LLM_Client SHALL return structured response matching expected schema

### Requirement 8

**User Story:** As a teacher, I want to see grading history in the class detail page, so that I can track all grading activities for a class.

#### Acceptance Criteria

1. WHEN viewing class detail page THEN the Frontend SHALL display a "批改历史" Tab showing grading records
2. WHEN clicking a grading record THEN the Frontend SHALL navigate to the grading results review page
3. WHEN viewing homework management page THEN the Frontend SHALL display a "一键批改" button for triggering grading
4. WHEN viewing submission records THEN the Frontend SHALL provide "查看批改详情" link to grading results
