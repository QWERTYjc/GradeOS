'use client';

// Prevent SSR prerendering - this page uses pdfjs-dist which requires browser APIs
export const dynamic = 'force-dynamic';

import React, { useState, useEffect, useMemo } from 'react';
import { Images, ScanLine, Send, ArrowLeft, CheckCircle2, Loader2 } from 'lucide-react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { AppContext, AppContextType } from '@/components/bookscan/AppContext';
import Scanner from '@/components/bookscan/Scanner';
import Gallery from '@/components/bookscan/Gallery';
import { ScannedImage, Session } from '@/components/bookscan/types';
import { homeworkApi, HomeworkResponse } from '@/services/api';
import { useAuthStore } from '@/store/authStore';

type ViewTab = 'scan' | 'gallery';

export default function StudentScanPage() {
  const searchParams = useSearchParams();
  const homeworkId = searchParams.get('homeworkId');
  const { user } = useAuthStore();
  
  const [sessions, setSessions] = useState<Session[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<ViewTab>('scan');
  const [splitImageIds, setSplitImageIds] = useState<Set<string>>(new Set());

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitResult, setSubmitResult] = useState<{
    success: boolean;
    score?: number;
    feedback?: string;
  } | null>(null);
  
  // 作业信息
  const [homework, setHomework] = useState<HomeworkResponse | null>(null);
  const [loadingHomework, setLoadingHomework] = useState(false);

  // 加载作业信息
  useEffect(() => {
    if (homeworkId) {
      setLoadingHomework(true);
      homeworkApi.getDetail(homeworkId)
        .then(setHomework)
        .catch(console.error)
        .finally(() => setLoadingHomework(false));
    }
  }, [homeworkId]);

  useEffect(() => {
    try {
      // 清空所有可能的旧 localStorage 数据，避免配额问题
      const keysToRemove = [];
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        if (key && (key.includes('scan') || key.includes('gradeos') || key.includes('session'))) {
          keysToRemove.push(key);
        }
      }
      keysToRemove.forEach(key => localStorage.removeItem(key));
    } catch (e) {
      // 忽略错误
    }
    createNewSession('默认扫描会话');
  }, []);

  // 不再保存 sessions 到 localStorage，避免配额问题
  // 图片数据只保存在内存中，提交后清空

  const createNewSession = (name?: string) => {
    const newSession: Session = {
      id: crypto.randomUUID(),
      name: name || `扫描 ${new Date().toLocaleTimeString()}`,
      createdAt: Date.now(),
      images: []
    };
    setSessions(prev => [newSession, ...prev]);
    setCurrentSessionId(newSession.id);
  };

  const addImageToSession = (img: ScannedImage) => {
    if (!currentSessionId) return;
    setSessions(prev => prev.map(s =>
      s.id === currentSessionId ? { ...s, images: [...s.images, img] } : s
    ));
  };

  const addImagesToSession = (imgs: ScannedImage[]) => {
    if (!currentSessionId) return;
    setSessions(prev => prev.map(s =>
      s.id === currentSessionId ? { ...s, images: [...s.images, ...imgs] } : s
    ));
  };

  const deleteSession = (id: string) => {
    setSessions(prev => {
      const filtered = prev.filter(s => s.id !== id);
      if (currentSessionId === id) {
        setCurrentSessionId(filtered.length > 0 ? filtered[0].id : null);
      }
      return filtered;
    });
  };

  const deleteImages = (sessionId: string, imageIds: string[]) => {
    setSessions(prev => prev.map(s =>
      s.id === sessionId ? { ...s, images: s.images.filter(img => !imageIds.includes(img.id)) } : s
    ));
  };

  const updateImage = (sessionId: string, imageId: string, newUrl: string, isOptimizing: boolean = false) => {
    setSessions(prev => prev.map(s =>
      s.id === sessionId ? {
        ...s,
        images: s.images.map(img => img.id === imageId ? { ...img, url: newUrl, isOptimizing } : img)
      } : s
    ));
  };

  const reorderImages = (sessionId: string, fromIndex: number, toIndex: number) => {
    setSessions(prev => prev.map(s => {
      if (s.id === sessionId) {
        const imgs = [...s.images];
        const [moved] = imgs.splice(fromIndex, 1);
        imgs.splice(toIndex, 0, moved);
        return { ...s, images: imgs };
      }
      return s;
    }));
  };

  const markImageAsSplit = (imageId: string) => {
    setSplitImageIds(prev => new Set(prev).add(imageId));
  };

  const currentSession = sessions.find(s => s.id === currentSessionId);
  const imageCount = currentSession?.images.length || 0;

  const handleSubmit = async () => {
    if (!currentSession || currentSession.images.length === 0) {
      alert('请先扫描或上传图片');
      return;
    }
    
    if (!homeworkId) {
      alert('缺少作业ID，请从作业列表进入');
      return;
    }

    setIsSubmitting(true);
    try {
      const images = currentSession.images.map(img => img.url);
      const studentId = user?.id || 'student-001';
      const studentName = user?.name || '测试学生';
      
      const result = await homeworkApi.submitScan({
        homework_id: homeworkId,
        student_id: studentId,
        student_name: studentName,
        images
      });
      
      // 清空扫描会话
      setSessions([]);
      localStorage.removeItem('gradeos_scan_sessions');
      createNewSession('默认扫描会话');
      
      setSubmitResult({
        success: true,
        score: result.score,
        feedback: result.feedback || '作业已提交，等待批改'
      });
    } catch (error: any) {
      setSubmitResult({ success: false, feedback: error.message });
    } finally {
      setIsSubmitting(false);
    }
  };

  const contextValue: AppContextType = useMemo(() => ({
    sessions,
    currentSessionId,
    createNewSession,
    addImageToSession,
    addImagesToSession,
    deleteSession,
    deleteImages,
    setCurrentSessionId,
    updateImage,
    reorderImages,
    splitImageIds,
    markImageAsSplit
  }), [sessions, currentSessionId, splitImageIds]);

  if (submitResult) {
    return (
      <div className="min-h-screen bg-[#F5F7FB] flex items-center justify-center p-4">
        <div className="bg-white rounded-3xl p-8 max-w-md w-full text-center shadow-xl">
          {submitResult.success ? (
            <>
              <div className="w-20 h-20 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-6">
                <CheckCircle2 className="text-green-600" size={40} />
              </div>
              <h2 className="text-2xl font-black text-slate-800 mb-2">提交成功！</h2>
              <p className="text-slate-500 mb-6">AI 已完成批改</p>
              <div className="bg-gradient-to-br from-blue-500 to-blue-600 text-white rounded-2xl p-6 mb-6">
                <div className="text-6xl font-black mb-2">{submitResult.score}</div>
                <div className="text-blue-100 text-sm">分数</div>
              </div>
              <div className="bg-slate-50 rounded-xl p-4 text-left mb-6">
                <div className="text-xs font-bold text-slate-400 mb-2">AI 反馈</div>
                <p className="text-slate-700 text-sm">{submitResult.feedback}</p>
              </div>
              <div className="flex gap-3">
                <button onClick={() => setSubmitResult(null)} className="flex-1 py-3 bg-slate-100 text-slate-600 rounded-xl font-bold">继续扫描</button>
                <Link href="/student/dashboard" className="flex-1">
                  <button className="w-full py-3 bg-blue-600 text-white rounded-xl font-bold">返回首页</button>
                </Link>
              </div>
            </>
          ) : (
            <>
              <div className="w-20 h-20 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-6">
                <span className="text-4xl">❌</span>
              </div>
              <h2 className="text-2xl font-black text-slate-800 mb-2">提交失败</h2>
              <p className="text-slate-500 mb-6">{submitResult.feedback}</p>
              <button onClick={() => setSubmitResult(null)} className="w-full py-3 bg-blue-600 text-white rounded-xl font-bold">重试</button>
            </>
          )}
        </div>
      </div>
    );
  }

  return (
    <AppContext.Provider value={contextValue}>
      <div className="flex flex-col h-screen bg-[#F5F7FB]">
        <div className="bg-white border-b border-slate-100 px-4 py-3 flex items-center justify-between sticky top-0 z-30">
          <div className="flex items-center gap-3">
            <Link href="/student/dashboard">
              <button className="p-2 hover:bg-slate-100 rounded-xl"><ArrowLeft size={20} className="text-slate-600" /></button>
            </Link>
            <div>
              <h1 className="text-lg font-black text-slate-800">
                {loadingHomework ? '加载中...' : (homework?.title || '扫描提交作业')}
              </h1>
              <p className="text-xs text-slate-400">
                {homework?.deadline ? `截止: ${homework.deadline}` : 'BookScan AI Engine'}
              </p>
            </div>
          </div>
          {imageCount > 0 && (
            <button onClick={handleSubmit} disabled={isSubmitting} className="flex items-center gap-2 px-5 py-2.5 bg-blue-600 text-white rounded-xl font-bold disabled:opacity-50 shadow-lg shadow-blue-200">
              {isSubmitting ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
              {isSubmitting ? '提交中...' : `提交 (${imageCount})`}
            </button>
          )}
        </div>

        <div className="bg-white px-4 py-2 border-b border-slate-100 flex gap-2">
          <button onClick={() => setActiveTab('scan')} className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-bold ${activeTab === 'scan' ? 'bg-blue-600 text-white shadow-lg shadow-blue-200' : 'text-slate-500 hover:bg-slate-100'}`}>
            <ScanLine size={16} /> 扫描
          </button>
          <button onClick={() => setActiveTab('gallery')} className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-bold ${activeTab === 'gallery' ? 'bg-blue-600 text-white shadow-lg shadow-blue-200' : 'text-slate-500 hover:bg-slate-100'}`}>
            <Images size={16} /> 已扫描 ({imageCount})
          </button>
        </div>

        <div className="flex-1 overflow-hidden">
          {activeTab === 'scan' ? <Scanner /> : <Gallery />}
        </div>

        {isSubmitting && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <div className="bg-white rounded-2xl p-8 text-center">
              <Loader2 size={48} className="animate-spin text-blue-600 mx-auto mb-4" />
              <p className="text-slate-600 font-medium">正在提交并等待 AI 批改...</p>
            </div>
          </div>
        )}
      </div>
    </AppContext.Provider>
  );
}
