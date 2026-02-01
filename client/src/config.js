export const API_BASE_URL = "http://127.0.0.1:8000";

// Helper function to get auth headers
export const getAuthHeaders = () => {
    const token = localStorage.getItem('eps_token');
    const headers = {
        'Content-Type': 'application/json'
    };
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }
    return headers;
};

// Helper for fetch with auth
export const fetchWithAuth = async (url, options = {}) => {
    const token = localStorage.getItem('eps_token');
    const headers = {
        ...options.headers
    };
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }
    return fetch(url, { ...options, headers });
};
