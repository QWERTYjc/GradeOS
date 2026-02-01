'use client';

import { useEffect, useMemo, useState, useRef, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import DashboardLayout from '@/components/layout/DashboardLayout';
import { useAuthStore } from '@/store/authStore';
import { 
  classApi, gradingApi, wrongbookApi,
  ClassResponse, GradingHistoryDetailResponse, GradingHistoryResponse,
  ManualWrongQuestionResponse 
} from '@/services/api';
import { Camera, Upload, X, Plus, Loader2, Trash2, Image as ImageIcon, FileText } from 'lucide-react';

type WrongQuestionEntry = {
  id: string;
  questionId: string;
  score: number;
  maxScore: number;
  feedback: string;
  studentAnswer: string;
  scoringPointResults: Array<{
    point_id?: string;
    description?: string;
    awarded: number;
    max_points?: number;
    evidence: string;
  }>;
  pageIndices: number[];
  sourceImportId: string;
  source: 'grading' | 'manual';
  images?: string[];
  subject?: string;
  topic?: string;
};

type SummaryStats = {
  totalQuestions: number;
  wrongQuestions: number;
  totalScore: number;
  totalMax: number;
};

type FocusStat = {
  questionId: string;
  wrongCount: number;
  totalCount: number;
  ratio: number;
};

const extractQuestions = (result: Record<string, unknown>): Array<Record<string, unknown>> => {
  const questions = result.questionResults || result.question_results || result.questions || result.questionDetails || result.question_details;
  if (Array.isArray(questions)) {
    return questions as Array<Record<string, unknown>>;
  }
  return [];
};

// 将文件转换为 base64
const fileToBase64 = (file: File): Promise<string> => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
};

// PDF 处理：懒加载 pdfjs-dist
let pdfjsLib: typeof import('pdfjs-dist') | null = null;
let pdfjsInitialized = false;

const initPdfJs = async () => {
  if (pdfjsInitialized && pdfjsLib) return pdfjsLib;
  if (typeof window === 'undefined') return null;
  
  try {
    pdfjsLib = await import('pdfjs-dist');
    const version = pdfjsLib.version;
    pdfjsLib.GlobalWorkerOptions.workerSrc = `https://unpkg.com/pdfjs-dist@${version}/build/pdf.worker.min.mjs`;
    pdfjsInitialized = true;
    return pdfjsLib;
  } catch (error) {
    console.error('Failed to initialize PDF.js:', error);
    return null;
  }
};

const renderPdfToImages = async (file: File, maxPages = 20): Promise<string[]> => {
  const pdfjs = await initPdfJs();
  if (!pdfjs) throw new Error('PDF.js not available');
  
  const buffer = await file.arrayBuffer();
  const pdf = await pdfjs.getDocument({ data: new Uint8Array(buffer) }).promise;
  const pages = Math.min(pdf.numPages, maxPages);
  const images: string[] = [];

  for (let i = 1; i <= pages; i++) {
    const page = await pdf.getPage(i);
    const viewport = page.getViewport({ scale: 1.5 });
    const canvas = document.createElement('canvas');
    const context = canvas.getContext('2d');
    if (!context) continue;
    canvas.width = viewport.width;
    canvas.height = viewport.height;
    await page.render({ canvasContext: context, viewport } as Parameters<typeof page.render>[0]).promise;
    images.push(canvas.toDataURL('image/jpeg', 0.85));
  }

  return images;
};

