'use client';

/**
 * ScoreDistribution 分数分布图组件
 * 
 * 使用 Recharts BarChart 展示各分数段的学生人数分布。
 * 支持自定义分数段配置，高亮最多学生的分数段。
 * 
 * @module components/statistics/ScoreDistribution
 * Requirements: 6.1, 6.2, 6.3, 6.4
 */

import React, { useMemo } from 'react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Cell,
  TooltipProps,
} from 'recharts';
import { GlassCard } from '@/components/design-system/GlassCard';

// ============ 接口定义 ============

/**
 * 分数段配置
 */
export interface ScoreRange {
  label: string;
  min: number;
  max: number;
}

/**
 * 分布数据项
 */
export interface DistributionItem {
  label: string;
  count: number;
  percentage: number;
  min: number;
  max: number;
}

/**
 * ScoreDistribution 组件属性
 */
export interface ScoreDistributionProps {
  /** 分数数组 */
  scores: number[];
  /** 自定义分数段配置 */
  ranges?: ScoreRange[];
  /** 满分值（默认 100） */
  maxScore?: number;
  /** 图表高度（默认 300） */
  height?: number;
  /** 标题 */
  title?: string;
}

// ============ 默认配置 ============

/**
 * 默认分数段配置
 */
const DEFAULT_RANGES: ScoreRange[] = [
  { label: '0-59', min: 0, max: 59 },
  { label: '60-69', min: 60, max: 69 },
  { label: '70-79', min: 70, max: 79 },
  { label: '80-89', min: 80, max: 89 },
  { label: '90-100', min: 90, max: 100 },
];

// ============ 颜色配置 ============

const COLORS = {
  // 普通柱子
  normal: {
    fill: '#3B82F6',      // blue-500
    hover: '#2563EB',     // blue-600
  },
  // 高亮柱子（最多学生）
  highlight: {
    fill: '#22D3EE',      // cyan-400
    hover: '#06B6D4',     // cyan-500
  },
  // 网格
  grid: '#E5E7EB',        // gray-200
  // 文字
  text: '#64748B',        // slate-500
};

// ============ 自定义 Tooltip ============

interface CustomTooltipProps extends TooltipProps<number, string> {
  totalStudents: number;
}

const CustomTooltip: React.FC<CustomTooltipProps> = ({ 
  active, 
  payload, 
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  totalStudents 
}) => {
  if (!active || !payload || !payload.length) return null;

  const data = payload[0].payload as DistributionItem;

  return (
    <div className="bg-white/95 backdrop-blur-sm border border-gray-200 rounded-lg shadow-lg p-3 min-w-[140px]">
      <p className="text-sm font-semibold text-gray-700 mb-2 border-b border-gray-100 pb-2">
        {data.label} 分
      </p>
      <div className="space-y-1.5">
        <div className="flex items-center justify-between text-sm">
          <span className="text-gray-600">人数</span>
          <span className="font-medium text-gray-900">{data.count} 人</span>
        </div>
        <div className="flex items-center justify-between text-sm">
          <span className="text-gray-600">占比</span>
          <span className="font-medium text-blue-600">{data.percentage.toFixed(1)}%</span>
        </div>
        <div className="flex items-center justify-between text-sm">
          <span className="text-gray-600">分数范围</span>
          <span className="font-medium text-gray-700">{data.min}-{data.max}</span>
        </div>
      </div>
    </div>
  );
};

// ============ 响应式高度 Hook ============

/**
 * 根据屏幕宽度返回合适的图表高度
 */
function useResponsiveHeight(defaultHeight: number): number {
  const [height, setHeight] = React.useState(defaultHeight);

  React.useEffect(() => {
    const updateHeight = () => {
      const width = window.innerWidth;
      if (width < 480) {
        setHeight(Math.min(defaultHeight, 220));
      } else if (width < 768) {
        setHeight(Math.min(defaultHeight, 260));
      } else {
        setHeight(defaultHeight);
      }
    };

    updateHeight();
    window.addEventListener('resize', updateHeight);
    return () => window.removeEventListener('resize', updateHeight);
  }, [defaultHeight]);

  return height;
}

// ============ 主组件 ============

/**
 * ScoreDistribution 分数分布图组件
 * 
 * 展示各分数段的学生人数分布，支持：
 * - 自定义分数段配置
 * - 高亮最多学生的分数段
 * - 悬停显示详细信息（人数、百分比）
 * - 响应式布局适配移动端
 * 
 * @example
 * <ScoreDistribution
 *   scores={[85, 72, 90, 65, 78, 88, 92, 70, 85, 95]}
 *   height={300}
 *   title="成绩分布"
 * />
 * 
 * Requirements: 6.1, 6.2, 6.3, 6.4, 9.3
 */
