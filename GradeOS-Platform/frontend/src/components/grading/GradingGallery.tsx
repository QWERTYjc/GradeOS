'use client';

import React from 'react';
import { useConsoleStore } from '@/store/consoleStore';
import { useGradingScan } from './index';

export default function GradingGallery() {
  const { setCurrentView } = useGradingScan();
  const uploadedImages = useConsoleStore((state) => state.uploadedImages);

  return (
    <div className="h-full w-full flex flex-col">
      <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200/70 bg-white/70">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">Uploaded Pages</h3>
          <p className="text-xs text-gray-500">{uploadedImages.length} page(s)</p>
        </div>
        <button
          onClick={() => setCurrentView('scanner')}
          className="rounded-full border border-gray-300 bg-white px-4 py-2 text-xs font-medium text-gray-600 hover:border-gray-400"
        >
          Back to Scanner
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-6">
        {uploadedImages.length === 0 ? (
          <div className="h-full flex items-center justify-center text-gray-400">
            No pages uploaded yet.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {uploadedImages.map((src, idx) => (
              <div key={idx} className="rounded-2xl border border-gray-200 bg-white p-3 shadow-sm">
                <div className="text-xs text-gray-500 mb-2">Page {idx + 1}</div>
                <div className="aspect-[3/4] overflow-hidden rounded-xl bg-gray-50">
                  <img src={src} alt={`Page ${idx + 1}`} className="h-full w-full object-contain" />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
