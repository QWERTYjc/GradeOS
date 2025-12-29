import { ScannedImage } from '../types';
import { jsPDF } from 'jspdf';

// ------------------------------------------------------------------
// API Output Interface (Based on Documentation)
// ------------------------------------------------------------------
export interface SubmissionResponse {
  submission_id: string;
  exam_id: string;
  student_id: string;
  status: "UPLOADED" | "PROCESSING" | "COMPLETED" | "FAILED";
  estimated_completion_time?: string;
  message?: string; // Optional error message
}

// Configuration with defaults
const DEFAULT_CONFIG = {
  API_BASE_URL: 'http://127.0.0.1:8000', // Use IP to avoid localhost resolution ambiguity
  DEFAULT_EXAM_ID: 'exam_default_001',
  DEFAULT_STUDENT_ID: 'student_guest',
};

/**
 * Converts a list of scanned images into a single PDF Blob.
 */
export const generatePDFFromImages = async (images: ScannedImage[]): Promise<Blob> => {
  if (images.length === 0) throw new Error("No images to generate PDF");

  // Default A4 size in mm
  const pdf = new jsPDF('p', 'mm', 'a4');
  const pageWidth = 210;
  const pageHeight = 297;

  for (let i = 0; i < images.length; i++) {
    const img = images[i];
    if (i > 0) pdf.addPage();

    // Get image dimensions
    const imgProps = pdf.getImageProperties(img.url);
    const imgRatio = imgProps.width / imgProps.height;
    
    // Calculate dimensions to fit A4 keeping aspect ratio
    let w = pageWidth;
    let h = pageWidth / imgRatio;

    if (h > pageHeight) {
        h = pageHeight;
        w = pageHeight * imgRatio;
    }

    const x = (pageWidth - w) / 2;
    const y = (pageHeight - h) / 2;

    pdf.addImage(img.url, 'JPEG', x, y, w, h);
  }

  return pdf.output('blob');
};

/**
 * Submits the PDF to the AI Grading System API.
 * Endpoint: POST /api/v1/submissions/
 */
export const submitToGradingSystem = async (
  images: ScannedImage[], 
  examId: string = DEFAULT_CONFIG.DEFAULT_EXAM_ID,
  studentId: string = DEFAULT_CONFIG.DEFAULT_STUDENT_ID
): Promise<SubmissionResponse> => {
  try {
    const pdfBlob = await generatePDFFromImages(images);
    const formData = new FormData();
    
    // Required fields per API Documentation
    formData.append('exam_id', examId);
    formData.append('student_id', studentId);
    formData.append('file', pdfBlob, `${studentId}_${examId}.pdf`);

    // Added trailing slash which is often required by FastAPI default router configuration
    // Using 127.0.0.1 from config
    const url = `${DEFAULT_CONFIG.API_BASE_URL}/api/v1/submissions/`;
    
    console.log(`[Submission] Posting to ${url} with ExamID: ${examId}, StudentID: ${studentId}`);

    const response = await fetch(url, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const errorText = await response.text();
      // Try to parse JSON error if possible
      try {
          const errorJson = JSON.parse(errorText);
          throw new Error(`API Error (${response.status}): ${JSON.stringify(errorJson)}`);
      } catch (e) {
          throw new Error(`API Error (${response.status}): ${errorText}`);
      }
    }

    // Strict typing of the response
    const data: SubmissionResponse = await response.json();
    return data;
  } catch (error) {
    console.error("Submission Error:", error);
    throw error;
  }
};