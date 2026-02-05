/**
 * 统计计算工具函数
 * 
 * 提供成绩统计分析所需的基础计算函数
 * 包括：平均值、中位数、标准差、百分位数等
 * 
 * @module utils/statistics
 * Requirements: 4.1, 4.2, 4.3, 4.4
 */

/**
 * 验证并过滤有效的分数数组
 * 过滤掉 null、undefined、NaN、Infinity 和负数
 * 
 * @param scores - 原始分数数组（可能包含 null 值）
 * @returns 过滤后的有效分数数组
 */
export function validateScores(scores: (number | null | undefined)[]): number[] {
  return scores
    .filter((s): s is number => s !== null && s !== undefined)
    .filter(s => !isNaN(s) && isFinite(s) && s >= 0);
}

/**
 * 计算平均值
 * 
 * @param scores - 分数数组
 * @returns 平均值，如果数组为空返回 0
 * 
 * @example
 * calculateAverage([80, 90, 100]) // 90
 * calculateAverage([]) // 0
 * 
 * Validates: Requirement 4.1
 */
export function calculateAverage(scores: number[]): number {
  if (scores.length === 0) return 0;
  
  const sum = scores.reduce((acc, score) => acc + score, 0);
  return sum / scores.length;
}

/**
 * 计算中位数
 * 
 * 对于奇数个元素，返回中间值
 * 对于偶数个元素，返回中间两个值的平均值
 * 
 * @param scores - 分数数组
 * @returns 中位数，如果数组为空返回 0
 * 
 * @example
 * calculateMedian([1, 2, 3, 4, 5]) // 3
 * calculateMedian([1, 2, 3, 4]) // 2.5
 * calculateMedian([]) // 0
 * 
 * Validates: Requirement 4.2
 */
export function calculateMedian(scores: number[]): number {
  if (scores.length === 0) return 0;
  
  const sorted = [...scores].sort((a, b) => a - b);
  const n = sorted.length;
  const mid = Math.floor(n / 2);
  
  if (n % 2 === 0) {
    // 偶数个元素：返回中间两个值的平均值
    return (sorted[mid - 1] + sorted[mid]) / 2;
  } else {
    // 奇数个元素：返回中间值
    return sorted[mid];
  }
}

/**
 * 计算标准差（总体标准差）
 * 
 * 使用总体标准差公式：σ = √(Σ(xi - μ)² / N)
 * 
 * @param scores - 分数数组
 * @returns 标准差，如果数组为空返回 0
 * 
 * @example
 * calculateStdDev([2, 4, 4, 4, 5, 5, 7, 9]) // 2
 * calculateStdDev([]) // 0
 * 
 * Validates: Requirement 4.4
 */
export function calculateStdDev(scores: number[]): number {
  if (scores.length === 0) return 0;
  
  const mean = calculateAverage(scores);
  const squaredDiffs = scores.map(s => Math.pow(s - mean, 2));
  const variance = squaredDiffs.reduce((acc, diff) => acc + diff, 0) / scores.length;
  
  return Math.sqrt(variance);
}

/**
 * 计算最小值
 * 
 * @param scores - 分数数组
 * @returns 最小值，如果数组为空返回 0
 * 
 * Validates: Requirement 4.3
 */
export function calculateMin(scores: number[]): number {
  if (scores.length === 0) return 0;
  return Math.min(...scores);
}

/**
 * 计算最大值
 * 
 * @param scores - 分数数组
 * @returns 最大值，如果数组为空返回 0
 * 
 * Validates: Requirement 4.3
 */
export function calculateMax(scores: number[]): number {
  if (scores.length === 0) return 0;
  return Math.max(...scores);
}

/**
 * 计算百分位数
 * 
 * 使用线性插值法计算指定百分位的值
 * 
 * @param sorted - 已排序的分数数组（升序）
 * @param p - 百分位数（0-100）
 * @returns 对应百分位的值，如果数组为空返回 0
 * 
 * @example
 * percentile([1, 2, 3, 4, 5], 50) // 3 (中位数)
 * percentile([1, 2, 3, 4, 5], 25) // 2 (Q1)
 * percentile([1, 2, 3, 4, 5], 75) // 4 (Q3)
 * 
 * Validates: Requirements 5.1, 5.2
 */
