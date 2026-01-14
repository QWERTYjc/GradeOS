import React, { useContext, useState, useEffect, useMemo } from 'react';
import { AppContext } from './AppContext';
import { Trash2, CheckSquare, Square, Wand2, Plus, Images, ArrowLeft, ArrowRight, Move, Sparkles, Loader2, Eye, Send, Split, Users } from 'lucide-react';
import ImageEditor from './ImageEditor';
import ImageViewer from './ImageViewer';
import { submitToGradingSystem, SubmissionResponse } from './submissionService';
import { ScannedImage } from './types';

interface StudentNameMapping {
  studentId: string;
  studentName: string;
  startIndex: number;
  endIndex: number;
}

interface GalleryProps {
  session?: any; // Optional direct session injection
  onSubmitBatch?: (images: ScannedImage[]) => Promise<void>;
  submitLabel?: string;
  onBoundariesChange?: (boundaries: number[]) => void;
  isRubricMode?: boolean;
  studentNameMapping?: StudentNameMapping[]; // 班级批改模式下的学生名称映射
  interactionEnabled?: boolean;
  onInteractionToggle?: (enabled: boolean) => void;
}

export default function Gallery({
  session,
  onSubmitBatch,
  submitLabel,
  onBoundariesChange,
  isRubricMode = false,
  studentNameMapping = [],
  interactionEnabled = false,
  onInteractionToggle
}: GalleryProps) {
  const context = useContext(AppContext);
  const [selectedImages, setSelectedImages] = useState<Set<string>>(new Set());
  const [editingImageId, setEditingImageId] = useState<string | null>(null);
  const [viewingImageId, setViewingImageId] = useState<string | null>(null);
  const [isReorderMode, setIsReorderMode] = useState(false);
  const [isSplitMode, setIsSplitMode] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (!context) return null;
  const {
    sessions, currentSessionId, deleteImages, createNewSession,
    setCurrentSessionId, reorderImages, splitImageIds, markImageAsSplit
  } = context;

  // Use injected session or fallback to context
  const currentSession = session || sessions.find(s => s.id === currentSessionId);

  // Notify parent of boundary changes whenever splitImageIds or image order changes
  useEffect(() => {
    if (!currentSession || isRubricMode) return;

    // Always include index 0 implicitly
    const indices = [0];

    currentSession.images.forEach((img, index) => {
      if (index > 0 && splitImageIds.has(img.id)) {
        indices.push(index);
      }
    });

    onBoundariesChange?.(indices);
  }, [splitImageIds, currentSession?.images, onBoundariesChange, isRubricMode]);

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
    if (!currentSession) return;
    if (selectedImages.size === currentSession.images.length) {
      setSelectedImages(new Set());
    } else {
      setSelectedImages(new Set(currentSession.images.map(img => img.id)));
    }
  };

  const handleBulkDelete = () => {
    if (!currentSessionId) return;
    if (confirm(`Delete ${selectedImages.size} images?`)) {
      deleteImages(currentSessionId, Array.from(selectedImages));
      setSelectedImages(new Set());
    }
  };

  const handleMove = (index: number, direction: 'left' | 'right') => {
    if (!currentSessionId || !currentSession) return;
    const newIndex = direction === 'left' ? index - 1 : index + 1;
    if (newIndex >= 0 && newIndex < currentSession.images.length) {
      reorderImages(currentSessionId, index, newIndex);
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

    const imagesToSend = selectedImages.size > 0
      ? currentSession.images.filter(img => selectedImages.has(img.id))
      : currentSession.images;

    if (imagesToSend.length === 0) {
      alert("No images to submit. Please scan or select images first.");
      return;
    }

    setIsSubmitting(true);
    try {
      if (onSubmitBatch) {
        console.log('Gallery: Using provided onSubmitBatch');
        await onSubmitBatch(imagesToSend);
      } else {
        console.warn('Gallery: Falling back to submitToGradingSystem (Legacy)');
        alert("Warning: Using legacy submission path! Check console logs.");
        const result: SubmissionResponse = await submitToGradingSystem(imagesToSend);

        console.log("API Response:", result);
        alert(`Uploaded Successfully!\n\nSubmission ID: ${result.submission_id}\nStatus: ${result.status}`);
      }

      setSelectedImages(new Set());
    } catch (e: any) {
      console.error(e);
      alert(`Submission Failed\n\n${e.message}\n\nEnsure backend is running at http://localhost:8001`);
    } finally {
      setIsSubmitting(false);
    }
  };

  // Helper to calculate student number for a given image index
  const getStudentNumber = (targetIndex: number) => {
    if (!currentSession) return 1;
    let count = 1;
    for (let i = 1; i <= targetIndex; i++) {
      if (splitImageIds.has(currentSession.images[i].id)) {
        count++;
      }
    }
    return count;
  };

  return (
    <div className="flex flex-col h-full bg-slate-50 relative text-[#0B0F17]">
      {/* Header Toolbar - Reduced Density */}
      <div className="px-3 py-2 bg-white border-b border-slate-200 flex flex-col gap-2 shadow-sm z-10 sticky top-0">

        <div className="flex flex-col md:flex-row items-center justify-between gap-3">
          {/* Left: Spacer or Title if needed in future (Empty for clean look as requested) */}
          <div className="hidden md:block"></div>

          <div className="flex items-center gap-1.5 w-full md:w-auto overflow-x-auto pb-1 md:pb-0 no-scrollbar">

            {/* Submit Button */}
            <button
              onClick={handleDirectSubmit}
              disabled={isRubricMode || isSubmitting || (currentSession?.images.length === 0)}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-gradient-to-r from-emerald-500 to-teal-600 text-white rounded-md shadow hover:shadow-lg transition-all whitespace-nowrap disabled:opacity-50 disabled:cursor-not-allowed font-medium"
            >
              {isSubmitting ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
              {isRubricMode ? 'Rubric Ready' : (isSubmitting ? 'Uploading...' : (submitLabel || 'Submit'))}
            </button>

            <div className="w-px h-5 bg-slate-300 mx-1"></div>

            {!isRubricMode && onInteractionToggle && (
              <label className="flex items-center gap-2 rounded-md border border-slate-200 bg-white px-2.5 py-1.5 text-xs text-slate-600 shadow-sm">
                <input
                  type="checkbox"
                  checked={interactionEnabled}
                  onChange={(event) => onInteractionToggle(event.target.checked)}
                  className="h-3.5 w-3.5 rounded border-slate-300 text-slate-900 focus:ring-slate-500"
                />
                启用人工交互（批改前）
              </label>
            )}

            {/* Split Mode (Boundary) - Integrated */}
            {!isRubricMode && (
              <button
                onClick={() => {
                  setIsSplitMode(!isSplitMode);
                  if (isReorderMode) setIsReorderMode(false);
                }}
                className={`flex items-center gap-1.5 px-2.5 py-1.5 text-xs rounded-md transition-colors whitespace-nowrap font-medium ${isSplitMode ? 'bg-blue-900 text-blue-50 ring-1 ring-blue-700' : 'text-slate-600 hover:bg-slate-100'}`}
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
              className={`flex items-center gap-1.5 px-2.5 py-1.5 text-xs rounded-md transition-colors whitespace-nowrap font-medium ${isReorderMode ? 'bg-indigo-100 text-indigo-700 ring-1 ring-indigo-200' : 'text-slate-600 hover:bg-slate-100'}`}
            >
              <Move size={14} />
              {isReorderMode ? 'Done' : 'Order'}
            </button>

            <div className="w-px h-5 bg-slate-300 mx-1"></div>

            <button
              onClick={selectAll}
              disabled={isReorderMode || isSplitMode}
              className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs text-slate-600 hover:bg-slate-100 rounded-md transition-colors whitespace-nowrap disabled:opacity-30 font-medium"
            >
              {currentSession && selectedImages.size === currentSession.images.length && currentSession.images.length > 0 ? <CheckSquare size={14} /> : <Square size={14} />}
              All
            </button>

            <button
              onClick={handleBulkDelete}
              disabled={selectedImages.size === 0 || isReorderMode || isSplitMode}
              className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs text-red-600 hover:bg-red-50 rounded-md disabled:opacity-30 transition-colors whitespace-nowrap font-medium"
            >
              <Trash2 size={14} />
            </button>
          </div>
        </div>
      </div>

      {/* Grid */}
      <div className="flex-1 overflow-y-auto p-4 bg-slate-50 space-y-8">
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
                    <div className="absolute left-0 top-3 bottom-3 w-1 bg-blue-900/30 rounded-full"></div>
                  )}

                  {/* Student Header (New Line) */}
                  {!isRubricMode && (
                    <div className="flex items-center gap-2 mb-3">
                      <div className="bg-blue-900 text-blue-50 text-[10px] font-bold px-2 py-0.5 rounded border border-blue-800 uppercase tracking-wider shadow-sm">
                        {studentNameMapping[groupIdx]?.studentName || `Student ${groupIdx + 1}`}
                      </div>
                      <div className="h-px bg-slate-200 flex-1 border-t border-dashed border-slate-300"></div>
                    </div>
                  )}

                  <div className="grid grid-cols-6 sm:grid-cols-8 md:grid-cols-10 lg:grid-cols-12 gap-1 auto-rows-max">
                    {group.map((img, groupImgIndex) => {
                      const actualIndex = startImageIndex + groupImgIndex;
                      const isStart = groupImgIndex === 0;
                      const isSelected = selectedImages.has(img.id);

                      return (
                        <div
                          key={img.id}
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
                        </div>
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
            if (currentSessionId) context.updateImage(currentSessionId, editingImageId, newUrl);
            setEditingImageId(null);
          }}
        />
      )}
    </div>
  );
}
