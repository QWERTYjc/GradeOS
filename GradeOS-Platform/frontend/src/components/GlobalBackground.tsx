'use client';

import dynamic from 'next/dynamic';

const AntiGravityScene = dynamic(() => import('@/components/scene/AntiGravityScene'), {
    ssr: false,
    loading: () => <div className="fixed inset-0 -z-10 bg-white" />
});

export default function GlobalBackground() {
    return (
        <div className="fixed inset-0 -z-10 pointer-events-none">
            <AntiGravityScene />
        </div>
    );
}
