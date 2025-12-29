import { ScannedImage, SubmissionResponse } from './types';

const API_BASE = 'http://localhost:8001';

export const submitToGradingSystem = async (
  images: ScannedImage[],
  homeworkId: string = 'hw-001',
  studentId: string = 'guest',
  studentName: string = 'Guest'
): Promise<SubmissionResponse> => {
  const imageData = images.map(img => img.url);
  
  const response = await fetch(`${API_BASE}/api/homework/submit-scan`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      homework_id: homeworkId,
      student_id: studentId,
      student_name: studentName,
      images: imageData
    })
  });

  if (!response.ok) {
    throw new Error(`API Error: ${response.status}`);
  }
  return response.json();
};

export const getSubmissionHistory = async (studentId: string) => {
  const response = await fetch(`${API_BASE}/api/submissions/history?student_id=${studentId}`);
  return response.json();
};
