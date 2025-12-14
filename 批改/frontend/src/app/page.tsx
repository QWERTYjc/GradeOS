'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect } from 'react';
import { useConsoleStore } from '@/store/consoleStore';
import { ArrowRight } from 'lucide-react';



export default function Home() {
  const { setView } = useConsoleStore();
  const router = useRouter();

  useEffect(() => {
    setView('LANDING');
  }, [setView]);

  const handleLaunch = (e: React.MouseEvent) => {
    e.preventDefault();
    setView('CONSOLE');
    // Delay navigation slightly to allow camera to start moving
    setTimeout(() => {
      router.push('/console');
    }, 800);
  };

  return (
    <main className="relative min-h-screen flex flex-col items-center justify-center overflow-hidden text-black">

      {/* Top Navigation (Visual only for reference match) */}
      <nav className="absolute top-0 left-0 right-0 p-6 flex justify-between items-center max-w-7xl mx-auto w-full z-20">
        <div className="flex items-center gap-2 font-medium text-gray-600">
          <span className="text-blue-600 font-bold text-xl">A</span> Google Antigravity
        </div>
        <div className="hidden md:flex gap-6 text-sm text-gray-500 font-medium">
          <span>Product</span>
          <span>Use Cases</span>
          <span>Pricing</span>
          <span>Resources</span>
        </div>
        <button onClick={handleLaunch} className="bg-black text-white px-5 py-2 rounded-full text-sm font-medium hover:bg-gray-800 transition-colors">
          Launch Console
        </button>
      </nav>

      <div className="z-10 text-center px-4 max-w-5xl mx-auto space-y-8 mt-[-5vh]">
        {/* Logo/Brand above title */}
        <div className="flex items-center justify-center gap-2 mb-6 opacity-80">
          <span className="text-blue-600 font-bold text-2xl">A</span>
          <span className="text-gray-600 font-medium text-xl">Google Antigravity</span>
        </div>

        <h1 className="text-6xl md:text-8xl font-medium tracking-tight text-black mb-6 leading-[1.1]">
          Experience liftoff<br />
          <span className="text-gray-400">with the next-generation IDE</span>
        </h1>

        <div className="flex flex-col md:flex-row items-center justify-center gap-4 pt-8">
          <button
            onClick={handleLaunch}
            className="group inline-flex items-center gap-2 px-8 py-4 bg-black text-white rounded-full text-lg font-medium transition-all hover:scale-105 hover:bg-gray-900"
          >
            <span>Launch Console</span>
          </button>

          <button className="px-8 py-4 bg-gray-100 text-black rounded-full text-lg font-medium hover:bg-gray-200 transition-colors">
            Explore use cases
          </button>
        </div>
      </div>
    </main>
  );
}
