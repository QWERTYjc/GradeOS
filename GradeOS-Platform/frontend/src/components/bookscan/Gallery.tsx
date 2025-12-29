import React, { useContext, useState } from 'react';
import { AppContext } from './AppContext';
import { Trash2, CheckSquare, Square, Wand2, Plus, Images, ArrowLeft, ArrowRight, Move, Sparkles, Loader2, Eye, Send } from 'lucide-react';
import ImageEditor from './ImageEditor';
import ImageViewer from './ImageViewer';
import { submitToGradingSystem, SubmissionResponse } from './submissionService';

export default function Gallery() {
  const context = useContext(AppContext);
  const [selectedImages, setSelectedImages] = useState<Set<string>>(new Set());
  const [editingImageId, setEditingImageId] = useState<string | null>(null);
  const [viewingImageId, setViewingImageId] = useState<string | null>(null);
  const [isReorderMode, setIsReorderMode] = useState(false);
  
  // Submission State
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (!context) return null;
  const { sessions, currentSessionId, deleteImages, createNewSession, setCurrentSessionId, reorderImages } = context;

  const currentSession = sessions.find(s => s.id === currentSessionId);

  const toggleSelection = (id: string) => {
    const newSet = new Set(selectedImages);
    if (newSet.has(id)) newSet.delete(id);
    else newSet.add(id);
    setSelectedImages(newSet);
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

  const handleImageClick = (id: string) => {
      if (isReorderMode) return;
      setViewingImageId(id);
  };

  const handleDirectSubmit = async () => {
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
          // Direct upload using defaults
          // You can pass dynamic IDs here if you have them in the AppContext later
          const result: SubmissionResponse = await submitToGradingSystem(imagesToSend);
          
          console.log("API Response:", result);
          alert(`✅ Uploaded Successfully!\n\nSubmission ID: ${result.submission_id}\nStatus: ${result.status}`);
          
          // Optional: Clear selection after success
          setSelectedImages(new Set());
      } catch (e: any) {
          console.error(e);
          alert(`❌ Submission Failed\n\n${e.message}\n\nEnsure backend is running at http://localhost:8000`);
      } finally {
          setIsSubmitting(false);
      }
  };

  return (
    <div className="flex flex-col h-full bg-slate-50 relative">
      {/* Header Toolbar */}
      <div className="p-4 bg-white border-b border-slate-200 flex flex-col gap-4 shadow-sm z-10 sticky top-0">
        
        <div className="flex flex-col md:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-2 w-full md:w-auto">
            <select 
                value={currentSessionId || ''} 
                onChange={(e) => { setCurrentSessionId(e.target.value); setSelectedImages(new Set()); }}
                className="flex-1 md:flex-none p-2 border border-slate-300 rounded-md text-sm font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white"
            >
                {sessions.map(s => (
                <option key={s.id} value={s.id}>{s.name} ({s.images.length})</option>
                ))}
            </select>
            <button 
                onClick={() => createNewSession()}
                className="p-2 text-indigo-600 hover:bg-indigo-50 rounded-md"
                title="New Session"
            >
                <Plus size={24} />
            </button>
            </div>

            <div className="flex items-center gap-2 w-full md:w-auto overflow-x-auto pb-1 md:pb-0 no-scrollbar">
                
                {/* Submit to API Button (Direct) */}
                <button
                    onClick={handleDirectSubmit}
                    disabled={isSubmitting || (currentSession?.images.length === 0)}
                    className="flex items-center gap-2 px-4 py-2 text-sm bg-gradient-to-r from-emerald-500 to-teal-600 text-white rounded-md shadow hover:shadow-lg transition-all whitespace-nowrap disabled:opacity-50 disabled:cursor-not-allowed"
                >
                    {isSubmitting ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
                    {isSubmitting ? 'Uploading...' : 'Submit to Grading'}
                </button>

                <div className="w-px h-6 bg-slate-300 mx-1"></div>

                {/* Reorder Toggle */}
                <button
                    onClick={() => setIsReorderMode(!isReorderMode)}
                    className={`flex items-center gap-2 px-3 py-2 text-sm rounded-md transition-colors whitespace-nowrap ${isReorderMode ? 'bg-indigo-600 text-white' : 'text-slate-600 hover:bg-slate-100'}`}
                >
                    <Move size={16} />
                    {isReorderMode ? 'Done' : 'Reorder'}
                </button>

                <div className="w-px h-6 bg-slate-300 mx-1"></div>

                <button 
                    onClick={selectAll}
                    disabled={isReorderMode}
                    className="flex items-center gap-2 px-3 py-2 text-sm text-slate-600 hover:bg-slate-100 rounded-md transition-colors whitespace-nowrap disabled:opacity-30"
                >
                    {currentSession && selectedImages.size === currentSession.images.length ? <CheckSquare size={16}/> : <Square size={16}/>}
                    All
                </button>

                <button 
                    onClick={handleBulkDelete}
                    disabled={selectedImages.size === 0 || isReorderMode}
                    className="flex items-center gap-2 px-3 py-2 text-sm text-red-600 hover:bg-red-50 rounded-md disabled:opacity-30 transition-colors whitespace-nowrap"
                >
                    <Trash2 size={16} />
                </button>
            </div>
        </div>
      </div>

      {/* Grid */}
      <div className="flex-1 overflow-y-auto p-4 md:p-6 bg-slate-100/50">
        {currentSession && currentSession.images.length > 0 ? (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3 md:gap-4">
            {currentSession.images.map((img, index) => (
              <div 
                key={img.id} 
                className={`group relative bg-white rounded-lg shadow-sm border overflow-hidden transition-all ${selectedImages.has(img.id) ? 'ring-2 ring-indigo-500 border-transparent' : 'border-slate-200'}`}
              >
                <div className="aspect-[3/4] relative bg-slate-100 cursor-pointer" onClick={() => handleImageClick(img.id)}>
                  <img 
                    src={img.url} 
                    alt={img.name} 
                    className={`w-full h-full object-cover transition-opacity duration-300 ${img.isOptimizing ? 'opacity-50' : 'opacity-100'}`}
                    loading="lazy"
                  />
                  
                  {/* Processing Overlay */}
                  {img.isOptimizing && (
                      <div className="absolute inset-0 flex flex-col items-center justify-center bg-indigo-900/10 backdrop-blur-[1px]">
                          <Loader2 className="animate-spin text-indigo-600 mb-2" size={24} />
                          <span className="text-[10px] font-bold text-indigo-700 bg-white/80 px-2 py-1 rounded-full shadow-sm">AI Optimizing...</span>
                      </div>
                  )}

                  {/* Standard Actions Overlay */}
                  {!isReorderMode && !img.isOptimizing && (
                    <div className="absolute inset-0 bg-black/0 md:group-hover:bg-black/40 transition-colors flex flex-col justify-between p-2">
                        <div className="flex justify-between items-start opacity-100 md:opacity-0 md:group-hover:opacity-100 transition-opacity">
                            <button 
                                onClick={(e) => { e.stopPropagation(); toggleSelection(img.id); }}
                                className={`p-1.5 rounded-full ${selectedImages.has(img.id) ? 'bg-indigo-600 text-white' : 'bg-black/30 text-white hover:bg-black/50'}`}
                            >
                                {selectedImages.has(img.id) ? <CheckSquare size={16} /> : <Square size={16} />}
                            </button>
                        </div>

                        <div className="hidden md:flex justify-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                            <button onClick={(e) => { e.stopPropagation(); setEditingImageId(img.id); }} className="bg-white text-indigo-600 p-2 rounded-full shadow-lg hover:scale-110 transition-transform"><Wand2 size={16} /></button>
                            <button onClick={(e) => { e.stopPropagation(); deleteImages(currentSession.id, [img.id]); }} className="bg-white text-red-600 p-2 rounded-full shadow-lg hover:scale-110 transition-transform"><Trash2 size={16} /></button>
                        </div>
                        
                        <div className="md:hidden absolute inset-0 flex items-center justify-center pointer-events-none opacity-0 active:opacity-100">
                             <Eye className="text-white/80 w-12 h-12" />
                        </div>
                    </div>
                  )}

                  {/* Reorder Overlay */}
                  {isReorderMode && (
                      <div className="absolute inset-0 bg-white/60 flex items-center justify-center gap-4 animate-in fade-in duration-200 cursor-default" onClick={(e) => e.stopPropagation()}>
                          <button 
                            disabled={index === 0}
                            onClick={() => handleMove(index, 'left')}
                            className="p-3 bg-white border border-slate-200 rounded-full shadow-lg text-slate-700 disabled:opacity-30 active:scale-90 transition-transform"
                          >
                              <ArrowLeft size={20} />
                          </button>
                          <span className="font-bold text-slate-500">{index + 1}</span>
                          <button 
                            disabled={index === currentSession.images.length - 1}
                            onClick={() => handleMove(index, 'right')}
                            className="p-3 bg-white border border-slate-200 rounded-full shadow-lg text-slate-700 disabled:opacity-30 active:scale-90 transition-transform"
                          >
                              <ArrowRight size={20} />
                          </button>
                      </div>
                  )}

                </div>
                
                <div className="p-2 text-xs text-slate-600 truncate bg-white flex items-center justify-between border-t border-slate-100">
                  <span className="truncate flex-1">{img.name}</span>
                  {img.isOptimizing && <Sparkles size={12} className="text-indigo-500 animate-pulse ml-1" />}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="h-full flex flex-col items-center justify-center text-slate-400">
            <div className="w-16 h-16 mb-4 bg-slate-200 rounded-full flex items-center justify-center">
              <Images size={32} />
            </div>
            <p>No images in this session.</p>
            <p className="text-sm mt-2">Go to Scanner to capture content.</p>
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