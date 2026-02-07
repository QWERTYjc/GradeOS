import React, { useContext, useState, useEffect, useRef } from 'react';
import { motion, useReducedMotion, useScroll, useTransform } from 'framer-motion';
import { AppContext } from './AppContext';
import { Trash2, CheckSquare, Square, Wand2, Images, ArrowLeft, ArrowRight, Move, Loader2, Send, Split } from 'lucide-react';
import ImageEditor from './ImageEditor';
import ImageViewer from './ImageViewer';
import { ScannedImage, Session } from './types';

interface StudentNameMapping {
  studentId?: string;
  studentName?: string;
  studentKey?: string;
  startIndex?: number;
  endIndex?: number;
}

interface GalleryProps {
  session?: any; // Optional direct session injection
  onSubmitBatch?: (images: ScannedImage[]) => Promise<void>;
  submitLabel?: string;
  onBoundariesChange?: (boundaries: number[]) => void;
  isRubricMode?: boolean;
  studentNameMapping?: StudentNameMapping[]; // 班级批改模式下的学生名称映射
  onStudentInfoChange?: (index: number, info: { studentName?: string; studentId?: string }) => void;
  interactionEnabled?: boolean;
  onInteractionToggle?: (enabled: boolean) => void;
  gradingMode?: string;
  onGradingModeChange?: (mode: string) => void;
}

interface PreviewCardProps {
  children: React.ReactNode;
  className?: string;
  containerRef: React.RefObject<HTMLElement | null>;
}

const PreviewCard = ({ children, className, containerRef }: PreviewCardProps) => {
  const ref = useRef<HTMLDivElement>(null);
  const reduceMotion = useReducedMotion();
  const { scrollYProgress } = useScroll({
    target: ref,
    container: containerRef,
    offset: ["start end", "center center", "end start"],
  });
  const scale = useTransform(
    scrollYProgress,
    [0, 0.5, 1],
    reduceMotion ? [1, 1, 1] : [0.96, 1.02, 0.96]
  );
  const y = useTransform(
    scrollYProgress,
    [0, 0.5, 1],
    reduceMotion ? [0, 0, 0] : [10, 0, -10]
  );

  return (
    <motion.div
      ref={ref}
      style={{ scale, y }}
      className={`transform-gpu will-change-transform ${className || ""}`}
    >
      {children}
    </motion.div>
  );
};

