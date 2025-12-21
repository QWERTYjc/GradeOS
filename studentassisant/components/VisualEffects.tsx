
import React from 'react';

export const TechBackground: React.FC = () => (
  <div className="fixed inset-0 pointer-events-none z-0 overflow-hidden">
    <div className="tech-grid absolute inset-0"></div>
    <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-blue-100 rounded-full blur-[120px] opacity-40"></div>
    <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-cyan-100 rounded-full blur-[120px] opacity-40"></div>
  </div>
);

export const GlassCard: React.FC<{ children: React.ReactNode; className?: string }> = ({ children, className = "" }) => (
  <div className={`bg-white/70 backdrop-blur-md border border-white/40 rounded-2xl p-6 transition-all duration-300 hover:shadow-xl hover:border-blue-200/50 ${className}`}>
    {children}
  </div>
);

export const ScanningOverlay: React.FC = () => (
  <div className="absolute inset-0 overflow-hidden pointer-events-none rounded-2xl opacity-20">
    <div className="scanning-line"></div>
  </div>
);
