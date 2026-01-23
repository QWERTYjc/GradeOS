'use client';

import React from 'react';
import DashboardLayout from '@/components/layout/DashboardLayout';
import AIChat from './components/AIChat';

export default function StudentAssistant() {
  return (
    <DashboardLayout>
      <AIChat />
    </DashboardLayout>
  );
}
