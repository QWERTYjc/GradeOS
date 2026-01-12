import { TEXTIN_CONFIG } from './constants';

/**
 * Converts a base64 string to a Uint8Array.
 */
function base64ToUint8Array(base64: string): Uint8Array {
  const binaryString = atob(base64);
  const len = binaryString.length;
  const bytes = new Uint8Array(len);
  for (let i = 0; i < len; i++) {
    bytes[i] = binaryString.charCodeAt(i);
  }
  return bytes;
}

/**
 * Calls the TextIn crop_enhance_image service.
 * Performs edge detection, perspective correction, and enhancement.
 */
export const enhanceWithTextIn = async (base64Image: string): Promise<string> => {
  // Strip data URL prefix if present
  const base64Data = base64Image.includes(',') ? base64Image.split(',')[1] : base64Image;
  const binaryData = base64ToUint8Array(base64Data);

  try {
    const response = await fetch(TEXTIN_CONFIG.ENDPOINT, {
      method: 'POST',
      headers: {
        'x-ti-app-id': TEXTIN_CONFIG.APP_ID,
        'x-ti-secret-code': TEXTIN_CONFIG.SECRET_CODE,
        'Content-Type': 'application/octet-stream'
      },
      body: binaryData
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`TextIn API Error: ${response.status} - ${errorText}`);
    }

    const result = await response.json();
    
    if (result.code === 200 && result.result && result.result.image_list) {
      // TextIn typically returns an image_list for this service
      const processedBase64 = result.result.image_list[0].image;
      return `data:image/jpeg;base64,${processedBase64}`;
    } else {
      throw new Error(result.message || 'TextIn processing failed');
    }
  } catch (error) {
    console.error('TextIn Enhancement Error:', error);
    throw error;
  }
};