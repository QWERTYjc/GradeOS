# Requirements Document

## Introduction

前端改进 v1 是 GradeOS 平台的前端功能升级，旨在实现完整的教师-学生作业提交与 AI 批改工作流。该系统包括教师端 Rubric 上传、学生端扫描提交、API 服务优化、以及 Console 页面改进。核心目标是让教师能够创建带评分标准的作业，学生能够通过扫描/上传方式提交作业，并自动触发 AI 批改。

## Glossary

- **Rubric**: 评分标准，教师上传的评分规则图片，用于指导 AI 批改
- **Scanner_Component**: 扫描组件，用于通过摄像头或文件上传获取图片
- **Gallery_Component**: 图库组件，用于展示和管理已上传的图片
- **AppContext**: 应用上下文，用于在组件间共享扫描会话状态
- **Submission**: 学生提交记录，包含作答图片和批改结果
- **Base64_Image**: Base64 编码的图片数据，用于存储和传输图片
- **PDF_Processing**: PDF 处理功能，将 PDF 文件转换为图片
- **Console_Page**: AI 批改控制台页面，用于执行和管理批改任务

## Requirements

### Requirement 1: 教师端 Rubric 上传

**User Story:** As a teacher, I want to upload rubric images when creating homework, so that the AI grading system can use them as scoring criteria.

#### Acceptance Criteria

1. WHEN a teacher opens the homework creation modal THEN the Frontend SHALL display a Rubric upload section with Scanner and Gallery components
2. WHEN a teacher clicks "扫描" tab THEN the Scanner_Component SHALL allow camera capture or file import
3. WHEN a teacher uploads images or PDF THEN the Scanner_Component SHALL convert them to Base64_Image format
4. WHEN a teacher clicks "已上传" tab THEN the Gallery_Component SHALL display all uploaded Rubric images
5. WHEN a teacher submits the homework form THEN the Frontend SHALL include rubric_images in the API request
6. IF the Rubric upload fails THEN the Frontend SHALL display an error message and allow retry

### Requirement 2: 学生端扫描提交

**User Story:** As a student, I want to scan or upload my homework answers, so that I can submit them for AI grading.

#### Acceptance Criteria

1. WHEN a student clicks "📸 扫描提交" button on dashboard THEN the Frontend SHALL redirect to scan page with homework_id parameter
2. WHEN the scan page loads THEN the Frontend SHALL display homework title and deadline from backend
3. WHEN a student uses Scanner_Component THEN the Frontend SHALL allow camera capture or file import
4. WHEN a student uploads PDF files THEN the PDF_Processing SHALL extract all pages as images
5. WHEN a student clicks "提交" button THEN the Frontend SHALL call homeworkApi.submitScan() with images
6. WHEN submission succeeds THEN the Frontend SHALL clear the scan session and show success message
7. IF submission fails THEN the Frontend SHALL display error message and allow retry

### Requirement 3: PDF 处理功能

**User Story:** As a user, I want to upload PDF files and have them automatically converted to images, so that I can use PDF documents as rubric or homework answers.

#### Acceptance Criteria

1. WHEN a user selects a PDF file THEN the PDF_Processing SHALL initialize PDF.js library
2. WHEN PDF.js initializes THEN the PDF_Processing SHALL load worker from CDN
3. WHEN parsing PDF THEN the PDF_Processing SHALL extract up to 80 pages
4. WHEN rendering each page THEN the PDF_Processing SHALL convert to JPEG image with 0.9 quality
5. WHEN PDF processing completes THEN the PDF_Processing SHALL return array of Base64_Image
6. IF PDF processing fails THEN the PDF_Processing SHALL log error and display user-friendly message

### Requirement 4: API 服务更新

**User Story:** As a developer, I want the API client to support rubric_images field, so that the frontend can send rubric data to backend.

#### Acceptance Criteria

1. WHEN calling homeworkApi.create() THEN the API_Client SHALL accept optional rubric_images parameter
2. WHEN receiving homework response THEN the API_Client SHALL parse rubric_images field
3. WHEN calling homeworkApi.submitScan() THEN the API_Client SHALL send images array to backend
4. WHEN API call fails THEN the API_Client SHALL throw error with descriptive message

### Requirement 5: Console 页面改进

**User Story:** As a teacher, I want to use the AI grading console to manage grading tasks, so that I can review and control the grading process.

#### Acceptance Criteria

1. WHEN Console page loads with homework_id THEN the Frontend SHALL automatically load student submissions
2. WHEN teacher uploads rubric THEN the Console SHALL display rubric preview
3. WHEN grading starts THEN the Console SHALL show progress indicator
4. WHEN grading completes THEN the Console SHALL display results with scores and feedback
5. WHEN teacher reviews results THEN the Console SHALL allow modifications before finalizing

### Requirement 6: 错误处理与用户反馈

**User Story:** As a user, I want clear error messages and loading indicators, so that I know what's happening during file processing.

#### Acceptance Criteria

1. WHEN file processing starts THEN the Frontend SHALL display "Processing files..." message
2. WHEN file processing succeeds THEN the Frontend SHALL display success message with file count
3. WHEN file processing fails THEN the Frontend SHALL display specific error message
4. WHEN unsupported file type is selected THEN the Frontend SHALL skip file and show warning
5. WHEN network request is in progress THEN the Frontend SHALL disable submit button and show loading state

