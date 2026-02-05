'use client';

/**
 * 批注编辑器组件
 * 
 * 支持：
 * - 显示现有批注
 * - 拖拽移动批注
 * - 点击删除批注
 * - 手动添加新批注
 */

import React, { useRef, useEffect, useState, useCallback } from 'react';
import { Trash2, Plus, Move, Type, Circle, Check, X } from 'lucide-react';
import clsx from 'clsx';
import type { VisualAnnotation } from '@/types/annotation';
import { toPixelCoords, getAnnotationColor } from '@/types/annotation';

interface Annotation {
  id: string;
  annotation_type: string;
  bounding_box: {
    x_min: number;
    y_min: number;
    x_max: number;
    y_max: number;
  };
  text: string;
  color: string;
  question_id: string;
  scoring_point_id: string;
}

interface AnnotationEditorProps {
  imageSrc: string;
  annotations: Annotation[];
  onAnnotationsChange: (annotations: Annotation[]) => void;
  onAnnotationDelete?: (annotationId: string) => void;
  onAnnotationAdd?: (annotation: Omit<Annotation, 'id'>) => void;
  onAnnotationUpdate?: (annotationId: string, updates: Partial<Annotation>) => void;
  className?: string;
  readOnly?: boolean;
}

type EditMode = 'select' | 'add_score' | 'add_mark' | 'add_comment' | 'add_error';
type ResizeHandle = 'nw' | 'ne' | 'sw' | 'se';

const ANNOTATION_TOOLS = [
  { mode: 'select' as EditMode, icon: Move, label: '选择/移动', color: 'slate' },
  { mode: 'add_score' as EditMode, icon: Type, label: '添加分数', color: 'orange' },
  { mode: 'add_mark' as EditMode, icon: Check, label: '添加标记', color: 'green' },
  { mode: 'add_error' as EditMode, icon: Circle, label: '圈选错误', color: 'red' },
  { mode: 'add_comment' as EditMode, icon: Type, label: '添加批注', color: 'blue' },
];

