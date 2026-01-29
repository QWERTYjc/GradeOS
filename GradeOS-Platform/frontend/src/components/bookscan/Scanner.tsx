import React, { useState, useRef, useCallback, useContext, useEffect } from 'react';
import { Camera, Upload, X, Loader2, Zap, ZapOff, Sparkles, BookOpen, Smartphone, ScanLine, Info, CheckCircle2, FileUp, PlusCircle, Split, Paperclip } from 'lucide-react';
import { AppContext } from './AppContext';
import { fileToDataURL } from './imageProcessing';
import { optimizeDocument } from './llmService';

type ScanMode = 'single' | 'book';

// Lazy load pdfjs-dist only on client side to avoid SSR DOMMatrix error
let pdfjsLib: typeof import('pdfjs-dist') | null = null;
let pdfjsInitialized = false;

const initPdfJs = async () => {
  if (pdfjsInitialized) return pdfjsLib;
  if (typeof window === 'undefined') return null;
  
  pdfjsLib = await import('pdfjs-dist');
  // Use unpkg CDN with .mjs extension for ES module worker
  // pdfjs-dist 4.x requires .mjs worker
  const version = pdfjsLib.version;
  pdfjsLib.GlobalWorkerOptions.workerSrc = `https://unpkg.com/pdfjs-dist@${version}/build/pdf.worker.min.mjs`;
  pdfjsInitialized = true;
  return pdfjsLib;
};

const renderPdfToImages = async (file: File, maxPages = 80) => {
  const pdfjs = await initPdfJs();
  if (!pdfjs) throw new Error('PDF.js not available');
  
  const buffer = await file.arrayBuffer();
  const pdf = await pdfjs.getDocument({ data: new Uint8Array(buffer) }).promise;
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
    await page.render({ canvasContext: context, viewport } as any).promise;
    images.push(canvas.toDataURL('image/jpeg', 0.9));
  }

  return images;
};