export function percentile(sorted: number[], p: number): number {
  if (sorted.length === 0) return 0;
  if (sorted.length === 1) return sorted[0];
  
  // 确保 p 在有效范围内
  const clampedP = Math.max(0, Math.min(100, p));
  
  const index = (clampedP / 100) * (sorted.length - 1);
  const lower = Math.floor(index);
  const upper = Math.ceil(index);
  const weight = index - lower;
  
  if (lower === upper) {
    return sorted[lower];
  }
  
  // 线性插值
  return sorted[lower] * (1 - weight) + sorted[upper] * weight;
}

/**
 * 计算完整的统计指标
 * 
 * 一次性计算所有基础统计指标，避免重复排序和计算
 * 
 * @param scores - 分数数组（可包含 null 值）
 * @param maxPossibleScore - 满分值（可选，默认 100）
 * @returns 统计指标对象
 * 
 * Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5
 */
export interface HomeworkStats {
  average: number;
  median: number;
  max: number;
  min: number;
  stdDev: number;
  studentCount: number;
  maxPossibleScore: number;
}

export function calculateHomeworkStats(
  scores: (number | null | undefined)[],
  maxPossibleScore: number = 100
): HomeworkStats {
  const validScores = validateScores(scores);
  
  if (validScores.length === 0) {
    return {
      average: 0,
      median: 0,
      max: 0,
      min: 0,
      stdDev: 0,
      studentCount: 0,
      maxPossibleScore,
    };
  }
  
  const sorted = [...validScores].sort((a, b) => a - b);
  
  return {
    average: calculateAverage(validScores),
    median: calculateMedian(validScores),
    max: sorted[sorted.length - 1],
    min: sorted[0],
    stdDev: calculateStdDev(validScores),
    studentCount: validScores.length,
    maxPossibleScore,
  };
}

/**
 * 箱线图数据接口
 * 
 * 包含箱线图所需的所有统计数据：
 * - min/max: 非异常值的最小/最大值（须线端点）
 * - q1/q3: 第一/第三四分位数（箱体边界）
 * - median: 中位数（箱体中线）
 * - outliers: 异常值数组
 * - mean: 平均值
 * 
 * Validates: Requirements 5.1, 5.2
 */
export interface BoxPlotData {
  min: number;
  q1: number;
  median: number;
  q3: number;
  max: number;
  outliers: number[];
  mean: number;
}

/**
 * 计算箱线图数据
 * 
 * 箱线图（Box-Whisker Plot）展示数据分布的五数概括：
 * - 最小值（非异常值）
 * - Q1（第一四分位数，25%）
 * - 中位数（Q2，50%）
 * - Q3（第三四分位数，75%）
 * - 最大值（非异常值）
 * 
 * 异常值定义：超出 [Q1 - 1.5*IQR, Q3 + 1.5*IQR] 范围的值
 * 其中 IQR = Q3 - Q1（四分位距）
 * 
 * @param scores - 分数数组（可包含 null 值）
 * @returns 箱线图数据对象
 * 
 * @example
 * calculateBoxPlotData([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
 * // { min: 1, q1: 3.25, median: 5.5, q3: 7.75, max: 10, outliers: [], mean: 5.5 }
 * 
 * calculateBoxPlotData([1, 2, 3, 4, 5, 100])
 * // 100 会被识别为异常值
 * 
 * Validates: Requirements 5.1, 5.2
 */
