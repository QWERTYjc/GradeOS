/**
 * useStatisticsData Hook
 * 
 * 加载班级成绩统计数据，处理数据转换为 StudentScoreRow[] 和 HomeworkColumn[]
 * 计算学生总分、平均分、班级平均分
 * 
 * @module hooks/useStatisticsData
 * Requirements: 1.1, 1.2, 2.4, 2.5
 */

import { useState, useEffect, useCallback } from 'react';
import { 
  classApi, 
  homeworkApi, 
  gradingApi,
  StudentInfo,
  HomeworkResponse,
  GradingImportRecord,
  GradingHistoryDetailResponse,
} from '@/services/api';
import { calculateAverage } from '@/utils/statistics';

// ============ 接口定义 ============

/**
 * 学生成绩行数据
 * 
 * @property studentId - 学生 ID
 * @property studentName - 学生姓名
 * @property scores - 各作业得分映射 (homeworkId -> score)
 * @property totalScore - 总分
 * @property averageScore - 平均分
 */
export interface StudentScoreRow {
  studentId: string;
  studentName: string;
  scores: Record<string, number | null>; // homeworkId -> score
  totalScore: number;
  averageScore: number;
}

/**
 * 作业列数据
 * 
 * @property homeworkId - 作业 ID
 * @property title - 作业标题
 * @property maxScore - 满分值
 * @property classAverage - 班级平均分
 */
export interface HomeworkColumn {
  homeworkId: string;
  title: string;
  maxScore: number;
  classAverage: number;
}

/**
 * Hook 返回值接口
 */
export interface UseStatisticsDataReturn {
  students: StudentScoreRow[];
  homeworks: HomeworkColumn[];
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}

// ============ 辅助函数 ============

/**
 * 计算学生总分
 * 
 * @param scores - 学生各作业得分映射
 * @returns 总分（null 值视为 0）
 * 
 * Validates: Requirement 2.4
 */
export function calculateStudentTotalScore(scores: Record<string, number | null>): number {
  const validScores = Object.values(scores).filter((s): s is number => s !== null);
  return validScores.reduce((sum, score) => sum + score, 0);
}

/**
 * 计算学生平均分
 * 
 * @param scores - 学生各作业得分映射
 * @returns 平均分（只计算有成绩的作业）
 * 
 * Validates: Requirement 2.4
 */
export function calculateStudentAverageScore(scores: Record<string, number | null>): number {
  const validScores = Object.values(scores).filter((s): s is number => s !== null);
  if (validScores.length === 0) return 0;
  return calculateAverage(validScores);
}

/**
 * 计算作业班级平均分
 * 
 * @param homeworkId - 作业 ID
 * @param studentScores - 所有学生的成绩数据
 * @returns 班级平均分
 * 
 * Validates: Requirement 2.5
 */
export function calculateHomeworkClassAverage(
  homeworkId: string,
  studentScores: Map<string, Record<string, number | null>>
): number {
  const scores: number[] = [];
  
  studentScores.forEach((studentScore) => {
    const score = studentScore[homeworkId];
    if (score !== null && score !== undefined) {
      scores.push(score);
    }
  });
  
  return calculateAverage(scores);
}

// ============ 主 Hook ============

/**
 * useStatisticsData Hook
 * 
 * 加载指定班级的成绩统计数据
 * 
 * @param classId - 班级 ID
 * @returns { students, homeworks, loading, error, refetch }
 * 
 * @example
 * const { students, homeworks, loading, error, refetch } = useStatisticsData('class-123');
 * 
 * if (loading) return <Spinner />;
 * if (error) return <Error message={error} />;
 * 
 * return <ScoreMatrix students={students} homeworks={homeworks} />;
 * 
 * Requirements: 1.1, 1.2, 2.4, 2.5
 */
