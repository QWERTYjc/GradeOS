# Implementation Plan: Statistics Dashboard

## Overview

实现 GradeOS 教师端成绩统计看板，包含成绩总览页（Excel 风格矩阵）和作业详情页（深度统计分析）。

技术栈：Next.js 15 + React 19 + Ant Design 5 + Tailwind CSS 4 + Recharts + fast-check

## Tasks

- [x] 1. 创建统计计算工具函数
  - [x] 1.1 实现基础统计函数（average, median, stdDev, min, max）
    - 创建 `src/utils/statistics.ts`
    - 实现 `calculateAverage`, `calculateMedian`, `calculateStdDev` 函数
    - 实现 `percentile` 辅助函数
    - _Requirements: 4.1, 4.2, 4.3, 4.4_
  
  - [ ]* 1.2 编写统计计算属性测试
    - **Property 5: Statistics Calculation Correctness**
    - **Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5**
  
  - [x] 1.3 实现箱线图数据计算函数
    - 实现 `calculateBoxPlotData` 函数
    - 计算 Q1, Q3, IQR, outliers
    - _Requirements: 5.1, 5.2_
  
  - [ ]* 1.4 编写箱线图数据属性测试
    - **Property 6: Box Plot Data Correctness**
    - **Validates: Requirements 5.1, 5.2**
  
  - [x] 1.5 实现分数分布分组函数
    - 实现 `groupScoresByRange` 函数
    - 支持自定义分数段配置
    - _Requirements: 6.1, 6.2_
  
  - [ ]* 1.6 编写分数分布属性测试
    - **Property 7: Score Distribution Grouping**
    - **Validates: Requirements 6.1, 6.2**
  
  - [x] 1.7 实现排名计算函数
    - 实现 `calculateRankings` 函数
    - 处理同分同名次逻辑
    - _Requirements: 7.1, 7.4_
  
  - [ ]* 1.8 编写排名属性测试
    - **Property 8: Ranking Correctness**
    - **Validates: Requirements 7.1, 7.2, 7.4**

- [x] 2. Checkpoint - 确保统计工具函数测试通过
  - 运行 `npm test` 确保所有属性测试通过
  - 如有问题请询问用户

- [x] 3. 创建数据处理 Hook
  - [x] 3.1 实现 useStatisticsData Hook
    - 创建 `src/hooks/useStatisticsData.ts`
    - 加载班级、作业、批改数据
    - 处理数据转换为 StudentScoreRow[] 和 HomeworkColumn[]
    - 计算学生总分、平均分、班级平均分
    - _Requirements: 1.1, 1.2, 2.4, 2.5_
  
  - [ ]* 3.2 编写学生总分/平均分属性测试
    - **Property 3: Student Total and Average Calculation**
    - **Validates: Requirements 2.4**
  
  - [ ]* 3.3 编写班级平均分属性测试
    - **Property 4: Class Average Calculation**
    - **Validates: Requirements 2.5**
  
  - [x] 3.4 实现 useHomeworkAnalysis Hook
    - 创建 `src/hooks/useHomeworkAnalysis.ts`
    - 根据 homeworkId 加载批改结果
    - 计算统计指标、箱线图数据、分布数据、排名
    - _Requirements: 4.1-4.5, 5.1-5.2, 6.1-6.2, 7.1-7.4_

