'use client';

/**
 * ScoreMatrix 组件
 * 
 * Excel 风格的成绩矩阵表格，支持固定首列（学生姓名）和横向滚动。
 * 显示所有学生在所有作业中的得分，以及总分、平均分和班级平均分。
 * 
 * @module components/statistics/ScoreMatrix
 * Requirements: 2.1, 2.2, 2.3, 2.4, 2.5
 */

import React, { useMemo } from 'react';
import { Table, Tooltip, Empty, Spin } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { User, BookOpen, Calculator, TrendingUp } from 'lucide-react';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

// ============ 工具函数 ============

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// ============ 接口定义 ============

/**
 * 学生成绩行数据
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
 */
export interface HomeworkColumn {
  homeworkId: string;
  title: string;
  maxScore: number;
  classAverage: number;
}

/**
 * ScoreMatrix 组件属性
 */
export interface ScoreMatrixProps {
  /** 学生成绩数据列表 */
  students: StudentScoreRow[];
  /** 作业列配置 */
  homeworks: HomeworkColumn[];
  /** 单元格点击回调 */
  onCellClick?: (studentId: string, homeworkId: string) => void;
  /** 列头点击回调 */
  onHeaderClick?: (homeworkId: string) => void;
  /** 加载状态 */
  loading?: boolean;
}

/**
 * 表格行数据类型（包含班级平均行标记）
 */
interface TableRowData extends StudentScoreRow {
  key: string;
  isClassAverage?: boolean;
}

// ============ 子组件 ============

/**
 * 分数单元格组件
 */
interface ScoreCellProps {
  score: number | null;
  maxScore: number;
  onClick?: () => void;
}

const ScoreCell: React.FC<ScoreCellProps> = ({ score, maxScore, onClick }) => {
  if (score === null || score === undefined) {
    return (
      <span className="text-gray-400 select-none">-</span>
    );
  }

  // 根据得分率计算颜色
  const ratio = score / maxScore;
  let colorClass = 'text-gray-700';
  let bgClass = 'bg-gray-50';
  
  if (ratio >= 0.9) {
    colorClass = 'text-green-700';
    bgClass = 'bg-green-50';
  } else if (ratio >= 0.8) {
    colorClass = 'text-blue-700';
    bgClass = 'bg-blue-50';
  } else if (ratio >= 0.6) {
    colorClass = 'text-yellow-700';
    bgClass = 'bg-yellow-50';
  } else {
    colorClass = 'text-red-700';
    bgClass = 'bg-red-50';
  }

  return (
    <Tooltip title={`${score} / ${maxScore} (${(ratio * 100).toFixed(1)}%)`}>
      <span
        className={cn(
          'inline-flex items-center justify-center min-w-[48px] px-2 py-1 rounded-md font-medium text-sm transition-all',
          colorClass,
          bgClass,
          onClick && 'cursor-pointer hover:ring-2 hover:ring-blue-400 hover:ring-offset-1'
        )}
        onClick={onClick}
      >
        {score}
      </span>
    </Tooltip>
  );
};

/**
 * 统计单元格组件（总分/平均分）
 */
interface StatCellProps {
  value: number;
  label: string;
  isAverage?: boolean;
}

const StatCell: React.FC<StatCellProps> = ({ value, label, isAverage }) => {
  return (
    <Tooltip title={label}>
      <span
        className={cn(
          'inline-flex items-center justify-center min-w-[56px] px-2 py-1 rounded-md font-semibold text-sm',
          isAverage 
            ? 'bg-blue-100 text-blue-800' 
            : 'bg-slate-100 text-slate-800'
        )}
      >
        {isAverage ? value.toFixed(1) : value}
      </span>
    </Tooltip>
  );
};

/**
 * 创建班级平均行数据
 */
function createClassAverageRow(homeworks: HomeworkColumn[]): TableRowData {
  // 计算所有作业的总平均分
  const validAverages = homeworks
    .map(h => h.classAverage)
    .filter(avg => avg > 0);
  
  const overallAverage = validAverages.length > 0
    ? validAverages.reduce((sum, avg) => sum + avg, 0) / validAverages.length
    : 0;

  const scores: Record<string, number | null> = {};
  homeworks.forEach((hw) => {
    scores[hw.homeworkId] = hw.classAverage > 0 ? hw.classAverage : null;
  });

  return {
    key: 'class-average',
    studentId: 'class-average',
    studentName: '班级平均',
    scores,
    totalScore: 0,
    averageScore: overallAverage,
    isClassAverage: true,
  };
}

// ============ 主组件 ============

/**
 * ScoreMatrix 成绩矩阵组件
 * 
 * Excel 风格的成绩表格，支持：
 * - 固定首列（学生姓名）
 * - 横向滚动查看所有作业
 * - 单元格点击导航
 * - 列头点击导航
 * - 底部班级平均行
 * 
 * @example
 * <ScoreMatrix
 *   students={students}
 *   homeworks={homeworks}
 *   onCellClick={(studentId, homeworkId) => router.push(`/teacher/statistics/${homeworkId}`)}
 *   onHeaderClick={(homeworkId) => router.push(`/teacher/statistics/${homeworkId}`)}
 *   loading={false}
 * />
 * 
 * Requirements: 2.1, 2.2, 2.3, 2.4, 2.5
 */
