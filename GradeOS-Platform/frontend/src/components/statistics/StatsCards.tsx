'use client';

/**
 * StatsCards 组件
 * 
 * 统计指标卡片组组件，显示作业的关键统计数据。
 * 使用 GlassCard 设计风格，展示平均分、中位数、最高分、最低分、标准差、学生人数。
 * 
 * @module components/statistics/StatsCards
 * Requirements: 4.1, 4.2, 4.3, 4.4, 4.5
 */

import React from 'react';
import { 
  TrendingUp, 
  BarChart3, 
  ArrowUp, 
  ArrowDown, 
  Activity, 
  Users 
} from 'lucide-react';
import { GlassCard } from '@/components/design-system/GlassCard';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

// ============ 工具函数 ============

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// ============ 接口定义 ============

/**
 * 作业统计数据
 */
export interface HomeworkStats {
  /** 平均分 */
  average: number;
  /** 中位数 */
  median: number;
  /** 最高分 */
  max: number;
  /** 最低分 */
  min: number;
  /** 标准差 */
  stdDev: number;
  /** 学生人数 */
  studentCount: number;
  /** 满分值 */
  maxPossibleScore: number;
}

/**
 * StatsCards 组件属性
 */
export interface StatsCardsProps {
  /** 统计数据 */
  stats: HomeworkStats | null | undefined;
}

// ============ 子组件 ============

/**
 * 单个统计卡片配置
 */
interface StatCardConfig {
  key: string;
  label: string;
  icon: React.ReactNode;
  getValue: (stats: HomeworkStats) => string;
  getSubtext?: (stats: HomeworkStats) => string;
  colorClass: string;
  bgClass: string;
}

/**
 * 单个统计卡片组件
 */
interface StatCardProps {
  label: string;
  value: string;
  subtext?: string;
  icon: React.ReactNode;
  colorClass: string;
  bgClass: string;
}

const StatCard: React.FC<StatCardProps> = ({
  label,
  value,
  subtext,
  icon,
  colorClass,
  bgClass,
}) => {
  return (
    <GlassCard 
      hoverEffect={true}
      className="p-3 sm:p-5 cursor-pointer"
    >
      <div className="flex items-start justify-between">
        {/* 图标 */}
        <div 
          className={cn(
            'flex items-center justify-center w-10 h-10 sm:w-12 sm:h-12 rounded-xl',
            bgClass
          )}
        >
          <div className={cn(colorClass, '[&>svg]:w-5 [&>svg]:h-5 sm:[&>svg]:w-6 sm:[&>svg]:h-6')}>
            {icon}
          </div>
        </div>
        
        {/* 数值和标签 */}
        <div className="flex-1 ml-3 sm:ml-4 text-right">
          <p className="text-xs sm:text-sm font-medium text-gray-500 mb-0.5 sm:mb-1">
            {label}
          </p>
          <p className={cn(
            'text-xl sm:text-2xl font-bold tracking-tight',
            colorClass
          )}>
            {value}
          </p>
          {subtext && (
            <p className="text-[10px] sm:text-xs text-gray-400 mt-0.5 sm:mt-1 truncate">
              {subtext}
            </p>
          )}
        </div>
      </div>
    </GlassCard>
  );
};

// ============ 卡片配置 ============

/**
 * 统计卡片配置列表
 */
