
import { ClassProblem, AnalysisResult, SavedProblem } from "../types";

// 环境配置：通过变量控制数据库模式
const IS_COMPLETE_VERSION = false; // 修改此值切换 离线版 (SQLite模拟) / 完整版 (PostgreSQL)

const BASE_URL = '/api';

/**
 * 模拟离线数据库操作 (SQLite 逻辑)
 * 在前端环境中，我们使用 localStorage 或 IndexedDB 模拟 SQLite 的持久化行为
 */
const sqliteMock = {
  save: (data: SavedProblem) => {
    const table = JSON.parse(localStorage.getItem('sqlite_error_table') || '[]');
    table.unshift(data);
    localStorage.setItem('sqlite_error_table', JSON.stringify(table));
    console.log("[SQLite] 数据已存入本地离线数据库 (table: error_problems)");
  },
  queryAll: (): SavedProblem[] => {
    return JSON.parse(localStorage.getItem('sqlite_error_table') || '[]');
  }
};

/**
 * 模拟完整版数据库操作 (PostgreSQL 逻辑)
 * 通过标准 REST API 与后端 PostgreSQL 交互
 */
const postgreMock = {
  sync: async (data: SavedProblem) => {
    console.log("[PostgreSQL] 正在同步数据至远程云端数据库...");
    // 实际生产环境下会使用 fetch(`${BASE_URL}/problems`, { method: 'POST', ... })
    try {
      const response = await fetch(`${BASE_URL}/db/sync`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: "INSERT INTO error_problems (id, subject, question, analysis) VALUES ($1, $2, $3, $4)",
          values: [data.id, data.subject, data.question, data.analysis]
        })
      });
      return response.ok;
    } catch (e) {
      // 演示环境模拟成功
      return true;
    }
  }
};

const transformHomeworkToError = (hw: any): SavedProblem => ({
  id: `hw_${hw.id}`,
  timestamp: Date.now() - (Math.random() * 100000000),
  subject: '数学',
  question: hw.question,
  analysis: {
    error_type: hw.errorType || '逻辑推导错误',
    error_severity: 'medium',
    knowledge_gaps: [{ knowledge_point: hw.tags[0], mastery_level: 0.4, confidence: 0.9 }],
    detailed_analysis: {
      step_by_step_correction: ['重新审题', '确定隐含条件', '代入公式计算'],
      common_mistakes: '忽略了定义域限制',
      correct_solution: '依据题目条件，x > 0...'
    },
    root_cause: `作业批改发现：${hw.comment || '知识点掌握不牢固'}`
  }
});

export const api = {
  config: {
    isComplete: IS_COMPLETE_VERSION
  },
  
  auth: {
    getUserInfo: () => fetch(`${BASE_URL}/user/info`).then(res => res.json()),
  },

  class: {
    getWrongProblems: async (): Promise<ClassProblem[]> => {
      return [
        { id: 'cp_001', question: '已知函数 f(x) = sin(ωx + φ) 的最小正周期为 π，则 ω = ?', errorRate: '65%', tags: ['三角函数', '周期性'] },
        { id: 'cp_002', question: '在等差数列 {an} 中，a1=2, a3=6, 求前10项和 S10。', errorRate: '42%', tags: ['等差数列', '求和公式'] },
        { id: 'cp_003', question: '若向量 a=(1,2), b=(x,1) 且 a⊥b，求 x。', errorRate: '38%', tags: ['向量垂直', '数量积'] }
      ];
    }
  },

  homework: {
    getFlaggedHomework: async (): Promise<SavedProblem[]> => {
      const mockHomeworkErrors = [
        { id: '101', question: '解方程：log₂(x-1) = 3', tags: ['对数方程'], errorType: '运算错误', comment: '注意对数符号内部必须大于0' },
        { id: '102', question: '求导数：y = x * e^x', tags: ['导数运算法则'], errorType: '公式记忆模糊', comment: '乘积求导法则运用不熟练' }
      ];
      return mockHomeworkErrors.map(transformHomeworkToError);
    }
  },

  database: {
    saveProblem: async (problem: SavedProblem) => {
      if (IS_COMPLETE_VERSION) {
        await postgreMock.sync(problem);
      } else {
        sqliteMock.save(problem);
      }
    },
    loadProblems: async (): Promise<SavedProblem[]> => {
      if (IS_COMPLETE_VERSION) {
        // 模拟从 PostgreSQL 获取数据
        const response = await fetch(`${BASE_URL}/db/list`);
        if (response.ok) return await response.json();
        return sqliteMock.queryAll(); // 降级处理
      } else {
        return sqliteMock.queryAll();
      }
    }
  }
};
