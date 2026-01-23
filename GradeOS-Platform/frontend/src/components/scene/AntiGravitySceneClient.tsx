'use client';

// Three.js background temporarily disabled for Railway deployment
// The actual Three.js scene code has been moved to AntiGravitySceneClient.backup.tsx
// To restore: rename the backup file back to AntiGravitySceneClient.tsx

export default function AntiGravitySceneClient() {
    return (
        <div className="fixed inset-0 -z-10 bg-gradient-to-br from-slate-50 via-white to-slate-100" />
    );
}
