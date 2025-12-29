import React, { useState } from 'react';
import { ResponsiveContainer, RadarChart, PolarGrid, PolarAngleAxis, Radar, Legend } from 'recharts';
import { MOCK_SCORES, COLORS, ICONS, I18N } from '../constants';
import { GlassCard, ScanningOverlay } from './VisualEffects';
import { StudyPlan, Language } from '../types';
import { geminiService } from '../services/gemini';

interface Props {
  lang: Language;
}

const ScoreAnalysis: React.FC<Props> = ({ lang }) => {
  const [analyzing, setAnalyzing] = useState(false);
  const [plan, setPlan] = useState<StudyPlan | null>(null);
  const t = I18N[lang];

  const handleAnalyze = async () => {
    setAnalyzing(true);
    try {
      // Create a prompt for Gemini to generate a study plan
      const scoresData = MOCK_SCORES.map(s => 
        `${s.subject}: ${s.score}% (average: ${s.averageScore}%, weak points: ${s.weakPoints.join(', ')})`
      ).join('\n');
      
      const prompt = `Based on these student performance scores, create a personalized weekly study plan:

${scoresData}

Please provide a structured study plan with:
1. Daily study periods (morning, afternoon, evening) with specific content and targets
2. Weekly review focus
3. Monthly checkpoint goal

Format the response as a JSON object with this structure:
{
  "dailyPlan": [
    {
      "period": "Morning (7-9 AM)",
      "content": "specific study activity",
      "target": "measurable goal"
    }
  ],
  "weeklyReview": "focus area for weekly review",
  "monthlyCheckPoint": "specific monthly goal"
}

Focus on the weak points and provide actionable, specific recommendations.`;

      const response = await geminiService.generateResponse(prompt, lang);
      
      try {
        // Try to parse JSON response
        const planData = JSON.parse(response);
        setPlan(planData);
      } catch (parseError) {
        // If JSON parsing fails, create a fallback plan
        console.warn('Failed to parse Gemini response as JSON, using fallback');
        const mockPlan: StudyPlan = {
          dailyPlan: [
            { period: 'Morning (7-9 AM)', content: 'Review weak subjects identified in analysis', target: 'Complete practice problems' },
            { period: 'Afternoon (2-4 PM)', content: 'Focus on strongest subjects for confidence building', target: 'Maintain performance level' },
            { period: 'Evening (7-9 PM)', content: 'Review and consolidate daily learning', target: 'Summarize key concepts' },
          ],
          weeklyReview: 'Focus on areas with lowest scores compared to average',
          monthlyCheckPoint: 'Improve overall performance by 5-10 points'
        };
        setPlan(mockPlan);
      }
    } catch (error) {
      console.error("Failed to generate plan", error);
      // Fallback plan if Gemini fails
      const fallbackPlan: StudyPlan = {
        dailyPlan: [
          { period: 'Morning (7-9 AM)', content: 'Review Calculus fundamentals', target: 'Complete 10 practice problems' },
          { period: 'Afternoon (2-4 PM)', content: 'Physics problem solving', target: 'Thermodynamics chapter review' },
          { period: 'Evening (7-9 PM)', content: 'Chemistry organic reactions', target: 'Memorize 20 reaction mechanisms' },
        ],
        weeklyReview: 'Focus on weak areas identified in recent tests',
        monthlyCheckPoint: 'Target: Improve Math score by 10 points'
      };
      setPlan(fallbackPlan);
    } finally {
      setAnalyzing(false);
    }
  };

  const radarData = MOCK_SCORES.map(s => ({
    subject: s.subject,
    score: s.score,
    average: s.averageScore,
    fullMark: 100
  }));

  return (
    <div className="space-y-8 animate-fadeIn">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <GlassCard className="h-[400px] flex flex-col">
          <h3 className="text-xl font-bold mb-4 flex items-center gap-2">
            <ICONS.Analysis className="w-5 h-5 text-blue-500" /> {t.performanceProfile}
          </h3>
          <div className="flex-1 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <RadarChart cx="50%" cy="50%" outerRadius="80%" data={radarData}>
                <PolarGrid stroke={COLORS.lineGray} />
                <PolarAngleAxis dataKey="subject" tick={{ fill: COLORS.inkBlack, fontSize: 10 }} />
                <Radar
                  name={lang === 'en' ? "My Score" : "我的成績"}
                  dataKey="score"
                  stroke={COLORS.azure600}
                  fill={COLORS.azure600}
                  fillOpacity={0.4}
                />
                <Radar
                  name={lang === 'en' ? "Average" : "平均分數"}
                  dataKey="average"
                  stroke={COLORS.cyanAccent}
                  fill={COLORS.cyanAccent}
                  fillOpacity={0.2}
                />
                <Legend />
              </RadarChart>
            </ResponsiveContainer>
          </div>
        </GlassCard>

        <GlassCard className="relative overflow-hidden group">
          {analyzing && <ScanningOverlay />}
          <h3 className="text-xl font-bold mb-4 flex items-center gap-2">
            <ICONS.Trophy className="w-5 h-5 text-blue-500" /> {t.weeklyOptimization}
          </h3>
          {!plan ? (
            <div className="flex flex-col items-center justify-center h-[280px] text-center space-y-4">
              <p className="text-gray-500 max-w-xs">{t.turnScoreData}</p>
              <button
                onClick={handleAnalyze}
                disabled={analyzing}
                className="bg-blue-600 text-white px-8 py-3 rounded-full font-medium shadow-lg hover:shadow-blue-500/50 transition-all active:scale-95 disabled:opacity-50"
              >
                {analyzing ? t.analyzing : t.analyzeAndPlan}
              </button>
            </div>
          ) : (
            <div className="space-y-4 max-h-[300px] overflow-y-auto pr-2 custom-scrollbar">
              {plan.dailyPlan.map((p, idx) => (
                <div key={idx} className="border-l-4 border-blue-500 pl-4 py-2 bg-blue-50/30 rounded-r-lg">
                  <div className="flex justify-between items-start">
                    <span className="text-xs font-bold text-blue-600 uppercase tracking-wider">{p.period}</span>
                    <span className="text-xs text-gray-400">Target: {p.target}</span>
                  </div>
                  <p className="text-sm mt-1">{p.content}</p>
                </div>
              ))}
              <div className="mt-6 p-4 bg-gray-50 rounded-xl border border-gray-100">
                <p className="text-sm font-semibold text-gray-700">{lang === 'en' ? 'Monthly Focus:' : '本月重點：'}</p>
                <p className="text-sm text-gray-500 mt-1 italic">{plan.monthlyCheckPoint}</p>
              </div>
              <button 
                onClick={() => setPlan(null)}
                className="text-xs text-blue-500 hover:underline mt-2"
              >
                {t.reAnalyze}
              </button>
            </div>
          )}
        </GlassCard>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {MOCK_SCORES.map((score) => (
          <GlassCard key={score.id} className="p-4 border-l-4 border-blue-600">
            <div className="flex justify-between items-center mb-2">
              <span className="font-bold">{score.subject}</span>
              <span className={`text-lg font-mono ${score.score >= 80 ? 'text-green-500' : 'text-blue-500'}`}>
                {score.score}%
              </span>
            </div>
            <div className="text-xs text-gray-500 mb-2">{t.weakSpots}:</div>
            <div className="flex flex-wrap gap-1">
              {score.weakPoints.map(wp => (
                <span key={wp} className="bg-blue-100 text-blue-700 px-2 py-0.5 rounded-md text-[10px]">
                  {wp}
                </span>
              ))}
            </div>
          </GlassCard>
        ))}
      </div>
    </div>
  );
};

export default ScoreAnalysis;