import React from 'react';
import { Language } from './types';

export const COLORS = {
  inkBlack: '#0B0F17',
  paperWhite: '#FFFFFF',
  mist: '#F5F7FB',
  azure600: '#2563EB',
  neonBlue: '#3B82F6',
  cyanAccent: '#22D3EE',
  lineGray: '#E5E7EB',
};

export const I18N = {
  en: {
    appName: 'Student Assistant',
    academicAnalysis: 'Academic Analysis',
    electiveSelection: 'Elective Selection',
    peerChat: 'Peer Chat',
    dataHub: 'Data Hub',
    performanceProfile: 'Performance Profile',
    weeklyOptimization: 'Weekly Optimization',
    analyzeAndPlan: 'Analyze & Plan',
    analyzing: 'Analyzing Data...',
    weakSpots: 'Weak spots',
    electiveNavigator: 'Elective Navigator',
    discoverPath: 'Discover your path for future studies.',
    science: 'Science',
    humanities: 'Humanities',
    business: 'Business',
    suitableMajors: 'Suitable Majors',
    viewCurriculum: 'View Detailed Curriculum',
    uniTracker: 'Uni Admission Tracker',
    uniDesc: 'Stay updated with the latest admission requirements from top universities.',
    medSchool: 'Med School',
    engineering: 'Engineering',
    law: 'Law',
    openJupas: 'Open Admission Explorer',
    peerAi: 'Peer Support AI',
    alwaysListening: 'Always Listening',
    chatPlaceholder: 'Ask me anything...',
    chatIntro: "I'm your Socratic learning agent. Share a concept and we'll rebuild it from first principles, one question at a time.",
    brainFreeze: "I'm having a bit of a brain freeze! Let's try again in a moment.",
    disclaimer: "Peer Support AI is for reference only. For serious concerns, please talk to a trusted adult.",
    reAnalyze: "Re-analyze scores",
    turnScoreData: "Let's turn your score data into a smart study journey!",
    inputScore: "Input Score",
    mistakeNotebook: "Mistake Notebook",
    subject: "Subject",
    score: "Score",
    topic: "Topic / Question",
    whyWrong: "Why was it wrong?",
    correctionNote: "How to fix it next time?",
    save: "Save Entry",
    recentMistakes: "Recent Mistakes",
    addRecord: "Add Record"
  },
  zh: {
    appName: '學業小助手',
    academicAnalysis: '學業分析',
    electiveSelection: '選科指南',
    peerChat: '同儕對話',
    dataHub: '數據中心',
    performanceProfile: '成績分析圖表',
    weeklyOptimization: '每週優化建議',
    analyzeAndPlan: '分析並生成計劃',
    analyzing: '正在分析數據...',
    weakSpots: '薄弱知識點',
    electiveNavigator: '選科導航',
    discoverPath: '探索你未來的學習方向。',
    science: '理科',
    humanities: '文科',
    business: '商科',
    suitableMajors: '相關大學專業',
    viewCurriculum: '查看詳細課程',
    uniTracker: '大學入學追踪',
    uniDesc: '掌握院校最新的入學要求。',
    medSchool: '醫學院',
    engineering: '工程學院',
    law: '法學院',
    openJupas: '開啟升學探索',
    peerAi: '同儕支援 AI',
    alwaysListening: '傾聽你的心聲',
    chatPlaceholder: '隨便聊聊...',
    chatIntro: "嘿！我是你的學業同儕助手。對考試感到壓力，或者想聊聊學業？我都在這裡聽你說！",
    brainFreeze: "哎呀，我的大腦當機了！請稍後再試。",
    disclaimer: "同儕支援 AI 僅供參考。如有嚴重困擾，請向信任的成年人尋求幫助。",
    reAnalyze: "重新分析成績",
    turnScoreData: "讓我們將你的成績數據轉化為智能學習旅程！",
    inputScore: "成績錄入",
    mistakeNotebook: "錯題本",
    subject: "科目",
    score: "分數",
    topic: "題目 / 知識點",
    whyWrong: "錯誤原因",
    correctionNote: "正確思路 / 筆記",
    save: "保存記錄",
    recentMistakes: "最近錯題",
    addRecord: "新增記錄"
  }
};

export const ICONS = {
  Analysis: (props: React.SVGProps<SVGSVGElement>) => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="M21.21 15.89A10 10 0 1 1 8 2.83" />
      <path d="M22 12A10 10 0 0 0 12 2v10z" />
    </svg>
  ),
  Subject: (props: React.SVGProps<SVGSVGElement>) => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" />
      <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />
    </svg>
  ),
  Chat: (props: React.SVGProps<SVGSVGElement>) => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </svg>
  ),
  Trophy: (props: React.SVGProps<SVGSVGElement>) => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6" />
      <path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18" />
      <path d="M4 22h16" />
      <path d="M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20.24 7 22" />
      <path d="M14 14.66V17c0 .55.47.98.97 1.21C16.15 18.75 17 20.24 17 22" />
      <path d="M18 2H6v7a6 6 0 0 0 12 0V2Z" />
    </svg>
  ),
  Edit: (props: React.SVGProps<SVGSVGElement>) => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
      <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
    </svg>
  ),
};
