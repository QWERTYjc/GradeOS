'use client';

import React from 'react';
import { motion } from 'framer-motion';
import { useConsoleStore } from '@/store/consoleStore';
import { useGradingScan } from './index';
import { GlassCard } from '@/components/design-system/GlassCard';
import { SmoothButton } from '@/components/design-system/SmoothButton';
import { ArrowLeft, Image as ImageIcon } from 'lucide-react';

export default function GradingGallery() {
  const { setCurrentView } = useGradingScan();
  const uploadedImages = useConsoleStore((state) => state.uploadedImages);

  const container = {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: {
        staggerChildren: 0.1
      }
    }
  };

  const item = {
    hidden: { y: 20, opacity: 0 },
    show: { y: 0, opacity: 1 }
  };

  return (
    <div className="h-full w-full flex flex-col">
      <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200/50 bg-white/40 backdrop-blur-md sticky top-0 z-10">
        <div>
          <h3 className="text-xl font-bold bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent">
            Uploaded Pages
          </h3>
          <p className="text-xs text-gray-500 font-medium tracking-wide mt-1">
            {uploadedImages.length} PAGE{uploadedImages.length !== 1 ? 'S' : ''} DETECTED
          </p>
        </div>
        <SmoothButton
          variant="secondary"
          size="sm"
          onClick={() => setCurrentView('scanner')}
          className="group"
        >
          <ArrowLeft className="w-4 h-4 mr-2 transition-transform group-hover:-translate-x-1" />
          Back to Scanner
        </SmoothButton>
      </div>

      <motion.div
        className="flex-1 overflow-y-auto p-6 scrollbar-thin scrollbar-thumb-gray-300 scrollbar-track-transparent"
        variants={container}
        initial="hidden"
        animate="show"
      >
        {uploadedImages.length === 0 ? (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="h-full flex flex-col items-center justify-center text-gray-400"
          >
            <div className="w-16 h-16 rounded-full bg-gray-100 flex items-center justify-center mb-4">
              <ImageIcon className="w-8 h-8 text-gray-300" />
            </div>
            <p className="text-sm font-medium">No pages uploaded yet</p>
          </motion.div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 pb-10">
            {uploadedImages.map((src, idx) => (
              <GlassCard
                key={idx}
                className="p-0 overflow-hidden flex flex-col group"
                variants={item}
              >
                <div className="px-4 py-3 border-b border-gray-100 flex justify-between items-center bg-white/50">
                  <span className="text-xs font-semibold text-gray-600 uppercase tracking-wider">Page {idx + 1}</span>
                  <div className="w-2 h-2 rounded-full bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.6)]" />
                </div>
                <div className="aspect-[3/4] w-full bg-gray-50/50 relative overflow-hidden">
                  <img
                    src={src}
                    alt={`Page ${idx + 1}`}
                    className="h-full w-full object-contain p-2 transition-transform duration-500 group-hover:scale-105"
                  />
                </div>
              </GlassCard>
            ))}
          </div>
        )}
      </motion.div>
    </div>
  );
}
