
export enum QuestionType {
  MULTIPLE_CHOICE = '选择题',
  FILL_IN = '填空题',
  OPEN_ENDED = '解答题'
}

export enum ErrorType {
  CONCEPT = '概念错误',
  CALCULATION = '计算错误',
  UNDERSTANDING = '理解偏差',
  MISREADING = '审题错误'
}

export interface AnalysisResult {
  error_type: string;
  error_severity: 'high' | 'medium' | 'low';
  knowledge_gaps: Array<{
    knowledge_point: string;
    mastery_level: number;
    confidence: number;
  }>;
  detailed_analysis: {
    step_by_step_correction: string[];
    common_mistakes: string;
    correct_solution: string;
  };
  root_cause: string;
}

export interface Recommendation {
  immediate_actions: Array<{
    type: string;
    content: string;
    resources: Array<{
      id: string;
      title: string;
      type: 'video' | 'exercise' | 'text';
      url: string;
    }>;
  }>;
  practice_exercises: Array<{
    exercise_id: string;
    question: string;
    knowledge_points: string[];
    difficulty: number;
  }>;
  learning_path: {
    short_term_goals: string[];
    weekly_plan: Array<{
      day: number;
      tasks: string[];
    }>;
  };
}

export interface DiagnosisReport {
  student_id: string;
  report_period: string;
  overall_assessment: {
    mastery_score: number;
    improvement_rate: number;
    consistency_score: number;
  };
  progress_trend: Array<{
    date: string;
    score: number;
    average: number;
  }>;
  knowledge_map: Array<{
    knowledge_area: string;
    mastery_level: number;
    weak_points: string[];
    strengths: string[];
  }>;
  error_patterns: {
    most_common_error_types: Array<{ type: string; count: number; percentage: number }>;
  };
  personalized_insights: string[];
}
