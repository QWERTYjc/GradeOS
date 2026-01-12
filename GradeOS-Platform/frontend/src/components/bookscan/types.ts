
export interface ScannedImage {
  id: string;
  url: string; // Blob URL or Data URL
  timestamp: number;
  name: string;
  selected?: boolean;
  isOptimizing?: boolean; // New flag for background AI processing
}

export interface Session {
  id: string;
  name: string;
  createdAt: number;
  images: ScannedImage[];
}

export enum AppView {
  SCANNER = 'SCANNER',
  GALLERY = 'GALLERY',
  GENERATOR = 'GENERATOR',
}

export interface VideoExtractionConfig {
  intervalSeconds: number;
}

export type ImageSize = '1K' | '2K' | '4K';

export interface GeminiConfig {
  apiKey?: string;
}
