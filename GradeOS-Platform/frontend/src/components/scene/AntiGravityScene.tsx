'use client';

import React, { useEffect, useState } from 'react';

// This component only renders on the client side
// Three.js requires browser APIs (DOMMatrix, etc.) that don't exist in Node.js
export default function AntiGravityScene() {
    const [SceneComponent, setSceneComponent] = useState<React.ComponentType | null>(null);

    useEffect(() => {
        // Dynamically import the actual Three.js scene only on client
        import('./AntiGravitySceneClient').then((mod) => {
            setSceneComponent(() => mod.default);
        });
    }, []);

    if (!SceneComponent) {
        // Fallback while loading
        return <div className="fixed inset-0 -z-10 bg-white" />;
    }

    return <SceneComponent />;
}
