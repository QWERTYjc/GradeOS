/**
 * CSV 导出工具函数
 * 
 * 提供成绩数据的 CSV 导出功能
 * 
 * @module utils/csvExport
 * Requirements: 8.1, 8.2, 8.3
 */

import type { StudentScoreRow, HomeworkColumn } from '@/components/statistics/ScoreMatrix';

/**
 * CSV 导出数据接口
 */
export interface CSVExportData {
  headers: string[];
  rows: (string | number)[][];
  filename: string;
}

/**
 * 转义 CSV 单元格内容
 * 
 * 处理特殊字符：
 * - 包含逗号、引号、换行符的内容需要用双引号包裹
 * - 内容中的双引号需要转义为两个双引号
 * 
 * @param value - 单元格值
 * @returns 转义后的字符串
 */
export function escapeCSVCell(value: string | number | null | undefined): string {
  if (value === null || value === undefined) {
    return '';
  }
  
  const str = String(value);
  
  // 检查是否需要转义
  const needsEscape = str.includes(',') || 
                      str.includes('"') || 
                      str.includes('\n') || 
                      str.includes('\r');
  
  if (needsEscape) {
    // 双引号转义为两个双引号，然后用双引号包裹整个内容
    return `"${str.replace(/"/g, '""')}"`;
  }
  
  return str;
}

/**
 * 格式化日期为 YYYY-MM-DD 格式
 * 
 * @param date - 日期对象
 * @returns 格式化后的日期字符串
 */
export function formatDateForFilename(date: Date = new Date()): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

/**
 * 生成 CSV 文件名
 * 
 * 格式：{className}_成绩表_{YYYY-MM-DD}.csv
 * 
 * @param className - 班级名称
 * @param date - 日期（可选，默认当前日期）
 * @returns 文件名
 * 
 * Validates: Requirement 8.3
 */
export function generateCSVFilename(className: string, date?: Date): string {
  // 清理班级名称中的非法文件名字符
  const sanitizedClassName = className.replace(/[<>:"/\\|?*]/g, '_');
  const dateStr = formatDateForFilename(date);
  return `${sanitizedClassName}_成绩表_${dateStr}.csv`;
}

/**
 * 生成 CSV 内容
 * 
 * 将学生成绩数据转换为 CSV 格式字符串
 * 
 * 列顺序：学生姓名, 作业1, 作业2, ..., 总分, 平均分
 * 最后一行：班级平均
 * 
 * @param students - 学生成绩数据
 * @param homeworks - 作业列配置
 * @param className - 班级名称
 * @returns CSV 导出数据对象
 * 
 * Validates: Requirements 8.2, 8.3
 */
export function generateCSV(
  students: StudentScoreRow[],
  homeworks: HomeworkColumn[],
  className: string
): CSVExportData {
  // 构建表头
  const headers = [
    '学生姓名',
    ...homeworks.map(h => h.title),
    '总分',
    '平均分',
  ];
  
  // 构建数据行
  const rows: (string | number)[][] = students.map(student => [
    student.studentName,
    ...homeworks.map(h => {
      const score = student.scores[h.homeworkId];
      return score !== null && score !== undefined ? score : '';
    }),
    student.totalScore,
    Number(student.averageScore.toFixed(1)),
  ]);
  
  // 添加班级平均行
  if (students.length > 0 && homeworks.length > 0) {
    rows.push([
      '班级平均',
      ...homeworks.map(h => 
        h.classAverage > 0 ? Number(h.classAverage.toFixed(1)) : ''
      ),
      '', // 总分列留空
      '', // 平均分列留空
    ]);
  }
  
  return {
    headers,
    rows,
    filename: generateCSVFilename(className),
  };
}

/**
 * 将 CSV 数据转换为字符串
 * 
 * @param data - CSV 导出数据
 * @returns CSV 格式字符串
 */
export function csvDataToString(data: CSVExportData): string {
  const headerLine = data.headers.map(escapeCSVCell).join(',');
  const dataLines = data.rows.map(row => 
    row.map(escapeCSVCell).join(',')
  );
  
  return [headerLine, ...dataLines].join('\n');
}

/**
 * 触发 CSV 文件下载
 * 
 * 创建 Blob 并触发浏览器下载
 * 
 * @param csvString - CSV 格式字符串
 * @param filename - 文件名
 * 
 * Validates: Requirement 8.1
 */
export function downloadCSV(csvString: string, filename: string): void {
  // 添加 BOM 以支持 Excel 正确识别 UTF-8 编码
  const BOM = '\uFEFF';
  const blob = new Blob([BOM + csvString], { type: 'text/csv;charset=utf-8;' });
  
  // 创建下载链接
  const link = document.createElement('a');
  const url = URL.createObjectURL(blob);
  
  link.setAttribute('href', url);
  link.setAttribute('download', filename);
  link.style.visibility = 'hidden';
  
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  
  // 释放 URL 对象
  URL.revokeObjectURL(url);
}

/**
 * 一键导出成绩表为 CSV
 * 
 * 组合 generateCSV、csvDataToString、downloadCSV 的便捷函数
 * 
 * @param students - 学生成绩数据
 * @param homeworks - 作业列配置
 * @param className - 班级名称
 * 
 * @example
 * exportScoresToCSV(students, homeworks, '高一(1)班');
 * // 自动下载文件：高一(1)班_成绩表_2026-02-01.csv
 * 
 * Validates: Requirements 8.1, 8.2, 8.3
 */
export function exportScoresToCSV(
  students: StudentScoreRow[],
  homeworks: HomeworkColumn[],
  className: string
): void {
  const data = generateCSV(students, homeworks, className);
  const csvString = csvDataToString(data);
  downloadCSV(csvString, data.filename);
}
