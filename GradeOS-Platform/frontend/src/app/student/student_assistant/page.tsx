'use client';

import React, { Suspense } from 'react';
import AIChat from './components/AIChat';

function LoadingFallback() {
  return (
    <div className="min-h-screen bg-white flex items-center justify-center">
      <div className="text-center">
        <div className="w-8 h-8 border-2 border-black/20 border-t-black rounded-full animate-spin mx-auto mb-4" />
        <p className="text-sm text-black/60">加载学习助手...</p>
      </div>
    </div>
  );
}

export default function StudentAssistant() {
  return (
    <Suspense fallback={<LoadingFallback />}>
      <AIChat />
    </Suspense>
  );
}
