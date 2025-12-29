import React, { useState, useRef, useCallback, useEffect } from 'react';
import { CameraOutlined, ScanOutlined, BookOutlined, CloseOutlined, ThunderboltOutlined, ThunderboltFilled } from '@ant-design/icons';
import { Button, Segmented, message } from 'antd';
import { ScannedImage, ScanMode } from './types';
import { fileToDataURL } from './imageProcessing';

interface ScannerProps {
  onCapture: (images: ScannedImage[]) => void;
  isAutoEnhance?: boolean;
}

export const Scanner: React.FC<ScannerProps> = ({ onCapture, isAutoEnhance = false }) => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [stream, setStream] = useState<MediaStream | null>(null);
  const [isCameraActive, setIsCameraActive] = useState(false);
  const [scanMode, setScanMode] = useState<ScanMode>('single');
  const [isAutoScan, setIsAutoScan] = useState(false);
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
          width: { ideal: 2048 },
          height: { ideal: 1536 }
        }
      });
      setStream(mediaStream);
      setIsCameraActive(true);
      if (videoRef.current) {
        videoRef.current.srcObject = mediaStream;
        await videoRef.current.play();
      }
    } catch (err: any) {
      message.error(`相机启动失败: ${err.message}`);
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

  // 裁剪处理
  const processPage = (
    source: HTMLCanvasElement,
    sx: number, sy: number, sw: number, sh: number,
    tag: string
  ): ScannedImage => {
    const marginX = sw * 0.04;
    const marginY = sh * 0.04;
    const targetW = sw - marginX * 2;
    const targetH = sh - marginY * 2;

    const outCanvas = document.createElement('canvas');
    outCanvas.width = targetW;
    outCanvas.height = targetH;
    const oCtx = outCanvas.getContext('2d');
    if (!oCtx) throw new Error('Canvas error');

    oCtx.drawImage(source, sx + marginX, sy + marginY, targetW, targetH, 0, 0, targetW, targetH);

    return {
      id: crypto.randomUUID(),
      url: outCanvas.toDataURL('image/jpeg', 0.85),
      timestamp: Date.now(),
      name: `scan_${tag}_${Date.now()}.jpg`,
      isOptimizing: isAutoEnhance
    };
  };

  const captureFrame = useCallback(() => {
    if (!videoRef.current) return;

    const v = videoRef.current;
    const canvas = document.createElement('canvas');
    canvas.width = v.videoWidth;
    canvas.height = v.videoHeight;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.drawImage(v, 0, 0);

    // 闪光效果
    const flash = document.createElement('div');
    flash.style.cssText = 'position:fixed;inset:0;background:#2563EB;opacity:0.3;z-index:9999;pointer-events:none;transition:opacity 0.3s';
    document.body.appendChild(flash);
    setTimeout(() => {
      flash.style.opacity = '0';
      setTimeout(() => document.body.removeChild(flash), 300);
    }, 50);

    const newImages: ScannedImage[] = [];

    if (scanMode === 'single') {
      newImages.push(processPage(canvas, 0, 0, canvas.width, canvas.height, 'single'));
    } else {
      const halfW = canvas.width / 2;
      newImages.push(processPage(canvas, 0, 0, halfW, canvas.height, 'left'));
      newImages.push(processPage(canvas, halfW, 0, halfW, canvas.height, 'right'));
      message.success('双页已分割');
    }

    onCapture(newImages);
  }, [scanMode, isAutoEnhance, onCapture]);

  // 自动稳定检测
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

  // 文件上传
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files) return;

    const newImages: ScannedImage[] = [];
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      if (!file.type.startsWith('image/')) continue;
      const url = await fileToDataURL(file);
      newImages.push({
        id: crypto.randomUUID(),
        url,
        timestamp: Date.now(),
        name: file.name
      });
    }
    if (newImages.length > 0) {
      onCapture(newImages);
      message.success(`已添加 ${newImages.length} 张图片`);
    }
    e.target.value = '';
  };

  useEffect(() => {
    return () => {
      if (stream) stream.getTracks().forEach(t => t.stop());
      cancelAnimationFrame(requestRef.current);
    };
  }, [stream]);

  return (
    <div className="flex flex-col h-full bg-gray-50">
      <canvas ref={canvasRef} className="hidden" width="64" height="64" />

      {/* 扫描区域 */}
      <div className="relative flex-1 flex items-center justify-center overflow-hidden bg-gray-100">
        <video
          ref={videoRef}
          autoPlay
          playsInline
          muted
          className={`w-full h-full object-contain ${!isCameraActive ? 'hidden' : ''}`}
        />

        {/* 辅助线 */}
        {isCameraActive && (
          <div className="absolute inset-0 pointer-events-none z-10">
            {scanMode === 'single' ? (
              <div className="absolute inset-4 border-2 border-dashed border-blue-400/50 rounded-lg" />
            ) : (
              <div className="absolute inset-4 flex gap-2">
                <div className="flex-1 border-2 border-dashed border-blue-400/50 rounded-lg relative">
                  <span className="absolute top-2 left-2 text-xs bg-white/80 px-2 py-1 rounded text-blue-600 font-bold">左页</span>
                </div>
                <div className="w-1 bg-blue-400/40" />
                <div className="flex-1 border-2 border-dashed border-blue-400/50 rounded-lg relative">
                  <span className="absolute top-2 right-2 text-xs bg-white/80 px-2 py-1 rounded text-blue-600 font-bold">右页</span>
                </div>
              </div>
            )}
          </div>
        )}

        {/* 稳定度指示 */}
        {isCameraActive && isAutoScan && (
          <div className="absolute top-4 left-4 bg-white/90 px-3 py-2 rounded-full shadow flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${stabilityScore >= 100 ? 'bg-green-500 animate-ping' : 'bg-blue-500'}`} />
            <span className="text-xs font-bold text-gray-700">
              {stabilityScore >= 100 ? '拍摄中' : `稳定中 ${Math.round(stabilityScore)}%`}
            </span>
          </div>
        )}

        {/* 未开启相机时的提示 */}
        {!isCameraActive && (
          <div className="text-center p-8">
            <div className="w-20 h-20 bg-blue-50 rounded-2xl flex items-center justify-center mx-auto mb-4">
              <ScanOutlined className="text-3xl text-blue-500" />
            </div>
            <h3 className="text-lg font-bold mb-2">智能作业扫描</h3>
            <p className="text-gray-500 mb-6">拍照或上传作业图片</p>
            <div className="flex gap-3 justify-center">
              <Button type="primary" size="large" icon={<CameraOutlined />} onClick={startCamera}>
                开启相机
              </Button>
              <label>
                <Button size="large">上传图片</Button>
                <input type="file" accept="image/*" multiple className="hidden" onChange={handleFileUpload} />
              </label>
            </div>
          </div>
        )}
      </div>

      {/* 控制栏 */}
      {isCameraActive && (
        <div className="bg-white border-t p-4">
          <div className="max-w-md mx-auto space-y-4">
            {/* 模式切换 */}
            <div className="flex justify-center">
              <Segmented
                value={scanMode}
                onChange={(v) => setScanMode(v as ScanMode)}
                options={[
                  { label: <span><ScanOutlined /> 单页</span>, value: 'single' },
                  { label: <span><BookOutlined /> 书本</span>, value: 'book' }
                ]}
              />
            </div>

            {/* 操作按钮 */}
            <div className="flex items-center justify-between">
              <Button
                type={isAutoScan ? 'primary' : 'default'}
                icon={isAutoScan ? <ThunderboltFilled /> : <ThunderboltOutlined />}
                onClick={toggleAuto}
              >
                自动
              </Button>

              <Button
                type="primary"
                shape="circle"
                size="large"
                className="w-16 h-16 shadow-lg"
                onClick={captureFrame}
              />

              <Button icon={<CloseOutlined />} onClick={stopCamera}>
                关闭
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
