// BookScan 模块类型定义

export interface ScannedImage {
  id: string;
  url: string; // Data URL
  timestamp: number;
  name: string;
  isOptimizing?: boolean;
}

export interface ScanSession {
  id: string;
  name: string;
  createdAt: number;
  images: ScannedImage[];
}

export type ScanMode = 'single' | 'book';