export const ScoreMatrix: React.FC<ScoreMatrixProps> = ({
  students,
  homeworks,
  onCellClick,
  onHeaderClick,
  loading = false,
}) => {
  // 构建表格列配置
  const columns = useMemo<ColumnsType<TableRowData>>(() => {
    const cols: ColumnsType<TableRowData> = [
      // 固定列：学生姓名
      {
        title: (
          <div className="flex items-center gap-2 text-gray-700">
            <User className="w-4 h-4" />
            <span>学生姓名</span>
          </div>
        ),
        dataIndex: 'studentName',
        key: 'studentName',
        fixed: 'left',
        width: 140,
        className: 'bg-white',
        render: (name: string, record: TableRowData) => (
          <span 
            className={cn(
              'font-medium',
              record.isClassAverage 
                ? 'text-blue-600 font-semibold' 
                : 'text-gray-900'
            )}
          >
            {name}
          </span>
        ),
      },
    ];

    // 作业列
    homeworks.forEach((homework) => {
      cols.push({
        title: (
          <Tooltip title={`点击查看 "${homework.title}" 详情`}>
            <div
              className={cn(
                'flex flex-col items-center gap-1 py-1 px-2 -mx-2 rounded-md transition-colors',
                onHeaderClick && 'cursor-pointer hover:bg-blue-50'
              )}
              onClick={() => onHeaderClick?.(homework.homeworkId)}
            >
              <BookOpen className="w-4 h-4 text-blue-500" />
              <span className="text-xs font-medium text-gray-700 max-w-[80px] truncate">
                {homework.title}
              </span>
              <span className="text-[10px] text-gray-400">
                满分 {homework.maxScore}
              </span>
            </div>
          </Tooltip>
        ),
        dataIndex: ['scores', homework.homeworkId],
        key: homework.homeworkId,
        width: 100,
        align: 'center',
        render: (_: unknown, record: TableRowData) => {
          const score = record.scores[homework.homeworkId];
          
          // 班级平均行显示平均分
          if (record.isClassAverage) {
            return score !== null && score !== undefined ? (
              <span className="text-blue-600 font-semibold">
                {score.toFixed(1)}
              </span>
            ) : (
              <span className="text-gray-400">-</span>
            );
          }
          
          return (
            <ScoreCell
              score={score}
              maxScore={homework.maxScore}
              onClick={
                score !== null && onCellClick
                  ? () => onCellClick(record.studentId, homework.homeworkId)
                  : undefined
              }
            />
          );
        },
      });
    });

    // 总分列
    cols.push({
      title: (
        <div className="flex items-center gap-2 text-gray-700">
          <Calculator className="w-4 h-4 text-slate-500" />
          <span>总分</span>
        </div>
      ),
      dataIndex: 'totalScore',
      key: 'totalScore',
      width: 90,
      align: 'center',
      render: (value: number, record: TableRowData) => {
        if (record.isClassAverage) {
          return <span className="text-gray-400">-</span>;
        }
        return (
          <StatCell
            value={value}
            label={`总分: ${value}`}
          />
        );
      },
    });

    // 平均分列
    cols.push({
      title: (
        <div className="flex items-center gap-2 text-gray-700">
          <TrendingUp className="w-4 h-4 text-blue-500" />
          <span>平均分</span>
        </div>
      ),
      dataIndex: 'averageScore',
      key: 'averageScore',
      width: 90,
      align: 'center',
      render: (value: number, record: TableRowData) => (
        <StatCell
          value={value}
          label={record.isClassAverage ? '班级总平均分' : `平均分: ${value.toFixed(1)}`}
          isAverage
        />
      ),
    });

    return cols;
  }, [homeworks, onCellClick, onHeaderClick]);

  // 构建数据源（包含班级平均行）
  const dataSource = useMemo<TableRowData[]>(() => {
    const rows: TableRowData[] = students.map((student) => ({
      ...student,
      key: student.studentId,
    }));

    // 添加班级平均行
    if (students.length > 0 && homeworks.length > 0) {
      rows.push(createClassAverageRow(homeworks));
    }

    return rows;
  }, [students, homeworks]);

  // 空状态
  if (!loading && students.length === 0) {
    return (
      <div className="flex items-center justify-center py-16">
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description={
            <span className="text-gray-500">
              暂无成绩数据
            </span>
          }
        />
      </div>
    );
  }

  return (
    <div className="score-matrix-container">
      <Spin spinning={loading}>
        <Table<TableRowData>
          columns={columns}
          dataSource={dataSource}
          pagination={false}
          scroll={{ x: 'max-content' }}
          size="middle"
          bordered
          className="score-matrix-table"
          rowClassName={(record) => 
            cn(
              'transition-colors',
              record.isClassAverage 
                ? 'bg-blue-50/50 font-medium' 
                : 'hover:bg-gray-50'
            )
          }
        />
      </Spin>
      
      {/* 自定义样式 */}
      <style jsx global>{`
        .score-matrix-table .ant-table {
          font-family: var(--font-body);
        }
        
        .score-matrix-table .ant-table-thead > tr > th {
          background: linear-gradient(to bottom, #f8fafc, #f1f5f9);
          border-bottom: 2px solid #e2e8f0;
          padding: 12px 8px;
          white-space: nowrap;
        }
        
        .score-matrix-table .ant-table-tbody > tr > td {
          padding: 10px 8px;
          vertical-align: middle;
        }
        
        .score-matrix-table .ant-table-cell-fix-left {
          background: #ffffff !important;
          box-shadow: 2px 0 8px rgba(0, 0, 0, 0.06);
          z-index: 2;
        }
        
        .score-matrix-table .ant-table-thead .ant-table-cell-fix-left {
          background: linear-gradient(to bottom, #f8fafc, #f1f5f9) !important;
        }
        
        .score-matrix-table .ant-table-row:last-child td {
          border-bottom: 2px solid #e2e8f0;
        }
        
        /* 班级平均行样式 */
        .score-matrix-table .ant-table-row:last-child {
          background: linear-gradient(to bottom, #eff6ff, #dbeafe) !important;
        }
        
        .score-matrix-table .ant-table-row:last-child td {
          background: transparent !important;
        }
        
        .score-matrix-table .ant-table-row:last-child .ant-table-cell-fix-left {
          background: linear-gradient(to bottom, #eff6ff, #dbeafe) !important;
        }
        
        /* 响应式优化 - 平板 */
        @media (max-width: 1023px) {
          .score-matrix-table .ant-table-thead > tr > th {
            padding: 10px 6px;
          }
          
          .score-matrix-table .ant-table-tbody > tr > td {
            padding: 8px 6px;
          }
        }
        
        /* 响应式优化 - 移动端 */
        @media (max-width: 768px) {
          .score-matrix-container {
            position: relative;
            margin-bottom: 32px;
          }
          
          /* 滚动提示 */
          .score-matrix-container::after {
            content: '← 左右滑动查看更多 →';
            position: absolute;
            bottom: -28px;
            left: 50%;
            transform: translateX(-50%);
            font-size: 12px;
            color: #94a3b8;
            white-space: nowrap;
            background: linear-gradient(90deg, transparent, #f8fafc 20%, #f8fafc 80%, transparent);
            padding: 4px 16px;
            border-radius: 12px;
          }
          
          .score-matrix-table .ant-table-thead > tr > th {
            padding: 8px 4px;
            font-size: 12px;
          }
          
          .score-matrix-table .ant-table-tbody > tr > td {
            padding: 6px 4px;
            font-size: 13px;
          }
          
          /* 固定列宽度优化 */
          .score-matrix-table .ant-table-cell-fix-left {
            min-width: 100px !important;
            max-width: 120px !important;
          }
          
          /* 分数单元格紧凑显示 */
          .score-matrix-table .ant-table-tbody .min-w-\\[48px\\] {
            min-width: 40px;
            padding: 2px 4px;
            font-size: 12px;
          }
          
          /* 统计单元格紧凑显示 */
          .score-matrix-table .ant-table-tbody .min-w-\\[56px\\] {
            min-width: 44px;
            padding: 2px 4px;
            font-size: 12px;
          }
        }
        
        /* 超小屏幕 */
        @media (max-width: 480px) {
          .score-matrix-table .ant-table-cell-fix-left {
            min-width: 80px !important;
            max-width: 100px !important;
          }
          
          .score-matrix-table .ant-table-thead > tr > th {
            padding: 6px 3px;
            font-size: 11px;
          }
          
          .score-matrix-table .ant-table-tbody > tr > td {
            padding: 5px 3px;
            font-size: 12px;
          }
        }
        
        /* 触摸设备优化 */
        @media (hover: none) and (pointer: coarse) {
          .score-matrix-table .ant-table-tbody .min-w-\\[48px\\] {
            min-width: 44px;
            min-height: 44px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
          }
          
          /* 增大点击区域 */
          .score-matrix-table .ant-table-thead > tr > th > div {
            min-height: 44px;
            display: flex;
            align-items: center;
            justify-content: center;
          }
        }
        
        /* 横屏模式优化 */
        @media (max-height: 500px) and (orientation: landscape) {
          .score-matrix-table .ant-table-thead > tr > th {
            padding: 6px 4px;
          }
          
          .score-matrix-table .ant-table-tbody > tr > td {
            padding: 4px;
          }
          
          .score-matrix-container::after {
            display: none;
          }
        }
      `}</style>
    </div>
  );
};

export default ScoreMatrix;
