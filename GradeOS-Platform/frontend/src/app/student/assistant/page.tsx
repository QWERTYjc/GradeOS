'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

export default function StudentAssistantRedirect() {
  const router = useRouter();

  useEffect(() => {
    router.replace('/student/student_assistant');
  }, [router]);

  return null;
}
