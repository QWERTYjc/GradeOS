'use client';

import dynamic from 'next/dynamic';

const ParticleBackground = dynamic(() => import('@/components/ui/particle-background'), {
    ssr: false,
});

export default function GlobalBackground() {
    return (
        <>
            {/* Base Gradient Overlay for depth */}
            <div className="fixed inset-0 -z-20 bg-gradient-to-br from-background via-background/90 to-background/80" />

            {/* 3D Particles */}
            <ParticleBackground />

            {/* Subtle Grid Pattern Overlay */}
            <div
                className="fixed inset-0 -z-10 opacity-[0.03] pointer-events-none"
                style={{
                    backgroundImage: `linear-gradient(to right, #ffffff 1px, transparent 1px),
                                    linear-gradient(to bottom, #ffffff 1px, transparent 1px)`,
                    backgroundSize: '40px 40px'
                }}
            />
        </>
    );
}