export default function Gallery({
  session,
  onSubmitBatch,
  submitLabel,
  onBoundariesChange,
  isRubricMode = false,
  studentNameMapping = [],
  onStudentInfoChange,
  interactionEnabled = false,
  onInteractionToggle,
  gradingMode = 'auto',
  onGradingModeChange
}: GalleryProps) {
  const context = useContext(AppContext);
  const [selectedImages, setSelectedImages] = useState<Set<string>>(new Set());
  const [editingImageId, setEditingImageId] = useState<string | null>(null);
  const [viewingImageId, setViewingImageId] = useState<string | null>(null);
  const [isReorderMode, setIsReorderMode] = useState(false);
  const [isSplitMode, setIsSplitMode] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  // Use injected session or fallback to context
  const currentSession = context ? (session || context.sessions.find(s => s.id === context.currentSessionId)) as Session | undefined : undefined;
  const splitImageIds = context?.splitImageIds || new Set();

  // Notify parent of boundary changes whenever splitImageIds or image order changes
  useEffect(() => {
    if (!context || !currentSession || isRubricMode) return;

    // Always include index 0 implicitly
    const indices = [0];

    currentSession.images.forEach((img: ScannedImage, index: number) => {
      if (index > 0 && splitImageIds.has(img.id)) {
        indices.push(index);
      }
    });

    onBoundariesChange?.(indices);
  }, [context, splitImageIds, currentSession?.images, onBoundariesChange, isRubricMode]);

  if (!context) return null;

  const {
    deleteImages, reorderImages, markImageAsSplit
  } = context;

  const toggleSelection = (id: string) => {
    const newSet = new Set(selectedImages);
    if (newSet.has(id)) newSet.delete(id);
    else newSet.add(id);
    setSelectedImages(newSet);
  };

  const toggleSplit = (id: string) => {
    markImageAsSplit(id);
  };

  const selectAll = () => {
    if (!onSubmitBatch) {
      alert('Submission handler is not configured for this page.');
      return;
    }
    if (!currentSession) return;
    if (selectedImages.size === currentSession.images.length) {
      setSelectedImages(new Set());
    } else {
      setSelectedImages(new Set(currentSession.images.map(img => img.id)));
    }
  };

  const handleBulkDelete = () => {
    if (!context?.currentSessionId) return;
    if (confirm(`Delete ${selectedImages.size} images?`)) {
      deleteImages(context.currentSessionId, Array.from(selectedImages));
      setSelectedImages(new Set());
    }
  };

  const handleMove = (index: number, direction: 'left' | 'right') => {
    if (!context?.currentSessionId || !currentSession) return;
    const newIndex = direction === 'left' ? index - 1 : index + 1;
    if (newIndex >= 0 && newIndex < currentSession.images.length) {
      reorderImages(context.currentSessionId, index, newIndex);
    }
  };

  const handleImageClick = (id: string, index: number) => {
    if (isReorderMode) return;
    if (isSplitMode && index > 0) { // Cannot toggle split on first image
      toggleSplit(id);
      return;
    }
    setViewingImageId(id);
  };

  const handleDirectSubmit = async () => {
    if (isRubricMode) {
      alert('评分标准已保存，请切换到 Student Exams 并点击 Start Grading 开始批改。');
      return;
    }
    if (!currentSession) return;
    if (!onSubmitBatch) {
      alert('Submission handler is not configured for this page.');
      return;
    }

    const imagesToSend = selectedImages.size > 0
      ? currentSession.images.filter(img => selectedImages.has(img.id))
      : currentSession.images;

    if (imagesToSend.length === 0) {
      alert("No images to submit. Please scan or select images first.");
      return;
    }

    setIsSubmitting(true);
    try {
      console.log('Gallery: Using provided onSubmitBatch');
      await onSubmitBatch(imagesToSend);

      setSelectedImages(new Set());
    } catch (e: any) {
      console.error(e);
      alert(`Submission Failed\n\n${e.message}\n\nEnsure backend is running at http://localhost:8001`);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="flex flex-col h-full bg-white relative text-[#0B0F17]">
      {/* Header Toolbar - Reduced Density */}
      <div className="px-4 py-3 bg-white flex flex-col gap-2 border-b border-slate-100 z-10 sticky top-0">

        <div className="flex flex-col md:flex-row items-center justify-between gap-3">
          {/* Left: Spacer or Title if needed in future (Empty for clean look as requested) */}
          <div className="hidden md:block"></div>

          <div className="flex items-center gap-1.5 w-full md:w-auto overflow-x-auto pb-1 md:pb-0 no-scrollbar">

            {/* Submit Button */}
            <button
              onClick={handleDirectSubmit}
              disabled={isRubricMode || isSubmitting || !onSubmitBatch || (currentSession?.images.length === 0)}
              className="flex items-center gap-1.5 px-3 py-2 text-xs bg-slate-900 text-white rounded shadow-sm hover:bg-slate-800 transition-all whitespace-nowrap disabled:opacity-50 disabled:cursor-not-allowed font-medium"
              title={!isRubricMode && !onSubmitBatch ? 'Submission handler is not configured.' : undefined}
            >
              {isSubmitting ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
              {isRubricMode ? 'Rubric Ready' : (isSubmitting ? 'Uploading...' : (submitLabel || 'Submit'))}
            </button>



            {!isRubricMode && onInteractionToggle && (
              <label className="flex items-center gap-2 px-2 py-1 text-xs text-slate-600 hover:text-slate-900 transition-colors">
                <input
                  type="checkbox"
                  checked={interactionEnabled}
                  onChange={(event) => onInteractionToggle(event.target.checked)}
                  className="h-3.5 w-3.5 rounded border-slate-300 text-slate-900 focus:ring-slate-500"
                />
                启用人工交互（批改前）
              </label>
            )}

            {!isRubricMode && onGradingModeChange && (
              <label className="flex items-center gap-2 px-2 py-1 text-xs text-slate-600 hover:text-slate-900 transition-colors">
                <span className="text-[10px] uppercase tracking-wide text-slate-400">Mode</span>
                <select
                  value={gradingMode}
                  onChange={(event) => onGradingModeChange(event.target.value)}
                  className="bg-transparent text-xs text-slate-700 focus:outline-none"
                >
                  <option value="auto">Auto</option>
                  <option value="standard">Standard (Rubric)</option>
                  <option value="assist_teacher">Assist (Teacher)</option>
                  <option value="assist_student">Assist (Student)</option>
                </select>
              </label>
            )}

            {/* Split Mode (Boundary) - Integrated */}
            {!isRubricMode && (
              <button
                onClick={() => {
                  setIsSplitMode(!isSplitMode);
                  if (isReorderMode) setIsReorderMode(false);
                }}
                className={`flex items-center gap-1.5 px-2 py-1 text-xs font-semibold uppercase tracking-wider transition-all whitespace-nowrap ${isSplitMode ? 'text-slate-900 border-b-2 border-slate-900' : 'text-slate-500 hover:text-slate-700 border-b-2 border-transparent'}`}
                title="Click images to split into separate students"
              >
                <Split size={14} className={isSplitMode ? "rotate-90" : ""} />
                {isSplitMode ? 'Splitting' : 'Split'}
              </button>
            )}

            {/* Reorder Toggle */}
            <button
              onClick={() => {
                setIsReorderMode(!isReorderMode);
                if (isSplitMode) setIsSplitMode(false);
              }}
              className={`flex items-center gap-1.5 px-2 py-1 text-xs font-semibold uppercase tracking-wider transition-all whitespace-nowrap ${isReorderMode ? 'text-slate-900 border-b-2 border-slate-900' : 'text-slate-500 hover:text-slate-700 border-b-2 border-transparent'}`}
            >
              <Move size={14} />
              {isReorderMode ? 'Done' : 'Order'}
            </button>



            <button
              onClick={selectAll}
              disabled={isReorderMode || isSplitMode}
              className="flex items-center gap-1.5 px-2 py-1 text-xs text-slate-500 hover:text-slate-700 transition-colors whitespace-nowrap disabled:opacity-30 font-medium border-b-2 border-transparent"
            >
              {currentSession && selectedImages.size === currentSession.images.length && currentSession.images.length > 0 ? <CheckSquare size={14} /> : <Square size={14} />}
              All
            </button>

            <button
              onClick={handleBulkDelete}
              disabled={selectedImages.size === 0 || isReorderMode || isSplitMode}
              className="flex items-center gap-1.5 px-2 py-1 text-xs text-slate-400 hover:text-red-600 disabled:opacity-30 transition-colors whitespace-nowrap font-medium border-b-2 border-transparent"
            >
              <Trash2 size={14} />
            </button>
          </div>
        </div>
      </div>

      {/* Grid */}
      <div
        ref={scrollContainerRef}
        className="flex-1 overflow-y-auto p-3 sm:p-4 lg:p-6 bg-white space-y-8"
      >
        {currentSession && currentSession.images.length > 0 ? (
          (() => {
            // Group images by student (logic: splitImageIds marks start of NEW student)
            const groups: typeof currentSession.images[] = [];
            let currentGroup: typeof currentSession.images = [];

            // Re-calculate split indices based on splitImageIds
            currentSession.images.forEach((img, index) => {
              // If it's a split point (start of new student) AND not the very first image
              if (index > 0 && splitImageIds.has(img.id)) {
                groups.push(currentGroup);
                currentGroup = [];
              }
              currentGroup.push(img);
            });
            if (currentGroup.length > 0) groups.push(currentGroup);

            let globalIndex = 0;

            return groups.map((group, groupIdx) => {
              const startImageIndex = globalIndex;
              globalIndex += group.length;

              return (
                <div key={groupIdx} className="relative pl-3">
                  {/* Visual Indentation Marker (Left Line) */}
                  {!isRubricMode && (
                    <div className="absolute left-0 top-3 bottom-3 w-1 bg-slate-300 rounded-full"></div>
                  )}

                  {/* Student Header (New Line) */}
                  {!isRubricMode && (
                    <div className="flex items-center gap-2 mb-3">
                      <div className="bg-slate-900 text-white text-[10px] font-bold px-2 py-0.5 rounded uppercase tracking-wider shadow-sm">
                        {studentNameMapping[groupIdx]?.studentName
                          || studentNameMapping[groupIdx]?.studentId
                          || studentNameMapping[groupIdx]?.studentKey
                          || `Student ${groupIdx + 1}`}
                      </div>
                      {onStudentInfoChange && (
                        <div className="flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
                          <input
                            type="text"
                            placeholder="姓名"
                            value={studentNameMapping[groupIdx]?.studentName || ''}
                            onChange={(event) => {
                              onStudentInfoChange(groupIdx, {
                                studentName: event.target.value,
                                studentId: studentNameMapping[groupIdx]?.studentId,
                              });
                            }}
                            className="h-7 w-28 rounded-full border border-slate-200 bg-white px-3 text-[11px] font-medium text-slate-700 shadow-sm outline-none focus:border-slate-400"
                          />
                          <input
                            type="text"
                            placeholder="学号"
                            value={studentNameMapping[groupIdx]?.studentId || ''}
                            onChange={(event) => {
                              onStudentInfoChange(groupIdx, {
                                studentName: studentNameMapping[groupIdx]?.studentName,
                                studentId: event.target.value,
                              });
                            }}
                            className="h-7 w-24 rounded-full border border-slate-200 bg-white px-3 text-[11px] font-medium text-slate-700 shadow-sm outline-none focus:border-slate-400"
                          />
                        </div>
                      )}
                      <div className="h-px bg-slate-200 flex-1 border-t border-dashed border-slate-300"></div>
                    </div>
                  )}

                  <div className="grid grid-cols-3 sm:grid-cols-5 md:grid-cols-8 lg:grid-cols-12 gap-1.5 auto-rows-max">
                    {group.map((img, groupImgIndex) => {
                      const actualIndex = startImageIndex + groupImgIndex;
                      const isStart = groupImgIndex === 0;
                      const isSelected = selectedImages.has(img.id);

                      return (
                        <PreviewCard
                          key={img.id}
                          containerRef={scrollContainerRef}
                          className={`relative group bg-white rounded-sm overflow-hidden select-none transition-all duration-200
                                    ${isSelected ? 'ring-2 ring-indigo-500 z-10' : 'hover:ring-1 hover:ring-slate-300'}
                                    ${isSplitMode && isStart ? 'ring-2 ring-amber-500 z-10' : ''}
                                `}
                        >
                          {/* Minimal Page Indicator (Inside Card) */}
                          <div className="absolute top-0 right-0 z-20 px-1 py-0.5 bg-black/50 text-white backdrop-blur-[2px] opacity-0 group-hover:opacity-100 transition-opacity">
                            <span className="text-[9px] font-medium">P{groupImgIndex + 1}</span>
                          </div>

                          <div
                            className="aspect-[210/297] relative cursor-pointer bg-slate-200"
                            onClick={() => handleImageClick(img.id, actualIndex)}
                          >
                            <img
                              src={img.url}
                              alt=""
                              className={`w-full h-full object-cover transition-opacity ${img.isOptimizing ? 'opacity-70 blur-sm' : 'opacity-100'}`}
                              loading="lazy"
                              onError={(e) => {
                                e.currentTarget.style.display = 'none';
                                e.currentTarget.parentElement?.classList.add('flex', 'items-center', 'justify-center');
                                const icon = document.createElement('div');
                                icon.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-slate-400"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><circle cx="8.5" cy="8.5" r="1.5"></circle><polyline points="21 15 16 10 5 21"></polyline></svg>';
                                e.currentTarget.parentElement?.appendChild(icon);
                              }}
                            />

                            {/* Processing Spinner */}
                            {img.isOptimizing && (
                              <div className="absolute inset-0 flex items-center justify-center">
                                <Loader2 className="animate-spin text-indigo-600" size={12} />
                              </div>
                            )}

                            {/* Hover Actions Overlay */}
                            {!isReorderMode && !isSplitMode && !img.isOptimizing && (
                              <div className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity bg-black/10 flex flex-col justify-between p-1">
                                <div className="flex justify-between">
                                  <button
                                    onClick={(e) => { e.stopPropagation(); toggleSelection(img.id); }}
                                    className={`w-4 h-4 rounded flex items-center justify-center transition-colors ${isSelected ? 'bg-indigo-600 text-white' : 'bg-white/80 text-slate-600 hover:bg-white'}`}
                                  >
                                    {isSelected ? <CheckSquare size={10} /> : <Square size={10} />}
                                  </button>
                                </div>
                                <div className="flex justify-end gap-1">
                                  <button onClick={(e) => { e.stopPropagation(); setEditingImageId(img.id); }} className="p-1 bg-white/90 text-indigo-600 rounded hover:scale-105 shadow-sm"><Wand2 size={10} /></button>
                                  <button onClick={(e) => { e.stopPropagation(); deleteImages(currentSession.id, [img.id]); }} className="p-1 bg-white/90 text-red-600 rounded hover:scale-105 shadow-sm"><Trash2 size={10} /></button>
                                </div>
                              </div>
                            )}

                            {/* Selection Overlay */}
                            {isSelected && !isReorderMode && (
                              <div className="absolute inset-0 ring-inset ring-2 ring-indigo-500 pointer-events-none" />
                            )}

                            {/* Split Mode Interaction Overlay */}
                            {isSplitMode && (
                              <div className="absolute inset-x-0 top-0 h-1/3 hover:bg-amber-500/20 transition-colors flex justify-center items-start pt-2">
                                {actualIndex > 0 && !isStart && (
                                  <div className="opacity-0 hover:opacity-100 bg-amber-500 text-white text-[8px] font-bold px-1.5 py-0.5 rounded-full shadow-sm transform hover:scale-110 transition-transform">SPLIT</div>
                                )}
                              </div>
                            )}

                            {/* Reorder Interaction Overlay */}
                            {isReorderMode && (
                              <div className="absolute inset-0 bg-white/40 flex items-center justify-center gap-1 cursor-grab active:cursor-grabbing" onClick={(e) => e.stopPropagation()}>
                                <div className="bg-white/90 rounded-full px-1.5 py-0.5 text-[8px] font-mono border shadow-sm">
                                  {actualIndex + 1}
                                </div>
                                <div className="flex gap-0.5">
                                  <button disabled={actualIndex === 0} onClick={() => handleMove(actualIndex, 'left')} className="p-1 bg-white rounded-sm shadow-sm hover:text-indigo-600 disabled:opacity-30"><ArrowLeft size={10} /></button>
                                  <button disabled={actualIndex === currentSession.images.length - 1} onClick={() => handleMove(actualIndex, 'right')} className="p-1 bg-white rounded-sm shadow-sm hover:text-indigo-600 disabled:opacity-30"><ArrowRight size={10} /></button>
                                </div>
                              </div>
                            )}
                          </div>

                          {/* No Footer Text - Pure Image Density */}
                        </PreviewCard>
                      );
                    })}
                  </div>
                </div>
              );
            });
          })()
        ) : (
          <div className="h-full flex flex-col items-center justify-center text-slate-400">
            <div className="w-10 h-10 mb-2 bg-slate-100 rounded-full flex items-center justify-center text-slate-300">
              <Images size={18} />
            </div>
            <p className="text-xs font-medium">Session Empty</p>
            <p className="text-[10px] text-slate-400 opacity-70">Capture content to begin</p>
          </div>
        )}
      </div>

      {/* Viewer Modal */}
      {viewingImageId && currentSession && (
        <ImageViewer
          image={currentSession.images.find(i => i.id === viewingImageId)!}
          onClose={() => setViewingImageId(null)}
          onEdit={() => {
            setViewingImageId(null);
            setEditingImageId(viewingImageId);
          }}
        />
      )}

      {/* Editor Modal */}
      {editingImageId && currentSession && (
        <ImageEditor
          image={currentSession.images.find(i => i.id === editingImageId)!}
          onClose={() => setEditingImageId(null)}
          onSave={(newUrl) => {
            if (context?.currentSessionId) context.updateImage(context.currentSessionId, editingImageId, newUrl);
            setEditingImageId(null);
          }}
        />
      )}
    </div>
  );
}