export function calculateBoxPlotData(scores: (number | null | undefined)[]): BoxPlotData {
  const validScores = validateScores(scores);
  
  // 处理空数组的边界情况
  if (validScores.length === 0) {
    return {
      min: 0,
      q1: 0,
      median: 0,
      q3: 0,
      max: 0,
      outliers: [],
      mean: 0,
    };
  }
  
  // 处理单个元素的边界情况
  if (validScores.length === 1) {
    const value = validScores[0];
    return {
      min: value,
      q1: value,
      median: value,
      q3: value,
      max: value,
      outliers: [],
      mean: value,
    };
  }
  
  // 排序数组
  const sorted = [...validScores].sort((a, b) => a - b);
  const n = sorted.length;
  
  // 计算四分位数
  const q1 = percentile(sorted, 25);
  const median = percentile(sorted, 50);
  const q3 = percentile(sorted, 75);
  
  // 计算四分位距 (IQR)
  const iqr = q3 - q1;
  
  // 计算异常值边界（栅栏）
  const lowerFence = q1 - 1.5 * iqr;
  const upperFence = q3 + 1.5 * iqr;
  
  // 分离异常值和非异常值
  const outliers: number[] = [];
  const nonOutliers: number[] = [];
  
  for (const score of sorted) {
    if (score < lowerFence || score > upperFence) {
      outliers.push(score);
    } else {
      nonOutliers.push(score);
    }
  }
  
  // 计算平均值
  const mean = validScores.reduce((acc, s) => acc + s, 0) / n;
  
  // 处理所有值都是异常值的极端情况（理论上不应该发生）
  // 在这种情况下，使用原始数据的 min/max
  const whiskerMin = nonOutliers.length > 0 ? Math.min(...nonOutliers) : sorted[0];
  const whiskerMax = nonOutliers.length > 0 ? Math.max(...nonOutliers) : sorted[n - 1];
  
  return {
    min: whiskerMin,
    q1,
    median,
    q3,
    max: whiskerMax,
    outliers,
    mean,
  };
}


/**
 * 分数段范围接口
 * 
 * 定义一个分数段的标签和边界值
 * 
 * @property label - 分数段显示标签（如 "0-59"）
 * @property min - 分数段最小值（包含）
 * @property max - 分数段最大值（包含）
 * 
 * Validates: Requirements 6.1, 6.2
 */
export interface ScoreRange {
  label: string;
  min: number;
  max: number;
}

/**
 * 默认分数段配置
 * 
 * 标准的五级分数段划分：
 * - 0-59: 不及格
 * - 60-69: 及格
 * - 70-79: 中等
 * - 80-89: 良好
 * - 90-100: 优秀
 * 
 * Validates: Requirements 6.1
 */
export const DEFAULT_RANGES: ScoreRange[] = [
  { label: '0-59', min: 0, max: 59 },
  { label: '60-69', min: 60, max: 69 },
  { label: '70-79', min: 70, max: 79 },
  { label: '80-89', min: 80, max: 89 },
  { label: '90-100', min: 90, max: 100 },
];

/**
 * 分数分布结果接口
 * 
 * 每个分数段的统计结果
 * 
 * @property label - 分数段标签
 * @property min - 分数段最小值
 * @property max - 分数段最大值
 * @property count - 该分数段的学生人数
 * @property percentage - 该分数段占总人数的百分比（0-100）
 * 
 * Validates: Requirements 6.2, 6.3
 */
export interface ScoreDistributionResult {
  label: string;
  min: number;
  max: number;
  count: number;
  percentage: number;
}

/**
 * 将分数分组到指定的分数段
 * 
 * 根据提供的分数段配置，统计每个分数段的学生人数和百分比。
 * 
 * 分组规则：
 * - 分数 >= min 且 <= max 时归入该分数段
 * - 每个分数只会归入一个分数段（按顺序匹配第一个符合的）
 * - 不在任何分数段范围内的分数会被忽略
 * 
 * @param scores - 分数数组（可包含 null 值）
 * @param ranges - 自定义分数段配置（可选，默认使用 DEFAULT_RANGES）
 * @returns 每个分数段的统计结果数组
 * 
 * @example
 * // 使用默认分数段
 * groupScoresByRange([55, 65, 75, 85, 95])
 * // [
 * //   { label: '0-59', min: 0, max: 59, count: 1, percentage: 20 },
 * //   { label: '60-69', min: 60, max: 69, count: 1, percentage: 20 },
 * //   { label: '70-79', min: 70, max: 79, count: 1, percentage: 20 },
 * //   { label: '80-89', min: 80, max: 89, count: 1, percentage: 20 },
 * //   { label: '90-100', min: 90, max: 100, count: 1, percentage: 20 },
 * // ]
 * 
 * @example
 * // 使用自定义分数段
 * groupScoresByRange([30, 60, 90], [
 *   { label: '低', min: 0, max: 50 },
 *   { label: '中', min: 51, max: 80 },
 *   { label: '高', min: 81, max: 100 },
 * ])
 * // [
 * //   { label: '低', min: 0, max: 50, count: 1, percentage: 33.33 },
 * //   { label: '中', min: 51, max: 80, count: 1, percentage: 33.33 },
 * //   { label: '高', min: 81, max: 100, count: 1, percentage: 33.33 },
 * // ]
 * 
 * @example
 * // 空数组返回所有分数段计数为 0
 * groupScoresByRange([])
 * // 所有分数段的 count 和 percentage 都为 0
 * 
 * Validates: Requirements 6.1, 6.2
 */
