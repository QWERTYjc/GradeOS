import React, { useState, useRef, useCallback, useContext, useEffect } from 'react';
import { Camera, Upload, X, Loader2, Zap, ZapOff, Sparkles, BookOpen, Smartphone, ScanLine, Info, CheckCircle2, FileUp, PlusCircle, Split, Paperclip } from 'lucide-react';
import { AppContext } from './AppContext';
import { fileToDataURL } from './imageProcessing';
import { optimizeDocument } from './geminiService';
import { COLORS } from './constants';
import * as pdfjsLib from 'pdfjs-dist/legacy/build/pdf';

type ScanMode = 'single' | 'book';

pdfjsLib.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url
).toString();

const renderPdfToImages = async (file: File, maxPages = 80) => {
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
    if (!videoRef.current || !context) return;
    const video = videoRef.current;

    // Create high-res canvas for capture
    const captureCanvas = document.createElement('canvas');
    captureCanvas.width = video.videoWidth;
    captureCanvas.height = video.videoHeight;
    const ctx = captureCanvas.getContext('2d');
    if (!ctx) return;

    ctx.drawImage(video, 0, 0);
    const dataUrl = captureCanvas.toDataURL('image/jpeg', 0.95);

    // Provide haptic/visual feedback
    if (navigator.vibrate) navigator.vibrate(50);

    // Process
    handleImageData(dataUrl, 'camera');

  }, [context, isAutoEnhance, willSplitNext]);

  // Auto-scan logic (Motion detection)
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

    requestRef.current = requestAnimationFrame(checkStability);

  }, [isAutoScan, capturePhoto]);

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
          } catch (err) {
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
    <div className="flex flex-col h-full bg-[#f8fafc] relative">

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
      <div className="flex-1 relative flex items-center justify-center overflow-hidden bg-slate-100">

        {/* Camera View */}
        {isCameraActive ? (
          <div className="relative w-full h-full">
            <video
              ref={videoRef}
              className="w-full h-full object-cover"
              playsInline
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
          /* IDLE STATE UI - Modern Blue/White */
          <div className="text-center p-12 max-w-md animate-in fade-in zoom-in duration-300">
            {isProcessing ? (
              <div className="flex flex-col items-center">
                <Loader2 className="animate-spin text-blue-600 mb-4" size={48} />
                <h3 className="text-xl font-bold text-slate-700">Importing Content...</h3>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-6">
                <div className="w-24 h-24 bg-blue-50 text-blue-600 rounded-3xl flex items-center justify-center shadow-sm">
                  <ScanLine size={48} />
                </div>
                <div>
                  <h2 className="text-2xl font-bold text-slate-800 mb-2">Ready to Capture</h2>
                  <p className="text-slate-500">Scan papers or import existing files</p>
                </div>

                <div className="grid grid-cols-2 gap-4 w-full">
                  <button
                    onClick={startCamera}
                    className="flex flex-col items-center justify-center gap-2 py-6 bg-blue-600 hover:bg-blue-700 text-white rounded-2xl shadow-lg shadow-blue-200 transition-all hover:-translate-y-1"
                  >
                    <Camera size={24} />
                    <span className="font-bold text-sm">Use Camera</span>
                  </button>
                  <button
                    onClick={() => fileInputRef.current?.click()}
                    className="flex flex-col items-center justify-center gap-2 py-6 bg-white hover:bg-slate-50 text-slate-700 border border-slate-200 rounded-2xl shadow-sm transition-all hover:border-blue-200 hover:text-blue-600 hover:-translate-y-1"
                  >
                    <FileUp size={24} />
                    <span className="font-bold text-sm">Import File</span>
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Modern Control Bar */}
      <div className="h-20 bg-white border-t border-slate-200 px-6 flex items-center justify-between shadow-[0_-4px_20px_rgba(0,0,0,0.02)] z-20">

        {/* Left: Mode Toggle */}
        <div className="flex bg-slate-100 rounded-lg p-1">
          <button
            onClick={() => setScanMode('single')}
            className={`px-4 py-2 rounded-md text-xs font-bold transition-all ${scanMode === 'single' ? 'bg-white text-blue-600 shadow-sm' : 'text-slate-500'}`}
          >
            Single
          </button>
          <button
            onClick={() => setScanMode('book')}
            className={`px-4 py-2 rounded-md text-xs font-bold transition-all ${scanMode === 'book' ? 'bg-white text-blue-600 shadow-sm' : 'text-slate-500'}`}
          >
            Book
          </button>
        </div>

        {/* Center: Trigger (Only if camera active) */}
        <div className="absolute left-1/2 -translate-x-1/2 -top-8">
          {isCameraActive && (
            <button
              onClick={capturePhoto}
              className="w-20 h-20 bg-blue-600 rounded-full border-4 border-white shadow-xl flex items-center justify-center text-white hover:scale-105 active:scale-95 transition-all"
            >
              <div className="w-16 h-16 rounded-full border-2 border-white/50"></div>
            </button>
          )}
        </div>

        {/* Right: Tools */}
        <div className="flex items-center gap-3">

          {/* New Student Toggle */}
          <button
            onClick={() => setWillSplitNext(!willSplitNext)}
            title="Next image starts new student (Shortcut: N)"
            className={`flex flex-col items-center justify-center w-12 h-12 rounded-xl transition-all border ${willSplitNext ? 'bg-amber-50 border-amber-200 text-amber-600' : 'bg-white border-slate-200 text-slate-400 hover:text-blue-600 hover:border-blue-200'}`}
          >
            <Split size={20} className={willSplitNext ? "animate-pulse" : ""} />
            <span className="text-[9px] font-bold mt-0.5">{willSplitNext ? 'ON' : 'SPLIT'}</span>
          </button>

          <button
            onClick={() => setIsAutoEnhance(!isAutoEnhance)}
            className={`flex flex-col items-center justify-center w-12 h-12 rounded-xl transition-all border ${isAutoEnhance ? 'bg-indigo-50 border-indigo-200 text-indigo-600' : 'bg-white border-slate-200 text-slate-400 hover:text-blue-600 hover:border-blue-200'}`}
          >
            <Sparkles size={20} />
            <span className="text-[9px] font-bold mt-0.5">AI</span>
          </button>

          {isCameraActive && (
            <button
              onClick={stopCamera}
              className="flex flex-col items-center justify-center w-12 h-12 rounded-xl bg-slate-100 text-slate-500 hover:bg-red-50 hover:text-red-500 transition-colors"
            >
              <X size={20} />
            </button>
          )}
        </div>

      </div>

      {feedbackMessage && (
        <div className="absolute top-6 left-1/2 -translate-x-1/2 bg-black/80 text-white px-6 py-3 rounded-full text-sm font-medium backdrop-blur-md animate-in fade-in slide-in-from-top-4">
          {feedbackMessage}
        </div>
      )}
    </div>
  );
}
