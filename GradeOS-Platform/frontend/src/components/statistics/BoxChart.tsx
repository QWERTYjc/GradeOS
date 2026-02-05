'use client';

/**
 * BoxChart 箱线图组件
 * 
 * 使用 Recharts ComposedChart 实现箱线图（Box-Whisker Plot）。
 * 展示数据分布的五数概括：最小值、Q1、中位数、Q3、最大值，以及异常值。
 * 
 * @module components/statistics/BoxChart
 * Requirements: 5.1, 5.2, 5.3
 */

import React, { useMemo } from 'react';
import {
  ResponsiveContainer,
  ComposedChart,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceArea,
  ReferenceLine,
  Scatter,
  Cell,
  TooltipProps,
} from 'recharts';
import { GlassCard } from '@/components/design-system/GlassCard';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

// ============ 工具函数 ============

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// ============ 接口定义 ============

/**
 * 箱线图数据接口
 * 
 * @property min - 非异常值的最小值（下须线端点）
 * @property q1 - 第一四分位数（箱体下边界）
 * @property median - 中位数（箱体中线）
 * @property q3 - 第三四分位数（箱体上边界）
 * @property max - 非异常值的最大值（上须线端点）
 * @property outliers - 异常值数组
 * @property mean - 平均值
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
 * BoxChart 组件属性
 */
export interface BoxChartProps {
  /** 箱线图数据 */
  data: BoxPlotData | null | undefined;
  /** 图表宽度（默认 100%） */
  width?: number | string;
  /** 图表高度（默认 300） */
  height?: number;
  /** 满分值（用于 Y 轴范围，默认 100） */
  maxScore?: number;
  /** 标题 */
  title?: string;
}

// ============ 颜色配置 ============

const COLORS = {
  // 箱体颜色
  box: {
    fill: 'rgba(37, 99, 235, 0.2)',      // --color-azure with opacity
    stroke: '#2563EB',                    // --color-azure
  },
  // 中位数线
  median: {
    stroke: '#2563EB',                    // --color-azure
  },
  // 均值点
  mean: {
    fill: '#22D3EE',                      // --color-cyan
    stroke: '#0891B2',                    // cyan-600
  },
  // 须线
  whisker: {
    stroke: '#64748B',                    // slate-500
  },
  // 异常值
  outlier: {
    fill: '#F97316',                      // orange-500
    stroke: '#EA580C',                    // orange-600
  },
  // 网格
  grid: {
    stroke: '#E5E7EB',                    // --color-line
  },
};

// ============ 自定义 Tooltip ============

interface CustomTooltipProps extends TooltipProps<number, string> {
  boxData: BoxPlotData | null | undefined;
}

