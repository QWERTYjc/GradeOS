# Implementation Plan: Teaching Cockpit, Mistake Analysis, and Progress Report

## Overview

This implementation plan connects the existing frontend components to real backend APIs for displaying grading results, mistake analysis, and progress reports. The implementation focuses on enhancing data flow and ensuring correct data transformation.

## Tasks

- [x] 1. Enhance Teaching Cockpit Data Integration
  - [x] 1.1 Update ResultsView.tsx to fetch from batch results API
    - Ensure `gradingApi.getResults(batchId)` is called correctly
    - Handle loading and error states
    - _Requirements: 1.1, 1.5_
  
  - [x] 1.2 Implement student results sorting by score
    - Sort results in descending order by score
    - Display rank numbers correctly
    - _Requirements: 1.6_
  
  - [x] 1.3 Enhance question detail display with scoring points
    - Display scoring_point_results when available
    - Show point descriptions, awarded points, and evidence
    - _Requirements: 1.3, 1.4_
  
  - [x] 1.4 Add cross-page question indicators
    - Display visual indicator for is_cross_page questions
    - Show all page_indices for cross-page questions
    - _Requirements: 5.1, 5.2_
  
  - [x] 1.5 Write property test for results sorting
    - **Property 2: Results Sorting Order**
    - **Validates: Requirements 1.6**

- [x] 2. Checkpoint - Verify Teaching Cockpit
  - Ensure all tests pass, ask the user if questions arise.

- [x] 3. Enhance Mistake Analysis Data Flow
  - [x] 3.1 Update analysis page to fetch grading history correctly
    - Call `gradingApi.getGradingHistory({ class_id })` with selected class
    - Fetch detail for each record with `gradingApi.getGradingHistoryDetail(import_id)`
    - _Requirements: 2.1_
  
  - [x] 3.2 Implement wrong question extraction logic
    - Extract questions where score < maxScore
    - Preserve all required fields including pageIndices and scoringPointResults
    - _Requirements: 2.2, 2.3, 2.4, 5.3_
  
  - [x] 3.3 Implement summary statistics calculation
    - Calculate totalQuestions, wrongQuestions, totalScore, totalMax
    - Calculate accuracyRate as (totalScore / totalMax) * 100
    - _Requirements: 2.5_
  
  - [x] 3.4 Implement focus area (薄弱集中区) calculation
    - Group questions by questionId
    - Calculate error ratio (wrongCount / totalCount)
    - Sort by ratio descending and take top 6
    - _Requirements: 2.6_
  
  - [x] 3.5 Handle empty state when no grading history exists
    - Display "暂无错题记录" message
    - _Requirements: 2.7_
  
  - [x] 3.6 Implement class switch data reload
    - Reload wrong questions when selectedClassId changes
    - _Requirements: 6.2_
  
  - [x] 3.7 Write property test for wrong question extraction
    - **Property 3: Wrong Question Extraction Correctness**
    - **Validates: Requirements 2.2**
  
  - [x] 3.8 Write property test for summary statistics
    - **Property 5: Summary Statistics Calculation**
    - **Validates: Requirements 2.5**
  
  - [x] 3.9 Write property test for focus area ranking
    - **Property 6: Focus Area Ranking**
    - **Validates: Requirements 2.6**

