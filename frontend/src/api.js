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
const POLL_INTERVAL = 2000; // 2 seconds for smoother progress updates
const MAX_POLL_TIME = 300000; // 5 minutes max

export const api = {
    // Async job-based evaluation with progress tracking
    evaluate: async (data, onProgress) => {
        try {
            console.log('[API] Starting async evaluation...');
            
            // Step 1: Start the job
            const startResponse = await axiosInstance.post(`${API_URL}/evaluate/start`, data);
            const jobId = startResponse.data.job_id;
            const steps = startResponse.data.steps || [];
            console.log('[API] Job started:', jobId, 'Steps:', steps.length);
            
            // Initial progress callback with steps info
            if (onProgress) {
                onProgress({
                    status: 'processing',
                    progress: 5,
                    currentStep: 'starting',
                    currentStepLabel: 'Initializing analysis...',
                    completedSteps: [],
                    etaSeconds: 90,
                    steps: steps
                });
            }
            
            // Step 2: Poll for results with progress tracking
            const startTime = Date.now();
            
            while (Date.now() - startTime < MAX_POLL_TIME) {
                await new Promise(resolve => setTimeout(resolve, POLL_INTERVAL));
                
                const statusResponse = await axiosInstance.get(`${API_URL}/evaluate/status/${jobId}`);
                const status = statusResponse.data;
                
                console.log('[API] Job status:', status.status, 'Progress:', status.progress);
                
                if (status.status === 'completed') {
                    console.log('[API] Evaluation completed!');
                    // Final progress update
                    if (onProgress) {
                        onProgress({
                            status: 'completed',
                            progress: 100,
                            currentStep: 'done',
                            currentStepLabel: 'Analysis complete!',
                            completedSteps: steps.map(s => s.id),
                            etaSeconds: 0
                        });
                    }
                    return status.result;
                } else if (status.status === 'failed') {
                    throw new Error(status.error || 'Evaluation failed');
                }
                
                // Update progress with detailed info
                const elapsed = Math.round((Date.now() - startTime) / 1000);
                const estimatedTotal = 90; // Base estimate in seconds
                const remaining = Math.max(0, estimatedTotal - elapsed);
                
                if (onProgress) {
                    onProgress({
                        status: status.status,
                        progress: status.progress || Math.min(95, (elapsed / estimatedTotal) * 100),
                        currentStep: status.current_step || 'processing',
                        currentStepLabel: status.current_step_label || `Analyzing... (${elapsed}s)`,
                        completedSteps: status.completed_steps || [],
                        etaSeconds: status.eta_seconds || remaining,
                        steps: status.steps || steps
                    });
                }
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
