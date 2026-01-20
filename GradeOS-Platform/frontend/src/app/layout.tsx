import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Antigravity Intelligence',
  description: 'Next-generation automated grading platform.',
};

import GlobalBackground from '@/components/GlobalBackground';

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
