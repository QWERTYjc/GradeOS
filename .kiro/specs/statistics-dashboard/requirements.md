# Requirements Document

## Introduction

本文档定义了 GradeOS 平台教师端成绩统计看板功能的需求。该功能为教师提供全面的学生成绩数据视图，包括跨作业的成绩总览表格和单个作业的深度数据分析。

## Glossary

- **Statistics_Dashboard**: 成绩统计看板系统，负责展示和分析学生成绩数据
- **Score_Matrix**: 成绩矩阵表格，以学生为行、作业为列展示所有成绩
- **Homework_Analysis**: 作业分析模块，提供单个作业的统计指标和可视化
- **Box_Plot**: 箱线图组件，展示成绩分布的五数概括（最小值、Q1、中位数、Q3、最大值）
- **Score_Distribution**: 分数分布图，展示各分数段的学生人数
- **Teacher**: 教师用户，可查看其所管理班级的所有成绩数据
- **Student_Score_Row**: 学生成绩行数据，包含学生信息和各作业得分

## Requirements

### Requirement 1: 班级选择与数据加载

**User Story:** As a teacher, I want to select a class and view all grading data, so that I can analyze student performance across assignments.

#### Acceptance Criteria

1. WHEN a teacher visits the statistics page, THE Statistics_Dashboard SHALL display a class selector with all classes the teacher manages
2. WHEN a teacher selects a class, THE Statistics_Dashboard SHALL load all homework assignments and grading records for that class
3. WHILE data is loading, THE Statistics_Dashboard SHALL display a loading indicator
4. IF no grading data exists for the selected class, THEN THE Statistics_Dashboard SHALL display an empty state message

### Requirement 2: 成绩总览表格（Excel 风格）

**User Story:** As a teacher, I want to see all students' scores across all assignments in a spreadsheet-like view, so that I can quickly compare performance.

#### Acceptance Criteria

1. THE Score_Matrix SHALL display students as rows and homework assignments as columns
2. WHEN rendering the matrix, THE Score_Matrix SHALL show each student's score in the corresponding cell
3. WHEN a student has no score for an assignment, THE Score_Matrix SHALL display a dash or empty indicator
4. THE Score_Matrix SHALL calculate and display each student's total score and average score
5. THE Score_Matrix SHALL calculate and display each assignment's class average in a summary row
6. WHEN a teacher clicks on a score cell, THE Statistics_Dashboard SHALL navigate to the homework detail page

### Requirement 3: 作业详情页导航

**User Story:** As a teacher, I want to navigate to detailed analysis for each assignment, so that I can understand performance patterns.

#### Acceptance Criteria

1. WHEN a teacher clicks on an assignment column header, THE Statistics_Dashboard SHALL navigate to the homework analysis page
2. THE Statistics_Dashboard SHALL pass the homework ID as a URL parameter to the detail page
3. WHEN navigating to a non-existent homework, THE Homework_Analysis SHALL display a not found message

### Requirement 4: 作业统计指标

**User Story:** As a teacher, I want to see key statistics for each assignment, so that I can quickly assess class performance.

#### Acceptance Criteria

1. THE Homework_Analysis SHALL calculate and display the average score for the assignment
2. THE Homework_Analysis SHALL calculate and display the median score for the assignment
3. THE Homework_Analysis SHALL display the highest and lowest scores
4. THE Homework_Analysis SHALL calculate and display the standard deviation
5. THE Homework_Analysis SHALL display the total number of graded students

### Requirement 5: 箱线图可视化

**User Story:** As a teacher, I want to see a box-whisker diagram, so that I can understand the score distribution at a glance.

#### Acceptance Criteria

1. THE Box_Plot SHALL display the minimum, Q1, median, Q3, and maximum values
2. THE Box_Plot SHALL render outliers as individual points outside the whiskers
3. WHEN hovering over the box plot, THE Box_Plot SHALL display a tooltip with exact values
4. THE Box_Plot SHALL use consistent colors matching the design system

### Requirement 6: 分数分布图

**User Story:** As a teacher, I want to see how scores are distributed across ranges, so that I can identify performance clusters.

#### Acceptance Criteria

1. THE Score_Distribution SHALL group scores into configurable ranges (e.g., 0-59, 60-69, 70-79, 80-89, 90-100)
2. THE Score_Distribution SHALL display a bar chart showing student count per range
3. WHEN hovering over a bar, THE Score_Distribution SHALL display the exact count and percentage
4. THE Score_Distribution SHALL highlight the range containing the most students

### Requirement 7: 学生排名列表

**User Story:** As a teacher, I want to see students ranked by score, so that I can identify top performers and those needing help.

#### Acceptance Criteria

1. THE Homework_Analysis SHALL display a ranked list of students sorted by score descending
2. THE Homework_Analysis SHALL show rank number, student name, and score for each entry
3. THE Homework_Analysis SHALL visually distinguish top performers (e.g., top 3) and low performers (e.g., bottom 3)
4. WHEN multiple students have the same score, THE Homework_Analysis SHALL assign them the same rank

### Requirement 8: 数据导出功能

**User Story:** As a teacher, I want to export the score matrix to a file, so that I can use the data in other tools.

#### Acceptance Criteria

1. WHEN a teacher clicks the export button, THE Statistics_Dashboard SHALL generate a CSV file with all score data
2. THE exported CSV SHALL include student names, all assignment scores, totals, and averages
3. THE exported file name SHALL include the class name and export date

### Requirement 9: 响应式布局

**User Story:** As a teacher, I want the statistics page to work on different screen sizes, so that I can view data on various devices.

#### Acceptance Criteria

1. THE Statistics_Dashboard SHALL adapt layout for desktop (1024px+), tablet (768px-1023px), and mobile (<768px) screens
2. WHEN on mobile, THE Score_Matrix SHALL enable horizontal scrolling to view all columns
3. THE Box_Plot and Score_Distribution SHALL resize appropriately for smaller screens
