'use client';

import React from 'react';
import Link from 'next/link';
import { useAuthStore } from '@/store/authStore';
import { Role } from '@/types';
import { HeroSection } from '@/components/landing/HeroSection';
import { FeatureGrid } from '@/components/landing/FeatureGrid';
import { HowItWorks } from '@/components/landing/HowItWorks';
import { StatsRow } from '@/components/landing/StatsRow';
import { PageFooter } from '@/components/landing/PageFooter';

export default function LandingPage() {
  const { user } = useAuthStore();
  const isTeacher = user?.role === Role.Teacher || user?.role === Role.Admin;

  return (
    <main className="landing-shell relative min-h-screen text-slate-200 selection:bg-blue-500/30 selection:text-blue-100 overflow-x-hidden italic-bg">
      {/* Navigation */}
      <nav className="fixed top-0 left-0 right-0 h-16 md:h-20 flex items-center justify-between px-6 md:px-12 z-50 transition-all duration-300 bg-slate-950/80 backdrop-blur-md border-b border-white/5">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 md:w-10 md:h-10 bg-gradient-to-br from-blue-600 to-cyan-500 rounded-xl flex items-center justify-center text-white font-bold shadow-lg shadow-blue-500/20">
            <span className="font-display text-lg">G</span>
          </div>
          <span className="font-display font-bold text-xl tracking-tight text-white hidden sm:block">GradeOS</span>
        </div>

        <div className="hidden md:flex items-center gap-8 text-sm font-medium text-slate-400">
          <Link href="#features" className="hover:text-white transition-colors">Features</Link>
          <Link href="#how-it-works" className="hover:text-white transition-colors">How it Works</Link>
          <Link href="#pricing" className="hover:text-white transition-colors">Pricing</Link>
        </div>

        <div className="flex items-center gap-4">
          {user ? (
            <Link
              href={isTeacher ? '/teacher/dashboard' : '/student/dashboard'}
              className="px-5 py-2 rounded-full bg-blue-600 hover:bg-blue-500 text-white text-sm font-semibold transition-all shadow-lg shadow-blue-600/20 hover:shadow-blue-600/40"
            >
              Enter Console
            </Link>
          ) : (
            <>
              <Link
                href="/login"
                className="hidden sm:block text-slate-400 hover:text-white text-sm font-medium transition-colors"
              >
                Log in
              </Link>
              <Link
                href="/register"
                className="landing-cta-primary text-sm"
              >
                <span>Get Started</span>
              </Link>
            </>
          )}
        </div>
      </nav>

      {/* Main Content */}
      <div className="pt-20">
        <HeroSection />
        <StatsRow />
        <div id="features">
          <FeatureGrid />
        </div>
        <div id="how-it-works">
          <HowItWorks />
        </div>
        <PageFooter />
      </div>
    </main>
  );
}
