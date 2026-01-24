/**
 * 批注批改 API 服务
 * 
 * 调用后端批注批改接口，获取带坐标的批改结果
 */

import axios from 'axios';
import type {
  AnnotateRequest,
  AnnotateResponse,
  BatchAnnotateRequest,
  BatchAnnotateResponse,
  RenderRequest,
  PageAnnotations,
  VisualAnnotation,
  QuestionRubricInput,
} from '@/types/annotation';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001';

/**
 * 批改单页并返回批注坐标
 */
export async function annotatePageWithCoords(
  imageBase64: string,
  rubrics: QuestionRubricInput[],
  pageIndex: number = 0
): Promise<AnnotateResponse> {
  const request: AnnotateRequest = {
    image_base64: imageBase64,
    rubrics,
    page_index: pageIndex,
  };

  const response = await axios.post<AnnotateResponse>(
    `${API_BASE}/api/grading/annotate`,
    request
  );

  return response.data;
}

/**
 * 批量批改多页并返回批注坐标
 */
export async function annotateSubmissionWithCoords(
  imagesBase64: string[],
  rubrics: QuestionRubricInput[],
  submissionId?: string
): Promise<BatchAnnotateResponse> {
  const request: BatchAnnotateRequest = {
    images_base64: imagesBase64,
    rubrics,
    submission_id: submissionId,
  };

  const response = await axios.post<BatchAnnotateResponse>(
    `${API_BASE}/api/grading/annotate/batch`,
    request
  );

  return response.data;
}

/**
 * 渲染批注到图片（返回 PNG Blob）
 */
export async function renderAnnotationsToImage(
  imageBase64: string,
  annotations: VisualAnnotation[]
): Promise<Blob> {
  const request: RenderRequest = {
    image_base64: imageBase64,
    annotations,
  };

  const response = await axios.post(
    `${API_BASE}/api/grading/render`,
    request,
    { responseType: 'blob' }
  );

  return response.data;
}

/**
 * 渲染批注到图片（返回 Base64）
 */
export async function renderAnnotationsToBase64(
  imageBase64: string,
  annotations: VisualAnnotation[]
): Promise<{ success: boolean; image_base64?: string; error?: string }> {
  const request: RenderRequest = {
    image_base64: imageBase64,
    annotations,
  };

  const response = await axios.post(
    `${API_BASE}/api/grading/render/base64`,
    request
  );

  return response.data;
}

/**
 * 一步完成批改并渲染（返回 PNG Blob）
 */
export async function annotateAndRender(
  imageBase64: string,
  rubrics: QuestionRubricInput[],
  pageIndex: number = 0
): Promise<Blob> {
  const request: AnnotateRequest = {
    image_base64: imageBase64,
    rubrics,
    page_index: pageIndex,
  };

  const response = await axios.post(
    `${API_BASE}/api/grading/annotate-and-render`,
    request,
    { responseType: 'blob' }
  );

  return response.data;
}

/**
 * 将文件转换为 Base64
 */
export function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      // 移除 data:image/xxx;base64, 前缀
      const base64 = result.split(',')[1] || result;
      resolve(base64);
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

/**
 * 将 Blob 转换为 Object URL（用于显示图片）
 */
export function blobToObjectUrl(blob: Blob): string {
  return URL.createObjectURL(blob);
}

/**
 * 释放 Object URL
 */
export function revokeObjectUrl(url: string): void {
  URL.revokeObjectURL(url);
}
