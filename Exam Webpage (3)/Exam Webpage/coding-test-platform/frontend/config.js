/**
 * Production & Development API Configuration
 * If deploying frontend on Vercel, set your production backend API URL below:
 * e.g., 'https://your-backend-api.onrender.com' or 'https://your-domain.com'
 */
window.APP_CONFIG = {
    // Backend URL (empty string allows automatic localhost/LAN port 8000 detection):
    BACKEND_API_URL: "",
    
    // Helper to resolve API BASE
    getApiBase: function() {
        if (this.BACKEND_API_URL && this.BACKEND_API_URL.trim().length > 0) {
            return this.BACKEND_API_URL.trim().replace(/\/$/, "");
        }
        
        const stored = localStorage.getItem('EXAM_BACKEND_API_URL');
        if (stored && stored.trim().length > 0) {
            return stored.trim().replace(/\/$/, "");
        }
        
        // Auto-detect based on current hostname
        if (window.location.protocol.startsWith('http') && window.location.hostname) {
            if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
                return 'http://localhost:8000';
            }
            // If accessed via LAN IP like 192.168.x.x
            if (/^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$/.test(window.location.hostname)) {
                return `${window.location.protocol}//${window.location.hostname}:8000`;
            }
        }
        
        return 'http://localhost:8000';
    }
};
