import { api, delay } from '../services/api';
import { loadDB, saveDB } from './database';
import { User, ClassEntity, Role, Homework, Submission } from '../types';
import dayjs from 'dayjs';
import { GoogleGenAI, Type } from "@google/genai";

// Utility to generate random ID
const genId = () => Math.random().toString(36).substr(2, 9);
// Utility to generate 6-char Invite Code
const genInviteCode = () => Math.random().toString(36).substr(2, 6).toUpperCase();

// --- Real AI Grading with Gemini ---
const gradeWithGemini = async (homeworkTitle: string, homeworkDesc: string, studentContent: string) => {
  try {
    if (!process.env.API_KEY) throw new Error("No Key");

    const ai = new GoogleGenAI({ apiKey: process.env.API_KEY });
    
    const response = await ai.models.generateContent({
      model: 'gemini-3-flash-preview',
      contents: `
        Task: You are a strict but encouraging teacher. Grade the following student submission based on the assignment details.
        
        Assignment Title: ${homeworkTitle}
        Assignment Instructions: ${homeworkDesc}
        
        Student Submission: "${studentContent}"
        
        Requirements:
        1. Provide a score between 0 and 100.
        2. Provide constructive feedback (max 2 sentences) highlighting what was good and what needs improvement.
      `,
      config: {
        responseMimeType: "application/json",
        responseSchema: {
          type: Type.OBJECT,
          properties: {
            score: { type: Type.NUMBER },
            feedback: { type: Type.STRING }
          }
        }
      }
    });

    const result = JSON.parse(response.text || "{}");
    return {
      score: result.score || 75,
      feedback: result.feedback || "Good effort, but I couldn't generate specific feedback."
    };

  } catch (error) {
    const score = Math.floor(Math.random() * (100 - 70 + 1)) + 70;
    return { 
      score, 
      feedback: "Automated grading (Mock): Good structure, but please expand on your examples." 
    };
  }
};

// --- Real AI Data Merging ---
const parseAndLinkWithGemini = async (internalStudents: any[], externalDataString: string) => {
    try {
        if (!externalDataString || externalDataString.trim() === '') {
            return {
                columns: [],
                matches: []
            };
        }

        if (!process.env.API_KEY) throw new Error("No Key");
    
        const ai = new GoogleGenAI({ apiKey: process.env.API_KEY });

        const prompt = `
            You are a Data Integration Assistant.
            
            Task: Match students from an uploaded CSV/Text file to a list of internal student records based on Name.
            
            Internal Students (JSON):
            ${JSON.stringify(internalStudents.map(s => ({ id: s.id, name: s.name })))}

            External Data (CSV/Text):
            "${externalDataString}"

            Instructions:
            1. Parse the External Data to find score columns (e.g., "Midterm", "Exam 1"). Ignore "Name" or "ID" columns in the output scores.
            2. Match each row in External Data to an Internal Student ID using fuzzy name matching (e.g., "Bob L." -> "Bob Liu").
            3. Return a JSON object with:
               - "columns": [Array of string names of the found score columns in external data]
               - "matches": [Array of objects { "studentId": "internal_id", "externalScores": { "ColumnName": number } }]
            4. If a student is not found in Internal list, ignore them.
        `;
        
        const response = await ai.models.generateContent({
          model: 'gemini-3-flash-preview',
          contents: prompt,
          config: {
            responseMimeType: "application/json",
            responseSchema: {
                type: Type.OBJECT,
                properties: {
                    columns: { type: Type.ARRAY, items: { type: Type.STRING } },
                    matches: { 
                        type: Type.ARRAY, 
                        items: { 
                            type: Type.OBJECT, 
                            properties: {
                                studentId: { type: Type.STRING },
                                externalScores: { type: Type.OBJECT, additionalProperties: true } // Simplified schema representation
                            }
                        } 
                    }
                }
            }
          }
        });
    
        return JSON.parse(response.text || "{ \"columns\": [], \"matches\": [] }");
    
      } catch (error) {
        console.error("Gemini Merge Failed", error);
        return { columns: [], matches: [] }; 
      }
};

