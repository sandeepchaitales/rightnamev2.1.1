import axios from 'axios';

// In production (deployed), use relative URL so it works on any domain
// In development, use the environment variable for the backend URL
const isProduction = process.env.NODE_ENV === 'production';
const API_URL = isProduction ? '/api' : `${process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001'}/api`;

export const api = {
    evaluate: async (data) => {
        try {
            const response = await axios.post(`${API_URL}/evaluate`, data);
            return response.data;
        } catch (error) {
            console.error("Evaluation API Error:", error);
            throw error;
        }
    },
    getReport: async (reportId) => {
        try {
            const response = await axios.get(`${API_URL}/reports/${reportId}`, {
                withCredentials: true
            });
            return response.data;
        } catch (error) {
            console.error("Get Report API Error:", error);
            throw error;
        }
    },
    status: async () => {
        return axios.get(`${API_URL}/`);
    }
};
