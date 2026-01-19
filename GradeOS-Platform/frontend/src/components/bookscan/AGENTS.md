# BOOKSCAN COMPONENTS KNOWLEDGE

**Generated:** 2026-01-19

## OVERVIEW
Book scanning UI components for camera capture, OCR, and layout analysis.

## STRUCTURE
```
bookscan/
├── CameraView.tsx          # Live camera feed
├── OCRProcessor.tsx        # OCR result display
├── LayoutAnalyzer.tsx      # Document layout detection
├── ScanControls.tsx        # Capture/retake controls
└── ... (11 more components)
```

## WHERE TO LOOK
| Component | File | Purpose |
|-----------|------|---------|
| Camera | `CameraView.tsx` | Live video stream |
| OCR | `OCRProcessor.tsx` | Display Gemini OCR results |
| Layout | `LayoutAnalyzer.tsx` | Visualize document structure |
| Controls | `ScanControls.tsx` | User capture actions |

## CONVENTIONS
- Uses Ant Design components + Tailwind utilities
- Framer Motion for animations
- TypeScript strict typing

## ANTI-PATTERNS
- No unit tests for complex components
- OCR error handling may need refinement (see `OCRProcessor.tsx`)

## NOTES
- Connects to backend `/api/batch/` endpoints for OCR processing
- Frontend wrapper for backend vision services
