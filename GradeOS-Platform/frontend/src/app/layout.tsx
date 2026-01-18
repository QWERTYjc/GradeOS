import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';

const inter = Inter({ subsets: ['latin'] });

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
      <body className={inter.className}>
        <GlobalBackground />
        <PageTransition>{children}</PageTransition>
        <GlobalNavLauncher />
      </body>
    </html>
  );
}
