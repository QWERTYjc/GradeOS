'use client';

/**
 * RankingList 学生排名列表组件
 * 
 * 展示学生按分数排名的列表，支持：
 * - 视觉区分前三名（金银铜）和后三名
 * - 同分同名次处理
 * - 可配置显示数量
 * 
 * @module components/statistics/RankingList
 * Requirements: 7.1, 7.2, 7.3, 7.4
 */

import React, { useMemo } from 'react';
import { GlassCard } from '@/components/design-system/GlassCard';
import { Trophy, Medal, Award, TrendingDown } from 'lucide-react';

// ============ 接口定义 ============

/**
 * 排名学生数据
 */
export interface RankedStudent {
  rank: number;
  studentId: string;
  studentName: string;
  score: number;
  maxScore: number;
}

/**
 * RankingList 组件属性
 */
export interface RankingListProps {
  /** 排名学生列表 */
  students: RankedStudent[];
  /** 最大显示数量（默认显示全部） */
  maxDisplay?: number;
  /** 标题 */
  title?: string;
  /** 是否显示百分比 */
  showPercentage?: boolean;
}

// ============ 辅助函数 ============

/**
 * 获取排名样式配置
 */
const getRankStyle = (rank: number, totalStudents: number) => {
  // 前三名
  if (rank === 1) {
    return {
      bgColor: 'bg-gradient-to-r from-yellow-50 to-amber-50',
      borderColor: 'border-yellow-300',
      textColor: 'text-yellow-700',
      icon: <Trophy className="w-5 h-5 text-yellow-500" />,
      badge: '🥇',
    };
  }
  if (rank === 2) {
    return {
      bgColor: 'bg-gradient-to-r from-gray-50 to-slate-100',
      borderColor: 'border-gray-300',
      textColor: 'text-gray-600',
      icon: <Medal className="w-5 h-5 text-gray-400" />,
      badge: '🥈',
    };
  }
  if (rank === 3) {
    return {
      bgColor: 'bg-gradient-to-r from-orange-50 to-amber-50',
      borderColor: 'border-orange-200',
      textColor: 'text-orange-700',
      icon: <Award className="w-5 h-5 text-orange-400" />,
      badge: '🥉',
    };
  }
  
  // 后三名（需要知道总人数）
  if (totalStudents > 6 && rank > totalStudents - 3) {
    return {
      bgColor: 'bg-red-50/50',
      borderColor: 'border-red-100',
      textColor: 'text-red-600',
      icon: <TrendingDown className="w-4 h-4 text-red-400" />,
      badge: null,
    };
  }
  
  // 普通排名
  return {
    bgColor: 'bg-white',
    borderColor: 'border-gray-100',
    textColor: 'text-gray-700',
    icon: null,
    badge: null,
  };
};

/**
 * 获取分数颜色
 */
const getScoreColor = (score: number, maxScore: number) => {
  const percentage = (score / maxScore) * 100;
  if (percentage >= 90) return 'text-green-600';
  if (percentage >= 80) return 'text-blue-600';
  if (percentage >= 70) return 'text-yellow-600';
  if (percentage >= 60) return 'text-orange-600';
  return 'text-red-600';
};

// ============ 主组件 ============

/**
 * RankingList 学生排名列表组件
 * 
 * @example
 * <RankingList
 *   students={[
 *     { rank: 1, studentId: '1', studentName: '张三', score: 95, maxScore: 100 },
 *     { rank: 2, studentId: '2', studentName: '李四', score: 88, maxScore: 100 },
 *   ]}
 *   maxDisplay={10}
 *   title="成绩排名"
 * />
 * 
 * Requirements: 7.1, 7.2, 7.3, 7.4
 */
export const RankingList: React.FC<RankingListProps> = ({
  students,
  maxDisplay,
  title = '成绩排名',
  showPercentage = true,
}) => {
  // 处理显示数量
  const displayStudents = useMemo(() => {
    if (!students || students.length === 0) return [];
    if (maxDisplay && maxDisplay > 0) {
      return students.slice(0, maxDisplay);
    }
    return students;
  }, [students, maxDisplay]);

  const totalStudents = students?.length || 0;

  // 空数据状态
  if (!students || students.length === 0) {
    return (
      <GlassCard hoverEffect={false} className="p-4 sm:p-6">
        <h3 className="text-base sm:text-lg font-semibold text-gray-700 mb-3 sm:mb-4">{title}</h3>
        <div className="flex items-center justify-center h-[160px] sm:h-[200px] text-gray-400 text-sm">
          暂无排名数据
        </div>
      </GlassCard>
    );
  }

  return (
    <GlassCard hoverEffect={false} className="p-4 sm:p-6">
      <div className="flex items-center justify-between mb-3 sm:mb-4">
        <h3 className="text-base sm:text-lg font-semibold text-gray-700">{title}</h3>
        <span className="text-xs sm:text-sm text-gray-500">
          共 {totalStudents} 人
          {maxDisplay && maxDisplay < totalStudents && (
            <span className="hidden sm:inline"> (显示前 {maxDisplay} 名)</span>
          )}
        </span>
      </div>

      <div className="space-y-1.5 sm:space-y-2 max-h-[320px] sm:max-h-[400px] overflow-y-auto pr-1 sm:pr-2">
        {displayStudents.map((student) => {
          const style = getRankStyle(student.rank, totalStudents);
          const scoreColor = getScoreColor(student.score, student.maxScore);
          const percentage = ((student.score / student.maxScore) * 100).toFixed(1);

          return (
            <div
              key={student.studentId}
              className={`
                flex items-center gap-2 sm:gap-3 p-2 sm:p-3 rounded-lg border
                ${style.bgColor} ${style.borderColor}
                transition-all duration-200 hover:shadow-sm cursor-pointer
              `}
            >
              {/* 排名 */}
              <div className={`
                flex items-center justify-center w-8 h-8 sm:w-10 sm:h-10 rounded-full flex-shrink-0
                ${student.rank <= 3 ? 'bg-white/80' : 'bg-gray-100'}
                font-bold ${style.textColor}
              `}>
                {style.badge || (
                  <span className="text-xs sm:text-sm">{student.rank}</span>
                )}
              </div>

              {/* 学生信息 */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1 sm:gap-2">
                  <span className="font-medium text-gray-800 truncate text-sm sm:text-base">
                    {student.studentName}
                  </span>
                  {style.icon && (
                    <span className="hidden sm:inline">{style.icon}</span>
                  )}
                </div>
                {showPercentage && (
                  <div className="text-[10px] sm:text-xs text-gray-500 mt-0.5">
                    得分率: {percentage}%
                  </div>
                )}
              </div>

              {/* 分数 */}
              <div className="text-right flex-shrink-0">
                <div className={`text-base sm:text-lg font-bold ${scoreColor}`}>
                  {student.score}
                </div>
                <div className="text-[10px] sm:text-xs text-gray-400">
                  / {student.maxScore}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* 查看更多提示 */}
      {maxDisplay && maxDisplay < totalStudents && (
        <div className="mt-3 sm:mt-4 pt-2 sm:pt-3 border-t border-gray-100 text-center">
          <span className="text-xs sm:text-sm text-gray-500">
            还有 {totalStudents - maxDisplay} 名学生未显示
          </span>
        </div>
      )}
    </GlassCard>
  );
};

export default RankingList;