export function groupScoresByRange(
  scores: (number | null | undefined)[],
  ranges: ScoreRange[] = DEFAULT_RANGES
): ScoreDistributionResult[] {
  // 验证并过滤有效分数
  const validScores = validateScores(scores);
  const totalCount = validScores.length;
  
  // 初始化每个分数段的计数
  const countMap = new Map<string, number>();
  for (const range of ranges) {
    countMap.set(range.label, 0);
  }
  
  // 统计每个分数落入的分数段
  for (const score of validScores) {
    // 按顺序查找第一个匹配的分数段
    for (const range of ranges) {
      if (score >= range.min && score <= range.max) {
        countMap.set(range.label, (countMap.get(range.label) || 0) + 1);
        break; // 每个分数只归入一个分数段
      }
    }
    // 注意：如果分数不在任何分数段范围内，会被忽略
  }
  
  // 构建结果数组
  return ranges.map(range => {
    const count = countMap.get(range.label) || 0;
    // 计算百分比，保留两位小数
    // 如果总数为 0，百分比也为 0
    const percentage = totalCount > 0 
      ? Math.round((count / totalCount) * 10000) / 100 
      : 0;
    
    return {
      label: range.label,
      min: range.min,
      max: range.max,
      count,
      percentage,
    };
  });
}

/**
 * 获取分数分布中人数最多的分数段
 * 
 * 用于高亮显示最多学生的分数段
 * 
 * @param distribution - 分数分布结果数组
 * @returns 人数最多的分数段，如果有多个相同最大值则返回第一个
 * 
 * @example
 * const dist = groupScoresByRange([75, 76, 77, 85, 95]);
 * getHighestCountRange(dist) // { label: '70-79', ... count: 3, ... }
 * 
 * Validates: Requirement 6.4
 */
export function getHighestCountRange(
  distribution: ScoreDistributionResult[]
): ScoreDistributionResult | null {
  if (distribution.length === 0) return null;
  
  let highest = distribution[0];
  for (const range of distribution) {
    if (range.count > highest.count) {
      highest = range;
    }
  }
  
  return highest;
}


/**
 * 排名学生接口
 * 
 * 包含学生排名信息
 * 
 * @property rank - 排名（使用标准竞赛排名：1, 2, 2, 4）
 * @property studentId - 学生 ID
 * @property studentName - 学生姓名
 * @property score - 学生得分
 * @property maxScore - 满分值
 * 
 * Validates: Requirements 7.1, 7.4
 */
export interface RankedStudent {
  rank: number;
  studentId: string;
  studentName: string;
  score: number;
  maxScore: number;
}

/**
 * 学生分数输入接口
 * 
 * 用于 calculateRankings 函数的输入数据
 */
export interface StudentScoreInput {
  studentId: string;
  studentName: string;
  score: number | null | undefined;
}

