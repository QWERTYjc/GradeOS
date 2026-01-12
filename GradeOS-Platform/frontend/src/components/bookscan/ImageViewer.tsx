import React, { useState } from 'react';
import { X, ZoomIn, ZoomOut, Edit3, Maximize, RotateCcw } from 'lucide-react';
import { ScannedImage } from './types';

interface ImageViewerProps {
  image: ScannedImage;
  onClose: () => void;
  onEdit: () => void;
}

export default function ImageViewer({ image, onClose, onEdit }: ImageViewerProps) {
  const [scale, setScale] = useState(1);

  const handleZoomIn = () => setScale(prev => Math.min(prev + 0.5, 4));
  const handleZoomOut = () => setScale(prev => Math.max(prev - 0.5, 1));
  const handleReset = () => setScale(1);

  return (
    <div className="fixed inset-0 z-50 bg-black/95 flex flex-col animate-in fade-in duration-200">
      
      {/* Header Toolbar */}
      <div className="flex items-center justify-between p-4 text-white z-10 bg-gradient-to-b from-black/50 to-transparent">
        <h3 className="font-medium text-lg truncate max-w-[200px]">{image.name}</h3>
        <div className="flex items-center gap-4">
          <button 
            onClick={onEdit} 
            className="flex items-center gap-2 px-4 py-2 bg-indigo-600 rounded-full hover:bg-indigo-500 transition-colors font-medium text-sm"
          >
            <Edit3 size={16} /> Edit
          </button>
          <button onClick={onClose} className="p-2 hover:bg-white/20 rounded-full transition-colors">
            <X size={24} />
          </button>
        </div>
      </div>

      {/* Image Container */}
      <div className="flex-1 overflow-hidden relative flex items-center justify-center">
        <div 
            className="w-full h-full overflow-auto flex items-center justify-center p-4"
            style={{ cursor: scale > 1 ? 'grab' : 'default' }}
        >
            <img 
              src={image.url} 
              alt={image.name} 
              className="max-w-none transition-transform duration-200 ease-out origin-center"
              style={{ 
                  transform: `scale(${scale})`,
                  maxHeight: scale === 1 ? '90vh' : 'none',
                  maxWidth: scale === 1 ? '100%' : 'none'
              }}
              draggable={false}
            />
        </div>
      </div>

      {/* Bottom Controls */}
      <div className="p-6 flex justify-center gap-6 safe-area-bottom">
        <div className="flex items-center gap-2 bg-slate-800/80 backdrop-blur-md px-4 py-2 rounded-full text-white border border-white/10 shadow-xl">
            <button onClick={handleZoomOut} disabled={scale <= 1} className="p-2 hover:text-indigo-400 disabled:opacity-30 transition-colors">
                <ZoomOut size={24} />
            </button>
            <span className="w-12 text-center font-mono text-sm">{Math.round(scale * 100)}%</span>
            <button onClick={handleZoomIn} disabled={scale >= 4} className="p-2 hover:text-indigo-400 disabled:opacity-30 transition-colors">
                <ZoomIn size={24} />
            </button>
            <div className="w-px h-6 bg-white/20 mx-2"></div>
            <button onClick={handleReset} className="p-2 hover:text-yellow-400 transition-colors" title="Reset Zoom">
                <Maximize size={20} />
            </button>
        </div>
      </div>
    </div>
  );
}
