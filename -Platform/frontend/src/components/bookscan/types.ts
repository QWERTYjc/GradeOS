export interface ScannedImage {
  id: string;
  url: string;
  timestamp: number;
  name: string;
  selected?: boolean;
  isOptimizing?: boolean;
}

export interface Session {
  id: string;
  name: string;
  createdAt: number;
  images: ScannedImage[];
}

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
