'use client';

import React, { useState, useEffect, useMemo } from 'react';
import dynamic from 'next/dynamic';
import { useRouter } from 'next/navigation';
import DashboardLayout from '@/components/layout/DashboardLayout';
import { useAuthStore } from '@/store/authStore';
import { classApi, homeworkApi, ClassResponse, HomeworkResponse, SubmissionResponse } from '@/services/api';
import dayjs from 'dayjs';
import { AppContext, AppContextType } from '@/components/bookscan/AppContext';
import { Session, ScannedImage } from '@/components/bookscan/types';

// 动态导入 Scanner 和 Gallery 组件
const Scanner = dynamic(() => import('@/components/bookscan/Scanner'), { ssr: false });
const Gallery = dynamic(() => import('@/components/bookscan/Gallery'), { ssr: false });

export default function TeacherHomework() {
  const { user } = useAuthStore();
  const router = useRouter();
  const [classes, setClasses] = useState<ClassResponse[]>([]);
  const [homeworks, setHomeworks] = useState<HomeworkResponse[]>([]);
  const [selectedClass, setSelectedClass] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [loadingHomeworks, setLoadingHomeworks] = useState(false);
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [currentHw, setCurrentHw] = useState<HomeworkResponse | null>(null);
  const [submissions, setSubmissions] = useState<SubmissionResponse[]>([]);
  const [loadingSubmissions, setLoadingSubmissions] = useState(false);
  const [error, setError] = useState('');

  // Form state
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [deadline, setDeadline] = useState('');
  const [allowEarlyGrading, setAllowEarlyGrading] = useState(false);
  
  // Rubric Scanner state
  const [rubricSessions, setRubricSessions] = useState<Session[]>([]);
  const [rubricCurrentSessionId, setRubricCurrentSessionId] = useState<string | null>(null);
  const [rubricSplitImageIds, setRubricSplitImageIds] = useState<Set<string>>(new Set());
  const [rubricActiveTab, setRubricActiveTab] = useState<'scan' | 'gallery'>('scan');
  
  // 初始化 Rubric 扫描会话
  useEffect(() => {
    if (isCreateOpen && rubricSessions.length === 0) {
      const newSession: Session = {
        id: crypto.randomUUID(),
        name: 'Rubric 扫描',
        createdAt: Date.now(),
        images: []
      };
      setRubricSessions([newSession]);
      setRubricCurrentSessionId(newSession.id);
    }
  }, [isCreateOpen, rubricSessions.length]);
  
  // Rubric context functions
  const createRubricSession = (name?: string) => {
    const newSession: Session = {
      id: crypto.randomUUID(),
      name: name || `Rubric ${new Date().toLocaleTimeString()}`,
      createdAt: Date.now(),
      images: []
    };
    setRubricSessions(prev => [newSession, ...prev]);
    setRubricCurrentSessionId(newSession.id);
  };
  
  const addRubricImage = (img: ScannedImage) => {
    if (!rubricCurrentSessionId) return;
    setRubricSessions(prev => prev.map(s =>
      s.id === rubricCurrentSessionId ? { ...s, images: [...s.images, img] } : s
    ));
  };
  
  const addRubricImages = (imgs: ScannedImage[]) => {
    if (!rubricCurrentSessionId) return;
    setRubricSessions(prev => prev.map(s =>
      s.id === rubricCurrentSessionId ? { ...s, images: [...s.images, ...imgs] } : s
    ));
  };
  
  const deleteRubricSession = (id: string) => {
    setRubricSessions(prev => {
      const filtered = prev.filter(s => s.id !== id);
      if (rubricCurrentSessionId === id) {
        setRubricCurrentSessionId(filtered.length > 0 ? filtered[0].id : null);
      }
      return filtered;
    });
  };
  
  const deleteRubricImages = (sessionId: string, imageIds: string[]) => {
    setRubricSessions(prev => prev.map(s =>
      s.id === sessionId ? { ...s, images: s.images.filter(img => !imageIds.includes(img.id)) } : s
    ));
  };
  
  const updateRubricImage = (sessionId: string, imageId: string, newUrl: string, isOptimizing: boolean = false) => {
    setRubricSessions(prev => prev.map(s =>
      s.id === sessionId ? {
        ...s,
        images: s.images.map(img => img.id === imageId ? { ...img, url: newUrl, isOptimizing } : img)
      } : s
    ));
  };
  
  const reorderRubricImages = (sessionId: string, fromIndex: number, toIndex: number) => {
    setRubricSessions(prev => prev.map(s => {
      if (s.id === sessionId) {
        const imgs = [...s.images];
        const [moved] = imgs.splice(fromIndex, 1);
        imgs.splice(toIndex, 0, moved);
        return { ...s, images: imgs };
      }
      return s;
    }));
  };
  
  const markRubricImageAsSplit = (imageId: string) => {
    setRubricSplitImageIds(prev => new Set(prev).add(imageId));
  };
  
  const rubricContextValue: AppContextType = useMemo(() => ({
    sessions: rubricSessions,
    currentSessionId: rubricCurrentSessionId,
    createNewSession: createRubricSession,
    addImageToSession: addRubricImage,
    addImagesToSession: addRubricImages,
    deleteSession: deleteRubricSession,
    deleteImages: deleteRubricImages,
    setCurrentSessionId: setRubricCurrentSessionId,
    updateImage: updateRubricImage,
    reorderImages: reorderRubricImages,
    splitImageIds: rubricSplitImageIds,
    markImageAsSplit: markRubricImageAsSplit
  }), [rubricSessions, rubricCurrentSessionId, rubricSplitImageIds]);
  
  const currentRubricSession = rubricSessions.find(s => s.id === rubricCurrentSessionId);
  const rubricImageCount = currentRubricSession?.images.length || 0;

  useEffect(() => {
    const teacherId = user?.id || 't-001';
    setLoading(true);
    classApi
      .getTeacherClasses(teacherId)
      .then((data) => {
        setClasses(data);
        if (data.length > 0) {
          setSelectedClass(data[0].class_id);
        }
      })
      .catch(() => {
        setClasses([]);
      })
      .finally(() => {
        setLoading(false);
      });
  }, [user]);

  useEffect(() => {
    if (!selectedClass) return;
    setLoadingHomeworks(true);
    homeworkApi
      .getList({ class_id: selectedClass })
      .then((data) => {
        setHomeworks(data);
      })
      .catch(() => {
        setHomeworks([]);
      })
      .finally(() => {
        setLoadingHomeworks(false);
      });
  }, [selectedClass]);

  const handleCreate = async () => {
    if (!title || !description || !deadline || !selectedClass) return;
    setError('');
    try {
      // 提取 rubric 图片
      const rubricImages = currentRubricSession?.images.map(img => img.url) || [];
      
      const created = await homeworkApi.create({
        class_id: selectedClass,
        title,
        description,
        deadline,
        allow_early_grading: allowEarlyGrading,
        rubric_images: rubricImages.length > 0 ? rubricImages : undefined,
      });
      setHomeworks((prev: HomeworkResponse[]) => [created, ...prev]);
      setTitle('');
      setDescription('');
      setDeadline('');
      setAllowEarlyGrading(false);
      // 重置 rubric 扫描会话
      setRubricSessions([]);
      setRubricCurrentSessionId(null);
      setIsCreateOpen(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : '创建作业失败');
    }
  };

  const openSubmissions = async (hw: HomeworkResponse) => {
    setCurrentHw(hw);
    setIsDrawerOpen(true);
    setLoadingSubmissions(true);
    try {
      const data = await homeworkApi.getSubmissions(hw.homework_id);
      setSubmissions(data);
    } catch {
      setSubmissions([]);
    } finally {
      setLoadingSubmissions(false);
    }
  };

  const getScoreColor = (score?: number) => {
    if (score === undefined || score === null) return 'bg-slate-100 text-slate-500';
    if (score >= 90) return 'bg-green-100 text-green-700';
    if (score >= 80) return 'bg-blue-100 text-blue-700';
    if (score >= 60) return 'bg-yellow-100 text-yellow-700';
    return 'bg-red-100 text-red-700';
  };

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div className="flex justify-between items-start bg-white p-6 rounded-xl border border-slate-200">
          <div className="flex gap-4 items-start">
            <button
              onClick={() => router.push('/teacher/dashboard')}
              className="mt-1 p-2 hover:bg-slate-100 rounded-lg transition-colors"
            >
              ←
            </button>
            <div>
              <h1 className="text-xl font-bold text-slate-800">Assignment Manager</h1>
              {loading && <div className="mt-2 text-xs text-slate-400">Loading classes...</div>}
              {classes.length > 0 && (
                <div className="flex gap-2 mt-3 flex-wrap">
                  {classes.map(cls => (
                    <button
                      key={cls.class_id}
                      onClick={() => setSelectedClass(cls.class_id)}
                      className={`px-3 py-1 rounded-full text-sm transition-all ${selectedClass === cls.class_id
                          ? 'bg-blue-600 text-white'
                          : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                        }`}
                    >
                      {cls.class_name}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
          <button
            onClick={() => setIsCreateOpen(true)}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            + New Assignment
          </button>
        </div>
        {error && (
          <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-600">
            {error}
          </div>
        )}

        {/* Homework List */}
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
          <table className="w-full">
            <thead className="bg-slate-50 border-b border-slate-200">
              <tr>
                <th className="text-left px-6 py-3 text-sm font-medium text-slate-600">Title</th>
                <th className="text-left px-6 py-3 text-sm font-medium text-slate-600">Deadline</th>
                <th className="text-left px-6 py-3 text-sm font-medium text-slate-600">Trigger</th>
                <th className="text-left px-6 py-3 text-sm font-medium text-slate-600">Created</th>
                <th className="text-right px-6 py-3 text-sm font-medium text-slate-600">Action</th>
              </tr>
            </thead>
            <tbody>
              {loadingHomeworks && (
                <tr>
                  <td className="px-6 py-4 text-slate-400" colSpan={5}>
                    Loading assignments...
                  </td>
                </tr>
              )}
              {homeworks.map(hw => (
                <tr key={hw.homework_id} className="border-b border-slate-100 hover:bg-slate-50">
                  <td className="px-6 py-4 font-medium text-slate-800">{hw.title}</td>
                  <td className="px-6 py-4 text-slate-600 font-mono text-sm">{hw.deadline}</td>
                  <td className="px-6 py-4 text-slate-600 text-sm">
                    {hw.allow_early_grading ? '全部提交后' : '截止后'}
                  </td>
                  <td className="px-6 py-4 text-slate-400 text-sm">
                    {dayjs(hw.created_at).format('MM-DD HH:mm')}
                  </td>
                  <td className="px-6 py-4 text-right flex justify-end gap-2">
                    <button
                      onClick={() => router.push(`/console?classId=${selectedClass}&homeworkId=${hw.homework_id}`)}
                      className="px-3 py-1 text-sm text-emerald-600 hover:bg-emerald-50 rounded-lg transition-colors"
                    >
                      一键批改
                    </button>
                    <button
                      onClick={() => openSubmissions(hw)}
                      className="px-3 py-1 text-sm text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                    >
                      View Grades
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!loadingHomeworks && homeworks.length === 0 && (
            <div className="text-center py-12 text-slate-400">No assignments yet</div>
          )}
        </div>

        {/* Create Modal */}
        {isCreateOpen && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <div className="bg-white rounded-xl p-6 w-full max-w-2xl mx-4 max-h-[90vh] overflow-y-auto">
              <h2 className="text-xl font-bold text-slate-800 mb-4">Create Assignment</h2>
              <div className="space-y-4">
                <input
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="Title"
                  className="w-full px-4 py-3 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Instructions"
                  rows={3}
                  className="w-full px-4 py-3 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <input
                  type="date"
                  value={deadline}
                  onChange={(e) => setDeadline(e.target.value)}
                  className="w-full px-4 py-3 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <label className="flex items-start gap-3 rounded-lg border border-slate-200 p-3 text-sm text-slate-600">
                  <input
                    type="checkbox"
                    checked={allowEarlyGrading}
                    onChange={(e) => setAllowEarlyGrading(e.target.checked)}
                    className="mt-1 h-4 w-4 rounded border-slate-300 text-slate-900"
                  />
                  <div>
                    <div className="font-medium text-slate-700">允许全部提交后提前批改</div>
                    <div className="text-xs text-slate-400">
                      开启后，所有学生提交完成即可触发批改；关闭则等待截止时间。
                    </div>
                  </div>
                </label>
                
                {/* Rubric 上传区域 */}
                <div className="border border-slate-200 rounded-lg p-4">
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="font-medium text-slate-700">评分标准 (Rubric)</h3>
                    <span className="text-xs text-slate-400">已上传 {rubricImageCount} 张</span>
                  </div>
                  
                  {/* Tab 切换 */}
                  <div className="flex gap-2 mb-3">
                    <button
                      type="button"
                      onClick={() => setRubricActiveTab('scan')}
                      className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                        rubricActiveTab === 'scan'
                          ? 'bg-blue-600 text-white'
                          : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                      }`}
                    >
                      扫描
                    </button>
                    <button
                      type="button"
                      onClick={() => setRubricActiveTab('gallery')}
                      className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                        rubricActiveTab === 'gallery'
                          ? 'bg-blue-600 text-white'
                          : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                      }`}
                    >
                      已上传 ({rubricImageCount})
                    </button>
                  </div>
                  
                  {/* Scanner/Gallery 组件 */}
                  <AppContext.Provider value={rubricContextValue}>
                    <div className="h-64 overflow-hidden rounded-lg border border-slate-100">
                      {rubricActiveTab === 'scan' ? (
                        <Scanner key="rubric-scanner" />
                      ) : (
                        <Gallery key="rubric-gallery" />
                      )}
                    </div>
                  </AppContext.Provider>
                </div>
              </div>
              <div className="flex gap-2 mt-6">
                <button
                  onClick={() => {
                    setIsCreateOpen(false);
                    setRubricSessions([]);
                    setRubricCurrentSessionId(null);
                  }}
                  className="flex-1 py-2 text-slate-600 hover:bg-slate-100 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  onClick={handleCreate}
                  className="flex-1 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                >
                  Create
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Submissions Drawer */}
        {isDrawerOpen && (
          <div className="fixed inset-0 bg-black/50 flex justify-end z-50">
            <div className="bg-white w-full max-w-2xl h-full overflow-y-auto">
              <div className="sticky top-0 bg-white border-b border-slate-200 p-4 flex justify-between items-center">
                <div>
                  <h2 className="font-bold text-slate-800">🤖 AI Gradebook: {currentHw?.title}</h2>
                </div>
                <button
                  onClick={() => setIsDrawerOpen(false)}
                  className="p-2 hover:bg-slate-100 rounded-lg"
                >
                  ✕
                </button>
              </div>
              <div className="p-6 space-y-4">
                {loadingSubmissions && (
                  <div className="text-sm text-slate-500">加载提交记录中...</div>
                )}
                {!loadingSubmissions && submissions.length === 0 && (
                  <div className="text-sm text-slate-400">暂无提交记录</div>
                )}
                {submissions.map(sub => {
                  const scoreLabel = sub.score ?? '--';
                  return (
                    <div key={sub.submission_id} className="bg-slate-50 rounded-xl p-4 border border-slate-200">
                      <div className="flex justify-between items-start mb-2">
                        <div>
                          <span className="font-bold text-slate-800">{sub.student_name}</span>
                          <span className="text-xs text-slate-400 ml-2">
                            {dayjs(sub.submitted_at).format('MM-DD HH:mm')}
                          </span>
                        </div>
                        <span className={`px-3 py-1 rounded-full text-sm font-bold ${getScoreColor(sub.score)}`}>
                          {scoreLabel}
                        </span>
                      </div>
                      <p className="text-xs text-slate-400 mb-2">状态：{sub.status}</p>
                      <p className="text-sm text-slate-600">{sub.feedback || '暂无反馈'}</p>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
