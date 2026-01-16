'use client';

import React, { useRef, useState } from 'react';
import { UploadCloud, FileText, Image as ImageIcon, Loader2 } from 'lucide-react';
import { useConsoleStore } from '@/store/consoleStore';
import { useGradingScan } from './index';
import { api } from '@/services/api';
import * as pdfjsLib from 'pdfjs-dist/legacy/build/pdf';

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
    await page.render({ canvasContext: context, viewport }).promise;
    images.push(canvas.toDataURL('image/jpeg', 0.92));
  }

  return images;
};

export default function GradingScanner() {
  const { setCurrentView } = useGradingScan();
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
        gradingMode
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
    <div className="h-full w-full flex flex-col items-center justify-center gap-6 p-10 text-center">
      <div className="max-w-3xl w-full space-y-5">
        <div>
          <h2 className="text-2xl font-semibold text-gray-900">扫描并预览</h2>
          <p className="text-sm text-gray-500">支持 PDF 自动转图片预览，确认后再启动批改流程。</p>
        </div>

        {error && (
          <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-600">
            {error}
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <button
            type="button"
            onClick={() => examInputRef.current?.click()}
            className="group rounded-2xl border-2 border-dashed border-gray-200 bg-white/70 p-8 text-left shadow-sm hover:border-blue-400 hover:bg-white"
          >
            <div className="flex items-center gap-3">
              <div className="rounded-full bg-blue-50 p-3 text-blue-500">
                <UploadCloud className="h-5 w-5" />
              </div>
              <div>
                <div className="text-sm font-semibold text-gray-900">答题文件</div>
                <div className="text-xs text-gray-500">支持 PDF / JPG / PNG</div>
              </div>
            </div>
            <div className="mt-4 text-xs text-gray-400">
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
          </button>

          <button
            type="button"
            onClick={() => rubricInputRef.current?.click()}
            className="group rounded-2xl border-2 border-dashed border-gray-200 bg-white/70 p-8 text-left shadow-sm hover:border-emerald-400 hover:bg-white"
          >
            <div className="flex items-center gap-3">
              <div className="rounded-full bg-emerald-50 p-3 text-emerald-500">
                <FileText className="h-5 w-5" />
              </div>
              <div>
                <div className="text-sm font-semibold text-gray-900">评分标准</div>
                <div className="text-xs text-gray-500">支持 PDF / JPG / PNG</div>
              </div>
            </div>
            <div className="mt-4 text-xs text-gray-400">
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
          </button>
        </div>

        <div className="rounded-2xl border border-dashed border-gray-300 bg-white/80 p-6 text-gray-600">
          {isParsing ? (
            <div className="flex items-center justify-center gap-2 text-sm">
              <Loader2 className="h-4 w-4 animate-spin" />
              正在解析 PDF 页面...
            </div>
          ) : uploadedImages.length > 0 ? (
            `已生成 ${uploadedImages.length} 页预览`
          ) : (
            '暂无预览页面'
          )}
        </div>

        <div className="flex items-center justify-center">
          <label className="flex items-center gap-2 rounded-full border border-gray-200 bg-white px-4 py-2 text-xs font-medium text-gray-600">
            <input
              type="checkbox"
              checked={interactionEnabled}
              onChange={(event) => setInteractionEnabled(event.target.checked)}
              className="h-4 w-4 rounded border-gray-300 text-gray-900 focus:ring-gray-400"
            />
            启用人工交互（批改前）
          </label>
        </div>

        <div className="flex items-center justify-center">
          <label className="flex items-center gap-2 rounded-full border border-gray-200 bg-white px-4 py-2 text-xs font-medium text-gray-600">
            <span className="text-[10px] uppercase tracking-wide text-gray-400">Mode</span>
            <select
              value={gradingMode}
              onChange={(event) => setGradingMode(event.target.value)}
              className="bg-transparent text-xs text-gray-700 focus:outline-none"
            >
              <option value="auto">Auto</option>
              <option value="standard">Standard (Rubric)</option>
              <option value="assist_teacher">Assist (Teacher)</option>
              <option value="assist_student">Assist (Student)</option>
            </select>
          </label>
        </div>

        <div className="flex flex-wrap items-center justify-center gap-3">
          <button
            onClick={() => setCurrentView('gallery')}
            className="inline-flex items-center justify-center rounded-full border border-gray-300 bg-white px-6 py-3 text-sm font-medium text-gray-700 transition-colors hover:border-gray-400"
          >
            <ImageIcon className="mr-2 h-4 w-4" />
            打开预览
          </button>
          <button
            onClick={handleUpload}
            disabled={isUploading || examFiles.length === 0}
            className="inline-flex items-center justify-center rounded-full bg-black px-8 py-3 text-sm font-medium text-white transition-colors hover:bg-gray-800 disabled:opacity-50"
          >
            {isUploading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                正在上传
              </>
            ) : (
              '开始批改'
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
