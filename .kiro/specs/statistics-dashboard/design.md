# Design Document: Statistics Dashboard

## Overview

Statistics Dashboard 是 GradeOS 教师端的成绩统计分析模块，提供两个核心视图：

1. **成绩总览页** (`/teacher/statistics`) - Excel 风格的成绩矩阵，展示所有学生在所有作业中的得分
2. **作业详情页** (`/teacher/statistics/[homeworkId]`) - 单个作业的深度统计分析，包括箱线图、分布图、排名等

技术栈：Next.js 15 + React 19 + Ant Design 5 + Tailwind CSS 4 + Recharts

## Architecture

```mermaid
graph TB
    subgraph Frontend
        SP[Statistics Page<br/>/teacher/statistics]
        HP[Homework Analysis Page<br/>/teacher/statistics/[homeworkId]]
        
        subgraph Components
            SM[ScoreMatrix]
            BC[BoxChart]
            SD[ScoreDistribution]
            RL[RankingList]
            SC[StatsCards]
        end
        
        subgraph Hooks
            USD[useStatisticsData]
            UHA[useHomeworkAnalysis]
        end
    end
    
    subgraph API Layer
        CA[classApi]
        HA[homeworkApi]
        GA[gradingApi]
    end
    
    subgraph Backend
        DB[(PostgreSQL)]
    end
    
    SP --> SM
    SP --> USD
    HP --> BC
    HP --> SD
    HP --> RL
    HP --> SC
    HP --> UHA
    
    USD --> CA
    USD --> HA
    USD --> GA
    UHA --> GA
    
    CA --> DB
    HA --> DB
    GA --> DB
```

## Components and Interfaces

### 1. ScoreMatrix Component

Excel 风格的成绩表格组件，支持固定首列（学生姓名）和横向滚动。

```typescript
interface ScoreMatrixProps {
  students: StudentScoreRow[];
  homeworks: HomeworkColumn[];
  onCellClick?: (studentId: string, homeworkId: string) => void;
  onHeaderClick?: (homeworkId: string) => void;
  loading?: boolean;
}

interface StudentScoreRow {
  studentId: string;
  studentName: string;
  scores: Record<string, number | null>; // homeworkId -> score
  totalScore: number;
  averageScore: number;
}

interface HomeworkColumn {
  homeworkId: string;
  title: string;
  maxScore: number;
  classAverage: number;
}
```

**实现要点**：
- 使用 CSS `position: sticky` 固定学生姓名列
- 使用 Ant Design Table 或自定义表格实现
- 支持横向滚动查看所有作业列
- 单元格点击导航到作业详情

### 2. BoxChart Component

箱线图组件，使用 Recharts 的 ComposedChart 实现。

```typescript
interface BoxChartProps {
  data: BoxPlotData;
  width?: number;
  height?: number;
}

interface BoxPlotData {
  min: number;
  q1: number;
  median: number;
  q3: number;
  max: number;
  outliers: number[];
  mean: number;
}
```

**实现要点**：
- Recharts 没有原生箱线图，需要用 ComposedChart + ReferenceArea + ReferenceLine 组合实现
- 或使用自定义 SVG 绘制
- 显示 IQR (Q3-Q1) 区域、中位数线、均值点

### 3. ScoreDistribution Component

分数分布柱状图组件。

```typescript
interface ScoreDistributionProps {
  scores: number[];
  ranges?: ScoreRange[];
  maxScore?: number;
}

interface ScoreRange {
  label: string;
  min: number;
  max: number;
}

// 默认分数段
const DEFAULT_RANGES: ScoreRange[] = [
  { label: '0-59', min: 0, max: 59 },
  { label: '60-69', min: 60, max: 69 },
  { label: '70-79', min: 70, max: 79 },
  { label: '80-89', min: 80, max: 89 },
  { label: '90-100', min: 90, max: 100 },
];
```

### 4. RankingList Component

学生排名列表组件。

```typescript
interface RankingListProps {
  students: RankedStudent[];
  maxDisplay?: number;
}

interface RankedStudent {
  rank: number;
  studentId: string;
  studentName: string;
  score: number;
  maxScore: number;
}
```

### 5. StatsCards Component

统计指标卡片组组件。

```typescript
interface StatsCardsProps {
  stats: HomeworkStats;
}

interface HomeworkStats {
  average: number;
  median: number;
  max: number;
  min: number;
  stdDev: number;
  studentCount: number;
  maxPossibleScore: number;
}
```

## Data Models

### Statistics Data Flow