export default function StudentWrongBookPage() {
  const router = useRouter();
  const { user } = useAuthStore();
  const [classes, setClasses] = useState<ClassResponse[]>([]);
  const [selectedClassId, setSelectedClassId] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [wrongQuestions, setWrongQuestions] = useState<WrongQuestionEntry[]>([]);
  const [summary, setSummary] = useState<SummaryStats>({
    totalQuestions: 0,
    wrongQuestions: 0,
    totalScore: 0,
    totalMax: 0,
  });
  const [focusStats, setFocusStats] = useState<FocusStat[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [isHydrated, setIsHydrated] = useState(false);

  // 拍照录入相关状态
  const [showAddModal, setShowAddModal] = useState(false);
  const [isCameraActive, setIsCameraActive] = useState(false);
  const [capturedImages, setCapturedImages] = useState<string[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [newQuestion, setNewQuestion] = useState({
    score: 0,
    maxScore: 10,
  });
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Hydration check
  useEffect(() => {
    setIsHydrated(true);
    console.log('[WrongBook] Hydrated, user:', user?.id, user?.name);
  }, []);

  // 加载班级列表
  useEffect(() => {
    console.log('[WrongBook] Class loading useEffect triggered, user?.id:', user?.id, 'isHydrated:', isHydrated);
    if (!isHydrated || !user?.id) {
      console.log('[WrongBook] Class loading - not hydrated or no user.id, returning');
      return;
    }
    classApi
      .getMyClasses(user.id)
      .then((data) => {
        console.log('[WrongBook] Classes loaded:', data.length, data.map(c => c.class_id));
        setClasses(data);
        if (data.length > 0) {
          console.log('[WrongBook] Setting selectedClassId to:', data[0].class_id);
          setSelectedClassId(data[0].class_id);
        }
      })
      .catch((err) => {
        console.error('[WrongBook] Class loading error:', err);
        setError(err instanceof Error ? err.message : '加载班级失败');
      });
  }, [user, isHydrated]);

  // 加载错题数据
  useEffect(() => {
    console.log('[WrongBook] useEffect triggered, selectedClassId:', selectedClassId, 'user?.id:', user?.id);
    if (!selectedClassId || !user?.id) {
      console.log('[WrongBook] Early return - missing selectedClassId or user.id');
      return;
    }
    const loadWrongBook = async () => {
      console.log('[WrongBook] loadWrongBook started');
      setLoading(true);
      setError('');
      try {
        const userName = user.name || user.username || '';
        const userId = user.id;
        console.log('[WrongBook] User info - userId:', userId, 'userName:', userName);

        // 辅助函数：模糊匹配学生名称
        const fuzzyMatchName = (name1: string, name2: string): boolean => {
          if (!name1 || !name2) return false;
          const n1 = name1.trim().toLowerCase().replace(/\s+/g, '');
          const n2 = name2.trim().toLowerCase().replace(/\s+/g, '');
          if (n1 === n2) return true;
          if (n1.includes(n2) || n2.includes(n1)) return true;
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
          if (resultStudentId && String(resultStudentId) === String(userId)) {
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

        // 1. 从批改历史加载错题
        const history: GradingHistoryResponse = await gradingApi.getGradingHistory({ class_id: selectedClassId });
        
        console.log('[WrongBook] Loaded history records:', history.records.length);
        
        const nextWrong: WrongQuestionEntry[] = [];
        const focusMap = new Map<string, FocusStat>();
        let totalQuestions = 0;
        let wrongCount = 0;
        let totalScore = 0;
        let totalMax = 0;

        // 遍历每个批改记录，优先使用 getResultsReviewContext 获取完整数据
        for (const record of history.records) {
          console.log('[WrongBook] Processing record:', record.import_id, 'batch_id:', record.batch_id);
          try {
            let studentResults: Array<Record<string, unknown>> = [];
            let answerImages: string[] = [];

            // 优先从 getResultsReviewContext 获取（包含 runs 表中的完整数据）
            if (record.batch_id) {
              try {
                const ctx = await gradingApi.getResultsReviewContext(record.batch_id);
                console.log('[WrongBook] ctx:', JSON.stringify({
                  batch_id: ctx.batch_id,
                  status: ctx.status,
                  student_results_length: ctx.student_results?.length,
                  answer_images_length: ctx.answer_images?.length,
                }));
                answerImages = ctx.answer_images || [];
                const allResults = ctx.student_results || [];
                
                console.log('[WrongBook] batch_id:', record.batch_id, 'allResults:', allResults.length, 'userId:', userId, 'userName:', userName);
                
                // 筛选当前学生的结果
                studentResults = allResults.filter((r: Record<string, unknown>) => matchStudent(r));
                
                console.log('[WrongBook] matched studentResults:', studentResults.length);
                
                // 如果没有匹配到且只有一个学生，直接使用（单人批改场景）
                if (studentResults.length === 0 && allResults.length === 1) {
                  console.log('[WrongBook] Using single student result (no match but only 1 student)');
                  studentResults = allResults;
                }
              } catch (ctxErr) {
                console.warn('Failed to load results context:', record.batch_id, ctxErr);
              }
            }

            // 如果没有从 context 获取到，回退到 detail.items
            if (studentResults.length === 0) {
              try {
                const detail = await gradingApi.getGradingHistoryDetail(record.import_id);
                const studentItems = detail.items.filter((item) => {
                  if (item.student_id && String(item.student_id) === String(userId)) return true;
                  if (userName && item.student_name && fuzzyMatchName(item.student_name, userName)) return true;
                  if (item.result) return matchStudent(item.result as Record<string, unknown>);
                  return false;
                });
                
                // 如果没有匹配到且只有一个学生，直接使用
                const finalItems = studentItems.length > 0 ? studentItems : 
                  (detail.items.length === 1 ? detail.items : []);
                
                studentResults = finalItems.map(item => ({
                  ...(item.result || {}),
                  studentName: item.student_name,
                  studentId: item.student_id,
                }));
              } catch (detailErr) {
                console.warn('Failed to load grading detail:', record.import_id, detailErr);
              }
            }

            // 处理每个学生结果中的题目
            console.log('[WrongBook] Processing studentResults:', studentResults.length);
            for (const result of studentResults) {
              const questions = extractQuestions(result);
              console.log('[WrongBook] Extracted questions:', questions.length);
              const studentStartPage = Number(result.startPage ?? result.start_page ?? 0);
              const studentEndPage = Number(result.endPage ?? result.end_page ?? studentStartPage);
              
              questions.forEach((question: Record<string, unknown>, idx: number) => {
                const score = Number(question.score ?? 0);
                const maxScore = Number(question.maxScore ?? question.max_score ?? 0);
                const questionId = String(question.questionId ?? question.question_id ?? idx + 1);
                
                if (idx < 5) {
                  console.log(`[WrongBook] Q${idx + 1}: score=${score}, maxScore=${maxScore}, isWrong=${score < maxScore}`);
                }
                
                if (maxScore > 0) {
                  totalQuestions += 1;
                  totalScore += score;
                  totalMax += maxScore;
                  const stat = focusMap.get(questionId) || { questionId, wrongCount: 0, totalCount: 0, ratio: 0 };
                  stat.totalCount += 1;
                  if (score < maxScore) stat.wrongCount += 1;
                  focusMap.set(questionId, stat);
                }

                // 只收集错题（得分 < 满分）
                if (maxScore > 0 && score < maxScore) {
                  wrongCount += 1;
                  
                  // 提取评分点结果（支持多种字段名）
                  const scoringPointResults = (
                    question.scoringPointResults || 
                    question.scoring_point_results || 
                    question.scoringPoints ||
                    []
                  ) as Array<Record<string, unknown>>;
                  
                  // 提取页面索引
                  const pageIndices = (
                    question.pageIndices || 
                    question.page_indices || 
                    []
                  ) as number[];

                  // 提取相关图片
                  let questionImages: string[] = [];
                  if (answerImages.length > 0) {
                    if (pageIndices.length > 0) {
                      // 使用题目的页面索引
                      questionImages = pageIndices
                        .map(pageIdx => answerImages[pageIdx])
                        .filter(Boolean)
                        .map(img => {
                          if (typeof img !== 'string') return '';
                          const trimmed = img.trim();
                          if (trimmed.startsWith('data:') || trimmed.startsWith('http')) return trimmed;
                          return `data:image/jpeg;base64,${trimmed}`;
                        })
                        .filter(Boolean);
                    } else if (studentStartPage >= 0 && studentEndPage >= studentStartPage) {
                      // 使用学生的页面范围
                      questionImages = answerImages
                        .slice(studentStartPage, studentEndPage + 1)
                        .map(img => {
                          if (typeof img !== 'string') return '';
                          const trimmed = img.trim();
                          if (trimmed.startsWith('data:') || trimmed.startsWith('http')) return trimmed;
                          return `data:image/jpeg;base64,${trimmed}`;
                        })
                        .filter(Boolean);
                    }
                  }

                  // 提取反馈信息
                  const feedback = String(
                    question.feedback || 
                    question.comment || 
                    question.overall_feedback ||
                    ''
                  );
                  
                  // 提取学生答案
                  const studentAnswer = String(
                    question.studentAnswer || 
                    question.student_answer || 
                    ''
                  );

                  nextWrong.push({
                    id: `${record.import_id}-${questionId}-${idx}`,
                    questionId,
                    score,
                    maxScore,
                    feedback,
                    studentAnswer,
                    scoringPointResults: scoringPointResults.map(sp => {
                      // 支持嵌套的 scoring_point 对象
                      const scoringPoint = (sp.scoringPoint || sp.scoring_point) as Record<string, unknown> | undefined;
                      return {
                        point_id: String(sp.pointId || sp.point_id || scoringPoint?.point_id || ''),
                        description: String(sp.description || scoringPoint?.description || ''),
                        awarded: Number(sp.awarded ?? sp.score ?? 0),
                        max_points: Number(sp.maxPoints ?? sp.max_points ?? scoringPoint?.score ?? 0),
                        evidence: String(sp.evidence || sp.reason || sp.decision || ''),
                      };
                    }),
                    pageIndices,
                    sourceImportId: record.import_id,
                    source: 'grading',
                    images: questionImages.length > 0 ? questionImages : undefined,
                    subject: record.class_name || undefined,
                    topic: String(question.questionType || question.question_type || ''),
                  });
                }
              });
            }
          } catch (recordErr) {
            console.warn('Failed to process grading record:', record.import_id, recordErr);
          }
        }

        // 2. 加载手动录入的错题
        try {
          const manualData = await wrongbookApi.listQuestions({ 
            student_id: user.id, 
            class_id: selectedClassId 
          });
          manualData.questions.forEach((mq: ManualWrongQuestionResponse) => {
            wrongCount += 1;
            totalQuestions += 1;
            totalScore += mq.score;
            totalMax += mq.max_score;
            nextWrong.push({
              id: mq.id,
              questionId: mq.question_id,
              score: mq.score,
              maxScore: mq.max_score,
              feedback: mq.feedback || '',
              studentAnswer: mq.student_answer || '',
              scoringPointResults: [],
              pageIndices: [],
              sourceImportId: '',
              source: 'manual',
              images: mq.images,
              subject: mq.subject,
              topic: mq.topic,
            });
          });
        } catch (manualErr) {
          console.warn('加载手动错题失败:', manualErr);
        }

        const focusList = Array.from(focusMap.values())
          .map((stat) => ({ ...stat, ratio: stat.totalCount > 0 ? stat.wrongCount / stat.totalCount : 0 }))
          .sort((a, b) => b.ratio - a.ratio)
          .slice(0, 6);

        console.log('[WrongBook] Final summary:', {
          totalQuestions,
          wrongCount,
          nextWrongLength: nextWrong.length,
          focusListLength: focusList.length,
        });

        setWrongQuestions(nextWrong);
        setSummary({ totalQuestions, wrongQuestions: wrongCount, totalScore, totalMax });
        setFocusStats(focusList);
        setActiveId(nextWrong[0]?.id || null);
      } catch (err) {
        setError(err instanceof Error ? err.message : '加载错题失败');
      } finally {
        setLoading(false);
      }
    };

    loadWrongBook();
  }, [selectedClassId, user?.id]);

  const activeQuestion = useMemo(
    () => wrongQuestions.find((item) => item.id === activeId) || null,
    [wrongQuestions, activeId]
  );

  const accuracyRate = summary.totalMax > 0 ? Math.round((summary.totalScore / summary.totalMax) * 100) : 0;

  // 相机控制
  const startCamera = useCallback(async () => {
    try {
      const mediaStream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment', width: { ideal: 1920 }, height: { ideal: 1080 } }
      });
      streamRef.current = mediaStream;
      setIsCameraActive(true);
      if (videoRef.current) {
        videoRef.current.srcObject = mediaStream;
        videoRef.current.play();
      }
    } catch (err) {
      setError('无法访问相机: ' + (err instanceof Error ? err.message : '未知错误'));
    }
  }, []);

  const stopCamera = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop());
      streamRef.current = null;
    }
    setIsCameraActive(false);
  }, []);

  const capturePhoto = useCallback(() => {
    if (!videoRef.current) return;
    const canvas = document.createElement('canvas');
    canvas.width = videoRef.current.videoWidth;
    canvas.height = videoRef.current.videoHeight;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.drawImage(videoRef.current, 0, 0);
    const dataUrl = canvas.toDataURL('image/jpeg', 0.9);
    setCapturedImages(prev => [...prev, dataUrl]);
    if (navigator.vibrate) navigator.vibrate(50);
  }, []);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files) return;
    const files = Array.from(e.target.files);
    setIsSubmitting(true);
    try {
      for (const file of files) {
        if (file.type === 'application/pdf') {
          // PDF 文件：转换为图片
          const pdfImages = await renderPdfToImages(file);
          setCapturedImages(prev => [...prev, ...pdfImages]);
        } else if (file.type.startsWith('image/')) {
          // 图片文件
          const dataUrl = await fileToBase64(file);
          setCapturedImages(prev => [...prev, dataUrl]);
        }
      }
    } catch (err) {
      setError('文件处理失败: ' + (err instanceof Error ? err.message : '未知错误'));
    } finally {
      setIsSubmitting(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const removeImage = (index: number) => {
    setCapturedImages(prev => prev.filter((_, i) => i !== index));
  };

  // 提交手动录入的错题
  const handleSubmitManualQuestion = async () => {
    if (!user?.id) return;
    if (capturedImages.length === 0) {
      setError('请先拍照或上传图片');
      return;
    }

    setIsSubmitting(true);
    try {
      await wrongbookApi.addQuestion({
        student_id: user.id,
        class_id: selectedClassId || undefined,
        score: newQuestion.score,
        max_score: newQuestion.maxScore,
        images: capturedImages,
        tags: [],
      });

      // 重置表单
      setShowAddModal(false);
      setCapturedImages([]);
      setNewQuestion({ score: 0, maxScore: 10 });
      stopCamera();

      // 重新加载错题列表
      window.location.reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : '添加错题失败');
    } finally {
      setIsSubmitting(false);
    }
  };

  // 删除/标记已学会的错题
  const handleDeleteManualQuestion = async (entryId: string) => {
    if (!user?.id) return;
    
    const question = wrongQuestions.find(q => q.id === entryId);
    if (!question) return;
    
    if (!confirm('确定已学会这道题，要从错题本移除吗？')) return;
    
    try {
      if (question.source === 'manual') {
        // 手动录入的错题：调用 API 删除
        await wrongbookApi.deleteQuestion(entryId, user.id);
      }
      // 无论是手动还是批改系统的错题，都从列表中移除
      setWrongQuestions(prev => prev.filter(q => q.id !== entryId));
      if (activeId === entryId) setActiveId(null);
      
      // 更新统计
      if (question) {
        setSummary(prev => ({
          ...prev,
          wrongQuestions: prev.wrongQuestions - 1,
          totalQuestions: prev.totalQuestions - 1,
          totalScore: prev.totalScore - question.score,
          totalMax: prev.totalMax - question.maxScore,
        }));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '操作失败');
    }
  };

  // 关闭模态框时停止相机
  const closeModal = () => {
    setShowAddModal(false);
    stopCamera();
    setCapturedImages([]);
  };

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* 页面标题 */}
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-slate-400">Wrong Book</p>
            <h1 className="text-2xl font-semibold text-slate-900">学生错题本</h1>
            <p className="text-sm text-slate-500">自动沉淀历次作业错题，支持拍照录入与深究复盘。</p>
          </div>
          <div className="flex items-center gap-3">
            <select
              value={selectedClassId}
              onChange={(e) => setSelectedClassId(e.target.value)}
              className="rounded-full border border-slate-200 bg-white px-4 py-2 text-sm text-slate-600"
            >
              {classes.map((cls) => (
                <option key={cls.class_id} value={cls.class_id}>{cls.class_name}</option>
              ))}
            </select>
            <button
              onClick={() => setShowAddModal(true)}
              className="flex items-center gap-2 rounded-full bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow hover:bg-blue-700"
            >
              <Plus size={16} /> 拍照录入
            </button>
            <button
              onClick={() => router.push('/student/assistant')}
              className="rounded-full bg-slate-900 px-4 py-2 text-sm font-semibold text-white shadow hover:bg-slate-800"
            >
              开启深究助手
            </button>
          </div>
        </div>

        {error && (
          <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-600">
            {error}
            <button onClick={() => setError('')} className="ml-2 text-rose-400 hover:text-rose-600">×</button>
          </div>
        )}

        {/* 统计卡片 */}
        <div className="grid gap-4 lg:grid-cols-4">
          <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <div className="text-xs uppercase tracking-[0.2em] text-slate-400">Accuracy</div>
            <div className="mt-4 text-3xl font-semibold text-slate-900">{accuracyRate}%</div>
            <div className="mt-2 text-xs text-slate-500">基于总得分与满分计算</div>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <div className="text-xs uppercase tracking-[0.2em] text-slate-400">Wrong Questions</div>
            <div className="mt-4 text-3xl font-semibold text-slate-900">{summary.wrongQuestions}</div>
            <div className="mt-2 text-xs text-slate-500">未满分题目数量</div>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <div className="text-xs uppercase tracking-[0.2em] text-slate-400">Total Questions</div>
            <div className="mt-4 text-3xl font-semibold text-slate-900">{summary.totalQuestions}</div>
            <div className="mt-2 text-xs text-slate-500">已统计题目</div>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <div className="text-xs uppercase tracking-[0.2em] text-slate-400">Score</div>
            <div className="mt-4 text-3xl font-semibold text-slate-900">
              {Math.round(summary.totalScore)}/{Math.round(summary.totalMax)}
            </div>
            <div className="mt-2 text-xs text-slate-500">累计得分</div>
          </div>
        </div>

        {/* 错题列表和详情 */}
        <div className="grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-slate-900">错题列表</h2>
              <span className="text-xs text-slate-500">共 {wrongQuestions.length} 条</span>
            </div>

            <div className="mt-4 max-h-[520px] overflow-auto space-y-3 pr-2">
              {loading && (
                <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-500">
                  正在加载错题...
                </div>
              )}
              {!loading && wrongQuestions.length === 0 && (
                <div className="rounded-xl border border-dashed border-slate-200 px-4 py-6 text-center">
                  <ImageIcon className="mx-auto mb-2 text-slate-300" size={32} />
                  <p className="text-sm text-slate-400">暂无错题记录</p>
                  <button
                    onClick={() => setShowAddModal(true)}
                    className="mt-3 text-sm text-blue-600 hover:text-blue-700"
                  >
                    点击拍照录入第一道错题
                  </button>
                </div>
              )}
              {wrongQuestions.map((item) => (
                <button
                  key={item.id}
                  onClick={() => setActiveId(item.id)}
                  className={`w-full rounded-xl border px-4 py-3 text-left transition ${
                    activeId === item.id ? 'border-blue-300 bg-blue-50' : 'border-slate-200 hover:border-slate-300'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <div className="text-sm font-semibold text-slate-800">Q{item.questionId}</div>
                      {item.source === 'manual' && (
                        <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-medium text-amber-600">手动</span>
                      )}
                      {item.images && item.images.length > 0 && (
                        <ImageIcon size={14} className="text-slate-400" />
                      )}
                    </div>
                    <div className="text-xs text-slate-500">{item.score}/{item.maxScore}</div>
                  </div>
                  <div className="mt-2 text-xs text-slate-500 line-clamp-2">
                    {item.feedback || item.studentAnswer || item.subject || '暂无评语'}
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* 错题详情 */}
          <div className="space-y-4">
            <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <h2 className="text-lg font-semibold text-slate-900">错题详情</h2>
              {!activeQuestion && (
                <div className="mt-3 text-sm text-slate-400">选择左侧错题查看详情。</div>
              )}
              {activeQuestion && (
                <div className="mt-4 space-y-4">
                  <div className="flex items-center justify-between">
                    <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600 flex-1">
                      <div className="font-semibold text-slate-700">Q{activeQuestion.questionId}</div>
                      <div className="mt-2 text-xs text-slate-500">
                        得分 {activeQuestion.score}/{activeQuestion.maxScore}
                        {activeQuestion.subject && ` · ${activeQuestion.subject}`}
                        {activeQuestion.topic && ` · ${activeQuestion.topic}`}
                      </div>
                    </div>
                    {activeQuestion.source === 'manual' && (
                      <button
                        onClick={() => handleDeleteManualQuestion(activeQuestion.id)}
                        className="ml-3 p-2 text-slate-400 hover:text-rose-500 transition"
                        title="删除此错题"
                      >
                        <Trash2 size={18} />
                      </button>
                    )}
                  </div>

                  {/* 显示图片 */}
                  {activeQuestion.images && activeQuestion.images.length > 0 && (
                    <div className="rounded-xl border border-slate-200 px-4 py-3">
                      <div className="text-xs uppercase tracking-[0.2em] text-slate-400 mb-3">Images</div>
                      <div className="grid grid-cols-2 gap-2">
                        {activeQuestion.images.map((img, idx) => (
                          <img key={idx} src={img} alt={`错题图片 ${idx + 1}`} className="rounded-lg w-full object-cover" />
                        ))}
                      </div>
                    </div>
                  )}

                  {activeQuestion.studentAnswer && (
                    <div className="rounded-xl border border-slate-200 px-4 py-3 text-sm text-slate-600">
                      <div className="text-xs uppercase tracking-[0.2em] text-slate-400">Student Answer</div>
                      <p className="mt-2 whitespace-pre-wrap">{activeQuestion.studentAnswer}</p>
                    </div>
                  )}
                  
                  {/* 评分点明细 */}
                  {activeQuestion.scoringPointResults && activeQuestion.scoringPointResults.length > 0 && (
                    <div className="rounded-xl border border-slate-200 px-4 py-3">
                      <div className="text-xs uppercase tracking-[0.2em] text-slate-400 mb-3">Scoring Details</div>
                      <div className="space-y-2">
                        {activeQuestion.scoringPointResults.map((sp, spIdx) => (
                          <div 
                            key={spIdx} 
                            className={`rounded-lg px-3 py-2 text-sm ${
                              sp.awarded >= (sp.max_points || 1) 
                                ? 'bg-emerald-50 border border-emerald-200' 
                                : sp.awarded > 0 
                                  ? 'bg-amber-50 border border-amber-200'
                                  : 'bg-rose-50 border border-rose-200'
                            }`}
                          >
                            <div className="flex items-center justify-between">
                              <span className={`font-medium ${
                                sp.awarded >= (sp.max_points || 1) 
                                  ? 'text-emerald-700' 
                                  : sp.awarded > 0 
                                    ? 'text-amber-700'
                                    : 'text-rose-700'
                              }`}>
                                {sp.description || `得分点 ${spIdx + 1}`}
                              </span>
                              <span className="text-xs font-semibold">
                                {sp.awarded}/{sp.max_points || '?'}
                              </span>
                            </div>
                            {sp.evidence && (
                              <p className="mt-1 text-xs text-slate-500">{sp.evidence}</p>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  
                  {activeQuestion.feedback && (
                    <div className="rounded-xl border border-slate-200 px-4 py-3 text-sm text-slate-600">
                      <div className="text-xs uppercase tracking-[0.2em] text-slate-400">Feedback</div>
                      <p className="mt-2 whitespace-pre-wrap">{activeQuestion.feedback}</p>
                    </div>
                  )}
                  <button
                    onClick={() => {
                      // 将错题信息存储到 localStorage，供学生助手页面使用
                      const wrongQuestionContext = {
                        questionId: activeQuestion.questionId,
                        score: activeQuestion.score,
                        maxScore: activeQuestion.maxScore,
                        feedback: activeQuestion.feedback,
                        studentAnswer: activeQuestion.studentAnswer,
                        scoringPointResults: activeQuestion.scoringPointResults,
                        subject: activeQuestion.subject,
                        topic: activeQuestion.topic,
                        images: activeQuestion.images,
                        timestamp: new Date().toISOString(),
                      };
                      localStorage.setItem('gradeos.wrong-question-context', JSON.stringify(wrongQuestionContext));
                      router.push('/student/student_assistant?from=wrongbook');
                    }}
                    className="w-full rounded-xl bg-slate-900 px-4 py-3 text-sm font-semibold text-white shadow hover:bg-slate-800"
                  >
                    深究这道题
                  </button>
                  <button
                    onClick={() => handleDeleteManualQuestion(activeQuestion.id)}
                    className="w-full rounded-xl border-2 border-emerald-500 bg-emerald-50 px-4 py-3 text-sm font-semibold text-emerald-600 hover:bg-emerald-100 transition"
                  >
                    ✓ 已学会，移出错题本
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* 拍照录入模态框 */}
        {showAddModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
            <div className="w-full max-w-2xl rounded-2xl bg-white p-6 shadow-2xl max-h-[90vh] overflow-auto">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-slate-900">拍照录入错题</h3>
                <button onClick={closeModal} className="p-2 text-slate-400 hover:text-slate-600">
                  <X size={20} />
                </button>
              </div>

              {/* 相机/上传区域 */}
              <div className="mb-4">
                {isCameraActive ? (
                  <div className="relative rounded-xl overflow-hidden bg-black">
                    <video ref={videoRef} className="w-full h-64 object-cover" playsInline autoPlay muted />
                    <div className="absolute bottom-4 left-1/2 -translate-x-1/2 flex gap-3">
                      <button
                        onClick={capturePhoto}
                        className="w-14 h-14 rounded-full bg-white flex items-center justify-center shadow-lg"
                      >
                        <div className="w-10 h-10 rounded-full border-2 border-slate-300" />
                      </button>
                      <button
                        onClick={stopCamera}
                        className="w-14 h-14 rounded-full bg-rose-500 text-white flex items-center justify-center shadow-lg"
                      >
                        <X size={24} />
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="grid grid-cols-2 gap-3">
                    <button
                      onClick={startCamera}
                      className="flex flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed border-slate-200 p-6 hover:border-blue-300 hover:bg-blue-50 transition"
                    >
                      <Camera size={32} className="text-slate-400" />
                      <span className="text-sm text-slate-600">打开相机</span>
                    </button>
                    <button
                      onClick={() => fileInputRef.current?.click()}
                      className="flex flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed border-slate-200 p-6 hover:border-blue-300 hover:bg-blue-50 transition"
                    >
                      <Upload size={32} className="text-slate-400" />
                      <span className="text-sm text-slate-600">上传图片/PDF</span>
                      <span className="text-xs text-slate-400">支持 JPG、PNG、PDF</span>
                    </button>
                  </div>
                )}
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*,application/pdf"
                  multiple
                  className="hidden"
                  onChange={handleFileUpload}
                />
              </div>

              {/* 已拍摄的图片 */}
              {capturedImages.length > 0 && (
                <div className="mb-4">
                  <div className="text-xs font-semibold text-slate-500 mb-2">已拍摄 ({capturedImages.length})</div>
                  <div className="grid grid-cols-4 gap-2">
                    {capturedImages.map((img, idx) => (
                      <div key={idx} className="relative group">
                        <img src={img} alt={`拍摄 ${idx + 1}`} className="w-full h-20 object-cover rounded-lg" />
                        <button
                          onClick={() => removeImage(idx)}
                          className="absolute top-1 right-1 w-5 h-5 rounded-full bg-rose-500 text-white flex items-center justify-center opacity-0 group-hover:opacity-100 transition"
                        >
                          <X size={12} />
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 表单字段 - 只需要分数 */}
              <div className="space-y-3">
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs text-slate-500 mb-1 block">得分</label>
                    <input
                      type="number"
                      value={newQuestion.score}
                      onChange={(e) => setNewQuestion(prev => ({ ...prev, score: Number(e.target.value) }))}
                      className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                      min={0}
                    />
                  </div>
                  <div>
                    <label className="text-xs text-slate-500 mb-1 block">满分</label>
                    <input
                      type="number"
                      value={newQuestion.maxScore}
                      onChange={(e) => setNewQuestion(prev => ({ ...prev, maxScore: Number(e.target.value) }))}
                      className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                      min={1}
                    />
                  </div>
                </div>
              </div>

              {/* 提交按钮 */}
              <div className="mt-6 flex gap-3">
                <button
                  onClick={closeModal}
                  className="flex-1 rounded-xl border border-slate-200 px-4 py-3 text-sm font-semibold text-slate-600 hover:bg-slate-50"
                >
                  取消
                </button>
                <button
                  onClick={handleSubmitManualQuestion}
                  disabled={isSubmitting || capturedImages.length === 0}
                  className="flex-1 rounded-xl bg-blue-600 px-4 py-3 text-sm font-semibold text-white shadow hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 size={16} className="animate-spin" />
                      保存中...
                    </>
                  ) : (
                    '保存错题'
                  )}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
