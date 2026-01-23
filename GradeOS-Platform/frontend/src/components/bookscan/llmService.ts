import { MODELS } from './constants';
import { ImageSize } from './types';
import { enhanceWithTextIn } from './textInService';

const getApiBase = () => {
  if (process.env.NEXT_PUBLIC_API_URL) {
    return process.env.NEXT_PUBLIC_API_URL;
  }
  if (typeof window !== 'undefined') {
    const hostname = window.location.hostname;
    if (hostname === 'localhost' || hostname === '127.0.0.1') {
      return 'http://localhost:8001/api';
    }
    if (hostname.includes('railway.app')) {
      return 'https://gradeos-production.up.railway.app/api';
    }
  }
  return 'http://localhost:8001/api';
};

const API_BASE = getApiBase();

async function request<T>(endpoint: string, payload: Record<string, unknown>): Promise<T> {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: 'Request failed' }));
    throw new Error(error.detail || error.message || `HTTP ${response.status}`);
  }

  return response.json();
}

export const editImage = async (
  base64Image: string,
  prompt: string,
  mimeType: string = 'image/jpeg'
): Promise<string> => {
  const data = await request<{ image?: string }>('/bookscan/edit', {
    image_base64: base64Image,
    prompt,
    mime_type: mimeType,
    model: MODELS.EDITING,
  });

  if (!data.image) {
    throw new Error('No image returned from editing endpoint.');
  }
  return data.image;
};

export const generateImage = async (prompt: string, size: ImageSize): Promise<string> => {
  const data = await request<{ image?: string }>('/bookscan/generate', {
    prompt,
    size,
    model: MODELS.GENERATION,
  });

  if (!data.image) {
    throw new Error('No image returned from generation endpoint.');
  }
  return data.image;
};

/**
 * Uses TextIn (CamScanner Engine) for document optimization.
 */
export const optimizeDocument = async (base64Image: string): Promise<string> => {
  return await enhanceWithTextIn(base64Image);
};