const CustomTooltip: React.FC<CustomTooltipProps> = ({ active, boxData }) => {
  if (!active || !boxData) return null;

  const items = [
    { label: '最大值', value: boxData.max, color: COLORS.whisker.stroke },
    { label: 'Q3 (75%)', value: boxData.q3, color: COLORS.box.stroke },
    { label: '中位数', value: boxData.median, color: COLORS.median.stroke },
    { label: '平均值', value: boxData.mean, color: COLORS.mean.fill },
    { label: 'Q1 (25%)', value: boxData.q1, color: COLORS.box.stroke },
    { label: '最小值', value: boxData.min, color: COLORS.whisker.stroke },
  ];

  return (
    <div className="bg-white/95 backdrop-blur-sm border border-gray-200 rounded-lg shadow-lg p-3 min-w-[160px]">
      <p className="text-sm font-semibold text-gray-700 mb-2 border-b border-gray-100 pb-2">
        成绩分布
      </p>
      <div className="space-y-1.5">
        {items.map((item) => (
          <div key={item.label} className="flex items-center justify-between text-sm">
            <span className="text-gray-600 flex items-center gap-2">
              <span 
                className="w-2 h-2 rounded-full" 
                style={{ backgroundColor: item.color }}
              />
              {item.label}
            </span>
            <span className="font-medium text-gray-900">
              {item.value.toFixed(1)}
            </span>
          </div>
        ))}
        {boxData.outliers.length > 0 && (
          <>
            <div className="border-t border-gray-100 pt-1.5 mt-1.5">
              <span className="text-gray-600 flex items-center gap-2 text-sm">
                <span 
                  className="w-2 h-2 rounded-full" 
                  style={{ backgroundColor: COLORS.outlier.fill }}
                />
                异常值 ({boxData.outliers.length}个)
              </span>
              <div className="text-xs text-gray-500 mt-1 ml-4">
                {boxData.outliers.slice(0, 5).map((v, i) => (
                  <span key={i}>
                    {v.toFixed(1)}
                    {i < Math.min(boxData.outliers.length - 1, 4) ? ', ' : ''}
                  </span>
                ))}
                {boxData.outliers.length > 5 && <span>...</span>}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

// ============ 自定义箱线图形状 ============

/**
 * 自定义箱线图 SVG 渲染
 * 使用 SVG 直接绘制箱线图的各个部分
 */
interface BoxPlotShapeProps {
  data: BoxPlotData;
  xCenter: number;
  yScale: (value: number) => number;
  boxWidth: number;
}

const BoxPlotShape: React.FC<BoxPlotShapeProps> = ({ 
  data, 
  xCenter, 
  yScale, 
  boxWidth 
}) => {
  const halfWidth = boxWidth / 2;
  const whiskerWidth = boxWidth / 3;

  // 计算 Y 坐标（注意：SVG Y 轴是从上到下的）
  const yMin = yScale(data.min);
  const yQ1 = yScale(data.q1);
  const yMedian = yScale(data.median);
  const yQ3 = yScale(data.q3);
  const yMax = yScale(data.max);
  const yMean = yScale(data.mean);

  return (
    <g className="box-plot-shape">
      {/* 下须线（min 到 Q1） */}
      <line
        x1={xCenter}
        y1={yMin}
        x2={xCenter}
        y2={yQ1}
        stroke={COLORS.whisker.stroke}
        strokeWidth={2}
        strokeDasharray="4 2"
      />
      {/* 下须线端点 */}
      <line
        x1={xCenter - whiskerWidth}
        y1={yMin}
        x2={xCenter + whiskerWidth}
        y2={yMin}
        stroke={COLORS.whisker.stroke}
        strokeWidth={2}
      />

      {/* 上须线（Q3 到 max） */}
      <line
        x1={xCenter}
        y1={yQ3}
        x2={xCenter}
        y2={yMax}
        stroke={COLORS.whisker.stroke}
        strokeWidth={2}
        strokeDasharray="4 2"
      />
      {/* 上须线端点 */}
      <line
        x1={xCenter - whiskerWidth}
        y1={yMax}
        x2={xCenter + whiskerWidth}
        y2={yMax}
        stroke={COLORS.whisker.stroke}
        strokeWidth={2}
      />

      {/* 箱体（Q1 到 Q3） */}
      <rect
        x={xCenter - halfWidth}
        y={yQ3}
        width={boxWidth}
        height={yQ1 - yQ3}
        fill={COLORS.box.fill}
        stroke={COLORS.box.stroke}
        strokeWidth={2}
        rx={4}
        ry={4}
      />

      {/* 中位数线 */}
      <line
        x1={xCenter - halfWidth}
        y1={yMedian}
        x2={xCenter + halfWidth}
        y2={yMedian}
        stroke={COLORS.median.stroke}
        strokeWidth={3}
      />

      {/* 均值点（菱形） */}
      <polygon
        points={`
          ${xCenter},${yMean - 6}
          ${xCenter + 6},${yMean}
          ${xCenter},${yMean + 6}
          ${xCenter - 6},${yMean}
        `}
        fill={COLORS.mean.fill}
        stroke={COLORS.mean.stroke}
        strokeWidth={1.5}
      />

      {/* 异常值点 */}
      {data.outliers.map((outlier, index) => (
        <circle
          key={index}
          cx={xCenter}
          cy={yScale(outlier)}
          r={5}
          fill={COLORS.outlier.fill}
          stroke={COLORS.outlier.stroke}
          strokeWidth={1.5}
        />
      ))}
    </g>
  );
};

// ============ 图例组件 ============

const Legend: React.FC = () => {
  const items = [
    { label: 'IQR 区间 (Q1-Q3)', shortLabel: 'IQR', color: COLORS.box.fill, border: COLORS.box.stroke, type: 'box' },
    { label: '中位数', shortLabel: '中位数', color: COLORS.median.stroke, type: 'line' },
    { label: '平均值', shortLabel: '均值', color: COLORS.mean.fill, type: 'diamond' },
    { label: '异常值', shortLabel: '异常', color: COLORS.outlier.fill, type: 'circle' },
  ];

  return (
    <div className="flex flex-wrap items-center justify-center gap-2 sm:gap-4 mt-4 text-xs sm:text-sm">
      {items.map((item) => (
        <div key={item.label} className="flex items-center gap-1 sm:gap-2">
          {item.type === 'box' && (
            <div 
              className="w-3 h-2 sm:w-4 sm:h-3 rounded-sm border sm:border-2"
              style={{ 
                backgroundColor: item.color, 
                borderColor: item.border 
              }}
            />
          )}
          {item.type === 'line' && (
            <div 
              className="w-3 sm:w-4 h-0.5"
              style={{ backgroundColor: item.color }}
            />
          )}
          {item.type === 'diamond' && (
            <svg className="w-2.5 h-2.5 sm:w-3 sm:h-3" viewBox="0 0 12 12">
              <polygon
                points="6,0 12,6 6,12 0,6"
                fill={item.color}
              />
            </svg>
          )}
          {item.type === 'circle' && (
            <div 
              className="w-2 h-2 sm:w-3 sm:h-3 rounded-full"
              style={{ backgroundColor: item.color }}
            />
          )}
          <span className="text-gray-600 hidden sm:inline">{item.label}</span>
          <span className="text-gray-600 sm:hidden">{item.shortLabel}</span>
        </div>
      ))}
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
 * BoxChart 箱线图组件
 * 
 * 使用 Recharts 和自定义 SVG 实现箱线图，展示：
 * - 箱体：Q1 到 Q3 的四分位距（IQR）
 * - 中位数线：数据的中间值
 * - 须线：延伸到非异常值的最小/最大值
 * - 均值点：数据的平均值（菱形标记）
 * - 异常值：超出 1.5*IQR 范围的数据点
 * 
 * @example
 * <BoxChart
 *   data={{
 *     min: 45,
 *     q1: 65,
 *     median: 75,
 *     q3: 85,
 *     max: 98,
 *     outliers: [20, 25],
 *     mean: 73.5,
 *   }}
 *   height={300}
 *   maxScore={100}
 *   title="成绩分布"
 * />
 * 
 * Requirements: 5.1, 5.2, 5.3, 9.3
 */
export const BoxChart: React.FC<BoxChartProps> = ({
  data,
  width = '100%',
  height = 300,
  maxScore = 100,
  title = '成绩分布箱线图',
}) => {
  // 响应式高度
  const responsiveHeight = useResponsiveHeight(height);
  // 计算 Y 轴范围
  const yDomain = useMemo(() => {
    if (!data) return [0, maxScore];
    
    // 考虑异常值来确定 Y 轴范围
    const allValues = [data.min, data.max, ...data.outliers];
    const minValue = Math.min(...allValues);
    const maxValue = Math.max(...allValues);
    
    // 添加一些边距
    const padding = (maxValue - minValue) * 0.1 || 10;
    return [
      Math.max(0, Math.floor(minValue - padding)),
      Math.min(maxScore, Math.ceil(maxValue + padding)),
    ];
  }, [data, maxScore]);

  // 空数据状态
  if (!data) {
    return (
      <GlassCard hoverEffect={false} className="p-6">
        <h3 className="text-lg font-semibold text-gray-700 mb-4">{title}</h3>
        <div className="flex items-center justify-center h-[200px] text-gray-400">
          暂无数据
        </div>
      </GlassCard>
    );
  }

  // 检查数据是否有效（所有值相同的情况）
  const isCollapsed = data.min === data.max;

  return (
    <GlassCard hoverEffect={false} className="p-4 sm:p-6">
      <h3 className="text-base sm:text-lg font-semibold text-gray-700 mb-3 sm:mb-4">{title}</h3>
      
      <div style={{ width, height: responsiveHeight }}>
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart
            margin={{ top: 20, right: 30, left: 20, bottom: 20 }}
          >
            <CartesianGrid 
              strokeDasharray="3 3" 
              stroke={COLORS.grid.stroke}
              vertical={false}
            />
            
            <XAxis 
              type="category"
              dataKey="name"
              tick={false}
              axisLine={{ stroke: COLORS.grid.stroke }}
            />
            
            <YAxis
              type="number"
              domain={yDomain}
              tick={{ fill: '#64748B', fontSize: 12 }}
              axisLine={{ stroke: COLORS.grid.stroke }}
              tickLine={{ stroke: COLORS.grid.stroke }}
              label={{ 
                value: '分数', 
                angle: -90, 
                position: 'insideLeft',
                style: { fill: '#64748B', fontSize: 12 }
              }}
            />

            <Tooltip
              content={<CustomTooltip boxData={data} />}
              cursor={{ fill: 'rgba(0, 0, 0, 0.05)' }}
            />

            {/* 使用 ReferenceArea 绘制 IQR 区域 */}
            {!isCollapsed && (
              <ReferenceArea
                y1={data.q1}
                y2={data.q3}
                fill={COLORS.box.fill}
                stroke={COLORS.box.stroke}
                strokeWidth={2}
                radius={4}
              />
            )}

            {/* 中位数参考线 */}
            <ReferenceLine
              y={data.median}
              stroke={COLORS.median.stroke}
              strokeWidth={3}
              label={{
                value: `中位数: ${data.median.toFixed(1)}`,
                position: 'right',
                fill: COLORS.median.stroke,
                fontSize: 11,
              }}
            />

            {/* 均值参考线 */}
            <ReferenceLine
              y={data.mean}
              stroke={COLORS.mean.fill}
              strokeWidth={2}
              strokeDasharray="5 3"
              label={{
                value: `均值: ${data.mean.toFixed(1)}`,
                position: 'left',
                fill: COLORS.mean.stroke,
                fontSize: 11,
              }}
            />

            {/* 最大值参考线 */}
            <ReferenceLine
              y={data.max}
              stroke={COLORS.whisker.stroke}
              strokeWidth={1}
              strokeDasharray="3 3"
              label={{
                value: `最高: ${data.max.toFixed(1)}`,
                position: 'right',
                fill: COLORS.whisker.stroke,
                fontSize: 10,
              }}
            />

            {/* 最小值参考线 */}
            <ReferenceLine
              y={data.min}
              stroke={COLORS.whisker.stroke}
              strokeWidth={1}
              strokeDasharray="3 3"
              label={{
                value: `最低: ${data.min.toFixed(1)}`,
                position: 'right',
                fill: COLORS.whisker.stroke,
                fontSize: 10,
              }}
            />

            {/* Q1 参考线 */}
            {!isCollapsed && (
              <ReferenceLine
                y={data.q1}
                stroke={COLORS.box.stroke}
                strokeWidth={1}
                strokeOpacity={0.5}
                label={{
                  value: `Q1: ${data.q1.toFixed(1)}`,
                  position: 'left',
                  fill: COLORS.box.stroke,
                  fontSize: 10,
                }}
              />
            )}

            {/* Q3 参考线 */}
            {!isCollapsed && (
              <ReferenceLine
                y={data.q3}
                stroke={COLORS.box.stroke}
                strokeWidth={1}
                strokeOpacity={0.5}
                label={{
                  value: `Q3: ${data.q3.toFixed(1)}`,
                  position: 'left',
                  fill: COLORS.box.stroke,
                  fontSize: 10,
                }}
              />
            )}

            {/* 异常值散点 */}
            {data.outliers.length > 0 && (
              <Scatter
                data={data.outliers.map((value, index) => ({ 
                  x: 0.5, 
                  y: value,
                  name: `异常值 ${index + 1}`,
                }))}
                dataKey="y"
                fill={COLORS.outlier.fill}
                stroke={COLORS.outlier.stroke}
                strokeWidth={1.5}
              >
                {data.outliers.map((_, index) => (
                  <Cell key={index} />
                ))}
              </Scatter>
            )}
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {/* 图例 */}
      <Legend />

      {/* 统计摘要 */}
      <div className="mt-3 sm:mt-4 pt-3 sm:pt-4 border-t border-gray-100">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 sm:gap-4 text-center">
          <div>
            <p className="text-[10px] sm:text-xs text-gray-500">四分位距 (IQR)</p>
            <p className="text-base sm:text-lg font-semibold text-blue-600">
              {(data.q3 - data.q1).toFixed(1)}
            </p>
          </div>
          <div>
            <p className="text-[10px] sm:text-xs text-gray-500">极差</p>
            <p className="text-base sm:text-lg font-semibold text-gray-700">
              {(data.max - data.min).toFixed(1)}
            </p>
          </div>
          <div>
            <p className="text-[10px] sm:text-xs text-gray-500">中位数-均值差</p>
            <p className={cn(
              'text-base sm:text-lg font-semibold',
              data.median > data.mean ? 'text-green-600' : 'text-orange-600'
            )}>
              {(data.median - data.mean).toFixed(1)}
            </p>
          </div>
          <div>
            <p className="text-[10px] sm:text-xs text-gray-500">异常值数量</p>
            <p className={cn(
              'text-base sm:text-lg font-semibold',
              data.outliers.length > 0 ? 'text-orange-500' : 'text-gray-700'
            )}>
              {data.outliers.length}
            </p>
          </div>
        </div>
      </div>
    </GlassCard>
  );
};

export default BoxChart;
