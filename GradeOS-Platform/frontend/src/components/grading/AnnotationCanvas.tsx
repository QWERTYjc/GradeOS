'use client';

/**
 * 批注画布组件
 * 
 * 在图片上渲染 AI 批改的批注（前端渲染方案）
 */

import React, { useRef, useEffect, useState, useCallback } from 'react';
import type {
  VisualAnnotation,
  PageAnnotations,
  BoundingBox,
  AnnotationType,
} from '@/types/annotation';
import { toPixelCoords, getAnnotationColor } from '@/types/annotation';

interface AnnotationCanvasProps {
  /** 图片 URL 或 Base64 */
  imageSrc: string;
  /** 批注数据 */
  annotations: VisualAnnotation[];
  /** 画布宽度（可选，默认自适应） */
  width?: number;
  /** 画布高度（可选，默认自适应） */
  height?: number;
  /** 是否显示批注文字 */
  showText?: boolean;
  /** 点击批注回调 */
  onAnnotationClick?: (annotation: VisualAnnotation) => void;
  /** 自定义样式 */
  className?: string;
}

export default function AnnotationCanvas({
  imageSrc,
  annotations,
  width,
  height,
  showText = true,
  onAnnotationClick,
  className = '',
}: AnnotationCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [imageLoaded, setImageLoaded] = useState(false);
  const [imageSize, setImageSize] = useState({ width: 0, height: 0 });
  const imageRef = useRef<HTMLImageElement | null>(null);

  // 加载图片
  useEffect(() => {
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.onload = () => {
      imageRef.current = img;
      setImageSize({ width: img.width, height: img.height });
      setImageLoaded(true);
    };
    img.onerror = () => {
      console.error('图片加载失败');
    };
    
    // 处理 Base64 或 URL
    if (imageSrc.startsWith('data:') || imageSrc.startsWith('http')) {
      img.src = imageSrc;
    } else {
      img.src = `data:image/png;base64,${imageSrc}`;
    }

    return () => {
      img.onload = null;
      img.onerror = null;
    };
  }, [imageSrc]);

  // 绘制批注
  const drawAnnotations = useCallback(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext('2d');
    const img = imageRef.current;

    if (!canvas || !ctx || !img || !imageLoaded) return;

    // 计算画布尺寸
    const canvasWidth = width || imageSize.width;
    const canvasHeight = height || imageSize.height;
    const scale = Math.min(canvasWidth / imageSize.width, canvasHeight / imageSize.height);
    
    canvas.width = imageSize.width * scale;
    canvas.height = imageSize.height * scale;

    // 绘制图片
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);

    // 绘制批注
    annotations.forEach((ann) => {
      const { x, y, width: w, height: h } = toPixelCoords(
        ann.bounding_box,
        canvas.width,
        canvas.height
      );
      const color = ann.color || getAnnotationColor(ann.annotation_type);

      ctx.strokeStyle = color;
      ctx.fillStyle = color;
      ctx.lineWidth = 2;
      ctx.font = '14px sans-serif';

      switch (ann.annotation_type) {
        case 'score':
          drawScore(ctx, x, y, w, h, ann.text || '', color);
          break;
        case 'error_circle':
          drawEllipse(ctx, x, y, w, h, color);
          break;
        case 'error_underline':
          drawUnderline(ctx, x, y + h, w, color);
          break;
        case 'correct_check':
          drawCheckMark(ctx, x, y, w, h, color);
          break;
        case 'partial_check':
          drawTriangle(ctx, x, y, w, h, color);
          break;
        case 'wrong_cross':
          drawCross(ctx, x, y, w, h, color);
          break;
        case 'comment':
          if (showText && ann.text) {
            drawComment(ctx, x, y, ann.text, color);
          }
          break;
        case 'highlight':
          drawHighlight(ctx, x, y, w, h, color);
          break;
      }
    });
  }, [annotations, imageLoaded, imageSize, width, height, showText]);

  useEffect(() => {
    drawAnnotations();
  }, [drawAnnotations]);

  // 处理点击事件
  const handleClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!onAnnotationClick || !canvasRef.current) return;

    const rect = canvasRef.current.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width;
    const y = (e.clientY - rect.top) / rect.height;

    // 查找点击的批注
    const clicked = annotations.find((ann) => {
      const bbox = ann.bounding_box;
      return x >= bbox.x_min && x <= bbox.x_max && y >= bbox.y_min && y <= bbox.y_max;
    });

    if (clicked) {
      onAnnotationClick(clicked);
    }
  };

  return (
    <canvas
      ref={canvasRef}
      className={`annotation-canvas ${className}`}
      onClick={handleClick}
      style={{ cursor: onAnnotationClick ? 'pointer' : 'default' }}
    />
  );
}

