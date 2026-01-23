import type { Metadata } from 'next';
import dynamic from 'next/dynamic';
import './globals.css';

export const metadata: Metadata = {
  title: 'Antigravity Intelligence',
  description: 'Next-generation automated grading platform.',
};

// Dynamic import to avoid SSR issues with Three.js (DOMMatrix not defined in Node.js)
const GlobalBackground = dynamic(() => import('@/components/GlobalBackground'), {
  ssr: false,
  loading: () => <div className="fixed inset-0 -z-10 bg-white" />,
});

import PageTransition from '@/components/layout/PageTransition';
import GlobalNavLauncher from '@/components/layout/GlobalNavLauncher';

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <GlobalBackground />
        <PageTransition>{children}</PageTransition>
        <GlobalNavLauncher />
      </body>
    </html>
  );
}
