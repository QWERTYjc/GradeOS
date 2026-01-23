import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Antigravity Intelligence',
  description: 'Next-generation automated grading platform.',
};

import ClientGlobalBackground from '@/components/ClientGlobalBackground';
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
        <ClientGlobalBackground />
        <PageTransition>{children}</PageTransition>
        <GlobalNavLauncher />
      </body>
    </html>
  );
}
