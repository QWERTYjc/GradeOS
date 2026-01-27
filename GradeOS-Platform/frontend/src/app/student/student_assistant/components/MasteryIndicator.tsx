'use client';

import React, { useEffect, useState } from 'react';

interface MasteryIndicatorProps {
  score: number;
  level: string;
  analysis?: string;
  evidence?: string[];
  suggestions?: string[];
  showDetails?: boolean;
  size?: 'sm' | 'md' | 'lg';
}

const MasteryIndicator: React.FC<MasteryIndicatorProps> = ({
  score,
  level,
  analysis,
  evidence = [],
  suggestions = [],
  showDetails = false,
  size = 'md',
}) => {
  const [animatedScore, setAnimatedScore] = useState(0);
  const [expanded, setExpanded] = useState(showDetails);

  useEffect(() => {
    const duration = 900;
    const steps = 60;
    const increment = score / steps;
    let current = 0;

    const timer = setInterval(() => {
      current += increment;
      if (current >= score) {
        setAnimatedScore(score);
        clearInterval(timer);
      } else {
        setAnimatedScore(Math.round(current));
      }
    }, duration / steps);

    return () => clearInterval(timer);
  }, [score]);

  const getTone = (s: number) => {
    if (s >= 76) return { primary: '#111827', secondary: '#E5E7EB', text: 'Mastery' };
    if (s >= 51) return { primary: '#1F2937', secondary: '#F3F4F6', text: 'Proficient' };
    if (s >= 26) return { primary: '#374151', secondary: '#F9FAFB', text: 'Developing' };
    return { primary: '#6B7280', secondary: '#F3F4F6', text: 'Beginner' };
  };

  const tone = getTone(animatedScore);

  const sizeConfig = {
    sm: { container: 80, stroke: 6, fontSize: 'text-lg', labelSize: 'text-xs' },
    md: { container: 120, stroke: 8, fontSize: 'text-2xl', labelSize: 'text-sm' },
    lg: { container: 160, stroke: 10, fontSize: 'text-4xl', labelSize: 'text-base' },
  };

  const config = sizeConfig[size];
  const radius = (config.container - config.stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (animatedScore / 100) * circumference;

  const getLevelMarker = () => {
    switch (level) {
      case 'mastery':
        return 'M';
      case 'proficient':
        return 'P';
      case 'developing':
        return 'D';
      default:
        return 'B';
    }
  };

  return (
    <div className="flex flex-col items-center gap-4">
      <div
        className="relative cursor-pointer transition-transform hover:scale-105"
        style={{ width: config.container, height: config.container }}
        onClick={() => setExpanded(!expanded)}
      >
        <svg width={config.container} height={config.container} className="-rotate-90 transform">
          <circle
            cx={config.container / 2}
            cy={config.container / 2}
            r={radius}
            fill="none"
            stroke={tone.secondary}
            strokeWidth={config.stroke}
          />
          <circle
            cx={config.container / 2}
            cy={config.container / 2}
            r={radius}
            fill="none"
            stroke={tone.primary}
            strokeWidth={config.stroke}
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            strokeLinecap="round"
            className="transition-all duration-1000 ease-out"
          />
        </svg>

        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className={`${config.fontSize} font-bold`} style={{ color: tone.primary }}>
            {animatedScore}
          </span>
          <span className={`${config.labelSize} text-black/50`}>Mastery</span>
        </div>
      </div>

      <div
        className="flex items-center gap-2 rounded-full px-4 py-2"
        style={{ backgroundColor: tone.secondary }}
      >
        <span className="text-xs font-semibold text-black/70">{getLevelMarker()}</span>
        <span className={`font-medium ${config.labelSize}`} style={{ color: tone.primary }}>
          {tone.text}
        </span>
      </div>

      {expanded && (analysis || evidence.length > 0 || suggestions.length > 0) && (
        <div className="w-full max-w-sm space-y-4 border-l-2 border-black/10 pl-4 text-sm text-black/70 animate-fadeIn">
          {analysis && (
            <div>
              <h4 className="text-xs font-semibold uppercase tracking-[0.2em] text-black/40">Insight</h4>
              <p className="mt-1 text-sm text-black/70">{analysis}</p>
            </div>
          )}

          {evidence.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold uppercase tracking-[0.2em] text-black/40">Evidence</h4>
              <ul className="mt-2 space-y-2">
                {evidence.map((item, idx) => (
                  <li key={idx} className="flex items-start gap-2 text-sm text-black/70">
                    <span className="mt-1 inline-block h-2 w-2 rounded-full bg-black/60" />
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {suggestions.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold uppercase tracking-[0.2em] text-black/40">Next steps</h4>
              <ul className="mt-2 space-y-2">
                {suggestions.map((item, idx) => (
                  <li key={idx} className="flex items-start gap-2 text-sm text-black/70">
                    <span className="mt-1 inline-block h-2 w-2 rounded-full bg-black/40" />
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {(analysis || evidence.length > 0 || suggestions.length > 0) && (
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-xs uppercase tracking-[0.2em] text-black/40 transition-colors hover:text-black/70"
        >
          {expanded ? 'Hide details' : 'View details'}
        </button>
      )}
    </div>
  );
};

export default MasteryIndicator;
