import { GoogleGenAI } from "@google/genai";
import { MODELS } from '../constants';
import { ImageSize } from '../types';
import { compressBase64Image } from './imageProcessing';

// Helper to ensure API key availability for Pro models
export const ensureApiKey = async (): Promise<void> => {
  if (window.aistudio && window.aistudio.hasSelectedApiKey) {
    const hasKey = await window.aistudio.hasSelectedApiKey();
    if (!hasKey && window.aistudio.openSelectKey) {
      await window.aistudio.openSelectKey();
    }
  }
};

const getAIClient = async () => {
    // For Pro models or if we need the selected key
    await ensureApiKey();
    return new GoogleGenAI({ apiKey: process.env.API_KEY });
};


export const editImage = async (base64Image: string, prompt: string, mimeType: string = 'image/jpeg'): Promise<string> => {
  const ai = new GoogleGenAI({ apiKey: process.env.API_KEY });
  
  try {
    const response = await ai.models.generateContent({
      model: MODELS.EDITING,
      contents: {
        parts: [
          {
            inlineData: {
              data: base64Image, // Expecting raw base64 data here (no header)
              mimeType: mimeType,
            },
          },
          {
            text: prompt,
          },
        ],
      },
    });

    for (const part of response.candidates?.[0]?.content?.parts || []) {
      if (part.inlineData) {
        return `data:${part.inlineData.mimeType || 'image/png'};base64,${part.inlineData.data}`;
      }
    }
    throw new Error("No image returned from editing model.");
  } catch (error) {
    console.error("Gemini Edit Error:", error);
    throw error;
  }
};

export const generateImage = async (prompt: string, size: ImageSize): Promise<string> => {
    // Pro model requires explicit key selection
    const ai = await getAIClient();

    try {
        const response = await ai.models.generateContent({
            model: MODELS.GENERATION,
            contents: {
                parts: [{ text: prompt }]
            },
            config: {
                imageConfig: {
                    imageSize: size,
                    aspectRatio: "1:1" // Defaulting to square for simplicity
                }
            }
        });

        for (const part of response.candidates?.[0]?.content?.parts || []) {
            if (part.inlineData) {
                return `data:${part.inlineData.mimeType || 'image/png'};base64,${part.inlineData.data}`;
            }
        }
        throw new Error("No image returned from generation model.");
    } catch (error) {
        console.error("Gemini Generate Error:", error);
        throw error;
    }
}

/**
 * Specialized function for document scanning: Cropping, Perspective Correction, and Enhancement.
 */
export const optimizeDocument = async (base64Image: string): Promise<string> => {
  // 1. Compress before sending to save bandwidth and latency.
  // The AI Model (Nano Banana) works perfectly fine with 1024-1600px width images.
  const compressedDataUrl = await compressBase64Image(base64Image);
  const compressedBase64 = compressedDataUrl.split(',')[1]; // Strip header for API

  // Enhanced prompt for strictly cropping background
  const prompt = `
    Perform a strict document scan processing:
    1. EXTREME CROP: Detect the document paper edges. Remove EVERYTHING else (tables, wooden texture, dark background). The output image must contain ONLY the paper content with NO margin.
    2. DE-SKEW: Flatten the document image to a perfect rectangle, correcting any camera perspective distortion (keystone correction).
    3. CLEAN: Remove shadows cast by fingers or the camera.
    4. BINARIZE-LIKE ENHANCEMENT: Make the paper background pure flat white (#FFFFFF) and text sharp black, high contrast for maximum readability.
    Return only the processed image.
  `;
  
  return await editImage(compressedBase64, prompt, 'image/jpeg');
};