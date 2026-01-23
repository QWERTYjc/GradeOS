'use client';

import dynamic from 'next/dynamic';

// Dynamic import with ssr: false must be in a Client Component
const GlobalBackground = dynamic(() => import('@/components/GlobalBackground'), {
    ssr: false,
    loading: () => <div className="fixed inset-0 -z-10 bg-white" />,
});

export default function ClientGlobalBackground() {
    return <GlobalBackground />;
}
