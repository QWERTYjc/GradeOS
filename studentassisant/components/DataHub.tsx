
import React, { useState } from 'react';
import { GlassCard } from './VisualEffects';
import { I18N, ICONS } from '../constants';
import { Language, WrongQuestion, Subject } from '../types';

interface Props {
  lang: Language;
}

const DataHub: React.FC<Props> = ({ lang }) => {
  const t = I18N[lang];
  const [activeForm, setActiveForm] = useState<'score' | 'mistake'>('score');
  const [mistakes, setMistakes] = useState<WrongQuestion[]>([]);

  // Score Form State
  const [scoreSubject, setScoreSubject] = useState<Subject>(Subject.MATH);
  const [scoreValue, setScoreValue] = useState<number>(0);

  // Mistake Form State
  const [mistakeSubject, setMistakeSubject] = useState<Subject>(Subject.MATH);
  const [topic, setTopic] = useState('');
  const [description, setDescription] = useState('');
  const [correction, setCorrection] = useState('');

  const handleSaveMistake = () => {
    if (!topic || !description) return;
    const newMistake: WrongQuestion = {
      id: Date.now().toString(),
      subject: mistakeSubject,
      topic,
      description,
      correction,
      date: new Date().toLocaleDateString()
    };
    setMistakes([newMistake, ...mistakes]);
    setTopic('');
    setDescription('');
    setCorrection('');
  };

  const inputClasses = "w-full bg-white border border-gray-200 rounded-xl px-4 py-3 text-sm text-black placeholder:text-gray-400 shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all";

  return (
    <div className="space-y-8 animate-fadeIn max-w-5xl mx-auto">
      <header className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-black">{t.dataHub}</h2>
          <p className="text-gray-500">{lang === 'en' ? 'Track your growth manually.' : '手動記錄你的成長軌跡。'}</p>
        </div>
        <div className="flex bg-gray-100 p-1 rounded-xl">
          <button
            onClick={() => setActiveForm('score')}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              activeForm === 'score' ? 'bg-white shadow-sm text-blue-600' : 'text-gray-500 hover:text-gray-800'
            }`}
          >
            {t.inputScore}
          </button>
          <button
            onClick={() => setActiveForm('mistake')}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              activeForm === 'mistake' ? 'bg-white shadow-sm text-blue-600' : 'text-gray-500 hover:text-gray-800'
            }`}
          >
            {t.mistakeNotebook}
          </button>
        </div>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Input Side */}
        <div className="lg:col-span-5">
          <GlassCard className="h-full bg-white/90">
            <h3 className="text-lg font-bold mb-6 flex items-center gap-2 text-black">
              <ICONS.Edit className="w-5 h-5 text-blue-600" />
              {activeForm === 'score' ? t.inputScore : t.mistakeNotebook}
            </h3>

            {activeForm === 'score' ? (
              <div className="space-y-6">
                <div>
                  <label className="block text-xs font-bold text-gray-500 uppercase tracking-wider mb-2">{t.subject}</label>
                  <select 
                    value={scoreSubject}
                    onChange={(e) => setScoreSubject(e.target.value as Subject)}
                    className={inputClasses}
                  >
                    {(Object.values(Subject) as Subject[]).map(s => <option key={s} value={s}>{s}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-bold text-gray-500 uppercase tracking-wider mb-2">{t.score} (%)</label>
                  <input 
                    type="number"
                    min="0" max="100"
                    value={scoreValue}
                    onChange={(e) => setScoreValue(parseInt(e.target.value) || 0)}
                    className={inputClasses}
                  />
                </div>
                <button className="w-full bg-blue-600 text-white py-4 rounded-xl font-bold shadow-lg shadow-blue-500/20 hover:bg-blue-700 transition-all">
                  {t.save}
                </button>
              </div>
            ) : (
              <div className="space-y-4">
                <div>
                  <label className="block text-xs font-bold text-gray-500 uppercase tracking-wider mb-2">{t.subject}</label>
                  <select 
                    value={mistakeSubject}
                    onChange={(e) => setMistakeSubject(e.target.value as Subject)}
                    className={inputClasses}
                  >
                    {(Object.values(Subject) as Subject[]).map(s => <option key={s} value={s}>{s}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-bold text-gray-500 uppercase tracking-wider mb-2">{t.topic}</label>
                  <input 
                    type="text"
                    value={topic}
                    onChange={(e) => setTopic(e.target.value)}
                    placeholder="e.g. Quadratic Formula Application"
                    className={inputClasses}
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-gray-500 uppercase tracking-wider mb-2">{t.whyWrong}</label>
                  <textarea 
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    rows={2}
                    className={inputClasses}
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold text-gray-500 uppercase tracking-wider mb-2">{t.correctionNote}</label>
                  <textarea 
                    value={correction}
                    onChange={(e) => setCorrection(e.target.value)}
                    rows={2}
                    className={inputClasses}
                  />
                </div>
                <button 
                  onClick={handleSaveMistake}
                  className="w-full bg-blue-600 text-white py-4 rounded-xl font-bold shadow-lg shadow-blue-500/20 hover:bg-blue-700 transition-all"
                >
                  {t.save}
                </button>
              </div>
            )}
          </GlassCard>
        </div>

        {/* Display Side */}
        <div className="lg:col-span-7">
          <h3 className="text-sm font-bold text-gray-400 uppercase tracking-widest mb-4">{t.recentMistakes}</h3>
          <div className="space-y-4 max-h-[600px] overflow-y-auto pr-2 custom-scrollbar">
            {mistakes.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-20 text-gray-300">
                <ICONS.Edit className="w-12 h-12 mb-2 opacity-20" />
                <p>{lang === 'en' ? 'No records yet. Start logging your challenges.' : '尚無記錄。開始記錄你的學業挑戰吧。'}</p>
              </div>
            ) : (
              mistakes.map(m => (
                <GlassCard key={m.id} className="p-4 border-l-4 border-blue-600 bg-white/95">
                  <div className="flex justify-between items-start mb-2">
                    <span className="bg-blue-100 text-blue-700 text-[10px] font-bold px-2 py-0.5 rounded">
                      {m.subject}
                    </span>
                    <span className="text-[10px] text-gray-400">{m.date}</span>
                  </div>
                  <h4 className="font-bold text-black mb-1">{m.topic}</h4>
                  <div className="bg-gray-50 rounded-lg p-3 mb-2 border border-gray-100">
                    <p className="text-xs text-gray-600 italic">"{m.description}"</p>
                  </div>
                  {m.correction && (
                    <div className="flex gap-2 items-start">
                      <div className="mt-1 w-2 h-2 rounded-full bg-green-500"></div>
                      <p className="text-xs text-green-700 font-medium">{m.correction}</p>
                    </div>
                  )}
                </GlassCard>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default DataHub;