export default function AnnotationEditor({
  imageSrc,
  annotations,
  onAnnotationsChange,
  onAnnotationDelete,
  onAnnotationAdd,
  onAnnotationUpdate,
  className = '',
  readOnly = false,
}: AnnotationEditorProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [imageLoaded, setImageLoaded] = useState(false);
  const [imageSize, setImageSize] = useState({ width: 0, height: 0 });
  const imageRef = useRef<HTMLImageElement | null>(null);
  
  const [editMode, setEditMode] = useState<EditMode>('select');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [newAnnotationText, setNewAnnotationText] = useState('');
  const [showTextInput, setShowTextInput] = useState(false);
  const [pendingPosition, setPendingPosition] = useState<{ x: number; y: number } | null>(null);
  const [isDrawingCircle, setIsDrawingCircle] = useState(false);
  const [circleStart, setCircleStart] = useState<{ x: number; y: number } | null>(null);
  const [draftCircle, setDraftCircle] = useState<{ bounding_box: Annotation['bounding_box']; color: string } | null>(null);
  const [isResizing, setIsResizing] = useState(false);
  const [resizeHandle, setResizeHandle] = useState<ResizeHandle | null>(null);

  const MIN_BOX_SIZE = 0.02;
  const HANDLE_SIZE = 6;

  const clamp01 = (value: number) => Math.max(0, Math.min(1, value));

  const normalizeBox = (bbox: Annotation['bounding_box']) => {
    let xMin = clamp01(Math.min(bbox.x_min, bbox.x_max));
    let xMax = clamp01(Math.max(bbox.x_min, bbox.x_max));
    let yMin = clamp01(Math.min(bbox.y_min, bbox.y_max));
    let yMax = clamp01(Math.max(bbox.y_min, bbox.y_max));

    const size = Math.max(xMax - xMin, yMax - yMin, MIN_BOX_SIZE);
    const cx = (xMin + xMax) / 2;
    const cy = (yMin + yMax) / 2;
    xMin = cx - size / 2;
    xMax = cx + size / 2;
    yMin = cy - size / 2;
    yMax = cy + size / 2;

    if (xMin < 0) {
      xMax -= xMin;
      xMin = 0;
    }
    if (xMax > 1) {
      xMin -= xMax - 1;
      xMax = 1;
    }
    if (yMin < 0) {
      yMax -= yMin;
      yMin = 0;
    }
    if (yMax > 1) {
      yMin -= yMax - 1;
      yMax = 1;
    }

    xMin = clamp01(xMin);
    xMax = clamp01(xMax);
    yMin = clamp01(yMin);
    yMax = clamp01(yMax);

    return { x_min: xMin, y_min: yMin, x_max: xMax, y_max: yMax };
  };

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

  useEffect(() => {
    if (editMode === 'add_error') {
      setShowTextInput(false);
      setPendingPosition(null);
      setNewAnnotationText('');
    }
  }, [editMode]);

  // 绘制画布
  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext('2d');
    const img = imageRef.current;

    if (!canvas || !ctx || !img || !imageLoaded) return;

    // 设置画布尺寸
    const container = containerRef.current;
    const maxWidth = container?.clientWidth || 800;
    const scale = Math.min(maxWidth / imageSize.width, 1);
    
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
      const color = ann.color || getAnnotationColor(ann.annotation_type as any);
      const isSelected = selectedId === ann.id;

      ctx.strokeStyle = color;
      ctx.fillStyle = color;
      ctx.lineWidth = isSelected ? 3 : 2;

      // 绘制选中边框
      if (isSelected) {
        ctx.strokeStyle = '#3B82F6';
        ctx.setLineDash([5, 5]);
        ctx.strokeRect(x - 2, y - 2, w + 4, h + 4);
        ctx.setLineDash([]);
        ctx.strokeStyle = color;
      }

      // 根据类型绘制
      switch (ann.annotation_type) {
        case 'score':
          drawScore(ctx, x, y, w, h, ann.text, color);
          break;
        case 'error_circle':
          drawEllipse(ctx, x, y, w, h, color);
          break;
        case 'm_mark':
        case 'a_mark':
          drawMark(ctx, x, y, w, h, ann.text, color);
          break;
        case 'correct_check':
        case 'step_check':
          drawCheckMark(ctx, x, y, w, h, color);
          break;
        case 'wrong_cross':
        case 'step_cross':
          drawCross(ctx, x, y, w, h, color);
          break;
        case 'comment':
          drawComment(ctx, x, y, ann.text, color);
          break;
        default:
          ctx.strokeRect(x, y, w, h);
          if (ann.text) {
            ctx.fillText(ann.text, x, y + h + 14);
          }
      }
    });

    if (draftCircle) {
      const { x, y, width: w, height: h } = toPixelCoords(
        draftCircle.bounding_box,
        canvas.width,
        canvas.height
      );
      ctx.save();
      ctx.setLineDash([4, 4]);
      drawEllipse(ctx, x, y, w, h, draftCircle.color);
      ctx.restore();
    }

    if (selectedId) {
      const selected = annotations.find((ann) => ann.id === selectedId);
      if (selected?.annotation_type === 'error_circle') {
        const { x, y, width: w, height: h } = toPixelCoords(
          selected.bounding_box,
          canvas.width,
          canvas.height
        );
        drawResizeHandles(ctx, x, y, w, h, HANDLE_SIZE);
      }
    }
  }, [annotations, imageLoaded, imageSize, selectedId, draftCircle, HANDLE_SIZE]);

  useEffect(() => {
    draw();
  }, [draw]);

  // 获取鼠标在画布上的归一化坐标
  const getCanvasPosition = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return { x: 0, y: 0 };
    
    const rect = canvas.getBoundingClientRect();
    return {
      x: (e.clientX - rect.left) / rect.width,
      y: (e.clientY - rect.top) / rect.height,
    };
  };

  // 查找点击的批注
  const findAnnotationAt = (x: number, y: number): Annotation | null => {
    for (const ann of annotations) {
      const bbox = ann.bounding_box;
      if (x >= bbox.x_min && x <= bbox.x_max && y >= bbox.y_min && y <= bbox.y_max) {
        return ann;
      }
    }
    return null;
  };

  const getResizeHandleAt = (pos: { x: number; y: number }, ann: Annotation): ResizeHandle | null => {
    const canvas = canvasRef.current;
    if (!canvas) return null;
    const { x, y, width: w, height: h } = toPixelCoords(ann.bounding_box, canvas.width, canvas.height);
    const px = pos.x * canvas.width;
    const py = pos.y * canvas.height;
    const half = HANDLE_SIZE / 2;
    const handles = [
      { name: 'nw' as ResizeHandle, x, y },
      { name: 'ne' as ResizeHandle, x: x + w, y },
      { name: 'sw' as ResizeHandle, x, y: y + h },
      { name: 'se' as ResizeHandle, x: x + w, y: y + h },
    ];
    for (const handle of handles) {
      if (Math.abs(px - handle.x) <= half && Math.abs(py - handle.y) <= half) {
        return handle.name;
      }
    }
    return null;
  };

  // 处理点击
  const handleCanvasClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (readOnly) return;
    
    const pos = getCanvasPosition(e);
    
    if (editMode === 'select') {
      const clicked = findAnnotationAt(pos.x, pos.y);
      setSelectedId(clicked?.id || null);
    } else if (editMode === 'add_error') {
      return;
    } else if (editMode.startsWith('add_')) {
      setPendingPosition(pos);
      setShowTextInput(true);
    }
  };

  // 处理拖拽
  const handleMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (readOnly) return;

    const pos = getCanvasPosition(e);

    if (editMode === 'add_error') {
      setIsDrawingCircle(true);
      setCircleStart(pos);
      setDraftCircle({
        bounding_box: { x_min: pos.x, y_min: pos.y, x_max: pos.x, y_max: pos.y },
        color: '#FF0000',
      });
      return;
    }

    if (editMode !== 'select') return;
    if (!selectedId) return;
    const ann = findAnnotationAt(pos.x, pos.y);

    if (ann && ann.id === selectedId) {
      if (ann.annotation_type === 'error_circle') {
        const handle = getResizeHandleAt(pos, ann);
        if (handle) {
          setIsResizing(true);
          setResizeHandle(handle);
          return;
        }
      }
      setIsDragging(true);
      setDragStart(pos);
    }
  };

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const pos = getCanvasPosition(e);

    if (isDrawingCircle && circleStart) {
      setDraftCircle({
        bounding_box: normalizeBox({
          x_min: circleStart.x,
          y_min: circleStart.y,
          x_max: pos.x,
          y_max: pos.y,
        }),
        color: '#FF0000',
      });
      return;
    }

    if (isResizing && selectedId && resizeHandle) {
      const updatedAnnotations = annotations.map((ann) => {
        if (ann.id === selectedId) {
          const next = { ...ann.bounding_box };
          if (resizeHandle === 'nw') {
            next.x_min = pos.x;
            next.y_min = pos.y;
          } else if (resizeHandle === 'ne') {
            next.x_max = pos.x;
            next.y_min = pos.y;
          } else if (resizeHandle === 'sw') {
            next.x_min = pos.x;
            next.y_max = pos.y;
          } else if (resizeHandle === 'se') {
            next.x_max = pos.x;
            next.y_max = pos.y;
          }
          return { ...ann, bounding_box: normalizeBox(next) };
        }
        return ann;
      });
      onAnnotationsChange(updatedAnnotations);
      return;
    }

    if (!isDragging || !selectedId) return;

    const dx = pos.x - dragStart.x;
    const dy = pos.y - dragStart.y;

    const updatedAnnotations = annotations.map((ann) => {
      if (ann.id === selectedId) {
        const newBbox = {
          x_min: Math.max(0, Math.min(1, ann.bounding_box.x_min + dx)),
          y_min: Math.max(0, Math.min(1, ann.bounding_box.y_min + dy)),
          x_max: Math.max(0, Math.min(1, ann.bounding_box.x_max + dx)),
          y_max: Math.max(0, Math.min(1, ann.bounding_box.y_max + dy)),
        };
        return { ...ann, bounding_box: newBbox };
      }
      return ann;
    });

    setDragStart(pos);
    onAnnotationsChange(updatedAnnotations);
  };

  const handleMouseUp = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (isDrawingCircle && circleStart) {
      setIsDrawingCircle(false);
      setDraftCircle(null);
      const endPos = getCanvasPosition(e);
      const finalBox = normalizeBox({
        x_min: circleStart.x,
        y_min: circleStart.y,
        x_max: endPos.x,
        y_max: endPos.y,
      });
      setCircleStart(null);
      if (onAnnotationAdd) {
        onAnnotationAdd({
          annotation_type: 'error_circle',
          bounding_box: finalBox,
          text: '',
          color: '#FF0000',
          question_id: '',
          scoring_point_id: '',
        });
      }
      setEditMode('select');
      return;
    }

    if (isResizing && selectedId) {
      setIsResizing(false);
      setResizeHandle(null);
      const ann = annotations.find((a) => a.id === selectedId);
      if (ann && onAnnotationUpdate) {
        onAnnotationUpdate(selectedId, { bounding_box: ann.bounding_box });
      }
      return;
    }

    if (isDragging && selectedId) {
      setIsDragging(false);
      const ann = annotations.find((a) => a.id === selectedId);
      if (ann && onAnnotationUpdate) {
        onAnnotationUpdate(selectedId, { bounding_box: ann.bounding_box });
      }
    }
  };

  // 添加新批注
  const handleAddAnnotation = () => {
    if (!pendingPosition || !onAnnotationAdd) return;
    
    let annotationType = 'comment';
    let color = '#0066FF';
    let text = newAnnotationText;
    
    switch (editMode) {
      case 'add_score':
        annotationType = 'score';
        color = '#FF8800';
        break;
      case 'add_mark':
        annotationType = text.startsWith('A') ? 'a_mark' : 'm_mark';
        color = text.endsWith('1') || text.endsWith('2') ? '#00AA00' : '#FF0000';
        break;
      case 'add_error':
        annotationType = 'error_circle';
        color = '#FF0000';
        break;
      case 'add_comment':
        annotationType = 'comment';
        color = '#0066FF';
        break;
    }
    
    const size = editMode === 'add_error' ? 0.08 : 0.05;
    
    onAnnotationAdd({
      annotation_type: annotationType,
      bounding_box: {
        x_min: pendingPosition.x - size / 2,
        y_min: pendingPosition.y - size / 2,
        x_max: pendingPosition.x + size / 2,
        y_max: pendingPosition.y + size / 2,
      },
      text,
      color,
      question_id: '',
      scoring_point_id: '',
    });
    
    setShowTextInput(false);
    setNewAnnotationText('');
    setPendingPosition(null);
    setEditMode('select');
  };

  // 删除选中批注
  const handleDeleteSelected = () => {
    if (selectedId && onAnnotationDelete) {
      onAnnotationDelete(selectedId);
      setSelectedId(null);
    }
  };

  return (
    <div className={clsx('annotation-editor', className)}>
      {/* 工具栏 */}
      {!readOnly && (
        <div className="flex items-center gap-2 mb-3 p-2 bg-slate-100 rounded-lg">
          {ANNOTATION_TOOLS.map((tool) => (
            <button
              key={tool.mode}
              onClick={() => setEditMode(tool.mode)}
              className={clsx(
                'flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium transition-colors',
                editMode === tool.mode
                  ? `bg-${tool.color}-500 text-white`
                  : `text-${tool.color}-600 hover:bg-${tool.color}-100`
              )}
              style={{
                backgroundColor: editMode === tool.mode ? getToolColor(tool.color) : undefined,
                color: editMode === tool.mode ? 'white' : getToolColor(tool.color),
              }}
            >
              <tool.icon className="w-3.5 h-3.5" />
              {tool.label}
            </button>
          ))}
          
          {selectedId && (
            <button
              onClick={handleDeleteSelected}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium text-red-600 hover:bg-red-100 ml-auto"
            >
              <Trash2 className="w-3.5 h-3.5" />
              删除选中
            </button>
          )}
        </div>
      )}

      {/* 画布容器 */}
      <div ref={containerRef} className="relative">
        <canvas
          ref={canvasRef}
          className="border border-slate-200 rounded cursor-crosshair"
          onClick={handleCanvasClick}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
          style={{ cursor: editMode === 'select' ? (isDragging ? 'grabbing' : 'grab') : 'crosshair' }}
        />

        {/* 文字输入弹窗 */}
        {showTextInput && pendingPosition && (
          <div
            className="absolute bg-white rounded-lg shadow-lg border border-slate-200 p-3 z-10"
            style={{
              left: `${pendingPosition.x * 100}%`,
              top: `${pendingPosition.y * 100}%`,
              transform: 'translate(-50%, -50%)',
            }}
          >
            <input
              type="text"
              value={newAnnotationText}
              onChange={(e) => setNewAnnotationText(e.target.value)}
              placeholder={editMode === 'add_score' ? '如: 3/5' : editMode === 'add_mark' ? '如: M1, A0' : '批注内容'}
              className="w-40 px-2 py-1 border border-slate-300 rounded text-sm mb-2"
              autoFocus
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleAddAnnotation();
                if (e.key === 'Escape') {
                  setShowTextInput(false);
                  setPendingPosition(null);
                }
              }}
            />
            <div className="flex gap-2">
              <button
                onClick={handleAddAnnotation}
                className="px-2 py-1 bg-blue-500 text-white rounded text-xs hover:bg-blue-600"
              >
                确定
              </button>
              <button
                onClick={() => {
                  setShowTextInput(false);
                  setPendingPosition(null);
                }}
                className="px-2 py-1 bg-slate-200 text-slate-600 rounded text-xs hover:bg-slate-300"
              >
                取消
              </button>
            </div>
          </div>
        )}
      </div>

      {/* 批注列表 */}
      {annotations.length > 0 && (
        <div className="mt-3 text-xs text-slate-500">
          共 {annotations.length} 个批注
          {selectedId && ' · 已选中 1 个'}
        </div>
      )}
    </div>
  );
}

