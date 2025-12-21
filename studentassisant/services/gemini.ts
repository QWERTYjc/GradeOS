
import { GoogleGenAI, Type, FunctionDeclaration, Tool, FunctionCall } from "@google/genai";
import { ScoreEntry, StudyPlan, Language } from "../types";
import { MOCK_SCORES } from "../constants";

// Always initialize with the direct process.env.API_KEY object.
const ai = new GoogleGenAI({ apiKey: process.env.API_KEY });

// --- Tools Definition ---

const getAcademicRecordTool: FunctionDeclaration = {
  name: 'getAcademicRecord',
  description: 'Retrieve the student\'s current academic scores and weak points from the database.',
  parameters: {
    type: Type.OBJECT,
    properties: {}, // No arguments needed for this simple mock
  },
};

const tools: Tool[] = [
  {
    functionDeclarations: [getAcademicRecordTool],
  },
];

// --- Helper to simulate DB call ---
export const executeLocalFunction = async (functionCall: FunctionCall): Promise<any> => {
  if (functionCall.name === 'getAcademicRecord') {
    // Simulate fetching data
    return {
      scores: MOCK_SCORES.map(s => ({
        subject: s.subject,
        score: s.score,
        average: s.averageScore,
        weakPoints: s.weakPoints
      }))
    };
  }
  return { error: 'Function not found' };
};

// --- Chat Session Creator ---

export const createChatSession = (lang: Language = 'en') => {
  const langText = lang === 'zh' ? 'Traditional Chinese' : 'English';
  
  const systemInstruction = `You are an advanced Academic AI Assistant.
  
  CORE BEHAVIOR:
  1.  **Persona**: You are a supportive, intelligent peer tutor. You are analytical but friendly.
  2.  **Tools**: You have access to the student's academic records via the 'getAcademicRecord' tool. ALWAYS call this tool if the user asks about their grades, performance, or weak spots. Do not make up numbers.
  3.  **Tone**: Concise, professional yet warm. Avoid flowery language.
  4.  **Formatting**: 
      - Do NOT use Markdown symbols like *, #, or \`. 
      - Use clear paragraph breaks for readability.
      - Use simple numbering (1. 2. 3.) if listing items.
  5.  **Language**: Respond strictly in ${langText}.
  
  If the user asks a question requiring data you don't have in the conversation context, check if your tools can provide it.`;

  return ai.chats.create({
    model: 'gemini-3-flash-preview',
    config: {
      systemInstruction,
      tools: tools,
    },
  });
};

// --- Existing functionality (kept for other components) ---

export const generateStudyPlan = async (scores: ScoreEntry[], lang: Language = 'en'): Promise<StudyPlan> => {
  const langText = lang === 'zh' ? 'Traditional Chinese' : 'English';
  const prompt = `Based on these secondary school student scores and weak points, generate a personalized weekly study plan.
  Scores: ${JSON.stringify(scores.map(s => ({ subject: s.subject, score: s.score, weakPoints: s.weakPoints })))}
  Requirement: Focus on weak points, use a peer-to-peer encouraging tone.
  Respond in ${langText}.
  `;

  const response = await ai.models.generateContent({
    model: 'gemini-3-flash-preview',
    contents: prompt,
    config: {
      responseMimeType: "application/json",
      responseSchema: {
        type: Type.OBJECT,
        properties: {
          dailyPlan: {
            type: Type.ARRAY,
            items: {
              type: Type.OBJECT,
              properties: {
                period: { type: Type.STRING },
                content: { type: Type.STRING },
                target: { type: Type.STRING }
              },
              required: ['period', 'content', 'target']
            }
          },
          weeklyReview: { type: Type.STRING },
          monthlyCheckPoint: { type: Type.STRING }
        },
        required: ['dailyPlan', 'weeklyReview', 'monthlyCheckPoint']
      }
    }
  });

  return JSON.parse(response.text || '{}');
};
