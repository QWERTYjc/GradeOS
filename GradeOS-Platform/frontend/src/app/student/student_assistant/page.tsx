'use client';

import React, { useState } from 'react';
import DashboardLayout from '@/components/layout/DashboardLayout';
import { TechBackground } from './components/VisualEffects';
import ScoreAnalysis from './components/ScoreAnalysis';
import SubjectSelection from './components/SubjectSelection';
import AIChat from './components/AIChat';
import DataHub from './components/DataHub';
import { ICONS, I18N } from './constants';
import { Language } from './types';

type Tab = 'analysis' | 'selection' | 'chat' | 'data';

export default function StudentAssistant() {
  const [activeTab, setActiveTab] = useState<Tab>('analysis');
  const [lang, setLang] = useState<Language>('en');
  const t = I18N[lang];

  return (
    <DashboardLayout>
      <div className="min-h-screen relative flex flex-col">
        <TechBackground />
        
        <nav className="sticky top-0 z-50 bg-white/80 backdrop-blur-xl border-b border-gray-200/50 px-6 py-4">
          <div className="max-w-7xl mx-auto flex items-center justify-between">
            <div className="flex items-center gap-2 group cursor-pointer">
              <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center text-white shadow-lg shadow-blue-500/30 group-hover:scale-110 transition-transform">
                <span className="font-bold text-lg">AI</span>
              </div>
              <h1 className="text-lg font-bold tracking-tight text-gradient">{t.appName}</h1>
            </div>
            
            <div className="hidden md:flex items-center gap-6">
              <button 
                onClick={() => setActiveTab('analysis')}
                className={`text-sm font-medium transition-colors ${activeTab === 'analysis' ? 'text-blue-600' : 'text-gray-500 hover:text-gray-800'}`}
              >
                {t.academicAnalysis}
              </button>
              <button 
                onClick={() => setActiveTab('data')}
                className={`text-sm font-medium transition-colors ${activeTab === 'data' ? 'text-blue-600' : 'text-gray-500 hover:text-gray-800'}`}
              >
                {t.dataHub}
              </button>
              <button 
                onClick={() => setActiveTab('selection')}
                className={`text-sm font-medium transition-colors ${activeTab === 'selection' ? 'text-blue-600' : 'text-gray-500 hover:text-gray-800'}`}
              >
                {t.electiveSelection}
              </button>
              <button 
                onClick={() => setActiveTab('chat')}
                className={`text-sm font-medium transition-colors ${activeTab === 'chat' ? 'text-blue-600' : 'text-gray-500 hover:text-gray-800'}`}
              >
                {t.peerChat}
              </button>
            </div>

            <div className="flex items-center gap-4">
              <div className="flex bg-gray-100 p-1 rounded-full border border-gray-200 shadow-inner">
                  <button 
                      onClick={() => setLang('en')}
                      className={`px-3 py-1 text-[10px] font-bold rounded-full transition-all ${lang === 'en' ? 'bg-white text-blue-600 shadow-sm' : 'text-gray-400 hover:text-gray-600'}`}
                  >
                      EN
                  </button>
                  <button 
                      onClick={() => setLang('zh')}
                      className={`px-3 py-1 text-[10px] font-bold rounded-full transition-all ${lang === 'zh' ? 'bg-white text-blue-600 shadow-sm' : 'text-gray-400 hover:text-gray-600'}`}
                  >
                      繁
                  </button>
              </div>
              <div className="w-8 h-8 rounded-full bg-gray-200 border-2 border-white overflow-hidden shadow-sm">
                <img src="https://picsum.photos/seed/student/32/32" alt="Avatar" />
              </div>
            </div>
          </div>
        </nav>

        <main className="flex-1 relative z-10 max-w-7xl mx-auto w-full px-6 py-10">
          {activeTab === 'analysis' && <ScoreAnalysis lang={lang} />}
          {activeTab === 'data' && <DataHub lang={lang} />}
          {activeTab === 'selection' && <SubjectSelection lang={lang} />}
          {activeTab === 'chat' && <AIChat lang={lang} />}
        </main>

        {/* Mobile Tab Bar */}
        <div className="md:hidden fixed bottom-0 left-0 right-0 z-50 bg-white/90 backdrop-blur-md border-t border-gray-100 flex justify-around items-center py-3">
          <button onClick={() => setActiveTab('analysis')} className={`flex flex-col items-center gap-1 ${activeTab === 'analysis' ? 'text-blue-600' : 'text-gray-400'}`}>
            <ICONS.Analysis className="w-5 h-5" />
            <span className="text-[10px] font-bold">{lang === 'en' ? 'Analysis' : '分析'}</span>
          </button>
          <button onClick={() => setActiveTab('data')} className={`flex flex-col items-center gap-1 ${activeTab === 'data' ? 'text-blue-600' : 'text-gray-400'}`}>
            <ICONS.Edit className="w-5 h-5" />
            <span className="text-[10px] font-bold">{lang === 'en' ? 'Data' : '數據'}</span>
          </button>
          <button onClick={() => setActiveTab('selection')} className={`flex flex-col items-center gap-1 ${activeTab === 'selection' ? 'text-blue-600' : 'text-gray-400'}`}>
            <ICONS.Subject className="w-5 h-5" />
            <span className="text-[10px] font-bold">{lang === 'en' ? 'Electives' : '選科'}</span>
          </button>
          <button onClick={() => setActiveTab('chat')} className={`flex flex-col items-center gap-1 ${activeTab === 'chat' ? 'text-blue-600' : 'text-gray-400'}`}>
            <ICONS.Chat className="w-5 h-5" />
            <span className="text-[10px] font-bold">{lang === 'en' ? 'Peer AI' : '助手'}</span>
          </button>
        </div>

        <footer className="relative z-10 bg-white border-t border-gray-100 py-8 px-6 hidden md:block">
          <div className="max-w-7xl mx-auto flex flex-col md:flex-row justify-between items-center gap-6">
            <div className="text-gray-400 text-xs">
              © 2024 Academic Student Assistant. Built for all secondary school students.
            </div>
            <div className="flex gap-6">
              <a href="#" className="text-xs text-gray-500 hover:text-blue-600">Privacy Policy</a>
              <a href="#" className="text-xs text-gray-500 hover:text-blue-600">Terms of Use</a>
              <a href="#" className="text-xs text-gray-500 hover:text-blue-600">Student Resources</a>
            </div>
          </div>
        </footer>
      </div>
    </DashboardLayout>
  );
}