export const setupMockServer = () => {
  const db = loadDB();

  api.interceptors.request.use(async (config) => {
    const isSubmit = config.url === '/homework/submit' && config.method === 'post';
    const isMerge = config.url === '/teacher/statistics/merge' && config.method === 'post';
    await delay(isSubmit || isMerge ? 1500 : 400); 
    return config;
  });

  // --- Auth Endpoints ---
  api.interceptors.response.use(
    async (response) => response, 
    async (error) => {
      const { method, url, data, params } = error.config;
      
      // Mock: Login
      if (method === 'post' && url === '/auth/login') {
        const { username, password } = JSON.parse(data);
        const user = db.users.find(u => u.username === username && u.password === password);
        
        if (user) {
          if (!user.classIds) user.classIds = [];
          return { data: user, status: 200 };
        }
        return Promise.reject({ response: { data: { message: 'Invalid credentials' }, status: 401 } });
      }

      // Mock: Teacher Create Class
      if (method === 'post' && url === '/teacher/classes') {
        const { name, teacherId } = JSON.parse(data);
        const newClass: ClassEntity = {
          id: genId(),
          name,
          teacherId,
          inviteCode: genInviteCode(),
          studentCount: 0
        };
        db.classes.push(newClass);
        saveDB(db);
        return { data: newClass, status: 201 };
      }

      // Mock: Teacher Get Classes
      if (method === 'get' && url === '/teacher/classes') {
        const teacherId = params?.teacherId;
        const classes = db.classes.filter(c => c.teacherId === teacherId);
        return { data: classes, status: 200 };
      }

      // Mock: Get Students in Class
      if (method === 'get' && url === '/class/students') {
        const classId = params?.classId;
        const students = db.users.filter(u => u.classIds && u.classIds.includes(classId));
        return { data: students, status: 200 };
      }

      // Mock: Get Student's Classes
      if (method === 'get' && url === '/student/classes') {
        const studentId = params?.studentId;
        const student = db.users.find(u => u.id === studentId);
        if (student && student.classIds) {
            const classes = db.classes.filter(c => student.classIds.includes(c.id));
            return { data: classes, status: 200 };
        }
        return { data: [], status: 200 };
      }

      // Mock: Student Join Class
      if (method === 'post' && url === '/student/join') {
        const { code, studentId } = JSON.parse(data);
        const targetClass = db.classes.find(c => c.inviteCode === code);
        
        if (!targetClass) {
          return Promise.reject({ response: { data: { message: 'Invalid invite code' }, status: 404 } });
        }

        const student = db.users.find(u => u.id === studentId);
        if (student) {
            if (!student.classIds) student.classIds = [];
            
            if (!student.classIds.includes(targetClass.id)) {
                student.classIds.push(targetClass.id);
                // Update class count
                const classIndex = db.classes.findIndex(c => c.id === targetClass.id);
                if (classIndex > -1) {
                    db.classes[classIndex].studentCount += 1;
                }
                saveDB(db);
            } else {
                 return Promise.reject({ response: { data: { message: 'You are already in this class' }, status: 400 } });
            }
            return { data: { success: true, class: targetClass }, status: 200 };
        }
      }

      // --- Homework Endpoints ---

      // Create Homework
      if (method === 'post' && url === '/homework') {
        const hwData = JSON.parse(data);
        const newHw: Homework = {
          id: genId(),
          createdAt: dayjs().format(),
          ...hwData
        };
        db.homeworks.push(newHw);
        saveDB(db);
        return { data: newHw, status: 201 };
      }

      // Get Homework
      if (method === 'get' && url === '/homework') {
        const { classId, studentId } = params || {};
        
        let resultHomeworks: Homework[] = [];

        if (studentId) {
             const student = db.users.find(u => u.id === studentId);
             if (student && student.classIds) {
                 resultHomeworks = db.homeworks.filter(h => student.classIds.includes(h.classId));
             }
        } else if (classId) {
             resultHomeworks = db.homeworks.filter(h => h.classId === classId);
        }

        if (studentId) {
          const enriched = resultHomeworks.map(h => {
            const sub = db.submissions.find(s => s.homeworkId === h.id && s.studentId === studentId);
            return {
              ...h,
              status: sub ? 'submitted' : 'pending',
              score: sub?.score,
              feedback: sub?.aiFeedback
            };
          });
          return { data: enriched, status: 200 };
        }

        return { data: resultHomeworks, status: 200 };
      }

      // Submit Homework
      if (method === 'post' && url === '/homework/submit') {
        const { homeworkId, studentId, content, studentName } = JSON.parse(data);
        const homework = db.homeworks.find(h => h.id === homeworkId);
        const title = homework?.title || "Assignment";
        const desc = homework?.description || "No instructions provided.";

        const { score, feedback } = await gradeWithGemini(title, desc, content);

        const newSubmission: Submission = {
          id: genId(),
          homeworkId,
          studentId,
          studentName,
          content,
          submittedAt: dayjs().format(),
          status: 'graded',
          score,
          aiFeedback: feedback
        };

        db.submissions.push(newSubmission);
        saveDB(db);
        return { data: newSubmission, status: 201 };
      }

      // Teacher Update Submission
      if (method === 'patch' && url === '/submission/update') {
        const { id, score, feedback } = JSON.parse(data);
        const subIndex = db.submissions.findIndex(s => s.id === id);
        
        if (subIndex > -1) {
            db.submissions[subIndex].score = score;
            db.submissions[subIndex].aiFeedback = feedback;
            saveDB(db);
            return { data: db.submissions[subIndex], status: 200 };
        }
        return Promise.reject({ response: { data: { message: 'Submission not found' }, status: 404 } });
      }

      // Get Submissions for a Homework
      if (method === 'get' && url === '/homework/submissions') {
         const { homeworkId } = params || {};
         const subs = db.submissions.filter(s => s.homeworkId === homeworkId);
         return { data: subs, status: 200 };
      }

      // --- New Endpoint: Merge Statistics & Return Raw Data for Weighting ---
      if (method === 'post' && url === '/teacher/statistics/merge') {
          const { classId, externalData } = JSON.parse(data);
          
          // 1. Gather Internal Data
          const classHomeworks = db.homeworks.filter(h => h.classId === classId);
          const classStudents = db.users.filter(u => u.classIds && u.classIds.includes(classId));
          
          // 2. Call Gemini to Parse External CSV and match to student IDs
          const { columns: externalCols, matches: externalMatches } = await parseAndLinkWithGemini(classStudents, externalData || "");

          // 3. Construct Unified Raw Data
          const unifiedData = classStudents.map(student => {
             const studentId = student.id;
             const name = student.name;
             const scores: Record<string, number | null> = {};

             // Internal Scores
             classHomeworks.forEach(hw => {
                 const sub = db.submissions.find(s => s.homeworkId === hw.id && s.studentId === studentId);
                 scores[hw.title] = sub ? (sub.score || 0) : 0;
             });

             // External Scores (from Gemini match)
             const extMatch = externalMatches.find((m: any) => m.studentId === studentId);
             if (extMatch && extMatch.externalScores) {
                 for (const key of externalCols) {
                     scores[key] = extMatch.externalScores[key] || 0;
                 }
             }

             return { id: studentId, name, scores };
          });

          return { 
              data: {
                  students: unifiedData,
                  internalAssignments: classHomeworks.map(h => h.title),
                  externalAssignments: externalCols
              }, 
              status: 200 
          };
      }

      return Promise.reject(error);
    }
  );
};