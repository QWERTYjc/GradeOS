'use client';

import React from 'react';
import { motion, HTMLMotionProps } from 'framer-motion';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs: ClassValue[]) {
    return twMerge(clsx(inputs));
}

interface GlassCardProps extends HTMLMotionProps<'div'> {
    children: React.ReactNode;
    className?: string;
    hoverEffect?: boolean;
}

export function GlassCard({ children, className, hoverEffect = true, ...props }: GlassCardProps) {
    return (
        <motion.div
            initial={hoverEffect ? { scale: 1, y: 0 } : undefined}
            whileHover={hoverEffect ? { scale: 1.01, y: -2, boxShadow: "0 20px 40px rgba(0,0,0,0.1)" } : undefined}
            transition={{ type: "spring", stiffness: 300, damping: 20 }}
            className={cn(
                "relative overflow-hidden rounded-2xl border border-white/20 bg-white/60 p-6 shadow-xl backdrop-blur-xl",
                "dark:border-white/10 dark:bg-black/40",
                className
            )}
            {...props}
        >
            <div className="absolute inset-0 z-0 bg-gradient-to-br from-white/40 via-transparent to-transparent opacity-50 pointer-events-none" />
            <div className="relative z-10">{children}</div>
        </motion.div>
    );
}
