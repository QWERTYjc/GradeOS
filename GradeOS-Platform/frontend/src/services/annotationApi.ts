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
  QuestionRubricInput,
} from '@/types/annotation';

// 注意：NEXT_PUBLIC_API_URL 已经包含 /api，所以这里不需要再加
const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001/api';

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
    `${API_BASE}/grading/annotate`,
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
    `${API_BASE}/grading/annotate/batch`,
    request
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
