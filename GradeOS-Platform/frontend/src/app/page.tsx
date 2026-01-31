'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { useAuthStore } from '@/store/authStore';
import { Role } from '@/types';
import { motion, AnimatePresence } from 'framer-motion';
import { Menu, X, ArrowRight } from 'lucide-react';
import { HeroSection } from '@/components/landing/HeroSection';
import { FeatureGrid } from '@/components/landing/FeatureGrid';
import { PageFooter } from '@/components/landing/PageFooter';

export default function LandingPage() {
  const { user } = useAuthStore();
  const isTeacher = user?.role === Role.Teacher || user?.role === Role.Admin;
  const [isScrolled, setIsScrolled] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  // 监听滚动事件
  useEffect(() => {
    const handleScroll = () => {
      setIsScrolled(window.scrollY > 50);
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  return (
    <main className="landing-page">
      {/* Navigation */}
      <motion.nav
        initial={{ y: -100 }}
        animate={{ y: 0 }}
        className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${isScrolled
          ? 'landing-nav-scrolled py-3'
          : 'py-4'
          }`}
        style={{
          background: isScrolled
            ? 'rgba(255, 255, 255, 0.9)'
            : 'transparent',
          backdropFilter: isScrolled ? 'blur(20px)' : 'none',
          borderBottom: isScrolled ? '1px solid rgba(226, 232, 240, 0.8)' : 'none'
        }}
      >
        <div className="landing-container">
          <div className="flex items-center justify-between">
            {/* Logo - Removed as per request */}
            <div />


            {/* Desktop Navigation */}
            <div className="hidden md:flex items-center gap-8">
              <Link
                href="#features"
                className="text-sm font-medium text-gray-600 hover:text-blue-600 transition-colors"
              >
                核心能力
              </Link>
            </div>

            {/* CTA Buttons */}
            <div className="flex items-center gap-4">
              {user ? (
                <Link
                  href={isTeacher ? '/teacher/dashboard' : '/student/dashboard'}
                  className="hidden sm:flex px-5 py-2.5 rounded-full bg-blue-600 text-white text-sm font-semibold hover:bg-blue-700 transition-all shadow-lg shadow-blue-600/20"
                >
                  进入控制台
                </Link>
              ) : (
                <>
                  <Link
                    href="/login"
                    className="hidden sm:block text-sm font-medium text-gray-600 hover:text-gray-900 transition-colors"
                  >
                    登录
                  </Link>
                  <Link
                    href="/register"
                    className="px-5 py-2.5 rounded-full bg-gray-900 text-white text-sm font-semibold hover:bg-gray-800 transition-all flex items-center gap-2"
                  >
                    <span>开始使用</span>
                    <ArrowRight className="w-4 h-4" />
                  </Link>
                </>
              )}

              {/* Mobile Menu Button */}
              <button
                onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
                className="md:hidden w-10 h-10 rounded-lg bg-gray-100 flex items-center justify-center"
              >
                {isMobileMenuOpen ? (
                  <X className="w-5 h-5 text-gray-700" />
                ) : (
                  <Menu className="w-5 h-5 text-gray-700" />
                )}
              </button>
            </div>
          </div>
        </div>

        {/* Mobile Menu */}
        <AnimatePresence>
          {isMobileMenuOpen && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              className="md:hidden bg-white border-t border-gray-100"
            >
              <div className="landing-container py-4 space-y-4">
                <Link
                  href="#features"
                  onClick={() => setIsMobileMenuOpen(false)}
                  className="block py-2 text-gray-600 hover:text-blue-600"
                >
                  核心特性
                </Link>
                {!user && (
                  <div className="pt-4 border-t border-gray-100 flex flex-col gap-3">
                    <Link
                      href="/login"
                      onClick={() => setIsMobileMenuOpen(false)}
                      className="block py-2 text-center text-gray-600"
                    >
                      登录
                    </Link>
                    <Link
                      href="/register"
                      onClick={() => setIsMobileMenuOpen(false)}
                      className="block py-2.5 text-center bg-blue-600 text-white rounded-lg font-medium"
                    >
                      开始使用
                    </Link>
                  </div>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.nav>

      {/* Hero Section */}
      <HeroSection />

      {/* Feature Grid */}
      <div id="features">
        <FeatureGrid />
      </div>

      {/* Footer */}
      <PageFooter />
    </main>
  );
}
