---
inclusion: always
---

# GradeOS Design System Rules

This document defines the design system for integrating Figma designs with the GradeOS codebase.

## Tech Stack

- **Framework**: Next.js 16 + React 19
- **Styling**: Tailwind CSS 4 + Custom CSS Variables
- **UI Library**: Ant Design 5
- **Animation**: Framer Motion 12
- **Icons**: Lucide React, Ant Design Icons
- **3D**: Three.js + React Three Fiber

## Design Tokens

### Colors (CSS Variables)

```css
--color-ink: #0B0F17;      /* Primary text */
--color-paper: #FFFFFF;    /* Background */
--color-mist: #F5F7FB;     /* Secondary background */
--color-azure: #2563EB;    /* Primary brand */
--color-neon: #3B82F6;     /* Accent blue */
--color-cyan: #22D3EE;     /* Accent cyan */
--color-line: #E5E7EB;     /* Borders */
```

### Typography

```css
--font-body: "Fira Sans", sans-serif;
--font-mono: "Fira Code", monospace;
--font-display: "Fira Sans", sans-serif;
```

Font weights available: 300, 400, 500, 600, 700

## Component Library

### Location
```
src/components/
├── design-system/     # Core design system components
│   ├── GlassCard.tsx  # Glassmorphism card with hover effects
│   └── SmoothButton.tsx # Animated button with variants
├── common/            # Shared utility components
├── console/           # AI grading console components
├── grading/           # Grading-specific components
├── landing/           # Landing page components
├── layout/            # Layout components (DashboardLayout, etc.)
└── scene/             # 3D scene components
```

### Core Components

#### GlassCard
Glassmorphism card with optional hover animation.
```tsx
import { GlassCard } from '@/components/design-system/GlassCard';

<GlassCard hoverEffect={true} className="p-6">
  {children}
</GlassCard>
```

#### SmoothButton
Animated button with variants: `primary`, `secondary`, `ghost`, `danger`
Sizes: `sm`, `md`, `lg`
```tsx
import { SmoothButton } from '@/components/design-system/SmoothButton';

<SmoothButton variant="primary" size="md" isLoading={false}>
  Click me
</SmoothButton>
```

## Styling Approach

### Utility Function
Use `cn()` for merging Tailwind classes:
```tsx
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
```

### CSS Class Naming Conventions

| Prefix | Purpose | Example |
|--------|---------|---------|
| `landing-` | Landing page styles | `landing-hero-glow`, `landing-cta-primary` |
| `console-` | Console/grading UI | `console-shell`, `console-aurora` |
| `stream-` | Streaming/real-time UI | `stream-item`, `stream-body` |
| `result-` | Results display | `result-row`, `result-score` |
| `assistant-` | Student assistant | `assistant-grid`, `assistant-orb` |

### Animation Classes

```css
.animate-float       /* Floating animation */
.animate-fadeIn      /* Fade in with translate */
.animate-expandIn    /* Expand animation */
.animate-glow-pulse  /* Glowing pulse effect */
```

## Icon System

### Primary: Lucide React
```tsx
import { BookOpen, Sparkles, Brain } from 'lucide-react';

<BookOpen className="w-6 h-6 text-azure" />
```

### Secondary: Ant Design Icons
```tsx
import { HomeOutlined, SettingOutlined } from '@ant-design/icons';
```

### Icon Sizing Convention
- Small: `w-4 h-4`
- Default: `w-5 h-5` or `w-6 h-6`
- Large: `w-8 h-8`

## Asset Management

### Images
- Store in `public/` directory
- Reference with absolute paths: `/image.svg`
- Use Next.js `<Image>` component for optimization

### SVG Icons
- Inline SVGs for icons (via Lucide/Ant Design)
- Static SVGs in `public/` for logos

## Responsive Design

### Breakpoints (Tailwind defaults)
- `sm`: 640px
- `md`: 768px
- `lg`: 1024px
- `xl`: 1280px
- `2xl`: 1536px

### Container
```tsx
<div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
```

## Figma Integration Rules

### When converting Figma designs:

1. **Replace Tailwind utilities** with project tokens when applicable
2. **Reuse existing components** from `src/components/design-system/`
3. **Use CSS variables** for colors: `var(--color-azure)` or Tailwind `text-blue-600`
4. **Apply existing animations** from `globals.css` instead of creating new ones
5. **Follow naming conventions** for new CSS classes

### Component Mapping

| Figma Element | Code Component |
|---------------|----------------|
| Card with blur | `<GlassCard>` |
| Primary button | `<SmoothButton variant="primary">` |
| Secondary button | `<SmoothButton variant="secondary">` |
| Icon button | `<SmoothButton variant="ghost" size="sm">` |
| Dashboard layout | `<DashboardLayout>` |

### Color Mapping

| Figma Color | Code |
|-------------|------|
| Primary Blue | `text-blue-600` / `bg-blue-600` / `var(--color-azure)` |
| Accent Cyan | `text-cyan-400` / `var(--color-cyan)` |
| Dark Text | `text-slate-900` / `var(--color-ink)` |
| Muted Text | `text-slate-500` / `text-gray-500` |
| Background | `bg-white` / `var(--color-paper)` |
| Secondary BG | `bg-slate-50` / `var(--color-mist)` |

## Accessibility Requirements

- All images must have `alt` text
- Form inputs must have associated labels
- Interactive elements need `cursor-pointer`
- Focus states must be visible
- Color contrast ratio: 4.5:1 minimum
- Support `prefers-reduced-motion`