// 工具颜色映射
function getToolColor(colorName: string): string {
  const colors: Record<string, string> = {
    slate: '#64748b',
    orange: '#f97316',
    green: '#22c55e',
    red: '#ef4444',
    blue: '#3b82f6',
  };
  return colors[colorName] || colors.slate;
}

// 绘制函数（简化版）
const ANNOTATION_BG_ALPHA = 0.7;

function drawScore(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, text: string, color: string) {
  ctx.font = 'bold 18px sans-serif';
  ctx.fillStyle = `rgba(255,255,255,${ANNOTATION_BG_ALPHA})`;
  ctx.fillRect(x, y, w, h);
  ctx.fillStyle = color;
  ctx.fillText(text, x + 4, y + h - 4);
}

function drawEllipse(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, color: string) {
  ctx.beginPath();
  ctx.ellipse(x + w/2, y + h/2, w/2, h/2, 0, 0, Math.PI * 2);
  ctx.strokeStyle = color;
  ctx.lineWidth = 3;
  ctx.stroke();
}

function drawMark(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, text: string, color: string) {
  ctx.beginPath();
  ctx.arc(x + w/2, y + h/2, Math.min(w, h)/2, 0, Math.PI * 2);
  ctx.fillStyle = `rgba(255,255,255,${ANNOTATION_BG_ALPHA})`;
  ctx.fill();
  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  ctx.stroke();
  ctx.fillStyle = color;
  ctx.font = 'bold 12px sans-serif';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(text, x + w/2, y + h/2);
  ctx.textAlign = 'start';
  ctx.textBaseline = 'alphabetic';
}

