// 图像处理工具函数

export const fileToDataURL = (file: File): Promise<string> => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
};

/**
 * 压缩 base64 图片
 */
export const compressBase64Image = (
  base64Str: string, 
  maxWidth = 1600, 
  quality = 0.7
): Promise<string> => {
  return new Promise((resolve, reject) => {
    const fullDataUrl = base64Str.startsWith('data:') 
      ? base64Str 
      : `data:image/jpeg;base64,${base64Str}`;
    
    const img = new Image();
    img.src = fullDataUrl;
    
    img.onload = () => {
      const canvas = document.createElement('canvas');
      let width = img.width;
      let height = img.height;

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
      
      ctx.drawImage(img, 0, 0, width, height);
      resolve(canvas.toDataURL('image/jpeg', quality));
    };

    img.onerror = (err) => reject(err);
  });
};

/**
 * 将多张图片合并为单个 base64 (模拟 PDF)
 */
export const mergeImagesToSubmission = async (
  images: { url: string }[]
): Promise<string[]> => {
  const compressed: string[] = [];
  for (const img of images) {
    const c = await compressBase64Image(img.url, 1200, 0.8);
    compressed.push(c);
  }
  return compressed;
};
