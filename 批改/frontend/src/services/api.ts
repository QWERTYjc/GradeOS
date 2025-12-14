const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8001';

export interface Submission {
    id: string;
    status: string;
    created_at: string;
}

export const api = {
    async createSubmission(files: File[], rubrics: File[]): Promise<Submission> {
        const formData = new FormData();

        files.forEach(file => {
            formData.append('files', file);
        });

        rubrics.forEach(rubric => {
            formData.append('rubrics', rubric);
        });

        // Add a generated exam_id
        formData.append('exam_id', 'exam_' + Date.now());

        try {
            const response = await fetch(`${API_BASE_URL}/batch/submit`, {
                method: 'POST',
                body: formData,
            });

            if (!response.ok) {
                throw new Error(`Upload failed: ${response.status} ${response.statusText}`);
            }

            const data = await response.json();
            // Map batch response to Submission interface
            return {
                id: data.batch_id,
                status: data.status || 'UPLOADED',
                created_at: new Date().toISOString()
            };
        } catch (error) {
            console.error("API Error:", error);
            throw new Error(error instanceof TypeError && error.message === 'Failed to fetch'
                ? 'Cannot connect to server. Is the backend running?'
                : error instanceof Error ? error.message : 'Unknown error');
        }
    },

    async getSubmission(id: string): Promise<Submission> {
        const response = await fetch(`${API_BASE_URL}/submissions/${id}`);
        if (!response.ok) {
            throw new Error(`Fetch failed: ${response.statusText}`);
        }
        return response.json();
    },

    async getNodeDetails(submissionId: string, nodeId: string): Promise<any> {
        // Mocking this for now as the backend endpoint might vary, 
        // but structure is ready for real call
        // const response = await fetch(`${API_BASE_URL}/submissions/${submissionId}/nodes/${nodeId}`);
        // return response.json();

        return {
            nodeId,
            status: 'completed',
            logs: ['Agent started', 'Processing data...', 'Agent finished'],
            output: { confidence: 0.98, result: 'Pass' }
        };
    }
};
