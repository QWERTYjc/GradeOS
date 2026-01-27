---
name: nextjs-react-landing-page
description: Expert in building cutting-edge frontend applications using Next.js and React, specializing in outstanding UI landing page design. Use when building Next.js/React frontends, designing landing pages, creating modern UI components, implementing responsive layouts, or when user mentions Next.js, React, landing page, frontend design, UI/UX.
---

# Next.js & React Landing Page Expert

Expert-level guidance for building cutting-edge frontend applications with Next.js and React, specializing in outstanding UI landing page design.

## When to Apply

Apply this skill when:
- Building Next.js or React frontend applications
- Designing and implementing landing pages
- Creating modern UI components and layouts
- Implementing responsive designs
- Working with React hooks, state management, or Next.js features
- User mentions Next.js, React, landing page, frontend design, or UI/UX

## Core Principles

### 1. Next.js Best Practices

**App Router (Next.js 13+)**
- Use App Router (`app/` directory) for new projects
- Leverage Server Components by default, use `'use client'` only when needed
- Use `next/image` for optimized images with automatic WebP conversion
- Implement route handlers in `app/api/` for API endpoints
- Use `next/font` for optimized font loading

**Performance Optimization**
- Implement code splitting with dynamic imports: `const Component = dynamic(() => import('./Component'))`
- Use `next/link` for client-side navigation (prefetching enabled by default)
- Leverage `generateStaticParams` for static generation
- Use `revalidate` for ISR (Incremental Static Regeneration)
- Optimize bundle size with `next.config.js` bundle analyzer

**SEO & Metadata**
- Use `metadata` export in App Router for SEO
- Implement Open Graph and Twitter Card metadata
- Use semantic HTML5 elements
- Ensure proper heading hierarchy (h1 → h2 → h3)

### 2. React Best Practices

**Component Architecture**
- Prefer functional components with hooks
- Keep components small and focused (single responsibility)
- Use composition over inheritance
- Extract reusable logic into custom hooks
- Use TypeScript for type safety

**State Management**
- Use `useState` for local component state
- Use `useReducer` for complex state logic
- Consider Zustand or Jotai for global state (lightweight)
- Use React Query/SWR for server state management
- Avoid prop drilling with Context API when appropriate

**Performance**
- Use `React.memo` for expensive components
- Implement `useMemo` and `useCallback` judiciously
- Avoid unnecessary re-renders
- Use React DevTools Profiler to identify bottlenecks

### 3. Landing Page Design Principles

**Hero Section**
- Clear value proposition above the fold
- Compelling headline (benefit-focused, not feature-focused)
- Strong call-to-action (CTA) button with contrast
- High-quality hero image or video
- Social proof elements (testimonials, logos, stats)