export default function Scanner() {
  const context = useContext(AppContext);
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [stream, setStream] = useState<MediaStream | null>(null);
  const [isCameraActive, setIsCameraActive] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [feedbackMessage, setFeedbackMessage] = useState<string | null>(null);

  const [scanMode, setScanMode] = useState<ScanMode>('single');
  const [isAutoScan, setIsAutoScan] = useState(false);
  const [isAutoEnhance, setIsAutoEnhance] = useState(false);
  // Flag: next captured image starts a new student
  const [willSplitNext, setWillSplitNext] = useState(false);
  const [stabilityScore, setStabilityScore] = useState(0);

  const lastFrameData = useRef<Uint8ClampedArray | null>(null);
  const stabilityCounter = useRef(0);
  const hasMovedRef = useRef(true);
  const isScanningRef = useRef(false);
  const requestRef = useRef<number>(0);

  // Shortcut Listener
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key.toLowerCase() === 'n') {
        setWillSplitNext(prev => !prev);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const startCamera = async () => {
    try {
      const mediaStream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: 'environment',
          width: { ideal: 1920 },
          height: { ideal: 1080 }
        }
      });
      setStream(mediaStream);
      setIsCameraActive(true);
    } catch (err: any) {
      setFeedbackMessage(`Camera error: ${err.message}`);
      setIsCameraActive(false);
    }
  };

  // Effect to bind stream to video element when it becomes available
  useEffect(() => {
    if (isCameraActive && stream && videoRef.current) {
      const video = videoRef.current;
      video.srcObject = stream;
      video.onloadedmetadata = () => {
        video.play().catch(e => console.error("Play error:", e));
      };
    }
  }, [isCameraActive, stream]);

  const stopCamera = () => {
    if (stream) stream.getTracks().forEach(t => t.stop());
    setStream(null);
    setIsCameraActive(false);
    setIsAutoScan(false);
    cancelAnimationFrame(requestRef.current);
  };

  /**
   * Core logic to handle a single image data URL (from camera or upload)
   */
  const handleImageData = async (dataUrl: string, tag: string) => {
    if (!context?.currentSessionId) return;

    const newId = crypto.randomUUID();
    context.addImageToSession({
      id: newId,
      url: dataUrl,
      timestamp: Date.now(),
      name: `asset_${tag}_${Date.now()}.jpg`,
      isOptimizing: isAutoEnhance
    });

    // Handle Split Logic
    if (willSplitNext) {
      context.markImageAsSplit(newId);
      setWillSplitNext(false); // Reset after splitting
      setFeedbackMessage("Marked as New Student Start");
      setTimeout(() => setFeedbackMessage(null), 2000);
    }

    if (isAutoEnhance) {
      // Async optimization
      optimizeDocument(dataUrl).then(enhancedUrl => {
        context.updateImage(context.currentSessionId!, newId, enhancedUrl, false);
      }).catch(err => {
        console.warn("Optimization failed", err);
        context.updateImage(context.currentSessionId!, newId, dataUrl, false);
      });
    }
  };

  const capturePhoto = useCallback(() => {
    if (!videoRef.current || !context) {
      setFeedbackMessage('Capture failed: no video ref');
      return;
    }
    const video = videoRef.current;

    // Create high-res canvas for capture
    const captureCanvas = document.createElement('canvas');
    if (video.videoWidth === 0 || video.videoHeight === 0) {
      setFeedbackMessage('Capture failed: video not ready');
      setTimeout(() => setFeedbackMessage(null), 2000);
      return;
    }
    captureCanvas.width = video.videoWidth;
    captureCanvas.height = video.videoHeight;
    const ctx = captureCanvas.getContext('2d');
    if (!ctx) return;

    ctx.drawImage(video, 0, 0);
    const dataUrl = captureCanvas.toDataURL('image/jpeg', 0.95);

    // Provide haptic/visual feedback
    if (navigator.vibrate) navigator.vibrate(50);
    setFeedbackMessage('Photo captured!');
    setTimeout(() => setFeedbackMessage(null), 1500);

    // Process
    handleImageData(dataUrl, 'camera');

  }, [context, isAutoEnhance, willSplitNext]);

  // Auto-scan logic (Motion detection)
  const checkStabilityRef = useRef<() => void>();
  
  const checkStability = useCallback(() => {
    if (!videoRef.current || !canvasRef.current || !isAutoScan) return;

    const video = videoRef.current;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d', { willReadFrequently: true });
    if (!ctx) return;

    if (canvas.width !== 320) {
      canvas.width = 320;
      canvas.height = 180;
    }

    ctx.drawImage(video, 0, 0, 320, 180);
    const frame = ctx.getImageData(0, 0, 320, 180);
    const data = frame.data;

    let diff = 0;
    if (lastFrameData.current) {
      // Simple pixel diff
      for (let i = 0; i < data.length; i += 32) { // sparse sampling
        diff += Math.abs(data[i] - lastFrameData.current[i]);
      }
    }
    lastFrameData.current = data;

    // Thresholds
    const MOVEMENT_THRESHOLD = 50000;

    if (diff > MOVEMENT_THRESHOLD) {
      stabilityCounter.current = 0;
      hasMovedRef.current = true;
      setStabilityScore(0);
    } else {
      stabilityCounter.current++;
      setStabilityScore(Math.min(100, stabilityCounter.current * 5));
    }

    // Trigger capture if stable for ~20 frames (~300ms)
    if (stabilityCounter.current > 20 && hasMovedRef.current && !isScanningRef.current) {
      isScanningRef.current = true;
      hasMovedRef.current = false; // Prevent double capture until move
      capturePhoto();

      // Reset after cooldown
      setTimeout(() => {
        isScanningRef.current = false;
      }, 1500);
    }

    if (checkStabilityRef.current) {
      requestRef.current = requestAnimationFrame(checkStabilityRef.current);
    }

  }, [isAutoScan, capturePhoto]);
  
  checkStabilityRef.current = checkStability;

  useEffect(() => {
    if (isAutoScan) {
      requestRef.current = requestAnimationFrame(checkStability);
    } else {
      cancelAnimationFrame(requestRef.current);
      setStabilityScore(0);
    }
    return () => cancelAnimationFrame(requestRef.current);
  }, [isAutoScan, checkStability]);

  // File Upload Handling
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setIsProcessing(true);
      const files = Array.from(e.target.files);

      for (const file of files) {
        if (file.type === 'application/pdf') {
          try {
            const images = await renderPdfToImages(file);
            for (const img of images) {
              await handleImageData(img, 'pdf');
            }
          } catch {
            alert("Failed to parse PDF");
          }
        } else {
          const dataUrl = await fileToDataURL(file);
          handleImageData(dataUrl, 'upload');
        }
      }
      setIsProcessing(false);
      // Reset input
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };


  return (
    <div className="flex flex-col h-full relative overflow-hidden bg-white">

      {/* Hidden Inputs */}
      <input
        type="file"
        multiple
        accept="image/*,application/pdf"
        className="hidden"
        ref={fileInputRef}
        onChange={handleFileUpload}
      />
      <canvas ref={canvasRef} className="hidden" />

      {/* Main Viewport */}
      <div className="flex-1 min-h-0 relative flex items-center justify-center overflow-hidden bg-white">

        {/* Camera View */}
        {isCameraActive ? (
          <div className="relative w-full h-full bg-black">
            <video
              ref={videoRef}
              className="w-full h-full object-cover"
              playsInline
              autoPlay
              muted // Essential for auto-play
            />

            {/* Guides */}
            <div className="absolute inset-0 pointer-events-none">
              <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-[80%] h-[70%] border-2 border-white/30 rounded-lg">
                <div className="absolute top-0 left-0 w-8 h-8 border-t-4 border-l-4 border-white"></div>
                <div className="absolute top-0 right-0 w-8 h-8 border-t-4 border-r-4 border-white"></div>
                <div className="absolute bottom-0 left-0 w-8 h-8 border-b-4 border-l-4 border-white"></div>
                <div className="absolute bottom-0 right-0 w-8 h-8 border-b-4 border-r-4 border-white"></div>
              </div>

              {/* Split Indicator Overlay */}
              {willSplitNext && (
                <div className="absolute left-1/2 top-10 -translate-x-1/2 bg-amber-500 text-white px-4 py-2 rounded-full shadow-lg font-bold flex items-center gap-2 animate-bounce">
                  <Split size={20} />
                  Next Image Starts New Student
                </div>
              )}
            </div>

          </div>
        ) : (

          <div className="w-full max-w-5xl px-6 sm:px-10 h-full flex flex-col justify-center">
            {
              isProcessing ? (
                <div className="flex flex-col items-center gap-3" >
                  <Loader2 className="animate-spin text-slate-900" size={40} />
                  <h3 className="text-lg font-semibold text-slate-800">Importing content...</h3>
                </div>
              ) : (
                <div className="flex flex-col gap-10">
                  <div className="space-y-4 text-center">
                    <div className="text-xs uppercase tracking-[0.4em] text-blue-600 font-bold">Upload Interface</div>
                    <h2 className="text-4xl sm:text-5xl font-bold text-slate-900 tracking-tight">Capture or import exams.</h2>
                    <p className="text-lg text-slate-500 max-w-2xl mx-auto">
                      Seamlessly scan physical papers or drop in existing PDF files.
                      <br className="hidden sm:block" />
                      Our AI will handle the rest.
                    </p>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6 w-full max-w-4xl mx-auto">
                    {/* Camera Option */}
                    <div
                      onClick={startCamera}
                      className="group relative overflow-hidden rounded-3xl bg-white border border-slate-200 p-8 cursor-pointer transition-all duration-300 hover:shadow-xl hover:border-slate-300 hover:-translate-y-1"
                    >
                      <div className="absolute top-0 right-0 p-4 opacity-50 text-slate-200 group-hover:text-blue-100 transition-colors">
                        <Camera size={120} strokeWidth={1} />
                      </div>
                      <div className="relative z-10 flex flex-col gap-4">
                        <div className="w-14 h-14 rounded-2xl bg-slate-900 text-white flex items-center justify-center shadow-lg group-hover:scale-110 transition-transform duration-300">
                          <Camera size={28} />
                        </div>
                        <div>
                          <h3 className="text-xl font-bold text-slate-900">Use Camera</h3>
                          <p className="text-slate-500 mt-1">Scan directly using your device camera.</p>
                        </div>
                        <div className="mt-4 flex items-center gap-2 text-sm font-semibold text-blue-600 opacity-0 group-hover:opacity-100 transition-opacity translate-y-2 group-hover:translate-y-0 duration-300">
                          Start Scanning <ScanLine size={14} />
                        </div>
                      </div>
                    </div>

                    {/* Import Option */}
                    <div
                      onClick={() => fileInputRef.current?.click()}
                      className="group relative overflow-hidden rounded-3xl bg-white border border-slate-200 p-8 cursor-pointer transition-all duration-300 hover:shadow-xl hover:border-slate-300 hover:-translate-y-1"
                    >
                      <div className="absolute top-0 right-0 p-4 opacity-50 text-slate-200 group-hover:text-amber-100 transition-colors">
                        <FileUp size={120} strokeWidth={1} />
                      </div>
                      <div className="relative z-10 flex flex-col gap-4">
                        <div className="w-14 h-14 rounded-2xl bg-white border-2 border-slate-100 text-slate-900 flex items-center justify-center shadow-sm group-hover:scale-110 transition-transform duration-300">
                          <FileUp size={28} />
                        </div>
                        <div>
                          <h3 className="text-xl font-bold text-slate-900">Import File</h3>
                          <p className="text-slate-500 mt-1">Upload PDF, JPG, or PNG files.</p>
                        </div>
                        <div className="mt-4 flex items-center gap-2 text-sm font-semibold text-amber-600 opacity-0 group-hover:opacity-100 transition-opacity translate-y-2 group-hover:translate-y-0 duration-300">
                          Choose File <Paperclip size={14} />
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="text-center">
                    <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-slate-50 border border-slate-100 text-xs font-semibold text-slate-400">
                      <Info size={14} />
                      <span>Supports PDF (up to 80 pages), JPG, PNG</span>
                    </div>
                  </div>
                </div>
              )}
          </div>
        )
        }
      </div >

      {/* Minimal Control Bar */}
      < div className="h-14 sm:h-16 bg-white px-4 sm:px-6 flex items-center justify-between border-t border-slate-100 z-20" >
        <div className="flex items-center gap-4">
          <button
            onClick={() => setScanMode('single')}
            className={`text-[11px] font-semibold uppercase tracking-[0.2em] pb-1 border-b-2 transition-colors ${scanMode === 'single' ? 'border-slate-900 text-slate-900' : 'border-transparent text-slate-400 hover:text-slate-700'}`}
          >
            Single
          </button>
          <button
            onClick={() => setScanMode('book')}
            className={`text-[11px] font-semibold uppercase tracking-[0.2em] pb-1 border-b-2 transition-colors ${scanMode === 'book' ? 'border-slate-900 text-slate-900' : 'border-transparent text-slate-400 hover:text-slate-700'}`}
          >
            Book
          </button>
        </div>

        <div className="absolute left-1/2 -translate-x-1/2 -top-6 sm:-top-7">
          {isCameraActive && (
            <button
              onClick={capturePhoto}
              className="w-14 h-14 sm:w-16 sm:h-16 rounded-full bg-slate-900 text-white flex items-center justify-center ring-2 ring-white/80 hover:scale-105 active:scale-95 transition-transform"
            >
              <div className="w-8 h-8 sm:w-9 sm:h-9 rounded-full border border-white/40"></div>
            </button>
          )}
        </div>

        <div className="flex items-center gap-4">
          <button
            onClick={() => setWillSplitNext(!willSplitNext)}
            title="Next image starts new student (Shortcut: N)"
            className={`flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.2em] pb-1 border-b-2 transition-colors ${willSplitNext ? 'border-amber-500 text-amber-600' : 'border-transparent text-slate-400 hover:text-slate-600'}`}
          >
            <Split size={16} />
            Split
          </button>
          <button
            onClick={() => setIsAutoEnhance(!isAutoEnhance)}
            className={`flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.2em] pb-1 border-b-2 transition-colors ${isAutoEnhance ? 'border-emerald-500 text-emerald-600' : 'border-transparent text-slate-400 hover:text-slate-600'}`}
          >
            <Sparkles size={16} />
            AI
          </button>

          {isCameraActive && (
            <button
              onClick={stopCamera}
              className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.2em] pb-1 border-b-2 border-transparent text-red-500 hover:text-red-600 transition-colors"
            >
              <X size={16} />
              Stop
            </button>
          )}
        </div>
      </div >

      {feedbackMessage && (
        <div className="absolute top-6 left-1/2 -translate-x-1/2 bg-slate-900/90 text-white px-6 py-3 rounded-full text-sm font-medium backdrop-blur-md animate-in fade-in slide-in-from-top-4">
          {feedbackMessage}
        </div>
      )}
    </div >
  );
}
