'use client';

import React, { createContext, useContext, useMemo, useState } from 'react';

type GradingView = 'scanner' | 'gallery';

interface GradingScanContextValue {
  currentView: GradingView;
  setCurrentView: (view: GradingView) => void;
  toggleView: () => void;
}

const GradingScanContext = createContext<GradingScanContextValue | undefined>(undefined);

export function GradingScanProvider({ children }: { children: React.ReactNode }) {
  const [currentView, setCurrentView] = useState<GradingView>('scanner');
  const toggleView = () => setCurrentView((prev) => (prev === 'scanner' ? 'gallery' : 'scanner'));
  const value = useMemo(() => ({ currentView, setCurrentView, toggleView }), [currentView]);

  return (
    <GradingScanContext.Provider value={value}>
      {children}
    </GradingScanContext.Provider>
  );
}

export function useGradingScan() {
  const context = useContext(GradingScanContext);
  if (!context) {
    throw new Error('useGradingScan must be used within GradingScanProvider');
  }
  return context;
}

export { default as GradingScanner } from './GradingScanner';
export { default as GradingGallery } from './GradingGallery';