const STAT_CARDS: StatCardConfig[] = [
  {
    key: 'average',
    label: '平均分',
    icon: <TrendingUp className="w-6 h-6" />,
    getValue: (stats) => stats.average.toFixed(1),
    getSubtext: (stats) => `满分 ${stats.maxPossibleScore}`,
    colorClass: 'text-blue-600',
    bgClass: 'bg-blue-100',
  },
  {
    key: 'median',
    label: '中位数',
    icon: <BarChart3 className="w-6 h-6" />,
    getValue: (stats) => stats.median.toFixed(1),
    getSubtext: (stats) => {
      const diff = stats.median - stats.average;
      if (Math.abs(diff) < 0.1) return '与平均分持平';
      return diff > 0 ? `高于平均 ${diff.toFixed(1)}` : `低于平均 ${Math.abs(diff).toFixed(1)}`;
    },
    colorClass: 'text-purple-600',
    bgClass: 'bg-purple-100',
  },
  {
    key: 'max',
    label: '最高分',
    icon: <ArrowUp className="w-6 h-6" />,
    getValue: (stats) => stats.max.toFixed(1),
    getSubtext: (stats) => {
      const ratio = (stats.max / stats.maxPossibleScore) * 100;
      return `得分率 ${ratio.toFixed(0)}%`;
    },
    colorClass: 'text-green-600',
    bgClass: 'bg-green-100',
  },
  {
    key: 'min',
    label: '最低分',
    icon: <ArrowDown className="w-6 h-6" />,
    getValue: (stats) => stats.min.toFixed(1),
    getSubtext: (stats) => {
      const ratio = (stats.min / stats.maxPossibleScore) * 100;
      return `得分率 ${ratio.toFixed(0)}%`;
    },
    colorClass: 'text-red-600',
    bgClass: 'bg-red-100',
  },
  {
    key: 'stdDev',
    label: '标准差',
    icon: <Activity className="w-6 h-6" />,
    getValue: (stats) => stats.stdDev.toFixed(2),
    getSubtext: (stats) => {
      // 变异系数 (CV) = 标准差 / 平均值
      if (stats.average === 0) return '无法计算变异系数';
      const cv = (stats.stdDev / stats.average) * 100;
      if (cv < 10) return '成绩分布集中';
      if (cv < 20) return '成绩分布适中';
      return '成绩分布分散';
    },
    colorClass: 'text-orange-600',
    bgClass: 'bg-orange-100',
  },
  {
    key: 'studentCount',
    label: '学生人数',
    icon: <Users className="w-6 h-6" />,
    getValue: (stats) => stats.studentCount.toString(),
    getSubtext: () => '已批改',
    colorClass: 'text-cyan-600',
    bgClass: 'bg-cyan-100',
  },
];

// ============ 主组件 ============

/**
 * StatsCards 统计卡片组组件
 * 
 * 以卡片形式展示作业的关键统计指标：
 * - 平均分：所有学生得分的算术平均值
 * - 中位数：排序后的中间值
 * - 最高分：最高得分
 * - 最低分：最低得分
 * - 标准差：成绩分布的离散程度
 * - 学生人数：参与批改的学生数量
 * 
 * @example
 * <StatsCards
 *   stats={{
 *     average: 78.5,
 *     median: 80,
 *     max: 98,
 *     min: 45,
 *     stdDev: 12.3,
 *     studentCount: 35,
 *     maxPossibleScore: 100,
 *   }}
 * />
 * 
 * Requirements: 4.1, 4.2, 4.3, 4.4, 4.5
 */
export const StatsCards: React.FC<StatsCardsProps> = ({ stats }) => {
  // 处理空数据状态
  if (!stats) {
    return (
      <div className="grid grid-cols-2 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-3 sm:gap-4">
        {STAT_CARDS.map((config) => (
          <GlassCard 
            key={config.key}
            hoverEffect={false}
            className="p-3 sm:p-5 opacity-50"
          >
            <div className="flex items-start justify-between">
              <div 
                className={cn(
                  'flex items-center justify-center w-10 h-10 sm:w-12 sm:h-12 rounded-xl',
                  'bg-gray-100'
                )}
              >
                <div className="text-gray-400 [&>svg]:w-5 [&>svg]:h-5 sm:[&>svg]:w-6 sm:[&>svg]:h-6">
                  {config.icon}
                </div>
              </div>
              <div className="flex-1 ml-3 sm:ml-4 text-right">
                <p className="text-xs sm:text-sm font-medium text-gray-400 mb-0.5 sm:mb-1">
                  {config.label}
                </p>
                <p className="text-xl sm:text-2xl font-bold text-gray-300">
                  --
                </p>
                <p className="text-[10px] sm:text-xs text-gray-300 mt-0.5 sm:mt-1">
                  暂无数据
                </p>
              </div>
            </div>
          </GlassCard>
        ))}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-3 sm:gap-4">
      {STAT_CARDS.map((config) => (
        <StatCard
          key={config.key}
          label={config.label}
          value={config.getValue(stats)}
          subtext={config.getSubtext?.(stats)}
          icon={config.icon}
          colorClass={config.colorClass}
          bgClass={config.bgClass}
        />
      ))}
    </div>
  );
};

export default StatsCards;