export const ScoreDistribution: React.FC<ScoreDistributionProps> = ({
  scores,
  ranges = DEFAULT_RANGES,
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  maxScore = 100,
  height = 300,
  title = '分数分布',
}) => {
  // 响应式高度
  const responsiveHeight = useResponsiveHeight(height);
  // 计算分布数据
  const distributionData = useMemo((): DistributionItem[] => {
    if (!scores || scores.length === 0) return [];

    const total = scores.length;
    
    return ranges.map(range => {
      const count = scores.filter(
        score => score >= range.min && score <= range.max
      ).length;
      
      return {
        label: range.label,
        count,
        percentage: (count / total) * 100,
        min: range.min,
        max: range.max,
      };
    });
  }, [scores, ranges]);

  // 找出最多学生的分数段索引
  const maxCountIndex = useMemo(() => {
    if (distributionData.length === 0) return -1;
    
    let maxIdx = 0;
    let maxCount = distributionData[0].count;
    
    distributionData.forEach((item, idx) => {
      if (item.count > maxCount) {
        maxCount = item.count;
        maxIdx = idx;
      }
    });
    
    return maxIdx;
  }, [distributionData]);

  // Y 轴最大值
  const yAxisMax = useMemo(() => {
    if (distributionData.length === 0) return 10;
    const maxCount = Math.max(...distributionData.map(d => d.count));
    return Math.ceil(maxCount * 1.2) || 10;
  }, [distributionData]);

  // 空数据状态
  if (!scores || scores.length === 0) {
    return (
      <GlassCard hoverEffect={false} className="p-6">
        <h3 className="text-lg font-semibold text-gray-700 mb-4">{title}</h3>
        <div className="flex items-center justify-center h-[200px] text-gray-400">
          暂无数据
        </div>
      </GlassCard>
    );
  }

  return (
    <GlassCard hoverEffect={false} className="p-4 sm:p-6">
      <h3 className="text-base sm:text-lg font-semibold text-gray-700 mb-3 sm:mb-4">{title}</h3>
      
      <div style={{ height: responsiveHeight }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={distributionData}
            margin={{ top: 20, right: 20, left: 10, bottom: 20 }}
          >
            <CartesianGrid 
              strokeDasharray="3 3" 
              stroke={COLORS.grid}
              vertical={false}
            />
            
            <XAxis
              dataKey="label"
              tick={{ fill: COLORS.text, fontSize: 11 }}
              axisLine={{ stroke: COLORS.grid }}
              tickLine={{ stroke: COLORS.grid }}
              interval={0}
              angle={-45}
              textAnchor="end"
              height={50}
            />
            
            <YAxis
              domain={[0, yAxisMax]}
              tick={{ fill: COLORS.text, fontSize: 12 }}
              axisLine={{ stroke: COLORS.grid }}
              tickLine={{ stroke: COLORS.grid }}
              label={{
                value: '人数',
                angle: -90,
                position: 'insideLeft',
                style: { fill: COLORS.text, fontSize: 12 }
              }}
            />

            <Tooltip
              content={<CustomTooltip totalStudents={scores.length} />}
              cursor={{ fill: 'rgba(0, 0, 0, 0.05)' }}
            />

            <Bar
              dataKey="count"
              radius={[4, 4, 0, 0]}
              maxBarSize={60}
            >
              {distributionData.map((_, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={index === maxCountIndex ? COLORS.highlight.fill : COLORS.normal.fill}
                  className="cursor-pointer transition-opacity hover:opacity-80"
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* 统计摘要 - 响应式布局 */}
      <div className="mt-3 sm:mt-4 pt-3 sm:pt-4 border-t border-gray-100">
        <div className="flex flex-wrap items-center justify-center gap-2 sm:gap-4 text-xs sm:text-sm">
          {distributionData.map((item, index) => (
            <div 
              key={item.label}
              className={`flex items-center gap-1 sm:gap-2 px-2 sm:px-3 py-1 sm:py-1.5 rounded-full ${
                index === maxCountIndex 
                  ? 'bg-cyan-50 text-cyan-700' 
                  : 'bg-gray-50 text-gray-600'
              }`}
            >
              <span className="font-medium">{item.label}:</span>
              <span>{item.count}人</span>
              <span className="text-[10px] sm:text-xs opacity-75 hidden sm:inline">({item.percentage.toFixed(1)}%)</span>
            </div>
          ))}
        </div>
      </div>

      {/* 总人数 */}
      <div className="mt-2 sm:mt-3 text-center text-xs sm:text-sm text-gray-500">
        共 <span className="font-semibold text-gray-700">{scores.length}</span> 名学生
      </div>
    </GlassCard>
  );
};

export default ScoreDistribution;
