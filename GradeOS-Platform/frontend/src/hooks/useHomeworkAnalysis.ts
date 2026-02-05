/**
 * useHomeworkAnalysis Hook
 * 
 * 加载单个作业的批改结果，计算统计指标、箱线图数据、分布数据、排名
 * 
 * @module hooks/useHomeworkAnalysis
 * Requirements: 4.1-4.5, 5.1-5.2, 6.1-6.2, 7.1-7.4
 */

import { useState, useEffect, useCallback } from 'react';
import { 
  gradingApi,
  homeworkApi,
  GradingHistoryDetailResponse,
  GradingImportRecord,
} from '@/services/api';
import {
  HomeworkStats,
  BoxPlotData,
  ScoreDistributionResult,
  RankedStudent,
  calculateHomeworkStats,
  calculateBoxPlotData,
  groupScoresByRange,
  calculateRankings,
  StudentScoreInput,
} from '@/utils/statistics';

// ============ 接口定义 ============

/**
 * Hook 返回值接口
 */
export interface UseHomeworkAnalysisReturn {
  /** 统计指标（平均分、中位数、最高分、最低分、标准差、学生人数） */
  stats: HomeworkStats | null;
  /** 箱线图数据（min, Q1, median, Q3, max, outliers, mean） */
  boxPlotData: BoxPlotData | null;
  /** 分数分布数据（各分数段人数和百分比） */
  distribution: ScoreDistributionResult[];
  /** 学生排名列表（按分数降序） */
  rankings: RankedStudent[];
  /** 作业标题 */
  homeworkTitle: string;
  /** 满分值 */
  maxPossibleScore: number;
  /** 加载状态 */
  loading: boolean;
  /** 错误信息 */
  error: string | null;
  /** 重新获取数据 */
  refetch: () => Promise<void>;
}

/**
 * 从批改结果中提取的学生成绩数据
 */
interface StudentGradingResult {
  studentId: string;
  studentName: string;
  score: number;
  maxScore: number;
}

// ============ 主 Hook ============

/**
 * useHomeworkAnalysis Hook
 * 
 * 加载指定作业的批改结果，计算完整的统计分析数据
 * 
 * @param homeworkId - 作业 ID
 * @returns { stats, boxPlotData, distribution, rankings, homeworkTitle, maxPossibleScore, loading, error, refetch }
 * 
 * @example
 * const { 
 *   stats, 
 *   boxPlotData, 
 *   distribution, 
 *   rankings, 
 *   loading, 
 *   error 
 * } = useHomeworkAnalysis('homework-123');
 * 
 * if (loading) return <Spinner />;
 * if (error) return <Error message={error} />;
 * 
 * return (
 *   <>
 *     <StatsCards stats={stats} />
 *     <BoxChart data={boxPlotData} />
 *     <ScoreDistribution data={distribution} />
 *     <RankingList students={rankings} />
 *   </>
 * );
 * 
 * Requirements: 4.1-4.5, 5.1-5.2, 6.1-6.2, 7.1-7.4
 */