/**
 * 计算学生排名
 * 
 * 根据分数对学生进行排名，使用标准竞赛排名规则：
 * - 分数相同的学生获得相同的排名
 * - 下一个不同分数的学生排名 = 前面所有学生的数量 + 1
 * - 例如：分数 [100, 90, 90, 80] 对应排名 [1, 2, 2, 4]
 * 
 * @param students - 学生分数数据数组
 * @param maxScore - 满分值（可选，默认 100）
 * @returns 排名后的学生数组，按分数降序排列
 * 
 * @example
 * // 基本用法
 * calculateRankings([
 *   { studentId: '1', studentName: '张三', score: 90 },
 *   { studentId: '2', studentName: '李四', score: 85 },
 *   { studentId: '3', studentName: '王五', score: 90 },
 * ])
 * // [
 * //   { rank: 1, studentId: '1', studentName: '张三', score: 90, maxScore: 100 },
 * //   { rank: 1, studentId: '3', studentName: '王五', score: 90, maxScore: 100 },
 * //   { rank: 3, studentId: '2', studentName: '李四', score: 85, maxScore: 100 },
 * // ]
 * 
 * @example
 * // 标准竞赛排名示例
 * // 分数: [100, 90, 90, 80, 80, 80, 70]
 * // 排名: [1,   2,  2,  4,  4,  4,  7]
 * 
 * @example
 * // 处理 null 分数 - 会被过滤掉
 * calculateRankings([
 *   { studentId: '1', studentName: '张三', score: 90 },
 *   { studentId: '2', studentName: '李四', score: null },
 * ])
 * // 只返回张三的排名结果
 * 
 * Validates: Requirements 7.1, 7.4
 */
export function calculateRankings(
  students: StudentScoreInput[],
  maxScore: number = 100
): RankedStudent[] {
  // 过滤掉无效分数的学生
  const validStudents = students.filter(
    (s): s is StudentScoreInput & { score: number } => 
      s.score !== null && 
      s.score !== undefined && 
      !isNaN(s.score) && 
      isFinite(s.score) &&
      s.score >= 0
  );
  
  // 如果没有有效学生，返回空数组
  if (validStudents.length === 0) {
    return [];
  }
  
  // 按分数降序排序
  // 使用稳定排序，相同分数保持原始顺序
  const sorted = [...validStudents].sort((a, b) => b.score - a.score);
  
  // 使用标准竞赛排名（Standard Competition Ranking）
  // 规则：相同分数获得相同排名，下一个不同分数的排名 = 当前位置 + 1
  const result: RankedStudent[] = [];
  
  for (let i = 0; i < sorted.length; i++) {
    const student = sorted[i];
    let rank: number;
    
    if (i === 0) {
      // 第一名
      rank = 1;
    } else {
      const prevStudent = sorted[i - 1];
      if (student.score === prevStudent.score) {
        // 与前一个学生分数相同，使用相同排名
        rank = result[i - 1].rank;
      } else {
        // 分数不同，排名 = 当前位置 + 1（因为索引从 0 开始）
        rank = i + 1;
      }
    }
    
    result.push({
      rank,
      studentId: student.studentId,
      studentName: student.studentName,
      score: student.score,
      maxScore,
    });
  }
  
  return result;
}

/**
 * 获取前 N 名学生
 * 
 * 注意：由于同分同名次，返回的学生数量可能超过 N
 * 例如：前 3 名可能返回 4 个学生（如果第 3 名有 2 人并列）
 * 
 * @param rankedStudents - 已排名的学生数组
 * @param topN - 要获取的名次数（默认 3）
 * @returns 前 N 名的学生数组
 * 
 * @example
 * // 如果排名是 [1, 2, 2, 4, 5]，getTopStudents(ranked, 3) 返回排名 1, 2, 2 的学生
 * 
 * Validates: Requirement 7.3
 */
export function getTopStudents(
  rankedStudents: RankedStudent[],
  topN: number = 3
): RankedStudent[] {
  return rankedStudents.filter(s => s.rank <= topN);
}

/**
 * 获取后 N 名学生
 * 
 * 注意：由于同分同名次，返回的学生数量可能超过 N
 * 
 * @param rankedStudents - 已排名的学生数组
 * @param bottomN - 要获取的后几名数量（默认 3）
 * @returns 后 N 名的学生数组
 * 
 * @example
 * // 如果有 10 个学生，bottomN=3 会返回排名 >= 8 的学生
 * 
 * Validates: Requirement 7.3
 */
export function getBottomStudents(
  rankedStudents: RankedStudent[],
  bottomN: number = 3
): RankedStudent[] {
  if (rankedStudents.length === 0) return [];
  
  // 找到最后一名的排名
  const maxRank = Math.max(...rankedStudents.map(s => s.rank));
  
  // 计算后 N 名的起始排名
  // 例如：10 个学生，bottomN=3，则返回排名 >= 8 的学生
  const cutoffRank = maxRank - bottomN + 1;
  
  return rankedStudents.filter(s => s.rank >= cutoffRank);
}
