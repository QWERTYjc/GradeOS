/**
 * 批注坐标类型定义
 * 
 * 用于 AI 批改输出的视觉批注数据结构
 */

/** 批注类型 */
export type AnnotationType =
  | 'score'           // 分数标注
  | 'error_circle'    // 错误圈选
  | 'error_underline' // 错误下划线
  | 'correct_check'   // 正确勾选 ✓
  | 'partial_check'   // 部分正确 △
  | 'wrong_cross'     // 错误叉 ✗
  | 'comment'         // 文字批注
  | 'highlight'       // 高亮区域
  | 'arrow';          // 箭头指示

/** 批注颜色 */
export const AnnotationColors = {
  RED: '#FF0000',      // 错误
  GREEN: '#00AA00',    // 正确
  ORANGE: '#FF8800',   // 部分正确
  BLUE: '#0066FF',     // 信息/讲解
  PURPLE: '#9900FF',   // 重要提示
} as const;

/** 边界框坐标（归一化 0.0-1.0） */
export interface BoundingBox {
  x_min: number;
  y_min: number;
  x_max: number;
  y_max: number;
}

/** 点坐标 */
export interface Point {
  x: number;
  y: number;
}

/** 视觉批注 */
export interface VisualAnnotation {
  annotation_type: AnnotationType;
  bounding_box: BoundingBox;
  text?: string;
  color?: string;
  confidence?: number;
  question_id?: string;
  scoring_point_id?: string;
  arrow_end?: Point;
  metadata?: Record<string, unknown>;
}

/** 单页批注集合 */
export interface PageAnnotations {
  page_index: number;
  image_width?: number;
  image_height?: number;
  annotations: VisualAnnotation[];
  total_score?: number;
  max_score?: number;
}

/** 完整批改批注结果 */
export interface GradingAnnotationResult {
  submission_id: string;
  pages: PageAnnotations[];
  total_score: number;
  max_total_score: number;
}

/** 得分点输入 */
export interface ScoringPointInput {
  description: string;
  score: number;
  point_id?: string;
  is_required?: boolean;
}

/** 题目评分标准输入 */
export interface QuestionRubricInput {
  question_id: string;
  max_score: number;
  question_text?: string;
  standard_answer?: string;
  scoring_points?: ScoringPointInput[];
  grading_notes?: string;
}

/** 批注批改请求 */
export interface AnnotateRequest {
  image_base64: string;
  rubrics: QuestionRubricInput[];
  page_index?: number;
}

/** 批注批改响应 */
export interface AnnotateResponse {
  success: boolean;
  page_annotations?: PageAnnotations;
  error?: string;
}

/** 渲染请求 */
export interface RenderRequest {
  image_base64: string;
  annotations: VisualAnnotation[];
}

/** 批量批注请求 */
export interface BatchAnnotateRequest {
  images_base64: string[];
  rubrics: QuestionRubricInput[];
  submission_id?: string;
}

/** 批量批注响应 */
export interface BatchAnnotateResponse {
  success: boolean;
  result?: GradingAnnotationResult;
  error?: string;
}

/**
 * 将归一化坐标转换为像素坐标
 */
export function toPixelCoords(
  bbox: BoundingBox,
  imageWidth: number,
  imageHeight: number
): { x: number; y: number; width: number; height: number } {
  return {
    x: bbox.x_min * imageWidth,
    y: bbox.y_min * imageHeight,
    width: (bbox.x_max - bbox.x_min) * imageWidth,
    height: (bbox.y_max - bbox.y_min) * imageHeight,
  };
}

/**
 * 获取批注的默认颜色
 */
export function getAnnotationColor(type: AnnotationType): string {
  switch (type) {
    case 'correct_check':
      return AnnotationColors.GREEN;
    case 'error_circle':
    case 'error_underline':
    case 'wrong_cross':
      return AnnotationColors.RED;
    case 'partial_check':
    case 'score':
      return AnnotationColors.ORANGE;
    case 'comment':
    case 'highlight':
      return AnnotationColors.BLUE;
    default:
      return AnnotationColors.RED;
  }
}
