import React, { useState, useRef, useCallback, useContext, useEffect } from 'react';
import { Camera, Upload, X, Loader2, Zap, ZapOff, Sparkles, BookOpen, Smartphone, ScanLine, Info, CheckCircle2 } from 'lucide-react';
import { AppContext } from '../App';
import { fileToDataURL } from '../services/imageProcessing';
import { optimizeDocument } from '../services/geminiService';
import { COLORS } from '../constants';

type ScanMode = 'single' | 'book';

export default function Scanner() {
  const context = useContext(AppContext);
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null); 
  const [stream, setStream] = useState<MediaStream | null>(null);
  const [isCameraActive, setIsCameraActive] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [feedbackMessage, setFeedbackMessage] = useState<string | null>(null);
  
  const [scanMode, setScanMode] = useState<ScanMode>('single');
  const [isAutoScan, setIsAutoScan] = useState(false);
  const [isAutoEnhance, setIsAutoEnhance] = useState(false);
  const [stabilityScore, setStabilityScore] = useState(0);
  
  const lastFrameData = useRef<Uint8ClampedArray | null>(null);
  const stabilityCounter = useRef(0);
  const hasMovedRef = useRef(true); 
  const isScanningRef = useRef(false); 
  const requestRef = useRef<number>(0);

  const startCamera = async () => {
    try {
      const mediaStream = await navigator.mediaDevices.getUserMedia({ 
        video: { 
          facingMode: 'environment', 
          width: { ideal: 4096 },
          height: { ideal: 2160 } 
        } 
      });
      setStream(mediaStream);
      setIsCameraActive(true);
      if (videoRef.current) {
        videoRef.current.srcObject = mediaStream;
        await videoRef.current.play();
      }
    } catch (err: any) {
      setFeedbackMessage(`Error: ${err.message}`);
      setIsCameraActive(false);
    }
  };

  const stopCamera = () => {
    if (stream) stream.getTracks().forEach(t => t.stop());
    setStream(null);
    setIsCameraActive(false);
    setIsAutoScan(false);
    cancelAnimationFrame(requestRef.current);
  };

  const processPage = async (source: HTMLCanvasElement, sx: number, sy: number, sw: number, sh: number, tag: string) => {
    if (!context?.currentSessionId) return;

    // Safety Crop: Remove 4% margins locally first
    const marginX = sw * 0.04;
    const marginY = sh * 0.04;
    const targetW = sw - (marginX * 2);
    const targetH = sh - (marginY * 2);

    const outCanvas = document.createElement('canvas');
    outCanvas.width = targetW;
    outCanvas.height = targetH;
    const oCtx = outCanvas.getContext('2d');
    if (!oCtx) return;

    oCtx.drawImage(source, sx + marginX, sy + marginY, targetW, targetH, 0, 0, targetW, targetH);

    const dataUrl = outCanvas.toDataURL('image/jpeg', 0.85);
    const newId = crypto.randomUUID();

    context.addImageToSession({
      id: newId,
      url: dataUrl,
      timestamp: Date.now(),
      name: `scan_${tag}_${Date.now()}.jpg`,
      isOptimizing: isAutoEnhance
    });

    if (isAutoEnhance) {
      try {
        const url = await optimizeDocument(dataUrl);
        context.updateImage(context.currentSessionId!, newId, url, false);
      } catch (e) {
        console.error("TextIn Enhancement Failed", e);
        context.updateImage(context.currentSessionId!, newId, dataUrl, false);
      }
    }
  };

  const captureFrame = useCallback(async () => {
    if (!videoRef.current || !context?.currentSessionId) return;
    
    const v = videoRef.current;
    const canvas = document.createElement('canvas');
    canvas.width = v.videoWidth;
    canvas.height = v.videoHeight;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.drawImage(v, 0, 0);

    // Azure 科技感闪光反馈
    const flash = document.createElement('div');
    flash.className = "fixed inset-0 bg-[#2563EB] opacity-30 z-50 pointer-events-none transition-opacity duration-300";
    document.body.appendChild(flash);
    setTimeout(() => {
      flash.classList.add('opacity-0');
      setTimeout(() => document.body.removeChild(flash), 300);
    }, 50);

    if (scanMode === 'single') {
      processPage(canvas, 0, 0, canvas.width, canvas.height, 'single');
    } else {
      const halfW = canvas.width / 2;
      processPage(canvas, 0, 0, halfW, canvas.height, 'left');
      processPage(canvas, halfW, 0, halfW, canvas.height, 'right');
      setFeedbackMessage("Dual Pages Captured (TextIn AI Active)");
      setTimeout(() => setFeedbackMessage(null), 1500);
    }
  }, [context, isAutoEnhance, scanMode]);

  const checkMotion = useCallback(() => {
    if (!videoRef.current || !canvasRef.current || !isScanningRef.current) return;
    const v = videoRef.current;
    const c = canvasRef.current;
    const ctx = c.getContext('2d', { willReadFrequently: true });
    if (!ctx || v.readyState !== 4) {
      requestRef.current = requestAnimationFrame(checkMotion);
      return;
    }
    ctx.drawImage(v, 0, 0, 64, 64);
    const data = ctx.getImageData(0, 0, 64, 64).data;
    if (lastFrameData.current) {
      let diff = 0;
      for (let i = 0; i < data.length; i += 16) diff += Math.abs(data[i] - lastFrameData.current[i]);
      if (diff / 1024 > 2) {
        stabilityCounter.current = 0;
        hasMovedRef.current = true;
        setStabilityScore(0);
      } else {
        stabilityCounter.current += 1;
        setStabilityScore(Math.min((stabilityCounter.current / 18) * 100, 100));
        if (stabilityCounter.current > 18 && hasMovedRef.current) {
          captureFrame();
          hasMovedRef.current = false;
        }
      }
    }
    lastFrameData.current = data;
    requestRef.current = requestAnimationFrame(checkMotion);
  }, [captureFrame]);

  const toggleAuto = () => {
    const next = !isAutoScan;
    setIsAutoScan(next);
    isScanningRef.current = next;
    if (next) requestRef.current = requestAnimationFrame(checkMotion);
    else cancelAnimationFrame(requestRef.current);
  };

  return (
    <div className="flex flex-col h-full bg-white text-[#0B0F17]">
      <canvas ref={canvasRef} className="hidden" width="64" height="64" />

      {/* 沉浸式扫描区 (Azure 风格) */}
      <div className="relative flex-1 bg-[#F5F7FB] flex items-center justify-center overflow-hidden">
        <video ref={videoRef} autoPlay playsInline muted className={`w-full h-full object-contain ${!isCameraActive ? 'hidden' : ''}`} />

        {isCameraActive && (
          <div className="absolute inset-0 pointer-events-none z-10">
            {scanMode === 'single' ? (
              <div className="absolute inset-0 flex items-center justify-center p-8">
                <div className="w-full h-full border-2 border-[#2563EB]/40 border-dashed rounded-2xl shadow-[inset_0_0_80px_rgba(37,99,235,0.05)] bg-gradient-to-br from-blue-500/5 to-transparent"></div>
              </div>
            ) : (
              <div className="absolute inset-0 flex p-4 gap-4">
                <div className="flex-1 border-2 border-[#2563EB]/40 border-dashed rounded-xl bg-white/5 relative">
                   <div className="absolute top-4 left-4 text-[10px] font-black text-blue-600 bg-white/90 px-2 py-1 rounded shadow-sm">PAGE L</div>
                </div>
                <div className="w-0.5 bg-[#2563EB]/30 h-full relative">
                   <div className="absolute inset-0 blur-md bg-blue-400/20"></div>
                </div>
                <div className="flex-1 border-2 border-[#2563EB]/40 border-dashed rounded-xl bg-white/5 relative">
                   <div className="absolute top-4 right-4 text-[10px] font-black text-blue-600 bg-white/90 px-2 py-1 rounded shadow-sm">PAGE R</div>
                </div>
              </div>
            )}
          </div>
        )}

        {!isCameraActive && (
          <div className="text-center p-12 max-w-sm animate-in fade-in zoom-in duration-500">
            <div className="w-24 h-24 bg-blue-50 rounded-3xl flex items-center justify-center mx-auto mb-8 shadow-sm border border-blue-100/50">
               <ScanLine className="text-blue-600" size={40} />
            </div>
            <h2 className="text-3xl font-black mb-4 tracking-tight">Industrial Scan</h2>
            <p className="text-slate-500 mb-10 leading-relaxed font-medium">TextIn AI-powered engine for precision document cropping and text enhancement.</p>
            <button onClick={startCamera} className="w-full py-5 bg-[#2563EB] hover:bg-blue-700 text-white rounded-3xl font-bold shadow-2xl shadow-blue-200 transition-all hover:-translate-y-1 active:scale-95">
              Initialize Engine
            </button>
          </div>
        )}

        {/* HUD Elements */}
        {isCameraActive && (
          <div className="absolute top-6 left-6 right-6 flex justify-between items-center z-20 pointer-events-none">
             <div className="flex gap-2">
                <div className="bg-white/90 backdrop-blur-md px-4 py-2 rounded-2xl border border-blue-100 flex items-center gap-3 shadow-lg">
                   <div className={`w-2.5 h-2.5 rounded-full ${isAutoScan ? 'bg-blue-500 animate-pulse' : 'bg-slate-300'}`}></div>
                   <span className="text-[10px] font-black tracking-widest text-slate-700 uppercase">
                     {isAutoScan ? 'Auto-Engine Active' : 'Manual Mode'}
                   </span>
                </div>
                {isAutoEnhance && (
                   <div className="bg-indigo-600 text-white px-4 py-2 rounded-2xl flex items-center gap-2 shadow-lg text-[10px] font-black tracking-widest animate-in slide-in-from-left-4">
                      <Sparkles size={12} /> TEXTIN AI ON
                   </div>
                )}
             </div>
             <div className="bg-blue-600 text-white px-4 py-2 rounded-2xl text-[10px] font-black tracking-widest shadow-lg">AZURE v1.3</div>
          </div>
        )}

        {feedbackMessage && (
          <div className="absolute bottom-16 left-1/2 -translate-x-1/2 z-40 animate-in fade-in slide-in-from-bottom-4">
            <div className="bg-[#0B0F17] text-white px-6 py-3 rounded-2xl text-xs font-black shadow-2xl flex items-center gap-3">
               <CheckCircle2 size={16} className="text-blue-400" />
               {feedbackMessage.toUpperCase()}
            </div>
          </div>
        )}
      </div>

      {/* Control Dashboard */}
      <div className="bg-white border-t border-slate-100 px-8 py-8 pb-14 safe-area-bottom shadow-[0_-10px_40px_rgba(0,0,0,0.02)]">
        <div className="max-w-xl mx-auto flex flex-col gap-8">
          
          <div className="flex justify-center gap-4">
            <div className="bg-[#F5F7FB] p-1.5 rounded-2xl flex gap-1 border border-slate-100 shadow-inner">
              <button onClick={() => setScanMode('single')} className={`flex items-center gap-2 px-8 py-3 rounded-xl text-xs font-black transition-all ${scanMode === 'single' ? 'bg-white text-blue-600 shadow-md' : 'text-slate-400 hover:text-slate-600'}`}>
                <ScanLine size={16} /> SINGLE
              </button>
              <button onClick={() => setScanMode('book')} className={`flex items-center gap-2 px-8 py-3 rounded-xl text-xs font-black transition-all ${scanMode === 'book' ? 'bg-white text-blue-600 shadow-md' : 'text-slate-400 hover:text-slate-600'}`}>
                <BookOpen size={16} /> BOOK
              </button>
            </div>
            
            <button 
              onClick={() => setIsAutoEnhance(!isAutoEnhance)}
              className={`p-1.5 rounded-2xl flex items-center gap-3 px-6 transition-all border shadow-sm ${isAutoEnhance ? 'bg-blue-50 border-blue-100 text-blue-600' : 'bg-white border-slate-100 text-slate-400'}`}
              title="Toggle TextIn AI Enhancement"
            >
              <Sparkles size={18} className={isAutoEnhance ? 'animate-pulse' : ''} />
              <span className="text-[10px] font-black">AI ENHANCE</span>
            </button>
          </div>

          <div className="flex items-center justify-between">
            <button onClick={toggleAuto} className={`flex flex-col items-center gap-2 transition-all ${isAutoScan ? 'text-blue-600' : 'text-slate-400'}`}>
               <div className={`w-16 h-16 rounded-[2rem] flex items-center justify-center border-2 transition-all ${isAutoScan ? 'border-blue-100 bg-blue-50 shadow-lg shadow-blue-100' : 'border-slate-50 bg-slate-50'}`}>
                 {isAutoScan ? <Zap size={28} fill="currentColor" /> : <ZapOff size={28} />}
               </div>
               <span className="text-[10px] font-black tracking-widest">AUTO</span>
            </button>

            <button onClick={captureFrame} disabled={!isCameraActive} className="relative group disabled:opacity-30">
              <div className="w-28 h-28 rounded-full border-4 border-[#F5F7FB] p-1.5 bg-white flex items-center justify-center shadow-xl">
                 <div className="w-full h-full rounded-full bg-[#2563EB] active:scale-90 transition-transform shadow-[0_12px_40px_rgb(37,99,235,0.4)] flex items-center justify-center">
                    <div className="w-10 h-10 rounded-full border-2 border-white/20"></div>
                 </div>
              </div>
            </button>

            <button onClick={isCameraActive ? stopCamera : () => {}} className="flex flex-col items-center gap-2 text-slate-400 group">
               <div className="w-16 h-16 rounded-[2rem] flex items-center justify-center border-2 border-slate-50 bg-slate-50 group-hover:bg-red-50 group-hover:text-red-500 transition-all">
                 <X size={28} />
               </div>
               <span className="text-[10px] font-black text-slate-300 tracking-widest">EXIT</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}