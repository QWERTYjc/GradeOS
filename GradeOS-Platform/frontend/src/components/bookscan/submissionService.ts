import { ScannedImage } from './types';

export interface SubmissionResponse {
  submission_id: string;
  homework_id: string;
  student_id: string;
  student_name: string;
  submitted_at: string;
  status: string;
  score?: number;
  feedback?: string;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001/api';

/**
 * 提交扫描图片到批改系统
 */
export const submitToGradingSystem = async (
  images: ScannedImage[],
  homeworkId: string = 'hw-001',
  studentId: string = 'guest',
  studentName: string = 'Guest'
): Promise<SubmissionResponse> => {
  const response = await fetch(`${API_BASE}/homework/submit-scan`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      homework_id: homeworkId,
      student_id: studentId,
      student_name: studentName,
      images: images.map(img => img.url)
    })
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`提交失败: ${error}`);
  }
  return response.json();
};

/**
 * 获取提交历史
 */
export const getSubmissionHistory = async (studentId: string) => {
  const response = await fetch(`${API_BASE}/submissions/history?student_id=${studentId}`);
  return response.json();
};

/**
 * 获取所有提交记录
 */
export const getAllSubmissions = async () => {
  const response = await fetch(`${API_BASE}/submissions/all`);
  return response.json();
};
