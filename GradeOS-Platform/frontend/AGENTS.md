# FRONTEND KNOWLEDGE BASE

**Stack**: Next.js 16 (App Router), React 19, Tailwind CSS 4, Zustand
**Manager**: `npm`

## OVERVIEW
The face of GradeOS. Features a Role-Based Access Control (RBAC) architecture separating Student, Teacher, and Admin (Console) experiences.

## STRUCTURE
```
frontend/src/
├── app/                  # App Router (File-based routing)
│   ├── (auth)/           # Login/Register (Route Group)
│   ├── student/          # Student dashboard & scanning
│   ├── teacher/          # Class management & analytics
│   └── console/          # Admin & Grading graph inspection
├── components/           # Shared UI components
│   ├── bookscan/         # Scanning & image processing
│   ├── grading/          # Rubric & results visualization
│   └── design-system/    # Reusable atoms (Buttons, Cards)
└── store/                # Global state (Zustand)
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Pages | `app/` | Organized by user role |
| Global Layout | `app/layout.tsx` | Root providers & styles |
| Scanning UI | `components/bookscan/` | Camera & upload logic |
| Graph Viz | `components/console/` | Visualizing LangGraph flows |
| Styles | `app/globals.css` | Tailwind base styles |

## CONVENTIONS
- **Server Components**: Default to Server Components; use `"use client"` only when needed.
- **Data Fetching**: Use SWR or Server Actions for API calls.
- **Styling**: Tailwind CSS utility classes; avoid CSS modules unless necessary.
- **State**: Local state for UI; Zustand for global user/session data.

## ANTI-PATTERNS (THIS FRONTEND)
- **NO `useEffect` Chains**: Use derived state or event handlers.
- **NO Direct DOM Access**: Use Refs.
- **NO Inline Styles**: Use Tailwind classes.
- No automated tests (no Jest/Vitest config)
- Hardcoded assignment ID in `src/app/teacher/class/[id]/page.tsx` (TODO)

## COMMANDS
```bash
npm run dev      # Start dev server
npm run build    # Production build
npm run lint     # Lint check
```

## NOTES
- Frontend uses Ant Design 5 + Zustand + Framer Motion 12
- State managed via Zustand (not Redux/Context)
- WebSocket integration for real-time grading updates
