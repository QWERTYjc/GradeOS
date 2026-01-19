import React, { useEffect, useState } from 'react';
import { ResponsiveContainer, RadarChart, PolarGrid, PolarAngleAxis, Radar, Legend } from 'recharts';
import { COLORS, ICONS, I18N } from '../constants';
import { GlassCard, ScanningOverlay } from './VisualEffects';
import { StudyPlan, Language, ScoreEntry } from '../types';
import { assistantApi, analysisApi } from '@/services/api';
import { useAuthStore } from '@/store/authStore';

interface Props {
  lang: Language;
}

const ScoreAnalysis: React.FC<Props> = ({ lang }) => {
  const [analyzing, setAnalyzing] = useState(false);
  const [plan, setPlan] = useState<StudyPlan | null>(null);
  const [planError, setPlanError] = useState<string | null>(null);
  const [scores, setScores] = useState<ScoreEntry[]>([]);
  const [loadingScores, setLoadingScores] = useState(false);
  const { user } = useAuthStore();
  const t = I18N[lang];

  useEffect(() => {
    if (!user?.id) {
      setScores([]);
      return;
    }
    let active = true;
    setLoadingScores(true);
    analysisApi.getDiagnosisReport(user.id)
      .then((report) => {
        if (!active) return;
        const average = Math.round((report.overall_assessment?.mastery_score || 0) * 100);
        const dateValue = new Date().toISOString().slice(0, 10);
        const mapped = (report.knowledge_map || []).map((entry, idx) => ({
          id: `${entry.knowledge_area}-${idx}`,
          subject: entry.knowledge_area,
          score: Math.round((entry.mastery_level || 0) * 100),
          averageScore: average,
          date: dateValue,
          weakPoints: entry.weak_points || [],
        }));
        setScores(mapped);
      })
      .catch((error) => {
        console.error('Failed to load diagnosis report', error);
        setScores([]);
      })
      .finally(() => {
        if (active) setLoadingScores(false);
      });
    return () => {
      active = false;
    };
  }, [user?.id]);

  const parseJsonResponse = (text: string): StudyPlan | null => {
    try {
      return JSON.parse(text) as StudyPlan;
    } catch {
      const match = text.match(/\{[\s\S]*\}/);
      if (!match) return null;
      try {
        return JSON.parse(match[0]) as StudyPlan;
      } catch {
        return null;
      }
    }
  };

  const handleAnalyze = async () => {
    setAnalyzing(true);
    setPlanError(null);
    try {
      if (!user?.id) {
        throw new Error('Missing user');
      }
      const scoresData = scores.map(s =>
        `${s.subject}: ${s.score}% (average: ${s.averageScore}%, weak points: ${s.weakPoints.join(', ') || 'none'})`
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
      const response = await assistantApi.chat({
        student_id: user.id,
        class_id: user.classIds?.[0],
        message: prompt,
        history: [],
      });
      const planData = parseJsonResponse(response.content);
      if (!planData) {
        throw new Error('Invalid plan response');
      }
      setPlan(planData);
    } catch (error) {
      console.error("Failed to generate plan", error);
      setPlanError(t.brainFreeze);
    } finally {
      setAnalyzing(false);
    }
  };

  const radarData = scores.map(s => ({
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
              <p className="text-gray-500 max-w-xs">
                {scores.length ? t.turnScoreData : (lang === 'en' ? 'No score data available yet.' : '暫無成績數據')}
              </p>
              {planError && (
                <p className="text-xs text-red-500">{planError}</p>
              )}
              <button
                onClick={handleAnalyze}
                disabled={analyzing || !scores.length}
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
        {loadingScores && (
          <div className="col-span-full flex items-center justify-center h-24 text-gray-400 text-sm">
            {t.analyzing}
          </div>
        )}
        {!loadingScores && scores.length === 0 && (
          <div className="col-span-full flex items-center justify-center h-24 text-gray-400 text-sm">
            {lang === 'en' ? 'No performance data yet.' : '暫無成績資料'}
          </div>
        )}
        {scores.map((score) => (
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
