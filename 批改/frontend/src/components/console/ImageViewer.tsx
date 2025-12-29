import React, { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { ZoomIn, ZoomOut, Maximize, Move } from 'lucide-react';

interface BoundingBox {
    box: [number, number, number, number]; // [ymin, xmin, ymax, xmax] 0-1000
    label?: string;
    color?: string;
    id?: string;
}

interface ImageViewerProps {
    src: string;
    annotations?: BoundingBox[];
    activeAnnotationId?: string | null;
    onAnnotationClick?: (id: string) => void;
    className?: string;
}

export default function ImageViewer({
    src,
    annotations = [],
    activeAnnotationId,
    onAnnotationClick,
    className
}: ImageViewerProps) {
    const [scale, setScale] = useState(1);
    const [position, setPosition] = useState({ x: 0, y: 0 });
    const containerRef = useRef<HTMLDivElement>(null);
    const imageRef = useRef<HTMLImageElement>(null);
    const [isDragging, setIsDragging] = useState(false);
    const dragStart = useRef({ x: 0, y: 0 });

    // Handle Zoom
    const handleZoom = (delta: number) => {
        setScale(prev => Math.min(Math.max(prev + delta, 0.5), 4));
    };

    // Handle Pan
    const handleMouseDown = (e: React.MouseEvent) => {
        if (scale > 1) {
            setIsDragging(true);
            dragStart.current = { x: e.clientX - position.x, y: e.clientY - position.y };
        }
    };

    const handleMouseMove = (e: React.MouseEvent) => {
        if (isDragging) {
            setPosition({
                x: e.clientX - dragStart.current.x,
                y: e.clientY - dragStart.current.y
            });
        }
    };

    const handleMouseUp = () => setIsDragging(false);

    // Auto-focus active annotation
    useEffect(() => {
        if (activeAnnotationId && annotations.length > 0 && imageRef.current) {
            const target = annotations.find(a => a.id === activeAnnotationId);
            if (target) {
                // Calculate center of box to center viewport
                // box: [ymin, xmin, ymax, xmax]
                const [ymin, xmin, ymax, xmax] = target.box;
                const centerX = (xmin + xmax) / 2 / 1000;
                const centerY = (ymin + ymax) / 2 / 1000;

                // Simple auto-pan logic could go here
                // For now, let's just highlight it
            }
        }
    }, [activeAnnotationId, annotations]);

    return (
        <div
            className={cn("relative overflow-hidden bg-gray-900 rounded-xl", className)}
            ref={containerRef}
        >
            {/* Controls */}
            <div className="absolute top-4 right-4 z-20 flex gap-2">
                <Button variant="secondary" size="icon" onClick={() => handleZoom(0.5)} className="bg-black/50 hover:bg-black/70 text-white">
                    <ZoomIn size={16} />
                </Button>
                <Button variant="secondary" size="icon" onClick={() => handleZoom(-0.5)} className="bg-black/50 hover:bg-black/70 text-white">
                    <ZoomOut size={16} />
                </Button>
                <Button variant="secondary" size="icon" onClick={() => { setScale(1); setPosition({ x: 0, y: 0 }); }} className="bg-black/50 hover:bg-black/70 text-white">
                    <Maximize size={16} />
                </Button>
            </div>

            {/* Image Plane */}
            <div
                className={cn("w-full h-full flex items-center justify-center cursor-move transition-transform duration-200 ease-out", isDragging ? 'cursor-grabbing' : 'cursor-grab')}
                onMouseDown={handleMouseDown}
                onMouseMove={handleMouseMove}
                onMouseUp={handleMouseUp}
                onMouseLeave={handleMouseUp}
                style={{
                    // Use CSS transform for performance
                    transform: `translate(${position.x}px, ${position.y}px) scale(${scale})`
                }}
            >
                <div className="relative shadow-2xl">
                    <img
                        ref={imageRef}
                        src={src}
                        alt="Exam Paper"
                        className="max-w-full max-h-[80vh] object-contain select-none pointer-events-none"
                        draggable={false}
                    />

                    {/* Overlays */}
                    {annotations.map((ann, idx) => {
                        const [ymin, xmin, ymax, xmax] = ann.box;
                        const top = `${ymin / 10}%`;
                        const left = `${xmin / 10}%`;
                        const height = `${(ymax - ymin) / 10}%`;
                        const width = `${(xmax - xmin) / 10}%`;
                        const isActive = activeAnnotationId === ann.id;

                        return (
                            <motion.div
                                key={ann.id || idx}
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 1, boxShadow: isActive ? "0 0 0 2px #3b82f6, 0 0 20px rgba(59, 130, 246, 0.5)" : "none" }}
                                className={cn(
                                    "absolute border-2 cursor-pointer transition-colors hover:bg-blue-500/10",
                                    isActive ? "border-blue-500 z-10 bg-blue-500/10" : "border-red-500/50 hover:border-blue-400"
                                )}
                                style={{ top, left, width, height }}
                                onClick={(e) => {
                                    e.stopPropagation();
                                    ann.id && onAnnotationClick?.(ann.id);
                                }}
                            >
                                {isActive && (
                                    <div className="absolute -top-6 left-0 bg-blue-600 text-white text-xs px-2 py-0.5 rounded shadow whitespace-nowrap">
                                        {ann.label || "Region"}
                                    </div>
                                )}
                            </motion.div>
                        );
                    })}
                </div>
            </div>
        </div>
    );
}
