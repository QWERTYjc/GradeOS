'use client';

import React, { useState, useRef, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import DashboardLayout from '@/components/layout/DashboardLayout';
import { ChatMessage, Language, ScoreEntry, Subject, StudyPlan } from '@/types';
import {
  ResponsiveContainer,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  Radar,
  Legend
} from 'recharts';

// Mock data
const MOCK_SCORES: ScoreEntry[] = [
  { id: '1', subject: Subject.MATH, score: 78, averageScore: 72, date: '2024-12', weakPoints: ['Calculus', 'Geometry'] },
  { id: '2', subject: Subject.PHYSICS, score: 85, averageScore: 70, date: '2024-12', weakPoints: ['Thermodynamics'] },
  { id: '3', subject: Subject.CHEMISTRY, score: 72, averageScore: 68, date: '2024-12', weakPoints: ['Organic Chemistry'] },
  { id: '4', subject: Subject.ENGLISH, score: 88, averageScore: 75, date: '2024-12', weakPoints: ['Writing'] },
  { id: '5', subject: Subject.CHINESE, score: 82, averageScore: 78, date: '2024-12', weakPoints: ['Classical Chinese'] },
];

type Tab = 'chat' | 'analysis' | 'data';

export default function StudentAssistant() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<Tab>('chat');
  const [lang, setLang] = useState<Language>('en');
  const [messages, setMessages] = useState<ChatMessage[]>([
    { role: 'assistant', content: 'Hello! I\'m your AI study assistant. How can I help you today?', timestamp: new Date() }
  ]);
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [plan, setPlan] = useState<StudyPlan | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSend = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!input.trim() || isStreaming) return;

    const userMsg = input;
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: userMsg, timestamp: new Date() }]);
    setIsStreaming(true);

    // Simulate AI response
    await new Promise(r => setTimeout(r, 1500));
    
    const responses = [
      'Based on your performance data, I recommend focusing on Calculus this week. Would you like me to create a study plan?',
      'Great question! Let me analyze your weak points and suggest some resources.',
      'I can see you\'re doing well in English. Keep up the good work! For Math, try practicing more problem sets.',
    ];
    
    setMessages(prev => [...prev, {
      role: 'assistant',
      content: responses[Math.floor(Math.random() * responses.length)],
      timestamp: new Date()
    }]);
    setIsStreaming(false);
  };

  const handleAnalyze = async () => {
    setAnalyzing(true);
    await new Promise(r => setTimeout(r, 2000));
    setPlan({
      dailyPlan: [
        { period: 'Morning (7-9 AM)', content: 'Review Calculus fundamentals', target: 'Complete 10 practice problems' },
        { period: 'Afternoon (2-4 PM)', content: 'Physics problem solving', target: 'Thermodynamics chapter review' },
        { period: 'Evening (7-9 PM)', content: 'Chemistry organic reactions', target: 'Memorize 20 reaction mechanisms' },
      ],
      weeklyReview: 'Focus on weak areas identified in recent tests',
      monthlyCheckPoint: 'Target: Improve Math score by 10 points'
    });
    setAnalyzing(false);
  };

  const radarData = MOCK_SCORES.map(s => ({
    subject: s.subject,
    score: s.score,
    average: s.averageScore,
  }));

  const tabs = [
    { id: 'chat' as Tab, label: '💬 AI Chat', icon: '💬' },
    { id: 'analysis' as Tab, label: '📊 Analysis', icon: '📊' },
    { id: 'data' as Tab, label: '📝 Data Hub', icon: '📝' },
  ];

  return (
    <DashboardLayout>
      <div className="max-w-5xl mx-auto">
        {/* Enhanced Assistant Promotion Banner */}
        <div className="mb-6 bg-gradient-to-r from-blue-600 to-cyan-500 rounded-xl p-6 text-white relative overflow-hidden">
          <div className="relative z-10">
            <div className="flex items-center justify-between">
              <div className="flex-1">
                <h2 className="text-xl font-bold mb-2 flex items-center gap-2">
                  ✨ Enhanced Student Assistant Available!
                </h2>
                <p className="text-blue-100 mb-4 max-w-2xl">
                  Experience our new comprehensive study companion with advanced features: 
                  Academic Analysis, Subject Selection Guide, Enhanced AI Chat, and Data Management Hub.
                </p>
                <div className="flex flex-wrap gap-2 text-sm">
                  <span className="bg-white/20 px-3 py-1 rounded-full">📊 Performance Analytics</span>
                  <span className="bg-white/20 px-3 py-1 rounded-full">🎯 Subject Selection</span>
                  <span className="bg-white/20 px-3 py-1 rounded-full">🤖 Advanced AI Chat</span>
                  <span className="bg-white/20 px-3 py-1 rounded-full">📝 Data Hub</span>
                </div>
              </div>
              <div className="ml-6">
                <button
                  onClick={() => router.push('/student/student_assistant')}
                  className="bg-white text-blue-600 px-6 py-3 rounded-xl font-bold shadow-lg hover:shadow-xl transform hover:scale-105 transition-all duration-200 flex items-center gap-2"
                >
                  Try Enhanced Version
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
                  </svg>
                </button>
              </div>
            </div>
          </div>
          <div className="absolute top-0 right-0 w-32 h-32 bg-white/10 rounded-full -translate-y-1/2 translate-x-1/2 blur-2xl"></div>
          <div className="absolute bottom-0 left-0 w-24 h-24 bg-cyan-300/20 rounded-full translate-y-1/2 -translate-x-1/2 blur-xl"></div>
        </div>

        {/* Tab Navigation */}
        <div className="flex gap-2 mb-6 bg-white p-2 rounded-xl border border-slate-200">
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex-1 py-3 rounded-lg font-medium transition-all ${
                activeTab === tab.id
                  ? 'bg-blue-600 text-white'
                  : 'text-slate-600 hover:bg-slate-100'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Chat Tab */}
        {activeTab === 'chat' && (
          <div className="bg-white rounded-xl border border-slate-200 h-[600px] flex flex-col">
            <div className="flex-1 overflow-y-auto p-6" ref={scrollRef}>
              {messages.map((msg, idx) => (
                <div key={idx} className={`mb-4 flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`max-w-[80%] p-4 rounded-2xl ${
                    msg.role === 'user'
                      ? 'bg-blue-600 text-white rounded-br-md'
                      : 'bg-slate-100 text-slate-800 rounded-bl-md'
                  }`}>
                    {msg.content}
                  </div>
                </div>
              ))}
              {isStreaming && (
                <div className="flex justify-start">
                  <div className="bg-slate-100 p-4 rounded-2xl rounded-bl-md">
                    <div className="flex gap-1">
                      <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" />
                      <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }} />
                      <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }} />
                    </div>
                  </div>
                </div>
              )}
            </div>
            <form onSubmit={handleSend} className="p-4 border-t border-slate-200">
              <div className="flex gap-2">
                <input
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="Ask me anything about your studies..."
                  className="flex-1 px-4 py-3 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500"
                  disabled={isStreaming}
                />
                <button
                  type="submit"
                  disabled={!input.trim() || isStreaming}
                  className="px-6 py-3 bg-blue-600 text-white rounded-xl hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                >
                  Send
                </button>
              </div>
            </form>
          </div>
        )}

        {/* Analysis Tab */}
        {activeTab === 'analysis' && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-white rounded-xl border border-slate-200 p-6 h-[400px]">
              <h3 className="font-bold text-slate-800 mb-4">📊 Performance Profile</h3>
              <ResponsiveContainer width="100%" height="85%">
                <RadarChart data={radarData}>
                  <PolarGrid stroke="#e2e8f0" />
                  <PolarAngleAxis dataKey="subject" tick={{ fill: '#64748b', fontSize: 10 }} />
                  <Radar name="My Score" dataKey="score" stroke="#2563eb" fill="#2563eb" fillOpacity={0.4} />
                  <Radar name="Average" dataKey="average" stroke="#06b6d4" fill="#06b6d4" fillOpacity={0.2} />
                  <Legend />
                </RadarChart>
              </ResponsiveContainer>
            </div>

            <div className="bg-white rounded-xl border border-slate-200 p-6">
              <h3 className="font-bold text-slate-800 mb-4">🏆 Weekly Study Plan</h3>
              {!plan ? (
                <div className="flex flex-col items-center justify-center h-[280px]">
                  <p className="text-slate-500 mb-4 text-center">Turn your score data into an actionable study plan</p>
                  <button
                    onClick={handleAnalyze}
                    disabled={analyzing}
                    className="px-6 py-3 bg-blue-600 text-white rounded-xl hover:bg-blue-700 disabled:opacity-50"
                  >
                    {analyzing ? 'Analyzing...' : '✨ Generate Plan'}
                  </button>
                </div>
              ) : (
                <div className="space-y-3 max-h-[280px] overflow-y-auto">
                  {plan.dailyPlan.map((p, idx) => (
                    <div key={idx} className="border-l-4 border-blue-500 pl-4 py-2 bg-blue-50 rounded-r-lg">
                      <div className="flex justify-between">
                        <span className="text-xs font-bold text-blue-600">{p.period}</span>
                        <span className="text-xs text-slate-400">{p.target}</span>
                      </div>
                      <p className="text-sm mt-1">{p.content}</p>
                    </div>
                  ))}
                  <div className="mt-4 p-3 bg-slate-50 rounded-lg">
                    <p className="text-sm text-slate-600">{plan.monthlyCheckPoint}</p>
                  </div>
                  <button onClick={() => setPlan(null)} className="text-xs text-blue-500 hover:underline">
                    Re-analyze
                  </button>
                </div>
              )}
            </div>

            <div className="lg:col-span-2 grid grid-cols-2 md:grid-cols-4 gap-4">
              {MOCK_SCORES.slice(0, 4).map(score => (
                <div key={score.id} className="bg-white rounded-xl border border-slate-200 p-4 border-l-4 border-l-blue-600">
                  <div className="flex justify-between items-center mb-2">
                    <span className="font-bold text-sm">{score.subject}</span>
                    <span className={`text-lg font-mono ${score.score >= 80 ? 'text-green-500' : 'text-blue-500'}`}>
                      {score.score}%
                    </span>
                  </div>
                  <div className="text-xs text-slate-500 mb-1">Weak spots:</div>
                  <div className="flex flex-wrap gap-1">
                    {score.weakPoints.map(wp => (
                      <span key={wp} className="bg-blue-100 text-blue-700 px-2 py-0.5 rounded text-[10px]">
                        {wp}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Data Hub Tab */}
        {activeTab === 'data' && (
          <div className="bg-white rounded-xl border border-slate-200 p-6">
            <h3 className="font-bold text-slate-800 mb-6">📝 Data Hub</h3>
            <p className="text-slate-500 text-center py-20">
              Coming soon: Manual score input and mistake notebook
            </p>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
