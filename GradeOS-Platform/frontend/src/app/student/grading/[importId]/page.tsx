'use client';

import { useEffect, useState } from 'react';
import dynamic from 'next/dynamic';
import { useParams, useRouter } from 'next/navigation';
import DashboardLayout from '@/components/layout/DashboardLayout';
import { gradingApi } from '@/services/api';
import { useConsoleStore } from '@/store/consoleStore';
import { normalizeStudentResults } from '@/lib/gradingResults';
import { useAuthStore } from '@/store/authStore';

const ResultsView = dynamic(() => import('@/components/console/ResultsView'), { ssr: false });

export default function StudentGradingDetailPage() {
  const router = useRouter();
  const params = useParams();
  const { user } = useAuthStore();
  const importId = params?.importId as string;
  const setFinalResults = useConsoleStore((state) => state.setFinalResults);
  const setUploadedImages = useConsoleStore((state) => state.setUploadedImages);
  const setSubmissionId = useConsoleStore((state) => state.setSubmissionId);
  const setStatus = useConsoleStore((state) => state.setStatus);
  const setCurrentTab = useConsoleStore((state) => state.setCurrentTab);
  const [batchId, setBatchId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [studentName, setStudentName] = useState<string>('');

  useEffect(() => {
    if (!importId || !user?.id) return;
    let active = true;
    
    const loadData = async () => {
      setLoading(true);
      try {
        // 1. 获取批改历史详情
        const detail = await gradingApi.getGradingHistoryDetail(importId);
        if (!active) return;
        
        const resolvedBatchId = detail.record.batch_id;
        setBatchId(resolvedBatchId);

        const userName = user.name || user.username || '';
        const userId = user.id || '';
        
        // 辅助函数：模糊匹配学生名称
        const fuzzyMatchName = (name1: string, name2: string): boolean => {
          if (!name1 || !name2) return false;
          const n1 = name1.trim().toLowerCase().replace(/\s+/g, '');
          const n2 = name2.trim().toLowerCase().replace(/\s+/g, '');
          // 完全匹配
          if (n1 === n2) return true;
          // 包含匹配（一个名字包含另一个）
          if (n1.includes(n2) || n2.includes(n1)) return true;
          // 去除常见前缀后匹配
          const prefixes = ['学生', 'student', '同学', '考生', '用户'];
          for (const prefix of prefixes) {
            const stripped1 = n1.replace(new RegExp(prefix, 'gi'), '');
            const stripped2 = n2.replace(new RegExp(prefix, 'gi'), '');
            if (stripped1 && stripped2 && (stripped1 === stripped2 || stripped1.includes(stripped2) || stripped2.includes(stripped1))) {
              return true;
            }
          }
          return false;
        };

        // 辅助函数：匹配学生（支持多种字段）
        const matchStudent = (result: Record<string, unknown>): boolean => {
          // 1. 优先匹配 student_id / studentId
          const resultStudentId = result.studentId || result.student_id;
          if (resultStudentId && userId && String(resultStudentId) === String(userId)) {
            return true;
          }
          
          // 2. 匹配学生姓名（支持多种字段名）
          const nameFields = ['studentName', 'student_name', 'student_key', 'name', 'userName', 'user_name'];
          for (const field of nameFields) {
            const resultName = result[field];
            if (typeof resultName === 'string' && userName && fuzzyMatchName(resultName, userName)) {
              return true;
            }
          }
          
          // 3. 匹配学号（如果有）
          const userAny = user as unknown as Record<string, unknown>;
          const studentNumber = userAny.studentNumber || userAny.student_number;
          if (studentNumber) {
            const resultNumber = result.studentNumber || result.student_number || result.student_no;
            if (resultNumber && String(resultNumber) === String(studentNumber)) {
              return true;
            }
          }
          
          return false;
        };

        // 2. 构建结果数据
        let studentResults: Array<Record<string, unknown>> = [];
        let answerImages: string[] = [];
        let displayName = '';

        // 优先从 getResultsReviewContext 获取完整数据（包含 runs 表中的数据）
        // 这样即使 student_grading_results 表为空，也能获取到批改结果
        if (resolvedBatchId && resolvedBatchId.trim() !== '') {
          try {
            const ctx = await gradingApi.getResultsReviewContext(resolvedBatchId);
            answerImages = ctx.answer_images || [];
            
            const allResults = ctx.student_results || [];
            
            if (allResults.length > 0) {
              // 尝试匹配当前学生 - 学生只能看到自己的结果
              const matchedResults = allResults.filter((r: Record<string, unknown>) => matchStudent(r));
              
              // 学生端只显示匹配到的自己的结果，不显示其他学生的
              studentResults = matchedResults;
              
              if (matchedResults.length > 0) {
                const firstResult = matchedResults[0] as Record<string, unknown>;
                displayName = String(firstResult?.studentName || firstResult?.student_name || firstResult?.student_key || '');
              }
            }
          } catch (ctxErr) {
            console.warn('Failed to load results context:', ctxErr);
          }
        }

        // 如果从 context 没有获取到结果，尝试从 items 获取
        if (studentResults.length === 0 && detail.items.length > 0) {
          const studentItems = detail.items.filter(item => {
            // 匹配 student_id
            if (item.student_id && userId && String(item.student_id) === String(userId)) {
              return true;
            }
            // 匹配学生姓名
            if (userName && item.student_name && fuzzyMatchName(item.student_name, userName)) {
              return true;
            }
            // 匹配 result 中的字段
            if (item.result) {
              return matchStudent(item.result as Record<string, unknown>);
            }
            return false;
          });
          
          // 学生端只显示匹配到的自己的结果
          if (studentItems.length > 0) {
            displayName = studentItems[0]?.student_name || '';
            
            studentResults = studentItems
              .filter(item => item.result && Object.keys(item.result).length > 0)
              .map(item => ({
                ...(item.result || {}),
                studentName: item.student_name,
                studentId: item.student_id,
              }));
            
            if (studentResults.length === 0) {
              studentResults = studentItems.map(item => ({
                studentName: item.student_name || 'Unknown',
                studentId: item.student_id,
                score: 0,
                maxScore: 100,
                questionResults: [],
              }));
            }
          }
        }

        if (studentResults.length === 0) {
          throw new Error('未找到您的批改结果，请确认您的姓名与提交时一致');
        }

        setStudentName(displayName);
        if (!active) return;

        // 3. 过滤答题图片，只显示当前学生的页面
        let filteredImages = answerImages;
        if (studentResults.length > 0 && answerImages.length > 0) {
          const firstResult = studentResults[0] as Record<string, unknown>;
          const startPage = firstResult.startPage ?? firstResult.start_page;
          const endPage = firstResult.endPage ?? firstResult.end_page;
          
          // 如果有页面范围信息，只显示对应页面的图片
          if (typeof startPage === 'number' && typeof endPage === 'number') {
            filteredImages = answerImages.slice(startPage, endPage + 1);
          } else {
            // 尝试从 questionResults 中获取页面索引
            const questionResults = (firstResult.questionResults || firstResult.question_results || []) as Array<Record<string, unknown>>;
            const pageIndices = new Set<number>();
            for (const q of questionResults) {
              const indices = q.pageIndices || q.page_indices || [];
              if (Array.isArray(indices)) {
                indices.forEach((idx: number) => pageIndices.add(idx));
              }
            }
            if (pageIndices.size > 0) {
              const sortedIndices = Array.from(pageIndices).sort((a, b) => a - b);
              filteredImages = sortedIndices.map(idx => answerImages[idx]).filter(Boolean);
            }
          }
        }

        // 4. 设置 store 状态
        setSubmissionId(resolvedBatchId || importId);
        setFinalResults(normalizeStudentResults(studentResults));
        
        const normalizedImages = filteredImages.map((img) => {
          if (!img) return img;
          const trimmed = img.trim();
          if (
            trimmed.startsWith('data:') ||
            trimmed.startsWith('http://') ||
            trimmed.startsWith('https://') ||
            trimmed.startsWith('blob:') ||
            trimmed.startsWith('/')
          ) {
            return trimmed;
          }
          return `data:image/jpeg;base64,${trimmed}`;
        });
        setUploadedImages(normalizedImages);
        setStatus('COMPLETED');
        setCurrentTab('results');
        setError(null);
      } catch (err) {
        if (!active) return;
        setError(err instanceof Error ? err.message : '加载批改结果失败');
      } finally {
        if (active) setLoading(false);
      }
    };

    loadData();
    return () => {
      active = false;
    };
  }, [importId, user?.id, setFinalResults, setUploadedImages, setSubmissionId, setStatus, setCurrentTab]);


  return (
    <DashboardLayout>
      <div className="flex flex-col gap-3 -mx-4 sm:-mx-6 lg:-mx-8">
        <div className="px-4 sm:px-6 lg:px-8 flex items-center justify-between">
          <button
            type="button"
            onClick={() => router.push('/student/dashboard')}
            className="text-xs font-semibold text-slate-500 hover:text-slate-700"
          >
            ← 返回作业列表
          </button>
          <div className="flex items-center gap-3">
            {studentName && (
              <span className="text-sm text-slate-600">{studentName}</span>
            )}
            {batchId && <div className="text-[11px] text-slate-400">批次 {batchId.slice(0, 8)}...</div>}
          </div>
        </div>
        <div className="h-[calc(100vh-8rem)] min-h-0 overflow-hidden bg-white border-t border-slate-100">
          {loading ? (
            <div className="h-full flex items-center justify-center text-sm text-slate-400">加载批改结果中...</div>
          ) : error ? (
            <div className="h-full flex flex-col items-center justify-center gap-4">
              <div className="text-sm text-rose-500">{error}</div>
              <button
                onClick={() => router.push('/student/dashboard')}
                className="px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 rounded-lg"
              >
                返回作业列表
              </button>
            </div>
          ) : (
            <ResultsView defaultExpandDetails={true} hideGradingTransparency={true} studentOnlyMode={true} />
          )}
        </div>
      </div>
    </DashboardLayout>
  );
}
