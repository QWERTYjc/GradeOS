import { GoogleGenerativeAI } from '@google/generative-ai';
import { Language } from '../types';

// Initialize Gemini AI with the API key
const genAI = new GoogleGenerativeAI('');

export class GeminiService {
  private model;

  constructor() {
    // Use gemini-3-flash-preview model as requested
    this.model = genAI.getGenerativeModel({ 
      model: 'gemini-3-flash-preview'
    });
  }

  async generateResponse(message: string, lang: Language = 'en'): Promise<string> {
    try {
      const langText = lang === 'zh' ? 'Traditional Chinese' : 'English';
      
      const systemPrompt = `You are a supportive AI study assistant for secondary school students. 
      
      CORE BEHAVIOR:
      1. Persona: You are a friendly, encouraging peer tutor who understands student challenges
      2. Tone: Warm, supportive, and motivational but not overly casual
      3. Language: Respond in ${langText}
      4. Focus: Academic support, study strategies, stress management, and encouragement
      
      GUIDELINES:
      - Keep responses concise and actionable
      - Offer specific study tips when relevant
      - Be empathetic to student stress and challenges
      - Encourage healthy study habits and work-life balance
      - If asked about grades or performance, suggest they check their data in the platform
      - Avoid giving direct answers to homework - instead guide learning process
      
      Student message: ${message}`;

      const result = await this.model.generateContent(systemPrompt);
      const response = result.response;
      return response.text();
    } catch (error) {
      console.error('Gemini API Error:', error);
      
      // Fallback responses based on language
      const fallbackResponses = {
        en: [
          "I'm having a bit of trouble connecting right now. Let me try to help anyway - what specific subject or topic are you working on?",
          "Sorry, I'm experiencing some technical difficulties. In the meantime, remember that taking breaks and staying organized are key to effective studying!",
          "I'm not able to process that fully right now, but I'm here to support you. What's the main challenge you're facing with your studies?"
        ],
        zh: [
          "我現在連接有點問題。不過讓我試著幫助你 - 你在學習哪個科目或主題？",
          "抱歉，我遇到了一些技術困難。不過記住，適當休息和保持有序是有效學習的關鍵！",
          "我現在無法完全處理這個問題，但我在這裡支持你。你在學習上面臨的主要挑戰是什麼？"
        ]
      };
      
      const responses = fallbackResponses[lang];
      return responses[Math.floor(Math.random() * responses.length)];
    }
  }

  async generateStreamResponse(message: string, lang: Language = 'en', onChunk: (chunk: string) => void): Promise<void> {
    try {
      const langText = lang === 'zh' ? 'Traditional Chinese' : 'English';
      
      const systemPrompt = `You are a supportive AI study assistant for secondary school students. 
      
      CORE BEHAVIOR:
      1. Persona: You are a friendly, encouraging peer tutor who understands student challenges
      2. Tone: Warm, supportive, and motivational but not overly casual
      3. Language: Respond in ${langText}
      4. Focus: Academic support, study strategies, stress management, and encouragement
      
      GUIDELINES:
      - Keep responses concise and actionable
      - Offer specific study tips when relevant
      - Be empathetic to student stress and challenges
      - Encourage healthy study habits and work-life balance
      - If asked about grades or performance, suggest they check their data in the platform
      - Avoid giving direct answers to homework - instead guide learning process
      
      Student message: ${message}`;

      const result = await this.model.generateContentStream(systemPrompt);
      
      for await (const chunk of result.stream) {
        const chunkText = chunk.text();
        if (chunkText) {
          onChunk(chunkText);
        }
      }
    } catch (error) {
      console.error('Gemini Streaming Error:', error);
      
      // Fallback to non-streaming response
      const fallbackResponse = await this.generateResponse(message, lang);
      onChunk(fallbackResponse);
    }
  }
}

export const geminiService = new GeminiService();