```typescript
// 从 API 获取的原始数据
interface RawGradingData {
  records: GradingImportRecord[];
  studentResults: Map<string, StudentResult[]>; // batchId -> results
}

// 处理后的统计数据
interface ProcessedStatistics {
  students: StudentScoreRow[];
  homeworks: HomeworkColumn[];
  homeworkStats: Map<string, HomeworkStats>;
}

// 统计计算函数
function calculateHomeworkStats(scores: number[], maxScore: number): HomeworkStats {
  const sorted = [...scores].sort((a, b) => a - b);
  const n = sorted.length;
  
  return {
    average: scores.reduce((a, b) => a + b, 0) / n,
    median: n % 2 === 0 
      ? (sorted[n/2 - 1] + sorted[n/2]) / 2 
      : sorted[Math.floor(n/2)],
    max: sorted[n - 1],
    min: sorted[0],
    stdDev: calculateStdDev(scores),
    studentCount: n,
    maxPossibleScore: maxScore,
  };
}

function calculateBoxPlotData(scores: number[]): BoxPlotData {
  const sorted = [...scores].sort((a, b) => a - b);
  const n = sorted.length;
  
  const q1 = percentile(sorted, 25);
  const median = percentile(sorted, 50);
  const q3 = percentile(sorted, 75);
  const iqr = q3 - q1;
  
  const lowerFence = q1 - 1.5 * iqr;
  const upperFence = q3 + 1.5 * iqr;
  
  const outliers = sorted.filter(s => s < lowerFence || s > upperFence);
  const nonOutliers = sorted.filter(s => s >= lowerFence && s <= upperFence);
  
  return {
    min: Math.min(...nonOutliers),
    q1,
    median,
    q3,
    max: Math.max(...nonOutliers),
    outliers,
    mean: scores.reduce((a, b) => a + b, 0) / n,
  };
}

function percentile(sorted: number[], p: number): number {
  const index = (p / 100) * (sorted.length - 1);
  const lower = Math.floor(index);
  const upper = Math.ceil(index);
  const weight = index - lower;
  
  if (lower === upper) return sorted[lower];
  return sorted[lower] * (1 - weight) + sorted[upper] * weight;
}

function calculateStdDev(scores: number[]): number {
  const mean = scores.reduce((a, b) => a + b, 0) / scores.length;
  const squaredDiffs = scores.map(s => Math.pow(s - mean, 2));
  const variance = squaredDiffs.reduce((a, b) => a + b, 0) / scores.length;
  return Math.sqrt(variance);
}
```

### CSV Export Format

```typescript
interface CSVExportData {
  headers: string[]; // ['学生姓名', '作业1', '作业2', ..., '总分', '平均分']
  rows: (string | number)[][];
  filename: string; // `${className}_成绩表_${date}.csv`
}

function generateCSV(data: ProcessedStatistics, className: string): string {
  const headers = [
    '学生姓名',
    ...data.homeworks.map(h => h.title),
    '总分',
    '平均分'
  ];
  
  const rows = data.students.map(student => [
    student.studentName,
    ...data.homeworks.map(h => student.scores[h.homeworkId] ?? ''),
    student.totalScore,
    student.averageScore.toFixed(1)
  ]);
  
  // 添加班级平均行
  rows.push([
    '班级平均',
    ...data.homeworks.map(h => h.classAverage.toFixed(1)),
    '',
    ''
  ]);
  
  return [headers, ...rows]
    .map(row => row.map(cell => `"${cell}"`).join(','))
    .join('\n');
}
```



## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Matrix Dimensions Match Input Data

*For any* list of N students and M homework assignments, the Score_Matrix SHALL render exactly N data rows and M+3 columns (student name + M assignments + total + average).

**Validates: Requirements 2.1**

### Property 2: Score Cell Values Match Input Data

*For any* student-homework pair with a known score S, the corresponding cell in the Score_Matrix SHALL display the value S.

**Validates: Requirements 2.2**

### Property 3: Student Total and Average Calculation

*For any* student with scores [s1, s2, ..., sn] across n assignments:
- Total score SHALL equal s1 + s2 + ... + sn
- Average score SHALL equal (s1 + s2 + ... + sn) / n

**Validates: Requirements 2.4**

### Property 4: Class Average Calculation

*For any* homework assignment with student scores [s1, s2, ..., sm] from m students, the class average SHALL equal (s1 + s2 + ... + sm) / m.

**Validates: Requirements 2.5**

### Property 5: Statistics Calculation Correctness

*For any* non-empty list of scores [s1, s2, ..., sn]:
- Average SHALL equal sum(scores) / n
- Median SHALL equal the middle value when sorted (or average of two middle values for even n)
- Max SHALL equal the largest value
- Min SHALL equal the smallest value
- Standard deviation SHALL equal sqrt(sum((si - mean)²) / n)

**Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5**

### Property 6: Box Plot Data Correctness

*For any* non-empty list of scores:
- Q1 SHALL equal the 25th percentile
- Median SHALL equal the 50th percentile
- Q3 SHALL equal the 75th percentile
- Outliers SHALL be all values outside [Q1 - 1.5*IQR, Q3 + 1.5*IQR] where IQR = Q3 - Q1
- Min/Max (whiskers) SHALL be the extreme non-outlier values

**Validates: Requirements 5.1, 5.2**

### Property 7: Score Distribution Grouping

*For any* list of scores and defined ranges:
- Each score SHALL fall into exactly one range
- The sum of counts across all ranges SHALL equal the total number of scores
- The count for each range SHALL equal the number of scores within that range's bounds

**Validates: Requirements 6.1, 6.2**

### Property 8: Ranking Correctness

*For any* list of students with scores:
- Students SHALL be sorted by score in descending order
- Students with equal scores SHALL have equal rank numbers
- Rank numbers SHALL follow standard competition ranking (1, 2, 2, 4 for ties)

**Validates: Requirements 7.1, 7.2, 7.4**

### Property 9: CSV Export Format Correctness

*For any* exported CSV:
- The header row SHALL contain: student name column, all homework titles, total column, average column
- Each data row SHALL contain the corresponding student's data in the same column order
- The filename SHALL match pattern: `{className}_成绩表_{YYYY-MM-DD}.csv`

**Validates: Requirements 8.2, 8.3**

## Error Handling

### API Errors

| Error Type | Handling Strategy |
|------------|-------------------|
| Network failure | Display error toast, show retry button, preserve last loaded data |
| 401 Unauthorized | Redirect to login page |
| 404 Class/Homework not found | Display "not found" message with back navigation |
| 500 Server error | Display generic error message, log to console |

### Data Edge Cases

| Edge Case | Handling |
|-----------|----------|
| Empty class (no students) | Show empty state: "该班级暂无学生" |
| No grading data | Show empty state: "暂无批改数据" |
| Single student | Statistics still calculated, box plot shows single point |
| All same scores | Box plot collapses to line, distribution shows single bar |
| Missing scores (null) | Display "-" in cell, exclude from calculations |

### Input Validation

```typescript
function validateScores(scores: (number | null)[]): number[] {
  return scores
    .filter((s): s is number => s !== null && s !== undefined)
    .filter(s => !isNaN(s) && isFinite(s) && s >= 0);
}
```

## Testing Strategy

### Unit Tests

Unit tests focus on specific examples and edge cases:

1. **Statistics calculations with known values**
   - Test average of [80, 90, 100] = 90
   - Test median of [1, 2, 3, 4, 5] = 3
   - Test median of [1, 2, 3, 4] = 2.5

2. **Edge cases**
   - Empty score array handling
   - Single score array
   - All identical scores
   - Scores with null values

3. **CSV generation**
   - Correct escaping of special characters
   - Correct filename format

### Property-Based Tests

Property-based tests use randomized inputs to verify universal properties. Each test runs minimum 100 iterations.

**Testing Library**: fast-check (TypeScript property-based testing library)

**Test Configuration**:
```typescript
import fc from 'fast-check';

// Arbitrary for valid scores (0-100)
const scoreArb = fc.integer({ min: 0, max: 100 });
const scoresArb = fc.array(scoreArb, { minLength: 1, maxLength: 50 });

// Arbitrary for student data
const studentArb = fc.record({
  studentId: fc.uuid(),
  studentName: fc.string({ minLength: 1, maxLength: 20 }),
  scores: fc.dictionary(fc.uuid(), fc.option(scoreArb)),
});
```

**Property Test Tags**:
- Feature: statistics-dashboard, Property 1: Matrix dimensions match input data
- Feature: statistics-dashboard, Property 3: Student total and average calculation
- Feature: statistics-dashboard, Property 4: Class average calculation
- Feature: statistics-dashboard, Property 5: Statistics calculation correctness
- Feature: statistics-dashboard, Property 6: Box plot data correctness
- Feature: statistics-dashboard, Property 7: Score distribution grouping
- Feature: statistics-dashboard, Property 8: Ranking correctness
- Feature: statistics-dashboard, Property 9: CSV export format correctness

### Integration Tests

1. **Data loading flow**: Mock API responses, verify correct state updates
2. **Navigation**: Verify correct routing between overview and detail pages
3. **Export functionality**: Verify CSV download triggers correctly

### Visual Regression Tests (Optional)

Use Playwright or Cypress for visual regression testing of:
- Score matrix layout at different screen sizes
- Box plot rendering
- Distribution chart rendering
