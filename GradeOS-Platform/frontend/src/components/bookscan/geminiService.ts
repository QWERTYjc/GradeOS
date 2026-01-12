import { GoogleGenAI } from "@google/genai";
import { MODELS } from './constants';
import { ImageSize } from './types';
import { compressBase64Image } from './imageProcessing';
import { enhanceWithTextIn } from './textInService';

export const ensureApiKey = async (): Promise<void> => {
  if (window.aistudio && window.aistudio.hasSelectedApiKey) {
    const hasKey = await window.aistudio.hasSelectedApiKey();
    if (!hasKey && window.aistudio.openSelectKey) {
      await window.aistudio.openSelectKey();
    }
  }
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
              data: base64Image,
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
    const ai = new GoogleGenAI({ apiKey: process.env.API_KEY });

    try {
        const response = await ai.models.generateContent({
            model: MODELS.GENERATION,
            contents: {
                parts: [{ text: prompt }]
            },
            config: {
                imageConfig: {
                    imageSize: size,
                    aspectRatio: "1:1"
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
 * Now uses TextIn (CamScanner Engine) for industrial-grade Document Optimization.
 */
export const optimizeDocument = async (base64Image: string): Promise<string> => {
  // Use TextIn for high-precision cropping and enhancement as requested
  return await enhanceWithTextIn(base64Image);
};