
import { GoogleGenAI, Type, FunctionDeclaration, GenerateContentResponse } from "@google/genai";
import { AnalysisResult, Recommendation, DiagnosisReport } from "../types";

// Refined mock student data for more realistic context
const MOCK_DB = {
  student_history: {
    id: "S20240101",
    recent_errors: ["二次函数顶点式", "不等式变号规则", "圆的切线判定", "含参一元二次方程"],
    avg_score: 78.5,
    learning_style: "逻辑分析型，对抽象代数理解较快，但在几何图形转换上存在滞后",
    recent_performance: [0.72, 0.75, 0.74, 0.79, 0.78, 0.82]
  },
  knowledge_graph: {
    "二次函数顶点式": {
      definition: "y=a(x-h)²+k，其中(h,k)为顶点坐标",
      prerequisites: ["配方法", "函数平移"],
      logic_chain: "从一般式配方 -> 确定对称轴 -> 确定最值",
      mistakes: ["忽略a的正负影响开口方向", "h的正负号与平移方向混淆", "忽视k值的几何意义"]
    }
  }
};

const tools: { functionDeclarations: FunctionDeclaration[] } = {
  functionDeclarations: [
    {
      name: "get_student_history",
      description: "获取特定学生的历史学习数据、过往错题分布和学习偏好。",
      parameters: {
        type: Type.OBJECT,
        properties: {
          student_id: { type: Type.STRING, description: "学生的唯一识别码" }
        },
        required: ["student_id"]
      }
    },
    {
      name: "get_knowledge_node_detail",
      description: "查询特定知识点的权威定义、逻辑前驱节点和常见误区。",
      parameters: {
        type: Type.OBJECT,
        properties: {
          knowledge_point: { type: Type.STRING, description: "知识点名称" }
        },
        required: ["knowledge_point"]
      }
    }
  ]
};

const SYSTEM_INSTRUCTION = `你是一位世界级的金牌教育诊断专家。你正在辅助学生进行精准错题诊断。
你的职责是：
1. 深入挖掘错因（知识漏洞、逻辑谬误、审题偏差或计算习惯）。
2. 提供具备教育心理学支撑的补救计划。
3. 语气专业、客观且富有鼓励性。
4. 所有数据指标（如掌握度、进步率）必须符合真实学生成长曲线，避免出现过于夸张或不合逻辑的突变。
5. 所有回答必须使用简体中文。
6. 必须严格遵守输出的JSON结构。`;

