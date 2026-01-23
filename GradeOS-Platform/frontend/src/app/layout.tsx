import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'GradeOS',
  description: 'Next-generation automated grading platform.',
};

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
        {/* Three.js background temporarily disabled for Railway deployment */}
        {/* <ClientGlobalBackground /> */}
        <div className="fixed inset-0 -z-10 bg-gradient-to-br from-slate-50 to-slate-100" />
        <PageTransition>{children}</PageTransition>
        <GlobalNavLauncher />
      </body>
    </html>
  );
}
