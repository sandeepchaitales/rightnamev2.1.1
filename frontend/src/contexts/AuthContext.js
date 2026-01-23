import React, { createContext, useContext, useState, useEffect } from 'react';

const AuthContext = createContext(null);

// Get API URL based on environment
const getApiUrl = () => {
    // In production (deployed), use relative URL
    if (process.env.NODE_ENV === 'production') {
        return '/api';
    }
    // In development, use the environment variable
    return `${process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001'}/api`;
};

const API_URL = getApiUrl();

// Helper to get session token from localStorage
const getStoredToken = () => localStorage.getItem('session_token');
const setStoredToken = (token) => localStorage.setItem('session_token', token);
const removeStoredToken = () => localStorage.removeItem('session_token');

export const useAuth = () => {
    const context = useContext(AuthContext);
    if (!context) {
        throw new Error('useAuth must be used within an AuthProvider');
    }
    return context;
};

export const AuthProvider = ({ children }) => {
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);
    const [showAuthModal, setShowAuthModal] = useState(false);
    const [pendingReportId, setPendingReportId] = useState(null);

    // Check authentication status on mount
    useEffect(() => {
        // Check if returning from Google OAuth with auth_token
        const params = new URLSearchParams(window.location.search);
        const authToken = params.get('auth_token');
        
        if (authToken) {
            try {
                // Decode the base64 user info
                const decoded = JSON.parse(atob(authToken));
                console.log('🔐 OAuth: Received auth token', decoded.email);
                
                // Store session token in localStorage
                if (decoded.session_token) {
                    setStoredToken(decoded.session_token);
                }
                
                // Store user data
                const userData = {
                    user_id: decoded.user_id,
                    email: decoded.email,
                    name: decoded.name,
                    picture: decoded.picture
                };
                
                setUser(userData);
                localStorage.setItem('user_authenticated', 'true');
                localStorage.setItem('user_data', JSON.stringify(userData));
                setLoading(false);
                
                // Clear the URL params
                window.history.replaceState(null, '', window.location.pathname);
                
                console.log('🔐 OAuth: User logged in successfully', decoded.email);
                return;
            } catch (e) {
                console.error('🔐 OAuth: Failed to decode auth token', e);
            }
        }
        
        // Check if there's an auth error
        if (window.location.search.includes('auth_error=')) {
            const error = params.get('auth_error');
            console.error('Google OAuth error:', error);
            window.history.replaceState(null, '', window.location.pathname);
        }
        
        // Normal auth check
        checkAuth();
    }, []);

    const checkAuth = async () => {
        try {
            // Get stored token
            const token = getStoredToken();
            
            const headers = {
                'Content-Type': 'application/json'
            };
            
            // Add Authorization header if we have a token
            if (token) {
                headers['Authorization'] = `Bearer ${token}`;
            }
            
            const response = await fetch(`${API_URL}/auth/me`, {
                credentials: 'include',
                headers
            });
            
            // Read response text first to avoid body stream issues
            const responseText = await response.text();
            
            if (response.ok) {
                try {
                    const userData = JSON.parse(responseText);
                    setUser(userData);
                    localStorage.setItem('user_authenticated', 'true');
                    localStorage.setItem('user_data', JSON.stringify(userData));
                } catch (parseError) {
                    console.error('Failed to parse auth response:', parseError);
                    setUser(null);
                }
            } else {
                // Check localStorage as fallback
                const storedAuth = localStorage.getItem('user_authenticated');
                const storedUser = localStorage.getItem('user_data');
                if (storedAuth === 'true' && storedUser) {
                    try {
                        setUser(JSON.parse(storedUser));
                    } catch {
                        setUser(null);
                        localStorage.removeItem('user_authenticated');
                        localStorage.removeItem('user_data');
                    }
                } else {
                    setUser(null);
                }
            }
        } catch (error) {
            console.error('Auth check failed:', error);
            // Check localStorage as fallback
            const storedAuth = localStorage.getItem('user_authenticated');
            const storedUser = localStorage.getItem('user_data');
            if (storedAuth === 'true' && storedUser) {
                try {
                    setUser(JSON.parse(storedUser));
                } catch {
                    setUser(null);
                }
            } else {
                setUser(null);
            }
        } finally {
            setLoading(false);
        }
    };

    // Custom Google OAuth - RIGHTNAME.AI branding only
    const loginWithGoogle = () => {
        // Save current location to return to after auth
        const currentPath = window.location.pathname;
        if (currentPath !== '/' && currentPath !== '/auth/callback') {
            localStorage.setItem('auth_return_url', currentPath);
        }
        // Use our custom Google OAuth endpoint
        window.location.href = `${API_URL}/auth/google?return_url=${encodeURIComponent(currentPath)}`;
    };

    // Email/Password Registration
    const registerWithEmail = async (email, password, name) => {
        try {
            const response = await fetch(`${API_URL}/auth/register`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ email, password, name })
            });
            
            const text = await response.text();
            let data;
            
            try {
                data = JSON.parse(text);
            } catch (parseError) {
                console.error('Response text:', text);
                throw new Error('Registration failed - invalid response');
            }
            
            if (!response.ok) {
                throw new Error(data.detail || 'Registration failed');
            }
            
            // Save auth status to localStorage for persistence
            localStorage.setItem('user_authenticated', 'true');
            localStorage.setItem('user_data', JSON.stringify(data));
            
            setUser(data);
            setShowAuthModal(false);
            return { success: true, user: data };
        } catch (error) {
            console.error('Registration error:', error);
            return { success: false, error: error.message };
        }
    };

    // Email/Password Login
    const loginWithEmail = async (email, password) => {
        try {
            const response = await fetch(`${API_URL}/auth/login/email`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ email, password })
            });
            
            const text = await response.text();
            let data;
            
            try {
                data = JSON.parse(text);
            } catch (parseError) {
                console.error('Response text:', text);
                throw new Error('Login failed - invalid response');
            }
            
            if (!response.ok) {
                throw new Error(data.detail || 'Login failed');
            }
            
            // Save auth status to localStorage for persistence
            localStorage.setItem('user_authenticated', 'true');
            localStorage.setItem('user_data', JSON.stringify(data));
            
            setUser(data);
            setShowAuthModal(false);
            return { success: true, user: data };
        } catch (error) {
            console.error('Login error:', error);
            return { success: false, error: error.message };
        }
    };

    const logout = async () => {
        try {
            const token = getStoredToken();
            const headers = {};
            if (token) {
                headers['Authorization'] = `Bearer ${token}`;
            }
            
            await fetch(`${API_URL}/auth/logout`, {
                method: 'POST',
                credentials: 'include',
                headers
            });
        } catch (error) {
            console.error('Logout error:', error);
        }
        // Clear all auth data
        removeStoredToken();
        localStorage.removeItem('user_authenticated');
        localStorage.removeItem('user_data');
        setUser(null);
        window.location.href = '/';
    };

    const processSessionId = async (sessionId) => {
        try {
            const response = await fetch(`${API_URL}/auth/session`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                body: JSON.stringify({ session_id: sessionId })
            });
            
            // Read response text first to avoid body stream issues
            const responseText = await response.text();
            
            if (response.ok) {
                try {
                    const userData = JSON.parse(responseText);
                    // Save auth status to localStorage for persistence
                    localStorage.setItem('user_authenticated', 'true');
                    localStorage.setItem('user_data', JSON.stringify(userData));
                    setUser(userData);
                    return userData;
                } catch (parseError) {
                    console.error('Failed to parse session response:', parseError);
                    return null;
                }
            }
            return null;
        } catch (error) {
            console.error('Session processing error:', error);
            return null;
        }
    };

    // Open auth modal with optional pending report
    const openAuthModal = (reportId = null) => {
        setPendingReportId(reportId);
        setShowAuthModal(true);
    };

    const closeAuthModal = () => {
        setShowAuthModal(false);
        setPendingReportId(null);
    };

    return (
        <AuthContext.Provider value={{ 
            user, 
            loading, 
            loginWithGoogle,
            loginWithEmail,
            registerWithEmail, 
            logout, 
            checkAuth, 
            processSessionId,
            showAuthModal,
            openAuthModal,
            closeAuthModal,
            pendingReportId
        }}>
            {children}
        </AuthContext.Provider>
    );
};

export default AuthContext;
