'use client';

/**
 * 成绩统计总览页
 * 
 * 展示 Excel 风格的成绩矩阵，支持：
 * - 班级选择
 * - 学生成绩表格（学生为行，作业为列）
 * - 单元格点击导航到作业详情
 * - CSV 导出功能
 * 
 * @module app/teacher/statistics/page
 * Requirements: 1.1-1.4, 2.1-2.6, 3.1, 3.2
 */

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import DashboardLayout from '@/components/layout/DashboardLayout';
import { useAuthStore } from '@/store/authStore';
import { classApi, ClassResponse } from '@/services/api';
import { ScoreMatrix } from '@/components/statistics/ScoreMatrix';
import { useStatisticsData } from '@/hooks/useStatisticsData';
import { GlassCard } from '@/components/design-system/GlassCard';
import { SmoothButton } from '@/components/design-system/SmoothButton';
import { Select, Spin, Empty, message } from 'antd';
import { BarChart3, Download, RefreshCw } from 'lucide-react';

export default function StatisticsPage() {
  const router = useRouter();
  const { user } = useAuthStore();
  
  // 班级列表和选中的班级
  const [classes, setClasses] = useState<ClassResponse[]>([]);
  const [selectedClassId, setSelectedClassId] = useState<string | null>(null);
  const [classesLoading, setClassesLoading] = useState(true);
  
  // 使用 useStatisticsData hook 加载成绩数据
  const { students, homeworks, loading, error, refetch } = useStatisticsData(selectedClassId);

  // 加载班级列表
  useEffect(() => {
    const fetchClasses = async () => {
      if (!user?.id) return;
      
      setClassesLoading(true);
      try {
        const data = await classApi.getTeacherClasses(user.id);
        setClasses(data);
        
        // 自动选择第一个班级
        if (data.length > 0 && !selectedClassId) {
          setSelectedClassId(data[0].class_id);
        }
      } catch (err) {
        console.error('Failed to fetch classes:', err);
        message.error('加载班级列表失败');
      } finally {
        setClassesLoading(false);
      }
    };
    
    fetchClasses();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.id]);

  // 处理班级切换
  const handleClassChange = (classId: string) => {
    setSelectedClassId(classId);
  };

  // 处理单元格点击 - 导航到作业详情
  const handleCellClick = (studentId: string, homeworkId: string) => {
    router.push(`/teacher/statistics/${homeworkId}?student=${studentId}`);
  };

  // 处理列头点击 - 导航到作业详情
  const handleHeaderClick = (homeworkId: string) => {
    router.push(`/teacher/statistics/${homeworkId}`);
  };

  // 处理 CSV 导出
  const handleExport = async () => {
    if (!students.length || !homeworks.length) {
      message.warning('暂无数据可导出');
      return;
    }

    try {
      // 动态导入 CSV 导出函数
      const { exportScoresToCSV } = await import('@/utils/csvExport');
      
      const selectedClass = classes.find(c => c.class_id === selectedClassId);
      const className = selectedClass?.class_name || '未知班级';
      
      exportScoresToCSV(students, homeworks, className);
      
      message.success('导出成功');
    } catch (err) {
      console.error('Export failed:', err);
      message.error('导出失败');
    }
  };

  // 获取当前选中班级名称
  const selectedClassName = classes.find(c => c.class_id === selectedClassId)?.class_name || '';

  return (
    <DashboardLayout role="teacher">
      <div className="p-6 space-y-6">
        {/* 页面标题和操作栏 */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-100 rounded-lg">
              <BarChart3 className="w-6 h-6 text-blue-600" />
            </div>
            <div>
              <h1 className="text-2xl font-semibold text-slate-900">成绩统计</h1>
              <p className="text-sm text-slate-500">查看班级学生的作业成绩总览</p>
            </div>
          </div>
          
          <div className="flex items-center gap-3">
            {/* 班级选择器 */}
            <Select
              value={selectedClassId || undefined}
              onChange={handleClassChange}
              placeholder="选择班级"
              loading={classesLoading}
              style={{ width: 200 }}
              options={classes.map(c => ({
                value: c.class_id,
                label: c.class_name,
              }))}
            />
            
            {/* 刷新按钮 */}
            <SmoothButton
              variant="secondary"
              size="sm"
              onClick={() => refetch()}
              disabled={loading}
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </SmoothButton>
            
            {/* 导出按钮 */}
            <SmoothButton
              variant="primary"
              size="sm"
              onClick={handleExport}
              disabled={!students.length}
            >
              <Download className="w-4 h-4 mr-1" />
              导出 CSV
            </SmoothButton>
          </div>
        </div>

        {/* 成绩矩阵 */}
        <GlassCard className="p-0 overflow-hidden">
          {classesLoading ? (
            <div className="flex flex-col items-center justify-center h-64 gap-3">
              <Spin size="large" />
              <span className="text-gray-500">加载班级列表...</span>
            </div>
          ) : classes.length === 0 ? (
            <div className="flex items-center justify-center h-64">
              <Empty
                description="暂无班级"
                image={Empty.PRESENTED_IMAGE_SIMPLE}
              />
            </div>
          ) : error ? (
            <div className="flex flex-col items-center justify-center h-64 gap-4">
              <p className="text-red-500">{error}</p>
              <SmoothButton variant="secondary" onClick={() => refetch()}>
                重试
              </SmoothButton>
            </div>
          ) : (
            <ScoreMatrix
              students={students}
              homeworks={homeworks}
              onCellClick={handleCellClick}
              onHeaderClick={handleHeaderClick}
              loading={loading}
            />
          )}
        </GlassCard>

        {/* 统计摘要 */}
        {!loading && students.length > 0 && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <GlassCard className="p-4 text-center">
              <p className="text-2xl font-bold text-blue-600">{students.length}</p>
              <p className="text-sm text-slate-500">学生人数</p>
            </GlassCard>
            <GlassCard className="p-4 text-center">
              <p className="text-2xl font-bold text-green-600">{homeworks.length}</p>
              <p className="text-sm text-slate-500">作业数量</p>
            </GlassCard>
            <GlassCard className="p-4 text-center">
              <p className="text-2xl font-bold text-purple-600">
                {students.length > 0 
                  ? (students.reduce((sum, s) => sum + s.averageScore, 0) / students.length).toFixed(1)
                  : '-'}
              </p>
              <p className="text-sm text-slate-500">班级平均分</p>
            </GlassCard>
            <GlassCard className="p-4 text-center">
              <p className="text-2xl font-bold text-orange-600">{selectedClassName}</p>
              <p className="text-sm text-slate-500">当前班级</p>
            </GlassCard>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
