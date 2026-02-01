'use client';

/**
 * 作业详情统计页
 * 
 * 展示单个作业的深度统计分析，包括：
 * - 统计指标卡片（平均分、中位数、最高分、最低分、标准差、学生人数）
 * - 箱线图可视化
 * - 分数分布图
 * - 学生排名列表
 * 
 * @module app/teacher/statistics/[homeworkId]/page
 * Requirements: 3.3, 4.1-4.5, 5.1-5.4, 6.1-6.4, 7.1-7.4
 */

import { useParams, useRouter } from 'next/navigation';
import DashboardLayout from '@/components/layout/DashboardLayout';
import { useHomeworkAnalysis } from '@/hooks/useHomeworkAnalysis';
import { StatsCards } from '@/components/statistics/StatsCards';
import { BoxChart } from '@/components/statistics/BoxChart';
import { ScoreDistribution } from '@/components/statistics/ScoreDistribution';
import { RankingList } from '@/components/statistics/RankingList';
import { GlassCard } from '@/components/design-system/GlassCard';
import { SmoothButton } from '@/components/design-system/SmoothButton';
import { Spin, Empty, Breadcrumb } from 'antd';
import { ArrowLeft, RefreshCw, BookOpen, BarChart3 } from 'lucide-react';

export default function HomeworkAnalysisPage() {
  const params = useParams();
  const router = useRouter();
  const homeworkId = params.homeworkId as string;

  // 使用 useHomeworkAnalysis hook 加载数据
  const {
    stats,
    boxPlotData,
    rankings,
    homeworkTitle,
    maxPossibleScore,
    loading,
    error,
    refetch,
  } = useHomeworkAnalysis(homeworkId);

  // 提取分数数组用于 ScoreDistribution
  const scores = rankings.map(r => r.score);

  // 返回总览页
  const handleBack = () => {
    router.push('/teacher/statistics');
  };

  // 处理作业不存在的情况
  if (error === '作业不存在') {
    return (
      <DashboardLayout>
        <div className="p-6">
          <div className="flex flex-col items-center justify-center h-[60vh] gap-6">
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description={
                <span className="text-gray-500">
                  作业不存在或已被删除
                </span>
              }
            />
            <SmoothButton variant="primary" onClick={handleBack}>
              <ArrowLeft className="w-4 h-4 mr-2" />
              返回成绩总览
            </SmoothButton>
          </div>
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="p-4 sm:p-6 space-y-4 sm:space-y-6">
        {/* 面包屑导航和标题 */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 sm:gap-4">
          <div>
            <Breadcrumb
              items={[
                {
                  title: (
                    <span 
                      className="cursor-pointer hover:text-blue-600 transition-colors"
                      onClick={handleBack}
                    >
                      成绩统计
                    </span>
                  ),
                },
                {
                  title: homeworkTitle || '作业详情',
                },
              ]}
              className="mb-2"
            />
            <div className="flex items-center gap-2 sm:gap-3">
              <div className="p-1.5 sm:p-2 bg-blue-100 rounded-lg">
                <BookOpen className="w-5 h-5 sm:w-6 sm:h-6 text-blue-600" />
              </div>
              <div>
                <h1 className="text-xl sm:text-2xl font-semibold text-slate-900">
                  {homeworkTitle || '作业详情'}
                </h1>
                <p className="text-xs sm:text-sm text-slate-500">
                  满分 {maxPossibleScore} 分 · 深度统计分析
                </p>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2 sm:gap-3">
            {/* 返回按钮 */}
            <SmoothButton variant="secondary" size="sm" onClick={handleBack}>
              <ArrowLeft className="w-4 h-4 sm:mr-1" />
              <span className="hidden sm:inline">返回总览</span>
            </SmoothButton>

            {/* 刷新按钮 */}
            <SmoothButton
              variant="secondary"
              size="sm"
              onClick={() => refetch()}
              disabled={loading}
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </SmoothButton>
          </div>
        </div>

        {/* 加载状态 */}
        {loading && (
          <div className="flex flex-col items-center justify-center h-64 gap-3">
            <Spin size="large" />
            <span className="text-gray-500">加载统计数据...</span>
          </div>
        )}

        {/* 错误状态 */}
        {error && error !== '作业不存在' && (
          <GlassCard className="p-6">
            <div className="flex flex-col items-center justify-center h-48 gap-4">
              <p className="text-red-500">{error}</p>
              <SmoothButton variant="secondary" onClick={() => refetch()}>
                重试
              </SmoothButton>
            </div>
          </GlassCard>
        )}

        {/* 主要内容 */}
        {!loading && !error && (
          <>
            {/* 统计指标卡片 */}
            <section>
              <StatsCards stats={stats} />
            </section>

            {/* 图表区域 - 响应式布局 */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6">
              {/* 箱线图 */}
              <section>
                <BoxChart
                  data={boxPlotData}
                  maxScore={maxPossibleScore}
                  title="成绩分布箱线图"
                  height={320}
                />
              </section>

              {/* 分数分布图 */}
              <section>
                <ScoreDistribution
                  scores={scores}
                  maxScore={maxPossibleScore}
                  title="分数段分布"
                  height={320}
                />
              </section>
            </div>

            {/* 排名列表 */}
            <section>
              <RankingList
                students={rankings}
                title="学生成绩排名"
                showPercentage={true}
              />
            </section>

            {/* 空数据提示 */}
            {rankings.length === 0 && (
              <GlassCard className="p-4 sm:p-6">
                <div className="flex flex-col items-center justify-center h-40 sm:h-48 gap-3 sm:gap-4">
                  <BarChart3 className="w-10 h-10 sm:w-12 sm:h-12 text-gray-300" />
                  <p className="text-gray-500 text-sm sm:text-base">该作业暂无批改数据</p>
                  <p className="text-xs sm:text-sm text-gray-400 text-center">
                    请先在批改控制台完成作业批改
                  </p>
                </div>
              </GlassCard>
            )}
          </>
        )}
      </div>
    </DashboardLayout>
  );
}