// ==================== 渲染配置（与后端保持一致） ====================

const RENDER_CONFIG = {
  // 字体大小
  fontSizeScore: 24,
  fontSizeComment: 16,
  // 线条宽度
  lineWidthCircle: 3,
  lineWidthUnderline: 2,
  lineWidthCheck: 3,
  // 透明度
  highlightAlpha: 0.3,
  bgAlpha: 0.9,
  // 内边距
  commentPadding: 4,
};

// ==================== 绘制辅助函数 ====================

function drawScore(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  text: string,
  color: string
) {
  const padding = RENDER_CONFIG.commentPadding;
  ctx.font = `bold ${RENDER_CONFIG.fontSizeScore}px "Microsoft YaHei", "PingFang SC", sans-serif`;
  
  const metrics = ctx.measureText(text);
  const textWidth = metrics.width;
  const textHeight = RENDER_CONFIG.fontSizeScore;
  
  // 计算居中位置
  const textX = x + (w - textWidth) / 2;
  const textY = y + (h - textHeight) / 2;
  
  // 背景
  ctx.fillStyle = `rgba(255, 255, 255, ${RENDER_CONFIG.bgAlpha})`;
  ctx.fillRect(textX - padding, textY - padding, textWidth + padding * 2, textHeight + padding * 2);
  
  // 文字
  ctx.fillStyle = color;
  ctx.fillText(text, textX, textY + textHeight - 4);
}

function drawEllipse(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  color: string
) {
  ctx.beginPath();
  ctx.ellipse(x + w / 2, y + h / 2, w / 2, h / 2, 0, 0, Math.PI * 2);
  ctx.strokeStyle = color;
  ctx.lineWidth = RENDER_CONFIG.lineWidthCircle;
  ctx.stroke();
}

function drawUnderline(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  color: string
) {
  ctx.beginPath();
  ctx.moveTo(x, y);
  ctx.lineTo(x + w, y);
  ctx.strokeStyle = color;
  ctx.lineWidth = RENDER_CONFIG.lineWidthUnderline;
  ctx.stroke();
}

function drawCheckMark(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  color: string
) {
  const cx = x + w / 2;
  const cy = y + h / 2;
  const size = Math.min(w, h) / 2;

  ctx.beginPath();
  ctx.moveTo(cx - size, cy);
  ctx.lineTo(cx - size / 3, cy + size / 2);
  ctx.lineTo(cx + size, cy - size / 2);
  ctx.strokeStyle = color;
  ctx.lineWidth = RENDER_CONFIG.lineWidthCheck;
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  ctx.stroke();
}

function drawTriangle(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  color: string
) {
  const cx = x + w / 2;

  ctx.beginPath();
  ctx.moveTo(cx, y);
  ctx.lineTo(x, y + h);
  ctx.lineTo(x + w, y + h);
  ctx.closePath();
  ctx.strokeStyle = color;
  ctx.lineWidth = RENDER_CONFIG.lineWidthCheck;
  ctx.stroke();
}

function drawCross(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  color: string
) {
  const padding = 2;
  ctx.beginPath();
  ctx.moveTo(x + padding, y + padding);
  ctx.lineTo(x + w - padding, y + h - padding);
  ctx.moveTo(x + w - padding, y + padding);
  ctx.lineTo(x + padding, y + h - padding);
  ctx.strokeStyle = color;
  ctx.lineWidth = RENDER_CONFIG.lineWidthCheck;
  ctx.lineCap = 'round';
  ctx.stroke();
}

function drawComment(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  text: string,
  color: string
) {
  const padding = RENDER_CONFIG.commentPadding;
  ctx.font = `${RENDER_CONFIG.fontSizeComment}px "Microsoft YaHei", "PingFang SC", sans-serif`;
  const metrics = ctx.measureText(text);
  const textWidth = metrics.width;
  const textHeight = RENDER_CONFIG.fontSizeComment;

  // 背景
  ctx.fillStyle = `rgba(255, 255, 255, 0.95)`;
  ctx.fillRect(x, y, textWidth + padding * 2, textHeight + padding * 2);
  
  // 边框
  ctx.strokeStyle = color;
  ctx.lineWidth = 1;
  ctx.strokeRect(x, y, textWidth + padding * 2, textHeight + padding * 2);
  
  // 文字
  ctx.fillStyle = color;
  ctx.fillText(text, x + padding, y + padding + textHeight - 2);
}

function drawHighlight(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  color: string
) {
  // 解析颜色并添加透明度
  ctx.fillStyle = color;
  ctx.globalAlpha = RENDER_CONFIG.highlightAlpha;
  ctx.fillRect(x, y, w, h);
  ctx.globalAlpha = 1.0;
}
