export const API_BASE = "http://localhost:8001";

export async function fetcher(url: string, options?: RequestInit) {
    const res = await fetch(`${API_BASE}${url}`, options);
    if (!res.ok) {
        throw new Error(`API Error: ${res.statusText}`);
    }
    return res.json();
}

export const api = {
    createSubmission: async (examFiles: File[], rubricFiles: File[]) => {
        const formData = new FormData();
        examFiles.forEach(f => formData.append('files', f));
        rubricFiles.forEach(f => formData.append('rubrics', f));
        formData.append('auto_identify', 'true');

        // Map backend response { batch_id, ... } to { id, ... } for frontend compat if needed
        const res = await fetcher("/batch/submit", {
            method: "POST",
            body: formData,
        });
        return { ...res, id: res.batch_id };
    },

    submitGrading: async (examId: string, studentId: string, file: File) => {
        // Legacy/Individual support if needed
        const formData = new FormData();
        formData.append("file", file);
        formData.append("exam_id", examId);
        formData.append("student_id", studentId);
        return fetcher("/api/v1/submissions", {
            method: "POST",
            body: formData,
        });
    },

    getSubmission: (id: string) => fetcher(`/batch/${id}/status`),

    getResults: (id: string) => fetcher(`/batch/${id}/results`),

    listSubmissions: () => fetcher("/batch/list"),

    reviewSubmission: (id: string, action: string, data?: any) =>
        fetcher(`/batch/${id}/review`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ action, ...data }),
        }),
};