export const analyzeProblem = async (
  subject: string,
  question: string,
  studentAnswer: string,
  onProcessUpdate?: (status: string) => void
): Promise<AnalysisResult> => {
  const ai = new GoogleGenAI({ apiKey: process.env.API_KEY || '' });
  const model = "gemini-3-flash-preview";
  
  onProcessUpdate?.("正在初始化认知引擎...");
  let response = await ai.models.generateContent({
    model,
    contents: `请分析。学生：S20240101，学科：${subject}。题目：${question}。学生答案：${studentAnswer}。`,
    config: {
      systemInstruction: SYSTEM_INSTRUCTION,
      tools: [tools]
    }
  });

  if (response.functionCalls) {
    onProcessUpdate?.("正在调取云端知识图谱与历史档案...");
    const functionResponses = response.functionCalls.map(fc => {
      let resData = {};
      if (fc.name === "get_student_history") {
        resData = MOCK_DB.student_history;
      } else if (fc.name === "get_knowledge_node_detail") {
        const kp = fc.args.knowledge_point as string;
        resData = MOCK_DB.knowledge_graph[kp as keyof typeof MOCK_DB.knowledge_graph] || { info: "暂无详细记录" };
      }
      return {
        id: fc.id,
        name: fc.name,
        response: { result: resData }
      };
    });

    onProcessUpdate?.("正在结合实时数据生成深度诊断...");
    response = await ai.models.generateContent({
      model,
      contents: [
        { role: 'user', parts: [{ text: `请分析。学生：S20240101，学科：${subject}。题目：${question}。学生答案：${studentAnswer}。` }] },
        { role: 'model', parts: response.candidates[0].content.parts },
        { 
          role: 'user', 
          parts: functionResponses.map(fr => ({
            functionResponse: {
              id: fr.id,
              name: fr.name,
              response: fr.response
            }
          }))
        }
      ],
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
  }

  return JSON.parse(response.text || "{}");
};

export const getRecommendations = async (analysis: AnalysisResult): Promise<Recommendation> => {
  const ai = new GoogleGenAI({ apiKey: process.env.API_KEY || '' });
  const response = await ai.models.generateContent({
    model: "gemini-3-flash-preview",
    contents: `基于以下诊断：${JSON.stringify(analysis)}，生成学习方案。`,
    config: {
      systemInstruction: SYSTEM_INSTRUCTION,
      responseMimeType: "application/json",
      responseSchema: {
        type: Type.OBJECT,
        properties: {
          immediate_actions: {
            type: Type.ARRAY,
            items: {
              type: Type.OBJECT,
              properties: {
                type: { type: Type.STRING },
                content: { type: Type.STRING },
                resources: {
                  type: Type.ARRAY,
                  items: {
                    type: Type.OBJECT,
                    properties: {
                      id: { type: Type.STRING },
                      title: { type: Type.STRING },
                      type: { type: Type.STRING },
                      url: { type: Type.STRING }
                    }
                  }
                }
              }
            }
          },
          practice_exercises: {
            type: Type.ARRAY,
            items: {
              type: Type.OBJECT,
              properties: {
                exercise_id: { type: Type.STRING },
                question: { type: Type.STRING },
                knowledge_points: { type: Type.ARRAY, items: { type: Type.STRING } },
                difficulty: { type: Type.NUMBER }
              }
            }
          },
          learning_path: {
            type: Type.OBJECT,
            properties: {
              short_term_goals: { type: Type.ARRAY, items: { type: Type.STRING } },
              weekly_plan: {
                type: Type.ARRAY,
                items: {
                  type: Type.OBJECT,
                  properties: {
                    day: { type: Type.NUMBER },
                    tasks: { type: Type.ARRAY, items: { type: Type.STRING } }
                  }
                }
              }
            }
          }
        },
        required: ["immediate_actions", "practice_exercises", "learning_path"]
      }
    }
  });

  return JSON.parse(response.text || "{}");
};

export const getDiagnosisReport = async (studentId: string): Promise<DiagnosisReport> => {
  const ai = new GoogleGenAI({ apiKey: process.env.API_KEY || '' });
  const response = await ai.models.generateContent({
    model: "gemini-3-flash-preview",
    contents: `生成学号 ${studentId} 的成长分析报告。数据指导：掌握度评分应在0.65-0.88之间，周进步率应在0.02-0.08之间，学习稳定性在75-92之间。趋势图应表现出微小波动并总体上行。`,
    config: {
      systemInstruction: SYSTEM_INSTRUCTION,
      responseMimeType: "application/json",
      responseSchema: {
        type: Type.OBJECT,
        properties: {
          student_id: { type: Type.STRING },
          report_period: { type: Type.STRING },
          overall_assessment: {
            type: Type.OBJECT,
            properties: {
              mastery_score: { type: Type.NUMBER },
              improvement_rate: { type: Type.NUMBER },
              consistency_score: { type: Type.NUMBER }
            }
          },
          progress_trend: {
            type: Type.ARRAY,
            items: {
              type: Type.OBJECT,
              properties: {
                date: { type: Type.STRING },
                score: { type: Type.NUMBER },
                average: { type: Type.NUMBER }
              }
            }
          },
          knowledge_map: {
            type: Type.ARRAY,
            items: {
              type: Type.OBJECT,
              properties: {
                knowledge_area: { type: Type.STRING },
                mastery_level: { type: Type.NUMBER },
                weak_points: { type: Type.ARRAY, items: { type: Type.STRING } },
                strengths: { type: Type.ARRAY, items: { type: Type.STRING } }
              }
            }
          },
          error_patterns: {
            type: Type.OBJECT,
            properties: {
              most_common_error_types: {
                type: Type.ARRAY,
                items: {
                  type: Type.OBJECT,
                  properties: {
                    type: { type: Type.STRING },
                    count: { type: Type.NUMBER },
                    percentage: { type: Type.NUMBER }
                  }
                }
              }
            }
          },
          personalized_insights: { type: Type.ARRAY, items: { type: Type.STRING } }
        },
        required: ["student_id", "report_period", "overall_assessment", "progress_trend", "knowledge_map", "error_patterns", "personalized_insights"]
      }
    }
  });

  return JSON.parse(response.text || "{}");
};

export const getClassWrongProblems = async (): Promise<Array<{ id: string; question: string; errorRate: string; tags: string[] }>> => {
  const ai = new GoogleGenAI({ apiKey: process.env.API_KEY || '' });
  const response = await ai.models.generateContent({
    model: "gemini-3-flash-preview",
    contents: "生成5道班级真实高频错题。错误率应在15%-45%之间。包含难度标签。",
    config: {
      responseMimeType: "application/json",
      responseSchema: {
        type: Type.OBJECT,
        properties: {
          problems: {
            type: Type.ARRAY,
            items: {
              type: Type.OBJECT,
              properties: {
                id: { type: Type.STRING },
                question: { type: Type.STRING },
                errorRate: { type: Type.STRING },
                tags: { type: Type.ARRAY, items: { type: Type.STRING } }
              },
              required: ["id", "question", "errorRate", "tags"]
            }
          }
        },
        required: ["problems"]
      }
    }
  });
  const data = JSON.parse(response.text || "{}");
  return data.problems || [];
};
