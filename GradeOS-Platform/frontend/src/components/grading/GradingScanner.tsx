'use client';

import React, { useRef, useState } from 'react';
import { UploadCloud, FileText, Image as ImageIcon, Loader2 } from 'lucide-react';
import { useConsoleStore } from '@/store/consoleStore';
import { useAuthStore } from '@/store/authStore';
import { useGradingScan } from './index';
import { api } from '@/services/api';
import * as pdfjsLib from 'pdfjs-dist';
import { GlassCard } from '@/components/design-system/GlassCard';
import { SmoothButton } from '@/components/design-system/SmoothButton';
import { motion } from 'framer-motion';

pdfjsLib.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url
).toString();

const toDataUrl = (file: File) =>
  new Promise<string>((resolve) => {
    const reader = new FileReader();
    reader.onload = (e) => resolve(e.target?.result as string);
    reader.readAsDataURL(file);
  });

const renderPdfToImages = async (file: File, maxPages = 80): Promise<string[]> => {
  const buffer = await file.arrayBuffer();
  const pdf = await pdfjsLib.getDocument({ data: new Uint8Array(buffer) }).promise;
  const pages = Math.min(pdf.numPages, maxPages);
  const images: string[] = [];

  for (let i = 1; i <= pages; i += 1) {
    const page = await pdf.getPage(i);
    const viewport = page.getViewport({ scale: 1.5 });
    const canvas = document.createElement('canvas');
    const context = canvas.getContext('2d');
    if (!context) continue;
    canvas.width = viewport.width;
    canvas.height = viewport.height;
    await page.render({ canvasContext: context as CanvasRenderingContext2D, viewport }).promise;
    images.push(canvas.toDataURL('image/jpeg', 0.92));
  }

  return images;
};