- [x] 4. 创建 UI 组件
  - [x] 4.1 实现 ScoreMatrix 组件
    - 创建 `src/components/statistics/ScoreMatrix.tsx`
    - 使用 Ant Design Table 或自定义表格
    - 固定首列（学生姓名），支持横向滚动
    - 显示分数单元格、总分列、平均分列
    - 底部显示班级平均行
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_
  
  - [ ]* 4.2 编写矩阵维度属性测试
    - **Property 1: Matrix Dimensions Match Input Data**
    - **Validates: Requirements 2.1**
  
  - [ ]* 4.3 编写分数单元格值属性测试
    - **Property 2: Score Cell Values Match Input Data**
    - **Validates: Requirements 2.2**
  
  - [x] 4.4 实现 StatsCards 组件
    - 创建 `src/components/statistics/StatsCards.tsx`
    - 显示平均分、中位数、最高分、最低分、标准差、学生人数
    - 使用 GlassCard 设计风格
    - _Requirements: 4.1-4.5_
  
  - [x] 4.5 实现 BoxChart 组件
    - 创建 `src/components/statistics/BoxChart.tsx`
    - 使用 Recharts ComposedChart 实现箱线图
    - 显示 min, Q1, median, Q3, max, outliers
    - 添加 Tooltip 显示详细数值
    - _Requirements: 5.1, 5.2, 5.3_
  
  - [x] 4.6 实现 ScoreDistribution 组件
    - 创建 `src/components/statistics/ScoreDistribution.tsx`
    - 使用 Recharts BarChart 显示分数分布
    - 高亮最多学生的分数段
    - 添加 Tooltip 显示人数和百分比
    - _Requirements: 6.1, 6.2, 6.3, 6.4_
  
  - [x] 4.7 实现 RankingList 组件
    - 创建 `src/components/statistics/RankingList.tsx`
    - 显示排名、学生姓名、分数
    - 视觉区分前三名和后三名
    - _Requirements: 7.1, 7.2, 7.3, 7.4_

- [x] 5. Checkpoint - 确保组件渲染正常
  - 运行开发服务器检查组件渲染
  - 如有问题请询问用户

- [x] 6. 实现页面
  - [x] 6.1 重构成绩总览页
    - 更新 `src/app/teacher/statistics/page.tsx`
    - 集成 useStatisticsData Hook
    - 渲染班级选择器和 ScoreMatrix
    - 实现单元格点击导航到作业详情
    - 实现列头点击导航到作业详情
    - _Requirements: 1.1-1.4, 2.1-2.6, 3.1, 3.2_
  
  - [x] 6.2 创建作业详情页
    - 创建 `src/app/teacher/statistics/[homeworkId]/page.tsx`
    - 集成 useHomeworkAnalysis Hook
    - 渲染 StatsCards, BoxChart, ScoreDistribution, RankingList
    - 处理作业不存在的情况
    - _Requirements: 3.3, 4.1-4.5, 5.1-5.4, 6.1-6.4, 7.1-7.4_

- [x] 7. 实现 CSV 导出功能
  - [x] 7.1 实现 CSV 生成函数
    - 创建 `src/utils/csvExport.ts`
    - 实现 `generateCSV` 函数
    - 处理特殊字符转义
    - 生成正确的文件名格式
    - _Requirements: 8.1, 8.2, 8.3_
  
  - [ ]* 7.2 编写 CSV 导出属性测试
    - **Property 9: CSV Export Format Correctness**
    - **Validates: Requirements 8.2, 8.3**
  
  - [x] 7.3 在总览页添加导出按钮
    - 添加导出按钮到页面头部
    - 触发 CSV 下载
    - _Requirements: 8.1_

- [x] 8. 响应式布局优化
  - [x] 8.1 优化 ScoreMatrix 移动端显示
    - 添加横向滚动支持
    - 固定首列在滚动时可见
    - _Requirements: 9.1, 9.2_
  
  - [x] 8.2 优化图表组件响应式
    - BoxChart 和 ScoreDistribution 自适应宽度
    - 调整移动端字体和间距
    - _Requirements: 9.3_

- [x] 9. Final Checkpoint - 确保所有测试通过
  - 运行 `npm test` 确保所有测试通过
  - 运行 `npm run lint` 确保代码规范
  - 如有问题请询问用户

## Notes

- 任务标记 `*` 为可选测试任务，可跳过以加快 MVP 开发
- 每个属性测试引用设计文档中的正确性属性
- 使用 fast-check 库进行属性测试，每个测试运行 100+ 次迭代
- 复用现有 API：classApi, homeworkApi, gradingApi
- 遵循 GradeOS Design System 的设计规范