- [x] 4. Checkpoint - Verify Mistake Analysis
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Enhance Progress Report Integration
  - [x] 5.1 Update report page to fetch diagnosis report
    - Call `analysisApi.getDiagnosisReport(studentId)`
    - Handle loading and error states
    - _Requirements: 3.1, 3.7_
  
  - [x] 5.2 Display overall assessment metrics
    - Show mastery_score as percentage
    - Show improvement_rate with +/- indicator
    - Show consistency_score out of 100
    - _Requirements: 3.2_
  
  - [x] 5.3 Render progress trend area chart
    - Use Recharts AreaChart with progress_trend data
    - Show student score vs class average
    - _Requirements: 3.3_
  
  - [x] 5.4 Render knowledge map radar chart
    - Use Recharts RadarChart with knowledge_map data
    - Display mastery levels for each knowledge area
    - _Requirements: 3.4_
  
  - [x] 5.5 Render error patterns bar chart
    - Use Recharts BarChart with error_patterns data
    - Show most common error types
    - _Requirements: 3.5_
  
  - [x] 5.6 Display personalized insights
    - Render AI-generated recommendations
    - Style as actionable cards
    - _Requirements: 3.6_
  
  - [x] 5.7 Display report period
    - Show date range of analyzed data
    - _Requirements: 6.3_
  
  - [x] 5.8 Write property test for diagnosis report display
    - **Property 7: Diagnosis Report Display Completeness**
    - **Validates: Requirements 3.2, 3.3, 3.4, 3.5, 3.6**

- [x] 6. Checkpoint - Verify Progress Report
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Backend Enhancements (if needed)
  - [x] 7.1 Verify grading history API returns correct data
    - Ensure student_id and class_id filtering works
    - Verify result_data contains all question details
    - _Requirements: 4.2_
  
  - [x] 7.2 Verify diagnosis report calculations
    - Verify mastery_score calculation (total_score / total_max)
    - Verify improvement_rate calculation (second_half_avg - first_half_avg) / first_half_avg
    - Verify consistency_score calculation based on variance
    - _Requirements: 4.3, 4.4, 4.5_
  
  - [x] 7.3 Write property test for mastery score calculation
    - **Property 8: Mastery Score Calculation**
    - **Validates: Requirements 4.3**
  
  - [x] 7.4 Write property test for improvement rate calculation
    - **Property 9: Improvement Rate Calculation**
    - **Validates: Requirements 4.4**
  
  - [x] 7.5 Write property test for consistency score calculation
    - **Property 10: Consistency Score Calculation**
    - **Validates: Requirements 4.5**

- [x] 8. Final Checkpoint - Integration Testing
  - Ensure all tests pass, ask the user if questions arise.
  - Verify end-to-end data flow from batch grading to student views

- [-] 9. Enhance Performance Dashboard with Real Data
  - [x] 9.1 Update Grading History API to return statistics
    - Add `include_stats` parameter to `/api/grading/history`
    - Calculate and return average_score, max_score, min_score for each record
    - Return overall summary with trend analysis
    - _Requirements: 7.1, 7.2_
  
  - [x] 9.2 Replace simulated trend data with real API data
    - Remove `70 + Math.random() * 20` mock data
    - Fetch actual statistics from enhanced Grading History API
    - Display real average, max, min scores in trend chart
    - _Requirements: 7.1, 7.2, 7.4_
  
  - [x] 9.3 Implement assignment dot selector UI
    - Replace button list with circular dot indicators
    - Show average score inside each dot with color coding
    - Add hover tooltip with assignment details
    - Highlight selected assignment with ring indicator
    - _Requirements: 7.3, 7.5_
  
  - [x] 9.4 Implement student progress tracking
    - Track individual student scores across assignments
    - Calculate improvement/regression for each student
    - Display progress indicators (↑ improving, ↓ regressing, → stable)
    - _Requirements: 7.6_
  
  - [x] 9.5 Add underperforming/improving student highlights
    - Identify students consistently below class average
    - Identify students showing significant improvement
    - Display alerts/badges for these students
    - _Requirements: 7.7_
  
  - [x] 9.6 Fix incomplete performance page file
    - Complete the missing JSX for selected homework view
    - Ensure proper rendering of student details when homework is selected
    - Add proper error handling and loading states

- [-] 10. Checkpoint - Verify Performance Dashboard
  - Ensure all tests pass, ask the user if questions arise.
  - Verify real data is displayed instead of mock data

## Notes

- All tasks are required for comprehensive implementation
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties
- Unit tests validate specific examples and edge cases
- The existing frontend components (ResultsView.tsx, analysis/page.tsx, report/page.tsx) already have most UI logic; focus is on data integration