export default function GradingScanner() {
  const { setCurrentView } = useGradingScan();
  const { user } = useAuthStore();
  const {
    setStatus,
    setSubmissionId,
    addLog,
    connectWs,
    setUploadedImages,
    gradingMode,
    setGradingMode
  } = useConsoleStore();
  const uploadedImages = useConsoleStore((state) => state.uploadedImages);
  const [examFiles, setExamFiles] = useState<File[]>([]);
  const [rubricFiles, setRubricFiles] = useState<File[]>([]);
  const [isParsing, setIsParsing] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [interactionEnabled, setInteractionEnabled] = useState(false);
  const examInputRef = useRef<HTMLInputElement>(null);
  const rubricInputRef = useRef<HTMLInputElement>(null);

  const handleExamFiles = async (files: File[]) => {
    setError(null);
    setExamFiles(files);
    setIsParsing(true);
    try {
      const images: string[] = [];
      for (const file of files) {
        if (file.type === 'application/pdf') {
          const pdfImages = await renderPdfToImages(file);
          images.push(...pdfImages);
        } else if (file.type.startsWith('image/')) {
          images.push(await toDataUrl(file));
        }
      }
      setUploadedImages(images);
      addLog(`Loaded ${images.length} page(s) for preview`, 'INFO');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'PDF 预览失败');
    } finally {
      setIsParsing(false);
    }
  };

  const handleUpload = async () => {
    if (examFiles.length === 0) {
      setError('请先选择答题文件');
      return;
    }
    
    // ⚠️ 分批提示弹窗
    const shouldContinue = await new Promise<boolean>((resolve) => {
      // 创建弹窗
      const overlay = document.createElement('div');
      overlay.className = 'fixed inset-0 z-[9999] flex items-center justify-center bg-black/50 backdrop-blur-sm';
      
      const modal = document.createElement('div');
      modal.className = 'bg-white rounded-xl shadow-2xl p-8 max-w-lg mx-4 animate-in fade-in zoom-in duration-200';
      modal.innerHTML = `
        <div class="flex items-start gap-4 mb-6">
          <div class="flex-shrink-0 w-12 h-12 rounded-full bg-amber-100 flex items-center justify-center">
            <svg class="w-6 h-6 text-amber-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
            </svg>
          </div>
          <div class="flex-1">
            <h3 class="text-xl font-semibold text-gray-900 mb-2">重要提示：请确认已按学生分批</h3>
            <div class="space-y-3 text-gray-600">
              <p class="text-sm leading-relaxed">
                为确保批改准确性，<span class="font-semibold text-gray-900">请在上传前完成学生试卷的分批</span>。
              </p>
              <div class="bg-blue-50 border border-blue-200 rounded-lg p-4">
                <p class="text-sm font-medium text-blue-900 mb-2">分批要求：</p>
                <ul class="text-sm text-blue-800 space-y-1 list-disc list-inside">
                  <li>每个学生的试卷应该按顺序排列</li>
                  <li>不同学生的试卷应该明确分开</li>
                  <li>确保页面顺序正确，没有遗漏或重复</li>
                </ul>
              </div>
              <p class="text-sm font-medium text-gray-700">
                确认已完成分批后，点击"继续批改"开始。
              </p>
            </div>
          </div>
        </div>
        <div class="flex gap-3 justify-end">
          <button id="cancel-btn" class="px-6 py-2.5 rounded-lg border border-gray-300 text-gray-700 font-medium hover:bg-gray-50 transition-colors">
            取消
          </button>
          <button id="continue-btn" class="px-6 py-2.5 rounded-lg bg-gradient-to-r from-blue-600 to-indigo-600 text-white font-medium hover:from-blue-700 hover:to-indigo-700 transition-all shadow-sm">
            已分批，继续批改
          </button>
        </div>
      `;
      
      overlay.appendChild(modal);
      document.body.appendChild(overlay);
      
      // 绑定按钮事件
      const cancelBtn = overlay.querySelector('#cancel-btn');
      const continueBtn = overlay.querySelector('#continue-btn');
      
      const cleanup = () => {
        overlay.remove();
      };
      
      cancelBtn?.addEventListener('click', () => {
        cleanup();
        resolve(false);
      });
      
      continueBtn?.addEventListener('click', () => {
        cleanup();
        resolve(true);
      });
      
      // ESC 键关闭
      const handleEsc = (e: KeyboardEvent) => {
        if (e.key === 'Escape') {
          cleanup();
          resolve(false);
          document.removeEventListener('keydown', handleEsc);
        }
      };
      document.addEventListener('keydown', handleEsc);
    });
    
    if (!shouldContinue) {
      return; // 用户取消
    }
    
    setIsUploading(true);
    setError(null);
    setStatus('UPLOADING');
    addLog(`Starting upload: ${examFiles.length} exams, ${rubricFiles.length} rubrics`, 'INFO');
    try {
      const submission = await api.createSubmission(
        examFiles,
        rubricFiles,
        [],
        undefined,
        undefined,
        interactionEnabled,
        gradingMode,
        user?.id
      );
      addLog(`Upload complete. Submission ID: ${submission.id}`, 'SUCCESS');
      setSubmissionId(submission.id);
      setTimeout(() => {
        setStatus('RUNNING');
        connectWs(submission.id);
      }, 500);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Upload failed';
      addLog(`Error: ${message}`, 'ERROR');
      setStatus('FAILED');
      setError(message);
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="h-full w-full flex flex-col items-center justify-center p-6 text-center">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="max-w-4xl w-full space-y-8"
      >
        <div className="space-y-2">
          <h2 className="text-3xl font-bold bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent">
            扫描并预览
          </h2>
          <p className="text-gray-500 text-lg">
            支持 PDF 自动转图片预览，确认后再启动批改流程
          </p>
        </div>

        {error && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            className="rounded-xl border border-rose-200 bg-rose-50/80 backdrop-blur-sm px-4 py-3 text-sm text-rose-600"
          >
            {error}
          </motion.div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          <GlassCard
            className="p-8 cursor-pointer group hover:border-blue-300 transition-colors"
            onClick={() => examInputRef.current?.click()}
          >
            <div className="flex flex-col items-center gap-4">
              <div className="rounded-full bg-blue-50 p-4 text-blue-500 group-hover:scale-110 transition-transform duration-300">
                <UploadCloud className="h-8 w-8" />
              </div>
              <div>
                <div className="text-lg font-semibold text-gray-900">答题文件</div>
                <div className="text-sm text-gray-500 mt-1">支持 PDF / JPG / PNG</div>
              </div>
            </div>
            <div className="mt-6 text-sm text-gray-400 font-medium bg-gray-50 py-2 px-4 rounded-lg">
              {examFiles.length > 0 ? `${examFiles.length} 个文件已选择` : '点击选择或拖拽上传'}
            </div>
            <input
              ref={examInputRef}
              type="file"
              multiple
              accept=".pdf,.jpg,.jpeg,.png"
              className="hidden"
              onChange={(e) => e.target.files && handleExamFiles(Array.from(e.target.files))}
            />
          </GlassCard>

          <GlassCard
            className="p-8 cursor-pointer group hover:border-emerald-300 transition-colors"
            onClick={() => rubricInputRef.current?.click()}
          >
            <div className="flex flex-col items-center gap-4">
              <div className="rounded-full bg-emerald-50 p-4 text-emerald-500 group-hover:scale-110 transition-transform duration-300">
                <FileText className="h-8 w-8" />
              </div>
              <div>
                <div className="text-lg font-semibold text-gray-900">评分标准</div>
                <div className="text-sm text-gray-500 mt-1">支持 PDF / JPG / PNG</div>
              </div>
            </div>
            <div className="mt-6 text-sm text-gray-400 font-medium bg-gray-50 py-2 px-4 rounded-lg">
              {rubricFiles.length > 0 ? `${rubricFiles.length} 个文件已选择` : '可选上传'}
            </div>
            <input
              ref={rubricInputRef}
              type="file"
              multiple
              accept=".pdf,.jpg,.jpeg,.png"
              className="hidden"
              onChange={(e) => e.target.files && setRubricFiles(Array.from(e.target.files))}
            />
          </GlassCard>
        </div>

        <GlassCard className="py-4 text-gray-600 font-medium">
          {isParsing ? (
            <div className="flex items-center justify-center gap-3">
              <Loader2 className="h-5 w-5 animate-spin text-blue-500" />
              正在解析 PDF 页面...
            </div>
          ) : uploadedImages.length > 0 ? (
            <span className="text-blue-600">已生成 {uploadedImages.length} 页预览</span>
          ) : (
            '暂无预览页面'
          )}
        </GlassCard>

        <div className="flex flex-wrap items-center justify-center gap-4">
          <label className="flex items-center gap-3 px-5 py-3 rounded-full bg-white/60 border border-gray-200 backdrop-blur-sm cursor-pointer hover:bg-white/80 transition-colors">
            <input
              type="checkbox"
              checked={interactionEnabled}
              onChange={(event) => setInteractionEnabled(event.target.checked)}
              className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            <span className="text-sm font-medium text-gray-700">启用人工交互（批改前）</span>
          </label>

          <label className="flex items-center gap-3 px-5 py-3 rounded-full bg-white/60 border border-gray-200 backdrop-blur-sm cursor-pointer hover:bg-white/80 transition-colors">
            <span className="text-xs font-bold uppercase tracking-wider text-gray-400">Mode</span>
            <select
              value={gradingMode}
              onChange={(event) => setGradingMode(event.target.value)}
              className="bg-transparent text-sm font-medium text-gray-700 focus:outline-none cursor-pointer"
            >
              <option value="auto">Auto</option>
              <option value="standard">Standard (Rubric)</option>
              <option value="assist_teacher">Assist (Teacher)</option>
              <option value="assist_student">Assist (Student)</option>
            </select>
          </label>
        </div>

        <div className="flex flex-wrap items-center justify-center gap-4 pt-4">
          <SmoothButton
            variant="secondary"
            onClick={() => setCurrentView('gallery')}
            size="lg"
            className="min-w-[160px]"
          >
            <ImageIcon className="mr-2 h-5 w-5" />
            打开预览
          </SmoothButton>

          <SmoothButton
            variant="primary"
            onClick={handleUpload}
            disabled={isUploading || examFiles.length === 0}
            isLoading={isUploading}
            size="lg"
            className="min-w-[160px] shadow-blue-500/25"
          >
            {isUploading ? '正在上传' : '开始批改'}
          </SmoothButton>
        </div>
      </motion.div>
    </div>
  );
}
