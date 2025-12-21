
import React, { useState } from 'react';
import { ResponsiveContainer, RadarChart, PolarGrid, PolarAngleAxis, Radar, Legend } from 'recharts';
import { MOCK_SCORES, COLORS, ICONS, I18N } from '../constants';
import { GlassCard, ScanningOverlay } from './VisualEffects';
import { generateStudyPlan } from '../services/gemini';
import { StudyPlan, Language } from '../types';

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
      const result = await generateStudyPlan(MOCK_SCORES, lang);
      setPlan(result);
    } catch (error) {
      console.error("Failed to generate plan", error);
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
