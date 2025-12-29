import { ScannedImage } from '../types';

export const extractFramesFromVideo = async (
  videoFile: File,
  intervalSeconds: number
): Promise<ScannedImage[]> => {
  return new Promise((resolve, reject) => {
    const video = document.createElement('video');
    const url = URL.createObjectURL(videoFile);
    video.src = url;
    video.muted = true;
    video.playsInline = true;

    const frames: ScannedImage[] = [];
    
    video.onloadedmetadata = async () => {
      const duration = video.duration;
      const canvas = document.createElement('canvas');
      const ctx = canvas.getContext('2d');
      
      if (!ctx) {
        URL.revokeObjectURL(url);
        reject(new Error("Could not create canvas context"));
        return;
      }

      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;

      let currentTime = 0;

      const seekAndCapture = async () => {
        if (currentTime >= duration) {
          URL.revokeObjectURL(url);
          resolve(frames);
          return;
        }

        video.currentTime = currentTime;
      };

      video.onseeked = () => {
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        const dataUrl = canvas.toDataURL('image/jpeg', 0.7); // Compressed slightly for video frames
        
        frames.push({
          id: crypto.randomUUID(),
          url: dataUrl,
          timestamp: Date.now(),
          name: `frame_${Math.floor(currentTime)}s.jpg`,
          selected: false
        });

        currentTime += intervalSeconds;
        seekAndCapture();
      };

      // Start processing
      seekAndCapture();
    };

    video.onerror = (e) => {
      URL.revokeObjectURL(url);
      reject(e);
    };
  });
};

export const fileToDataURL = (file: File): Promise<string> => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
};

/**
 * Compresses a base64 string/DataURL.
 * Resizes large images to a max dimension (default 1600px) and reduces quality (default 0.7).
 * This significantly reduces payload size without affecting AI text recognition capabilities.
 */
export const compressBase64Image = (base64Str: string, maxWidth = 1600, quality = 0.7): Promise<string> => {
  return new Promise((resolve, reject) => {
    // Add header if missing for Image object to load
    const fullDataUrl = base64Str.startsWith('data:') ? base64Str : `data:image/jpeg;base64,${base64Str}`;
    
    const img = new Image();
    img.src = fullDataUrl;
    
    img.onload = () => {
      const canvas = document.createElement('canvas');
      let width = img.width;
      let height = img.height;

      // Calculate new dimensions
      if (width > maxWidth || height > maxWidth) {
        if (width > height) {
          height = Math.round((height * maxWidth) / width);
          width = maxWidth;
        } else {
          width = Math.round((width * maxWidth) / height);
          height = maxWidth;
        }
      }

      canvas.width = width;
      canvas.height = height;
      
      const ctx = canvas.getContext('2d');
      if (!ctx) {
        reject(new Error('Canvas context failed'));
        return;
      }
      
      // Draw and compress
      ctx.drawImage(img, 0, 0, width, height);
      // Returns full data URL
      resolve(canvas.toDataURL('image/jpeg', quality));
    };

    img.onerror = (err) => reject(err);
  });
};