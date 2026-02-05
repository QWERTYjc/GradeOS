# Requirements Document

## Introduction

This document specifies the requirements for implementing three interconnected features in the GradeOS platform that leverage the working batch grading results data:

1. **Teacher Teaching Cockpit** - A comprehensive view for teachers to manage and review student grading results
2. **Student Mistake Analysis (错题本)** - An intelligent system for students to analyze their errors from grading data
3. **Student Progress Report (学习报告)** - A personalized learning progress dashboard based on grading history

These features connect the existing frontend pages to real grading data from the batch grading API (`/api/batch/results/{batch_id}`).

## Glossary

- **Teaching_Cockpit**: The teacher-facing dashboard component that displays batch grading results, student scores, and question-level details
- **Mistake_Analysis_System**: The student-facing error analysis module that extracts and categorizes wrong questions from grading history
- **Progress_Report_System**: The student-facing learning analytics module that generates personalized insights based on grading data
- **Grading_History_API**: The backend API endpoints that provide historical grading records (`/api/grading/history`)
- **Diagnosis_Report_API**: The backend API endpoint that generates student diagnosis reports (`/api/v1/diagnosis/report/{student_id}`)
- **Batch_Results_API**: The backend API endpoint that returns complete batch grading results (`/api/batch/results/{batch_id}`)
- **Student_Grading_Results**: Database table storing individual student grading results with question-level details
- **Wrong_Question**: A question where the student's score is less than the maximum possible score
- **Scoring_Point_Result**: Detailed breakdown of how points were awarded for each scoring criterion

## Requirements

### Requirement 1: Teacher Teaching Cockpit Data Integration

**User Story:** As a teacher, I want to view and manage batch grading results in the Teaching Cockpit, so that I can review student performance and provide feedback.

#### Acceptance Criteria

1. WHEN a teacher opens the Teaching Cockpit with a valid batch_id, THE Teaching_Cockpit SHALL fetch and display results from the Batch_Results_API
2. WHEN grading results are loaded, THE Teaching_Cockpit SHALL display each student's name, total score, max score, and percentage
3. WHEN a teacher expands a student result, THE Teaching_Cockpit SHALL display question-level details including question_id, score, max_score, feedback, and page_indices
4. WHEN a question has scoring_point_results, THE Teaching_Cockpit SHALL display the detailed scoring breakdown with point descriptions and awarded points
5. IF the Batch_Results_API returns an error, THEN THE Teaching_Cockpit SHALL display a user-friendly error message and retry option
6. WHEN results are displayed, THE Teaching_Cockpit SHALL sort students by score in descending order by default

### Requirement 2: Student Mistake Analysis Data Flow

**User Story:** As a student, I want to see my wrong questions extracted from grading history, so that I can focus on areas that need improvement.

#### Acceptance Criteria

1. WHEN a student opens the Mistake Analysis page, THE Mistake_Analysis_System SHALL fetch grading history from the Grading_History_API filtered by the student's class
2. WHEN grading history is loaded, THE Mistake_Analysis_System SHALL extract all questions where score < max_score as wrong questions
3. WHEN displaying wrong questions, THE Mistake_Analysis_System SHALL show question_id, score, max_score, feedback, student_answer, and page_indices
4. WHEN a wrong question has scoring_point_results, THE Mistake_Analysis_System SHALL display the detailed scoring breakdown
5. THE Mistake_Analysis_System SHALL calculate and display summary statistics including total_questions, wrong_questions, total_score, and total_max
6. THE Mistake_Analysis_System SHALL identify and display focus areas (薄弱集中区) based on error frequency per question
7. IF no grading history exists for the student, THEN THE Mistake_Analysis_System SHALL display an empty state message

### Requirement 3: Student Progress Report Generation

**User Story:** As a student, I want to see my learning progress report with personalized insights, so that I can understand my strengths and areas for improvement.

#### Acceptance Criteria

1. WHEN a student opens the Progress Report page, THE Progress_Report_System SHALL fetch the diagnosis report from the Diagnosis_Report_API
2. WHEN the diagnosis report is loaded, THE Progress_Report_System SHALL display overall_assessment including mastery_score, improvement_rate, and consistency_score
3. WHEN progress_trend data is available, THE Progress_Report_System SHALL render an area chart showing score trends over time
4. WHEN knowledge_map data is available, THE Progress_Report_System SHALL render a radar chart showing mastery levels across knowledge areas
5. WHEN error_patterns data is available, THE Progress_Report_System SHALL render a bar chart showing common error type distribution
6. WHEN personalized_insights are available, THE Progress_Report_System SHALL display AI-generated learning recommendations
7. IF the Diagnosis_Report_API fails, THEN THE Progress_Report_System SHALL display a fallback message with retry option

### Requirement 4: Backend Data Consistency

**User Story:** As a system administrator, I want the grading data to flow consistently from batch grading to student views, so that students see accurate information.

#### Acceptance Criteria

1. WHEN batch grading completes, THE Student_Grading_Results table SHALL be updated with the grading results for each student
2. WHEN a student queries their grading history, THE Grading_History_API SHALL return results filtered by student_id and class_id
3. THE Diagnosis_Report_API SHALL calculate mastery_score based on total_score / total_max from Student_Grading_Results
4. THE Diagnosis_Report_API SHALL calculate improvement_rate by comparing first-half and second-half submission scores
5. THE Diagnosis_Report_API SHALL calculate consistency_score based on score variance across submissions

### Requirement 5: Cross-Page Question Handling

**User Story:** As a teacher, I want to see cross-page questions properly merged and displayed, so that I can accurately review student answers that span multiple pages.

#### Acceptance Criteria

1. WHEN a question spans multiple pages (is_cross_page = true), THE Teaching_Cockpit SHALL display a visual indicator
2. WHEN displaying cross-page questions, THE Teaching_Cockpit SHALL show all page_indices where the answer appears
3. THE Mistake_Analysis_System SHALL preserve cross-page information when extracting wrong questions

### Requirement 6: Real-time Data Refresh

**User Story:** As a user, I want to see updated grading data without manually refreshing the page, so that I have the latest information.

#### Acceptance Criteria

1. WHEN new grading results become available, THE Teaching_Cockpit SHALL provide a refresh button to reload data
2. WHEN the student switches classes in Mistake Analysis, THE Mistake_Analysis_System SHALL reload wrong questions for the selected class
3. THE Progress_Report_System SHALL display the report_period indicating the date range of analyzed data

### Requirement 7: Teacher Performance Dashboard Enhancement

**User Story:** As a teacher, I want to see comprehensive cross-assignment analysis with real data and intuitive assignment selection, so that I can track class progress over time.

#### Acceptance Criteria

1. WHEN viewing all assignments (全部作业), THE Performance_Dashboard SHALL display real statistics from the backend API instead of simulated data
2. THE Performance_Dashboard SHALL fetch actual average_score, max_score, min_score for each grading record from the Grading_History_API
3. WHEN displaying assignment selection, THE Performance_Dashboard SHALL use circular dot indicators (小圆片) similar to teacher/statistics page instead of button list
4. THE Performance_Dashboard SHALL calculate and display real progress/regression trends based on actual grading data
5. WHEN a teacher clicks on an assignment dot, THE Performance_Dashboard SHALL load and display detailed statistics for that assignment
6. THE Performance_Dashboard SHALL display student-level progress tracking showing which students improved or regressed across assignments
7. THE Performance_Dashboard SHALL identify and highlight students who consistently underperform or show significant improvement
