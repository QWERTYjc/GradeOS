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

  /**
   * 算法剪裁与分割
   * 严格遵守抛弃无效部分（4% 边距）并支持书本双页分割
   */
  const processPage = (source: HTMLCanvasElement, sx: number, sy: number, sw: number, sh: number, tag: string) => {
    if (!context?.currentSessionId) return;

    // 核心算法：安全裁剪 (Safety Crop)
    // 丢弃四周 4% 的像素，通常包含指尖、桌子边缘等干扰
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
      optimizeDocument(dataUrl.split(',')[1])
        .then(url => context.updateImage(context.currentSessionId!, newId, url, false))
        .catch(() => context.updateImage(context.currentSessionId!, newId, dataUrl, false));
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

    // Azure 极简闪光反馈
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
      // 书本模式：中缝分割
      const halfW = canvas.width / 2;
      processPage(canvas, 0, 0, halfW, canvas.height, 'left');
      processPage(canvas, halfW, 0, halfW, canvas.height, 'right');
      setFeedbackMessage("双页已分割并保存");
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

      {/* 沉浸式扫描区 */}
      <div className="relative flex-1 bg-[#F5F7FB] flex items-center justify-center overflow-hidden">
        <video ref={videoRef} autoPlay playsInline muted className={`w-full h-full object-contain ${!isCameraActive ? 'hidden' : ''}`} />

        {/* 专业 Azure 辅助线 */}
        {isCameraActive && (
          <div className="absolute inset-0 pointer-events-none z-10">
            {scanMode === 'single' ? (
              <div className="absolute inset-0 flex items-center justify-center p-8">
                <div className="w-full h-full border-2 border-[#2563EB]/30 border-dashed rounded-2xl shadow-[0_0_80px_rgba(37,99,235,0.05)] bg-gradient-to-br from-blue-500/5 to-transparent"></div>
              </div>
            ) : (
              <div className="absolute inset-0 flex p-4 gap-4">
                <div className="flex-1 border-2 border-[#2563EB]/40 border-dashed rounded-xl bg-white/5 relative">
                   <div className="absolute top-4 left-4 text-[10px] font-bold text-blue-600 bg-white/80 px-2 py-1 rounded">LEFT PAGE</div>
                </div>
                {/* 数字化中缝 */}
                <div className="w-1 bg-[#2563EB]/40 h-full relative">
                   <div className="absolute inset-0 blur-sm bg-blue-400/20"></div>
                </div>
                <div className="flex-1 border-2 border-[#2563EB]/40 border-dashed rounded-xl bg-white/5 relative">
                   <div className="absolute top-4 right-4 text-[10px] font-bold text-blue-600 bg-white/80 px-2 py-1 rounded">RIGHT PAGE</div>
                </div>
                
                {/* 移动端横屏提示 */}
                <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 md:hidden">
                    <div className="bg-white/90 backdrop-blur px-4 py-2 rounded-full border border-blue-100 flex items-center gap-2 shadow-xl animate-pulse">
                        <Smartphone className="text-blue-600 rotate-90" size={20} />
                        <span className="text-sm font-bold text-blue-800">请横置手机拍摄</span>
                    </div>
                </div>
              </div>
            )}
          </div>
        )}

        {!isCameraActive && (
          <div className="text-center p-12 max-w-sm">
            <div className="w-20 h-20 bg-blue-50 rounded-3xl flex items-center justify-center mx-auto mb-6 shadow-sm border border-blue-100">
               <ScanLine className="text-blue-600" size={32} />
            </div>
            <h2 className="text-2xl font-bold mb-3 tracking-tight">智能书页扫描</h2>
            <p className="text-slate-500 mb-8 leading-relaxed">基于 Azure 极简引擎，自动识别中缝并进行边缘裁剪。</p>
            <button onClick={startCamera} className="w-full py-4 bg-[#2563EB] hover:bg-blue-700 text-white rounded-2xl font-bold shadow-xl shadow-blue-200 transition-all hover:-translate-y-1">
              开启专业相机
            </button>
          </div>
        )}

        {/* 状态 HUD */}
        {isCameraActive && (
          <div className="absolute top-6 left-6 right-6 flex justify-between items-center z-20 pointer-events-none">
             {isAutoScan && (
                <div className="bg-white/90 backdrop-blur-md px-4 py-2 rounded-2xl border border-blue-100 flex items-center gap-3 shadow-lg">
                   <div className={`w-3 h-3 rounded-full ${stabilityScore >= 100 ? 'bg-green-500 animate-ping' : 'bg-blue-500'}`}></div>
                   <span className="text-[10px] font-black tracking-widest text-slate-700">
                     {stabilityScore >= 100 ? 'CAPTURE' : `STABILIZING ${Math.round(stabilityScore)}%`}
                   </span>
                </div>
             )}
             <div className="flex gap-2">
                <div className="bg-blue-600 text-white px-3 py-1 rounded-full text-[10px] font-bold shadow-lg">CORE ENGINE v1.2</div>
             </div>
          </div>
        )}

        {feedbackMessage && (
          <div className="absolute bottom-12 left-1/2 -translate-x-1/2 z-40 animate-in fade-in slide-in-from-bottom-2">
            <div className="bg-[#0B0F17]/90 text-white px-5 py-2 rounded-full text-xs font-bold shadow-2xl flex items-center gap-2">
               <CheckCircle2 size={14} className="text-blue-400" />
               {feedbackMessage}
            </div>
          </div>
        )}
      </div>

      {/* 控制中心 */}
      <div className="bg-white border-t border-slate-100 px-8 py-6 pb-12 safe-area-bottom">
        <div className="max-w-xl mx-auto flex flex-col gap-6">
          
          <div className="flex justify-center">
            <div className="bg-[#F5F7FB] p-1 rounded-2xl flex gap-1 border border-slate-100">
              <button onClick={() => setScanMode('single')} className={`flex items-center gap-2 px-6 py-2.5 rounded-xl text-xs font-black transition-all ${scanMode === 'single' ? 'bg-white text-blue-600 shadow-sm' : 'text-slate-400 hover:text-slate-600'}`}>
                <ScanLine size={16} /> 单页
              </button>
              <button onClick={() => setScanMode('book')} className={`flex items-center gap-2 px-6 py-2.5 rounded-xl text-xs font-black transition-all ${scanMode === 'book' ? 'bg-white text-blue-600 shadow-sm' : 'text-slate-400 hover:text-slate-600'}`}>
                <BookOpen size={16} /> 书本模式
              </button>
            </div>
          </div>

          <div className="flex items-center justify-between">
            <button onClick={toggleAuto} className={`flex flex-col items-center gap-2 transition-all ${isAutoScan ? 'text-blue-600' : 'text-slate-400'}`}>
               <div className={`w-14 h-14 rounded-3xl flex items-center justify-center border-2 transition-all ${isAutoScan ? 'border-blue-100 bg-blue-50' : 'border-slate-50 bg-slate-50'}`}>
                 {isAutoScan ? <Zap size={24} fill="currentColor" /> : <ZapOff size={24} />}
               </div>
               <span className="text-[10px] font-black">AUTO</span>
            </button>

            <button onClick={captureFrame} disabled={!isCameraActive} className="relative group disabled:opacity-30">
              <div className="w-24 h-24 rounded-full border-4 border-[#F5F7FB] p-1 bg-white flex items-center justify-center">
                 <div className="w-full h-full rounded-full bg-[#2563EB] active:scale-90 transition-transform shadow-[0_8px_30px_rgb(37,99,235,0.4)]"></div>
              </div>
            </button>

            <button onClick={isCameraActive ? stopCamera : () => {}} className="flex flex-col items-center gap-2 text-slate-400">
               <div className="w-14 h-14 rounded-3xl flex items-center justify-center border-2 border-slate-50 bg-slate-50 hover:bg-red-50 hover:text-red-500 transition-all">
                 <X size={24} />
               </div>
               <span className="text-[10px] font-black text-slate-300">CLOSE</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}