export function useStatisticsData(classId: string | null): UseStatisticsDataReturn {
  const [students, setStudents] = useState<StudentScoreRow[]>([]);
  const [homeworks, setHomeworks] = useState<HomeworkColumn[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  /**
   * 获取并处理统计数据
   */
  const fetchData = useCallback(async () => {
    if (!classId) {
      setStudents([]);
      setHomeworks([]);
      setError(null);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      // 1. 并行获取班级学生列表和作业列表
      const [studentsData, homeworksData] = await Promise.all([
        classApi.getClassStudents(classId),
        homeworkApi.getList({ class_id: classId }),
      ]);

      // 2. 获取批改历史记录
      const gradingHistory = await gradingApi.getGradingHistory({ 
        class_id: classId,
        include_stats: true,
      });

      // 3. 构建学生 ID -> 学生信息的映射
      const studentMap = new Map<string, StudentInfo>();
      studentsData.forEach((student) => {
        studentMap.set(student.id, student);
      });

      // 4. 构建作业 ID -> 作业信息的映射
      const homeworkMap = new Map<string, HomeworkResponse>();
      homeworksData.forEach((homework) => {
        homeworkMap.set(homework.homework_id, homework);
      });

      // 5. 获取每个批改记录的详细数据，构建学生成绩映射
      // studentScores: Map<studentId, Record<homeworkId, score>>
      const studentScores = new Map<string, Record<string, number | null>>();
      // homeworkMaxScores: Map<homeworkId, maxScore>
      const homeworkMaxScores = new Map<string, number>();

      // 初始化所有学生的成绩记录
      studentsData.forEach((student) => {
        const scores: Record<string, number | null> = {};
        homeworksData.forEach((homework) => {
          scores[homework.homework_id] = null;
        });
        studentScores.set(student.id, scores);
      });

      // 6. 处理批改记录，提取学生成绩
      // 只处理与当前班级作业相关的记录
      const relevantRecords = gradingHistory.records.filter(
        (record: GradingImportRecord) => 
          record.class_id === classId && 
          record.status !== 'revoked'
      );

      // 获取每个批改记录的详细数据
      for (const record of relevantRecords) {
        try {
          const detail: GradingHistoryDetailResponse = await gradingApi.getGradingHistoryDetail(record.import_id);
          
          // 处理每个学生的批改结果
          for (const item of detail.items) {
            if (item.status === 'revoked') continue;
            
            const studentId = item.student_id;
            const homeworkId = record.assignment_id;
            
            // 确保学生在班级中
            if (!studentScores.has(studentId)) continue;
            
            // 从 result 中提取分数
            const result = item.result as { total_score?: number; max_score?: number } | undefined;
            if (result && typeof result.total_score === 'number') {
              const scores = studentScores.get(studentId)!;
              
              // 如果有 homeworkId，记录到对应作业
              if (homeworkId) {
                scores[homeworkId] = result.total_score;
                
                // 记录满分值
                if (result.max_score && !homeworkMaxScores.has(homeworkId)) {
                  homeworkMaxScores.set(homeworkId, result.max_score);
                }
              }
            }
          }
        } catch (err) {
          // 单个记录获取失败不影响整体
          console.warn(`Failed to fetch grading detail for ${record.import_id}:`, err);
        }
      }

      // 7. 构建 StudentScoreRow[] 数据
      const studentRows: StudentScoreRow[] = [];
      
      studentScores.forEach((scores, studentId) => {
        const studentInfo = studentMap.get(studentId);
        if (!studentInfo) return;
        
        const totalScore = calculateStudentTotalScore(scores);
        const averageScore = calculateStudentAverageScore(scores);
        
        studentRows.push({
          studentId,
          studentName: studentInfo.name,
          scores,
          totalScore,
          averageScore,
        });
      });

      // 按学生姓名排序
      studentRows.sort((a, b) => a.studentName.localeCompare(b.studentName, 'zh-CN'));

      // 8. 构建 HomeworkColumn[] 数据
      const homeworkColumns: HomeworkColumn[] = homeworksData.map((homework) => {
        const classAverage = calculateHomeworkClassAverage(homework.homework_id, studentScores);
        const maxScore = homeworkMaxScores.get(homework.homework_id) || 100;
        
        return {
          homeworkId: homework.homework_id,
          title: homework.title,
          maxScore,
          classAverage,
        };
      });

      // 按创建时间排序（最新的在前）
      homeworkColumns.sort((a, b) => {
        const homeworkA = homeworkMap.get(a.homeworkId);
        const homeworkB = homeworkMap.get(b.homeworkId);
        if (!homeworkA || !homeworkB) return 0;
        return new Date(homeworkB.created_at).getTime() - new Date(homeworkA.created_at).getTime();
      });

      setStudents(studentRows);
      setHomeworks(homeworkColumns);
      setError(null);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : '加载数据失败';
      setError(errorMessage);
      console.error('Failed to fetch statistics data:', err);
    } finally {
      setLoading(false);
    }
  }, [classId]);

  // 初始加载和 classId 变化时重新加载
  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return {
    students,
    homeworks,
    loading,
    error,
    refetch: fetchData,
  };
}

export default useStatisticsData;