**Structure & Flow**
- Logical information hierarchy
- Progressive disclosure (don't overwhelm)
- Clear visual separation between sections
- Consistent spacing and rhythm
- Mobile-first responsive design

**Conversion Optimization**
- Multiple CTAs throughout the page
- Clear value proposition in first 3 seconds
- Trust signals (testimonials, certifications, guarantees)
- Urgency/scarcity elements (when appropriate)
- Minimal form fields for lead capture

### 4. Modern UI/UX Patterns

**Visual Design**
- Use modern design systems (Tailwind CSS, shadcn/ui, Chakra UI)
- Implement glassmorphism, gradients, or subtle shadows for depth
- Consistent color palette with proper contrast ratios (WCAG AA minimum)
- Smooth animations and micro-interactions (150-300ms)
- Dark mode support when appropriate

**Typography**
- Clear font hierarchy (heading → subheading → body)
- Readable line height (1.5-1.75 for body text)
- Appropriate font sizes (minimum 16px for body on mobile)
- Limit line length (65-75 characters)
- Use font pairing tools (Google Fonts, Font Pair)

**Accessibility**
- Semantic HTML elements
- ARIA labels for icon-only buttons
- Keyboard navigation support
- Focus states visible on all interactive elements
- Alt text for meaningful images
- Color contrast ratio minimum 4.5:1 for normal text

**Responsive Design**
- Mobile-first approach
- Breakpoints: 375px (mobile), 768px (tablet), 1024px (desktop), 1440px (large)
- Touch targets minimum 44x44px
- Test on real devices when possible
- Use CSS Grid and Flexbox for layouts

## Implementation Patterns

### Next.js App Router Structure

```
app/
├── layout.tsx          # Root layout
├── page.tsx            # Home page
├── globals.css         # Global styles
├── components/         # Shared components
│   ├── ui/            # Base UI components
│   ├── sections/      # Landing page sections
│   └── layout/        # Layout components
└── api/               # API routes
```

### Component Example: Hero Section

```tsx
'use client'

import { Button } from '@/components/ui/button'
import { ArrowRight } from 'lucide-react'
import Image from 'next/image'

export function Hero() {
  return (
    <section className="relative min-h-screen flex items-center justify-center overflow-hidden">
      <div className="absolute inset-0 -z-10">
        <Image
          src="/hero-bg.jpg"
          alt="Hero background"
          fill
          className="object-cover"
          priority
        />
        <div className="absolute inset-0 bg-gradient-to-b from-black/50 to-black/80" />
      </div>
      
      <div className="container mx-auto px-4 text-center text-white">
        <h1 className="text-5xl md:text-7xl font-bold mb-6 animate-fade-in">
          Transform Your Business Today
        </h1>
        <p className="text-xl md:text-2xl mb-8 max-w-2xl mx-auto opacity-90">
          The most powerful solution for modern businesses
        </p>
        <Button size="lg" className="group">
          Get Started
          <ArrowRight className="ml-2 group-hover:translate-x-1 transition-transform" />
        </Button>
      </div>
    </section>
  )
}
```

### Custom Hook Example: Scroll Animation

```tsx
'use client'

import { useEffect, useRef, useState } from 'react'

export function useScrollAnimation() {
  const [isVisible, setIsVisible] = useState(false)
  const ref = useRef<HTMLElement>(null)

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true)
          observer.disconnect()
        }
      },
      { threshold: 0.1 }
    )

    if (ref.current) {
      observer.observe(ref.current)
    }

    return () => observer.disconnect()
  }, [])

  return { ref, isVisible }
}
```

## Technology Stack Recommendations

### Core
- **Next.js 14+** (App Router)
- **React 19+**
- **TypeScript** (strict mode)
- **Tailwind CSS** (utility-first styling)

### UI Libraries
- **shadcn/ui** (accessible component primitives)
- **Framer Motion** (animations)
- **Lucide React** (icons)

### State Management
- **Zustand** (global state)
- **React Query** (server state)
- **React Hook Form** (forms)

### Styling
- **Tailwind CSS** (primary)
- **CSS Modules** (component-scoped styles when needed)
- **PostCSS** (for Tailwind processing)

## Common Patterns

### Landing Page Sections

1. **Hero** - Value proposition, CTA
2. **Features** - Key benefits with icons
3. **Social Proof** - Testimonials, logos, stats
4. **How It Works** - Process/steps
5. **Pricing** - Plans comparison
6. **FAQ** - Common questions
7. **CTA Section** - Final conversion opportunity
8. **Footer** - Links, contact, legal

### Animation Patterns

- Fade in on scroll (Intersection Observer)
- Stagger animations for lists
- Smooth page transitions
- Micro-interactions on hover
- Loading states with skeletons

### Performance Patterns

- Lazy load below-the-fold content
- Optimize images with Next.js Image
- Use dynamic imports for heavy components
- Implement loading states
- Minimize JavaScript bundle size

## Anti-Patterns to Avoid

❌ **Don't**: Use `useEffect` for data fetching (use Server Components or React Query)
❌ **Don't**: Import entire icon libraries (tree-shake or use dynamic imports)
❌ **Don't**: Use inline styles for responsive design (use Tailwind breakpoints)
❌ **Don't**: Block rendering with large images (use `next/image` with `priority` only for above-fold)
❌ **Don't**: Create deeply nested component trees (extract into smaller components)
❌ **Don't**: Ignore accessibility (always include ARIA labels, keyboard navigation)
❌ **Don't**: Use emojis as icons (use proper icon libraries like Lucide)
❌ **Don't**: Hardcode colors (use CSS variables or Tailwind theme)

## Quick Checklist

Before delivering a landing page:

- [ ] Mobile-responsive (test at 375px, 768px, 1024px)
- [ ] All images optimized with `next/image`
- [ ] Semantic HTML structure
- [ ] Accessibility (keyboard nav, ARIA labels, contrast)
- [ ] Performance (Lighthouse score > 90)
- [ ] SEO metadata implemented
- [ ] Smooth animations (respect `prefers-reduced-motion`)
- [ ] Loading states for async operations
- [ ] Error boundaries for error handling
- [ ] TypeScript types properly defined
- [ ] No console errors or warnings

## Resources

- [Next.js Documentation](https://nextjs.org/docs)
- [React Documentation](https://react.dev)
- [Tailwind CSS](https://tailwindcss.com/docs)
- [shadcn/ui Components](https://ui.shadcn.com)
- [Web.dev Accessibility](https://web.dev/accessible/)
- [Web.dev Performance](https://web.dev/performance/)