export function useHomeworkAnalysis(homeworkId: string | null): UseHomeworkAnalysisReturn {
  const [stats, setStats] = useState<HomeworkStats | null>(null);
  const [boxPlotData, setBoxPlotData] = useState<BoxPlotData | null>(null);
  const [distribution, setDistribution] = useState<ScoreDistributionResult[]>([]);
  const [rankings, setRankings] = useState<RankedStudent[]>([]);
  const [homeworkTitle, setHomeworkTitle] = useState<string>('');
  const [maxPossibleScore, setMaxPossibleScore] = useState<number>(100);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  /**
   * 获取并处理作业分析数据
   */
  const fetchData = useCallback(async () => {
    if (!homeworkId) {
      // 清空所有数据
      setStats(null);
      setBoxPlotData(null);
      setDistribution([]);
      setRankings([]);
      setHomeworkTitle('');
      setMaxPossibleScore(100);
      setError(null);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      // 1. 获取作业详情
      let homework;
      try {
        homework = await homeworkApi.getDetail(homeworkId);
        setHomeworkTitle(homework.title);
      } catch (err) {
        // 作业不存在
        setError('作业不存在');
        setLoading(false);
        return;
      }

      // 2. 获取与该作业相关的批改历史记录
      const gradingHistory = await gradingApi.getGradingHistory({
        assignment_id: homeworkId,
        include_stats: true,
      });

      // 3. 提取学生成绩数据
      const studentResults: StudentGradingResult[] = [];
      let detectedMaxScore = 100;

      // 过滤出有效的批改记录（未撤销的）
      const validRecords = gradingHistory.records.filter(
        (record: GradingImportRecord) => 
          record.assignment_id === homeworkId && 
          record.status !== 'revoked'
      );

      // 获取每个批改记录的详细数据
      for (const record of validRecords) {
        try {
          const detail: GradingHistoryDetailResponse = await gradingApi.getGradingHistoryDetail(record.import_id);
          
          // 处理每个学生的批改结果
          for (const item of detail.items) {
            if (item.status === 'revoked') continue;
            
            // 从 result 中提取分数
            const result = item.result as { 
              total_score?: number; 
              max_score?: number;
              student_name?: string;
            } | undefined;
            
            if (result && typeof result.total_score === 'number') {
              // 检测满分值
              if (result.max_score && result.max_score > 0) {
                detectedMaxScore = result.max_score;
              }
              
              studentResults.push({
                studentId: item.student_id,
                studentName: item.student_name || result.student_name || '未知学生',
                score: result.total_score,
                maxScore: result.max_score || detectedMaxScore,
              });
            }
          }
        } catch (err) {
          // 单个记录获取失败不影响整体
          console.warn(`Failed to fetch grading detail for ${record.import_id}:`, err);
        }
      }

      // 4. 如果没有批改数据，设置空状态
      if (studentResults.length === 0) {
        setStats(calculateHomeworkStats([], detectedMaxScore));
        setBoxPlotData(calculateBoxPlotData([]));
        setDistribution(groupScoresByRange([]));
        setRankings([]);
        setMaxPossibleScore(detectedMaxScore);
        setLoading(false);
        return;
      }

      // 5. 提取分数数组
      const scores = studentResults.map(r => r.score);
      
      // 更新满分值
      setMaxPossibleScore(detectedMaxScore);

      // 6. 计算统计指标
      // Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5
      const calculatedStats = calculateHomeworkStats(scores, detectedMaxScore);
      setStats(calculatedStats);

      // 7. 计算箱线图数据
      // Validates: Requirements 5.1, 5.2
      const calculatedBoxPlot = calculateBoxPlotData(scores);
      setBoxPlotData(calculatedBoxPlot);

      // 8. 计算分数分布
      // Validates: Requirements 6.1, 6.2
      const calculatedDistribution = groupScoresByRange(scores);
      setDistribution(calculatedDistribution);

      // 9. 计算排名
      // Validates: Requirements 7.1, 7.4
      const studentInputs: StudentScoreInput[] = studentResults.map(r => ({
        studentId: r.studentId,
        studentName: r.studentName,
        score: r.score,
      }));
      const calculatedRankings = calculateRankings(studentInputs, detectedMaxScore);
      setRankings(calculatedRankings);

      setError(null);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : '加载数据失败';
      setError(errorMessage);
      console.error('Failed to fetch homework analysis data:', err);
    } finally {
      setLoading(false);
    }
  }, [homeworkId]);

  // 初始加载和 homeworkId 变化时重新加载
  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return {
    stats,
    boxPlotData,
    distribution,
    rankings,
    homeworkTitle,
    maxPossibleScore,
    loading,
    error,
    refetch: fetchData,
  };
}

export default useHomeworkAnalysis;
