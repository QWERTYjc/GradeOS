
import { GoogleGenAI, Type } from "@google/genai";
import { AnalysisResult, Recommendation, DiagnosisReport } from "../types";

const SYSTEM_INSTRUCTION = `你是一位世界级的金牌教育诊断专家。
你的职责是：
1. 深入挖掘错因（知识漏洞、逻辑谬误、审题偏差 or 计算习惯）。
2. 支持识别图片中的文字和图形，特别是手写数学公式。
3. 提供具备教育心理学支撑的补救计划。
4. 掌握度数据必须精确，并符合真实学生成长曲线。
5. 所有回答必须使用简体中文，并严格遵守 JSON 格式输出。`;

/**
 * 智能深度解析题目并返回诊断结果
 */
export const analyzeProblemIntelligently = async (
  subject: string,
  textDescription: string,
  base64Image?: string,
  onProcessUpdate?: (status: string) => void
): Promise<AnalysisResult> => {
  const ai = new GoogleGenAI({ apiKey: process.env.API_KEY });
  const model = "gemini-3-pro-preview"; 
  
  onProcessUpdate?.("正在执行智能深度解析...");

  const parts: any[] = [{ text: `学科：${subject}。题目/描述：${textDescription}` }];
  
  if (base64Image) {
    parts.push({
      inlineData: {
        mimeType: "image/jpeg",
        data: base64Image.split(',')[1] || base64Image
      }
    });
  }

  const response = await ai.models.generateContent({
    model,
    contents: { parts },
    config: {
      systemInstruction: SYSTEM_INSTRUCTION,
      responseMimeType: "application/json",
      responseSchema: {
        type: Type.OBJECT,
        properties: {
          error_type: { type: Type.STRING },
          error_severity: { type: Type.STRING },
          knowledge_gaps: {
            type: Type.ARRAY,
            items: {
              type: Type.OBJECT,
              properties: {
                knowledge_point: { type: Type.STRING },
                mastery_level: { type: Type.NUMBER },
                confidence: { type: Type.NUMBER }
              },
              required: ["knowledge_point", "mastery_level", "confidence"]
            }
          },
          detailed_analysis: {
            type: Type.OBJECT,
            properties: {
              step_by_step_correction: { type: Type.ARRAY, items: { type: Type.STRING } },
              common_mistakes: { type: Type.STRING },
              correct_solution: { type: Type.STRING }
            },
            required: ["step_by_step_correction", "common_mistakes", "correct_solution"]
          },
          root_cause: { type: Type.STRING }
        },
        required: ["error_type", "error_severity", "knowledge_gaps", "detailed_analysis", "root_cause"]
      }
    }
  });

  return JSON.parse(response.text || "{}");
};

/**
 * 根据分析结果获取学习建议
 */
export const getRecommendations = async (analysis: AnalysisResult): Promise<Recommendation> => {
  const ai = new GoogleGenAI({ apiKey: process.env.API_KEY });
  const response = await ai.models.generateContent({
    model: "gemini-3-pro-preview",
    contents: `基于以下诊断结果：${JSON.stringify(analysis)}，请生成一个针对该学生的具体强化方案。要求包含短期目标、每日任务和推荐练习。`,
    config: {
      systemInstruction: SYSTEM_INSTRUCTION,
      responseMimeType: "application/json"
    }
  });

  return JSON.parse(response.text || "{}");
};

/**
 * 生成阶段性诊断报告
 */
export const getDiagnosisReport = async (studentId: string): Promise<DiagnosisReport> => {
  const ai = new GoogleGenAI({ apiKey: process.env.API_KEY });
  const model = "gemini-3-pro-preview";
  
  const response = await ai.models.generateContent({
    model,
    contents: `为学生 ID ${studentId} 生成成长报告。`,
    config: {
      systemInstruction: SYSTEM_INSTRUCTION,
      responseMimeType: "application/json"
    }
  });

  return JSON.parse(response.text || "{}");
};
