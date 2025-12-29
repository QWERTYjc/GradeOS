import React, { useState } from 'react';
import { X, Wand2, Loader2, Check, ArrowRight, ScanLine, Crop } from 'lucide-react';
import { ScannedImage } from '../types';
import { editImage, optimizeDocument } from '../services/geminiService';

interface ImageEditorProps {
  image: ScannedImage;
  onClose: () => void;
  onSave: (newUrl: string) => void;
}

export default function ImageEditor({ image, onClose, onSave }: ImageEditorProps) {
  const [prompt, setPrompt] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [resultUrl, setResultUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleEdit = async () => {
    if (!prompt.trim()) return;
    setIsProcessing(true);
    setError(null);

    try {
      const base64Data = image.url.split(',')[1];
      const mimeType = image.url.substring(image.url.indexOf(':') + 1, image.url.indexOf(';'));

      const newImageUrl = await editImage(base64Data, prompt, mimeType);
      setResultUrl(newImageUrl);
    } catch (err: any) {
      setError(err.message || "Failed to edit image.");
    } finally {
      setIsProcessing(false);
    }
  };

  const handleSmartEnhance = async () => {
    setIsProcessing(true);
    setError(null);
    setPrompt("Auto-cropping and optimizing document...");
    
    try {
      const base64Data = image.url.split(',')[1];
      const newImageUrl = await optimizeDocument(base64Data);
      setResultUrl(newImageUrl);
      setPrompt("Document optimized: Cropped to edges, perspective corrected, and text enhanced.");
    } catch (err: any) {
      setError(err.message || "Failed to optimize document.");
      setPrompt("");
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-5xl h-[90vh] flex flex-col overflow-hidden">
        
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-slate-200">
          <h2 className="text-xl font-semibold flex items-center gap-2 text-indigo-700">
            <Wand2 size={24} /> AI Smart Edit
          </h2>
          <button onClick={onClose} className="p-2 hover:bg-slate-100 rounded-full transition-colors">
            <X size={24} className="text-slate-500" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 flex flex-col md:flex-row overflow-hidden bg-slate-50">
          
          {/* Images Area */}
          <div className="flex-1 p-6 flex items-center justify-center gap-6 overflow-auto">
             {/* Original */}
             <div className="flex flex-col items-center gap-2 min-w-[300px] max-w-[45%]">
                <div className="bg-white p-2 rounded shadow-sm border border-slate-200">
                  <img src={image.url} alt="Original" className="max-h-[60vh] object-contain rounded" />
                </div>
                <span className="text-sm font-medium text-slate-500">Original</span>
             </div>

             {/* Arrow */}
             {resultUrl && <ArrowRight className="text-slate-400 shrink-0" size={32} />}

             {/* Result */}
             {resultUrl && (
               <div className="flex flex-col items-center gap-2 min-w-[300px] max-w-[45%] animate-in fade-in zoom-in duration-300">
                  <div className="bg-white p-2 rounded shadow-sm border border-indigo-200 ring-2 ring-indigo-100">
                    <img src={resultUrl} alt="Edited" className="max-h-[60vh] object-contain rounded" />
                  </div>
                  <span className="text-sm font-medium text-indigo-600">AI Result</span>
               </div>
             )}
          </div>

          {/* Controls Sidebar */}
          <div className="w-full md:w-80 bg-white border-l border-slate-200 p-6 flex flex-col gap-6 z-10">
            
            {/* Presets */}
            <div className="p-4 bg-indigo-50 rounded-lg border border-indigo-100">
               <h3 className="text-sm font-bold text-indigo-800 mb-3 flex items-center gap-2">
                 <ScanLine size={16} /> Quick Actions
               </h3>
               <button
                  onClick={handleSmartEnhance}
                  disabled={isProcessing}
                  className="w-full py-2 px-3 bg-white text-indigo-700 border border-indigo-200 rounded-md shadow-sm text-sm font-medium hover:bg-indigo-600 hover:text-white hover:border-transparent transition-all flex items-center justify-center gap-2"
               >
                 {isProcessing && prompt.includes("optimizing") ? <Loader2 size={14} className="animate-spin" /> : <Crop size={14} />}
                 Smart Crop & Enhance
               </button>
               <p className="text-[10px] text-indigo-400 mt-2 leading-tight">
                 Auto-detects page edges, fixes perspective, and sharpens text using AI.
               </p>
            </div>

            <div className="h-px bg-slate-200"></div>

            <div>
              <label className="block text-sm font-semibold text-slate-700 mb-2">
                Custom Edit Prompt
              </label>
              <textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder="E.g., 'Make it look vintage', 'Remove the text', 'High contrast'"
                className="w-full p-3 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent min-h-[100px] resize-none text-sm"
              />
            </div>

            {error && (
              <div className="p-3 bg-red-50 text-red-600 text-sm rounded-lg border border-red-100">
                {error}
              </div>
            )}

            <div className="mt-auto flex flex-col gap-3">
              <button
                onClick={handleEdit}
                disabled={isProcessing || !prompt.trim()}
                className="w-full py-3 px-4 bg-slate-800 text-white rounded-lg font-medium hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 transition-colors"
              >
                {isProcessing && !prompt.includes("optimizing") ? <Loader2 className="animate-spin" size={18} /> : <Wand2 size={18} />}
                {isProcessing ? 'Processing...' : 'Run Custom Edit'}
              </button>
              
              {resultUrl && (
                <button
                  onClick={() => onSave(resultUrl)}
                  className="w-full py-3 px-4 bg-green-600 text-white rounded-lg font-medium hover:bg-green-700 flex items-center justify-center gap-2 transition-colors shadow-lg shadow-green-200"
                >
                  <Check size={18} />
                  Save Changes
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
