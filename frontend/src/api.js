import axios from 'axios';

// In production (deployed), use relative URL so it works on any domain
// In development, use the environment variable for the backend URL
const isProduction = process.env.NODE_ENV === 'production';
const API_URL = isProduction ? '/api' : `${process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001'}/api`;

// Create axios instance with extended timeout for LLM operations
const axiosInstance = axios.create({
    timeout: 300000, // 5 minutes timeout for comprehensive LLM operations
});

// Poll interval for checking job status
const POLL_INTERVAL = 3000; // 3 seconds
const MAX_POLL_TIME = 300000; // 5 minutes max

export const api = {
    // Async job-based evaluation (prevents 524 timeout)
    evaluate: async (data, onProgress) => {
        try {
            console.log('[API] Starting async evaluation...');
            
            // Step 1: Start the job
            const startResponse = await axiosInstance.post(`${API_URL}/evaluate/start`, data);
            const jobId = startResponse.data.job_id;
            console.log('[API] Job started:', jobId);
            
            if (onProgress) onProgress('Job started, analyzing your brand...');
            
            // Step 2: Poll for results
            const startTime = Date.now();
            
            while (Date.now() - startTime < MAX_POLL_TIME) {
                await new Promise(resolve => setTimeout(resolve, POLL_INTERVAL));
                
                const statusResponse = await axiosInstance.get(`${API_URL}/evaluate/status/${jobId}`);
                const status = statusResponse.data;
                
                console.log('[API] Job status:', status.status);
                
                if (status.status === 'completed') {
                    console.log('[API] Evaluation completed!');
                    return status.result;
                } else if (status.status === 'failed') {
                    throw new Error(status.error || 'Evaluation failed');
                }
                
                // Update progress
                const elapsed = Math.round((Date.now() - startTime) / 1000);
                if (onProgress) onProgress(`Analyzing... (${elapsed}s)`);
            }
            
            throw new Error('Evaluation timed out after 5 minutes');
            
        } catch (error) {
            console.error("[API] Evaluation API Error:", error);
            
            // Fallback to synchronous endpoint if async fails
            if (error.response?.status === 404 || error.code === 'ECONNABORTED') {
                console.log('[API] Falling back to sync endpoint...');
                const response = await axiosInstance.post(`${API_URL}/evaluate`, data);
                return response.data;
            }
            
            throw error;
        }
    },
    
    getReport: async (reportId) => {
        try {
            const response = await axiosInstance.get(`${API_URL}/reports/${reportId}`, {
                withCredentials: true
            });
            return response.data;
        } catch (error) {
            console.error("Get Report API Error:", error);
            throw error;
        }
    },
    
    status: async () => {
        return axiosInstance.get(`${API_URL}/`);
    }
};
