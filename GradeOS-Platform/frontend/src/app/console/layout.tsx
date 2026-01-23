// Force dynamic rendering to avoid SSR prerendering issues with Three.js
// This prevents Next.js from trying to statically generate the console page
export const dynamic = 'force-dynamic';

export default function ConsoleLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return <>{children}</>;
}
