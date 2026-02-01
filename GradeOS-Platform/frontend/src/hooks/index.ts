/**
 * Hooks 模块导出
 * 
 * 集中导出所有自定义 React Hooks
 */

export { 
  useStatisticsData,
  calculateStudentTotalScore,
  calculateStudentAverageScore,
  calculateHomeworkClassAverage,
  type StudentScoreRow,
  type HomeworkColumn,
  type UseStatisticsDataReturn,
} from './useStatisticsData';

export {
  useHomeworkAnalysis,
  type UseHomeworkAnalysisReturn,
} from './useHomeworkAnalysis';