function drawCheckMark(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, color: string) {
  ctx.beginPath();
  ctx.moveTo(x + w*0.2, y + h*0.5);
  ctx.lineTo(x + w*0.4, y + h*0.7);
  ctx.lineTo(x + w*0.8, y + h*0.3);
  ctx.strokeStyle = color;
  ctx.lineWidth = 3;
  ctx.stroke();
}

function drawCross(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, color: string) {
  ctx.beginPath();
  ctx.moveTo(x + w*0.2, y + h*0.2);
  ctx.lineTo(x + w*0.8, y + h*0.8);
  ctx.moveTo(x + w*0.8, y + h*0.2);
  ctx.lineTo(x + w*0.2, y + h*0.8);
  ctx.strokeStyle = color;
  ctx.lineWidth = 3;
  ctx.stroke();
}

function drawComment(ctx: CanvasRenderingContext2D, x: number, y: number, text: string, color: string) {
  ctx.font = '12px sans-serif';
  const metrics = ctx.measureText(text);
  ctx.fillStyle = `rgba(255,255,240,${ANNOTATION_BG_ALPHA})`;
  ctx.fillRect(x, y, metrics.width + 8, 20);
  ctx.strokeStyle = color;
  ctx.lineWidth = 1;
  ctx.strokeRect(x, y, metrics.width + 8, 20);
  ctx.fillStyle = color;
  ctx.fillText(text, x + 4, y + 14);
}

function drawResizeHandles(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  size: number
) {
  const half = size / 2;
  const points = [
    [x, y],
    [x + w, y],
    [x, y + h],
    [x + w, y + h],
  ];
  ctx.save();
  ctx.fillStyle = '#ffffff';
  ctx.strokeStyle = '#3B82F6';
  ctx.lineWidth = 1;
  points.forEach(([px, py]) => {
    ctx.beginPath();
    ctx.rect(px - half, py - half, size, size);
    ctx.fill();
    ctx.stroke();
  });
  ctx.restore();
}
