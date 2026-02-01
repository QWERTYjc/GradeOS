'use client';

import React, { useEffect, useState } from 'react';
import dynamic from 'next/dynamic';
import { useParams, useRouter } from 'next/navigation';
import DashboardLayout from '@/components/layout/DashboardLayout';
import { gradingApi } from '@/services/api';
import { useConsoleStore } from '@/store/consoleStore';
import { normalizeStudentResults } from '@/lib/gradingResults';

const ResultsView = dynamic(() => import('@/components/console/ResultsView'), { ssr: false });

type ResultsReviewContext = {
  batch_id: string;
  status?: string;
  current_stage?: string;
  student_results: Array<Record<string, any>>;
  answer_images: string[];
};

export default function GradingHistoryDetailPage() {
  const router = useRouter();
  const params = useParams();
  const importId = params?.importId as string;
  const setFinalResults = useConsoleStore((state) => state.setFinalResults);
  const setUploadedImages = useConsoleStore((state) => state.setUploadedImages);
  const setSubmissionId = useConsoleStore((state) => state.setSubmissionId);
  const setStatus = useConsoleStore((state) => state.setStatus);
  const setCurrentTab = useConsoleStore((state) => state.setCurrentTab);
  const setParsedRubric = useConsoleStore((state) => state.setParsedRubric);
  const setRubricImages = useConsoleStore((state) => state.setRubricImages);
  const [batchId, setBatchId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!importId) return;
    let active = true;
    let resolvedBatchId = '';
    setLoading(true);
    gradingApi
      .getGradingHistoryDetail(importId)
      .then(async (detail) => {
        if (!active) return null;
        resolvedBatchId = detail.record.batch_id;
        setBatchId(resolvedBatchId);

        // 尝试从数据库加载图片
        let imagesFromDb: string[] = [];
        try {
          const imagesResponse = await gradingApi.getGradingHistoryImages(importId);
          if (imagesResponse && imagesResponse.images) {
            imagesFromDb = imagesResponse.images.map(img => 
              `data:image/${img.image_format};base64,${img.image_base64}`
            );
            console.log(`从数据库加载了 ${imagesFromDb.length} 张图片`);
          }
        } catch (err) {
          console.warn('从数据库加载图片失败，尝试从 batch context 加载:', err);
        }

        // 🔥 加载评分标准（rubric JSON + 图片）
        try {
          const rubricResponse = await gradingApi.getGradingHistoryRubric(importId);
          if (rubricResponse && rubricResponse.data) {
            const { rubric, rubric_images } = rubricResponse.data;
            
            // 设置 parsed rubric - 需要规范化字段命名（下划线 -> 驼峰）
            if (rubric) {
              console.log('📋 原始 Rubric 数据:', rubric);
              console.log('📋 原始 questions 字段:', rubric.questions);
              console.log('📋 原始 question_list 字段:', rubric.question_list);
              
              // 转换 questions 数组中每个题目的字段命名
              const rawQuestions = rubric.questions || rubric.question_list || [];
              const normalizedQuestions = rawQuestions.map((q: any) => ({
                questionId: q.question_id || q.questionId || '',
                maxScore: q.max_score ?? q.maxScore ?? 0,
                questionText: q.question_text || q.questionText || '',
                standardAnswer: q.standard_answer || q.standardAnswer || '',
                gradingNotes: q.grading_notes || q.gradingNotes || '',
                criteria: q.criteria || [],
                sourcePages: q.source_pages || q.sourcePages || [],
                scoringPoints: (q.scoring_points || q.scoringPoints || []).map((sp: any) => ({
                  pointId: sp.point_id || sp.pointId || '',
                  description: sp.description || '',
                  expectedValue: sp.expected_value || sp.expectedValue || '',
                  score: sp.score ?? 0,
                  isRequired: sp.is_required ?? sp.isRequired ?? true,
                  keywords: sp.keywords || [],
                })),
                alternativeSolutions: (q.alternative_solutions || q.alternativeSolutions || []).map((alt: any) => ({
                  description: alt.description || '',
                  scoringCriteria: alt.scoring_criteria || alt.scoringCriteria || '',
                  note: alt.note || '',
                })),
              }));
              
              // 转换字段命名：total_questions -> totalQuestions, total_score -> totalScore
              const normalizedRubric = {
                totalQuestions: rubric.total_questions ?? rubric.totalQuestions ?? 0,
                totalScore: rubric.total_score ?? rubric.totalScore ?? 0,
                questions: normalizedQuestions,
                generalNotes: rubric.general_notes || rubric.generalNotes || '',
                rubricFormat: rubric.rubric_format || rubric.rubricFormat || '',
                overallParseConfidence: rubric.overall_parse_confidence ?? rubric.overallParseConfidence ?? 1.0,
                parseSelfReport: rubric.parse_self_report || rubric.parseSelfReport,
              };
              
              console.log('📋 规范化后的 Rubric:', normalizedRubric);
              console.log('📋 规范化后的 questions:', normalizedRubric.questions);
              console.log('📋 规范化后的 questions[0]:', normalizedRubric.questions[0]);
              setParsedRubric(normalizedRubric);
              console.log(`从数据库加载了评分标准: ${normalizedRubric.totalQuestions} 道题，总分 ${normalizedRubric.totalScore}`);
            } else {
              console.warn('⚠️ Rubric 数据为空');
            }
            
            // 设置 rubric images URLs
            if (rubric_images && rubric_images.length > 0) {
              const rubricImageUrls = rubric_images.map(img => img.image_url);
              setRubricImages(rubricImageUrls);
              console.log(`从数据库加载了 ${rubric_images.length} 张评分标准图片`);
            }
          }
        } catch (err) {
          console.warn('从数据库加载评分标准失败:', err);
        }

        // 如果没有 batch_id，直接使用 detail.items 中的结果
        if (!resolvedBatchId || resolvedBatchId.trim() === '') {
          // 从 items 构建 student_results
          const studentResults = detail.items.map(item => ({
            ...item.result,
            studentName: item.student_name,
            studentId: item.student_id,
          }));

          return Promise.resolve({
            batch_id: importId,
            student_results: studentResults,
            answer_images: imagesFromDb.length > 0 ? imagesFromDb : [],
          });
        }

        // 尝试从 batch context 加载
        try {
          const contextData = await gradingApi.getResultsReviewContext(resolvedBatchId);
          return {
            ...contextData,
            // 优先使用数据库中的图片
            answer_images: imagesFromDb.length > 0 ? imagesFromDb : (contextData.answer_images || []),
          };
        } catch (err) {
          console.warn('从 batch context 加载失败，使用数据库图片:', err);
          // 如果 batch context 加载失败，使用 detail.items 构建结果
          const studentResults = detail.items.map(item => ({
            ...item.result,
            studentName: item.student_name,
            studentId: item.student_id,
          }));
          return {
            batch_id: resolvedBatchId,
            student_results: studentResults,
            answer_images: imagesFromDb,
          };
        }
      })
      .then((data: ResultsReviewContext | null) => {
        if (!active || !data) return;
        setSubmissionId(data.batch_id || resolvedBatchId || importId);
        setFinalResults(normalizeStudentResults(data.student_results || []));
        const normalizedImages = (data.answer_images || []).map((img) => {
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
      })
      .catch((err) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : 'Failed to load grading history.');
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [importId, setFinalResults, setUploadedImages, setSubmissionId, setStatus, setCurrentTab, setParsedRubric, setRubricImages]);

  return (
    <DashboardLayout>
      <div className="flex flex-col gap-3 -mx-4 sm:-mx-6 lg:-mx-8">
        <div className="px-4 sm:px-6 lg:px-8 flex items-center justify-between">
          <button
            type="button"
            onClick={() => router.push('/teacher/grading/history')}
            className="text-xs font-semibold text-slate-500 hover:text-slate-700"
          >
            Back to History
          </button>
          {batchId && <div className="text-[11px] text-slate-400">Batch {batchId}</div>}
        </div>
        <div className="h-[calc(100vh-8rem)] min-h-0 overflow-hidden bg-white border-t border-slate-100">
          {loading ? (
            <div className="h-full flex items-center justify-center text-sm text-slate-400">Loading results...</div>
          ) : error ? (
            <div className="h-full flex items-center justify-center text-sm text-rose-500">{error}</div>
          ) : (
            <ResultsView defaultExpandDetails={true} />
          )}
        </div>
      </div>
    </DashboardLayout>
  );
}
