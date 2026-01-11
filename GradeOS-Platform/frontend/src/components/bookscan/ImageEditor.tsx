import React, { useState } from 'react';
import { X, Wand2, Loader2, Check, ArrowRight, ScanLine, Crop, Sparkles } from 'lucide-react';
import { ScannedImage } from './types';
import { editImage, optimizeDocument } from './geminiService';

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
    setPrompt("TextIn Engine: Cropping & Enhancing...");

    try {
      // Use TextIn API for the smart optimize call
      const newImageUrl = await optimizeDocument(image.url);
      setResultUrl(newImageUrl);
      setPrompt("");
    } catch (err: any) {
      setError(err.message || "TextIn Optimization Failed.");
      setPrompt("");
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#0B0F17]/95 backdrop-blur-md p-4 animate-in fade-in duration-300">
      <div className="bg-white rounded-[2.5rem] shadow-2xl w-full max-w-6xl h-[92vh] flex flex-col overflow-hidden border border-white/10">

        {/* Header */}
        <div className="flex items-center justify-between px-8 py-6 border-b border-slate-100">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 bg-blue-50 rounded-2xl flex items-center justify-center">
              <Sparkles className="text-blue-600" size={24} />
            </div>
            <div>
              <h2 className="text-xl font-black tracking-tight text-[#0B0F17]">AI Editor</h2>
            </div>
          </div>
          <button onClick={onClose} className="p-3 bg-slate-50 hover:bg-slate-100 rounded-2xl transition-all text-slate-400">
            <X size={24} />
          </button>
        </div>

        {/* Workspace */}
        <div className="flex-1 flex flex-col md:flex-row overflow-hidden bg-[#F5F7FB]">

          {/* Visualization Area */}
          <div className="flex-1 p-8 flex items-center justify-center gap-8 overflow-auto">
            <div className="flex flex-col items-center gap-4 max-w-[45%]">
              <div className="bg-white p-3 rounded-3xl shadow-sm border border-slate-100 overflow-hidden">
                <img src={image.url} alt="Original" className="max-h-[55vh] object-contain rounded-xl" />
              </div>
              <span className="text-[10px] font-black tracking-widest text-slate-400 uppercase">Input Source</span>
            </div>

            {resultUrl && (
              <div className="flex flex-col items-center gap-4 max-w-[45%] animate-in fade-in slide-in-from-right-8 duration-500">
                <div className="bg-white p-3 rounded-3xl shadow-xl border-2 border-blue-100 overflow-hidden ring-4 ring-blue-50">
                  <img src={resultUrl} alt="Edited" className="max-h-[55vh] object-contain rounded-xl" />
                </div>
                <span className="text-[10px] font-black tracking-widest text-blue-600 uppercase">TextIn Optimized</span>
              </div>
            )}
          </div>

          {/* Controls Sidebar */}
          <div className="w-full md:w-96 bg-white border-l border-slate-100 p-8 flex flex-col gap-8 z-10">

            {/* Action Card */}
            <div className="p-6 bg-blue-600 rounded-[2rem] text-white shadow-xl shadow-blue-200">
              <h3 className="text-xs font-black tracking-widest mb-4 flex items-center gap-2">
                <ScanLine size={16} /> INDUSTRIAL PRESETS
              </h3>
              <button
                onClick={handleSmartEnhance}
                disabled={isProcessing}
                className="w-full py-4 bg-white text-blue-600 rounded-2xl font-bold text-sm shadow-lg hover:bg-blue-50 transition-all flex items-center justify-center gap-3 disabled:opacity-50"
              >
                {isProcessing && !prompt.includes("Custom") ? <Loader2 size={18} className="animate-spin" /> : <Crop size={18} />}
                Smart Crop & Enhance
              </button>
              <p className="text-[10px] text-blue-100/70 mt-4 leading-relaxed font-medium">
                Powered by TextIn CamScanner. Automatic edge rectification and ultra-sharp text enhancement.
              </p>
            </div>

            <div className="h-px bg-slate-100"></div>

            <div>
              <label className="block text-xs font-black tracking-widest text-slate-400 mb-3 uppercase">
                Custom Transformation
              </label>
              <textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder="E.g., 'Extract only headers', 'Binarize image', 'Make paper pure white'"
                className="w-full p-5 bg-[#F5F7FB] border-none rounded-2xl focus:ring-2 focus:ring-blue-100 min-h-[140px] resize-none text-sm font-medium"
              />
            </div>

            {error && (
              <div className="p-4 bg-red-50 text-red-600 text-[10px] font-bold rounded-2xl border border-red-100 animate-pulse">
                {error.toUpperCase()}
              </div>
            )}

            <div className="mt-auto flex flex-col gap-4">
              <button
                onClick={handleEdit}
                disabled={isProcessing || !prompt.trim()}
                className="w-full py-4 bg-[#0B0F17] text-white rounded-2xl font-bold text-sm hover:bg-slate-800 disabled:opacity-50 transition-all flex items-center justify-center gap-3"
              >
                {isProcessing && prompt.includes("Custom") ? <Loader2 className="animate-spin" size={18} /> : <Wand2 size={18} />}
                {isProcessing ? 'PROCESSING' : 'RUN CUSTOM AI'}
              </button>

              {resultUrl && (
                <button
                  onClick={() => onSave(resultUrl)}
                  className="w-full py-4 bg-blue-600 text-white rounded-2xl font-bold text-sm hover:bg-blue-700 flex items-center justify-center gap-3 shadow-2xl shadow-blue-200 transition-all"
                >
                  <Check size={18} />
                  COMMIT CHANGES
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}