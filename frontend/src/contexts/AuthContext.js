import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';

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
const getStoredUser = () => {
    try {
        const data = localStorage.getItem('user_data');
        return data ? JSON.parse(data) : null;
    } catch {
        return null;
    }
};

export const useAuth = () => {
    const context = useContext(AuthContext);
    if (!context) {
        throw new Error('useAuth must be used within an AuthProvider');
    }
    return context;
};

export const AuthProvider = ({ children }) => {
    // Initialize user from localStorage immediately
    const [user, setUser] = useState(() => getStoredUser());
    const [loading, setLoading] = useState(true);
    const [showAuthModal, setShowAuthModal] = useState(false);
    const [pendingReportId, setPendingReportId] = useState(null);

    // Process OAuth callback token
    const processAuthToken = useCallback((authToken) => {
        console.log('🔐 OAuth: Processing auth token...');
        console.log('🔐 OAuth: Token length:', authToken?.length);
        
        try {
            // The token is URL-encoded standard base64
            // URLSearchParams already decodes it, so we can use atob directly
            const decoded = JSON.parse(atob(authToken));
            console.log('🔐 OAuth: Decoded successfully for', decoded.email);
            
            // Store session token in localStorage
            if (decoded.session_token) {
                setStoredToken(decoded.session_token);
                console.log('🔐 OAuth: Session token stored in localStorage');
            }
            
            // Store user data
            const userData = {
                user_id: decoded.user_id,
                email: decoded.email,
                name: decoded.name,
                picture: decoded.picture
            };
            
            // Save to localStorage FIRST (persists across page reloads)
            localStorage.setItem('user_authenticated', 'true');
            localStorage.setItem('user_data', JSON.stringify(userData));
            
            // Then update React state
            setUser(userData);
            setLoading(false);
            
            console.log('🔐 OAuth: User logged in successfully!', decoded.email);
            console.log('🔐 OAuth: localStorage user_data:', localStorage.getItem('user_data'));
            
            // Clear the URL params AFTER everything is saved
            window.history.replaceState(null, '', window.location.pathname);
            
            return true;
        } catch (e) {
            console.error('🔐 OAuth: Failed to decode auth token', e);
            console.error('🔐 OAuth: Token was:', authToken?.substring(0, 50) + '...');
            return false;
        }
    }, []);

    // Check authentication status on mount
    useEffect(() => {
        console.log('🔐 AuthContext: Initializing...');
        console.log('🔐 AuthContext: Current URL:', window.location.href);
        console.log('🔐 AuthContext: localStorage user_data:', localStorage.getItem('user_data'));
        
        // Check if returning from Google OAuth with auth_token
        const params = new URLSearchParams(window.location.search);
        const authToken = params.get('auth_token');
        
        if (authToken) {
            console.log('🔐 AuthContext: Found auth_token in URL');
            const success = processAuthToken(authToken);
            if (success) {
                return; // Don't call checkAuth, we already have the user
            }
        }
        
        // Check if there's an auth error
        if (window.location.search.includes('auth_error=')) {
            const error = params.get('auth_error');
            console.error('Google OAuth error:', error);
            window.history.replaceState(null, '', window.location.pathname);
        }
        
        // Check if we have a stored user (from previous session)
        const storedUser = getStoredUser();
        if (storedUser) {
            console.log('🔐 AuthContext: Found stored user:', storedUser.email);
            setUser(storedUser);
            setLoading(false);
            // Optionally verify the session is still valid
            checkAuth();
            return;
        }
        
        // Normal auth check
        checkAuth();
    }, [processAuthToken]);

    const checkAuth = async () => {
        console.log('🔐 checkAuth: Starting auth check...');
        try {
            // Get stored token
            const token = getStoredToken();
            console.log('🔐 checkAuth: Token exists:', !!token);
            
            // If no token, check localStorage fallback
            if (!token) {
                const storedUser = getStoredUser();
                if (storedUser) {
                    console.log('🔐 checkAuth: No token but found stored user:', storedUser.email);
                    setUser(storedUser);
                    setLoading(false);
                    return;
                }
                console.log('🔐 checkAuth: No token and no stored user');
                setUser(null);
                setLoading(false);
                return;
            }
            
            const headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'Authorization': `Bearer ${token}`
            };
            
            const response = await fetch(`${API_URL}/auth/me`, {
                credentials: 'omit',
                headers
            });
            
            console.log('🔐 checkAuth: Response status:', response.status);
            
            // Use clone() to safely handle response body
            const responseClone = response.clone();
            
            if (response.ok) {
                try {
                    const userData = await response.json();
                    console.log('🔐 checkAuth: Got user from API:', userData.email);
                    setUser(userData);
                    localStorage.setItem('user_authenticated', 'true');
                    localStorage.setItem('user_data', JSON.stringify(userData));
                } catch (parseError) {
                    console.error('Failed to parse auth response:', parseError);
                    // Try reading from clone
                    try {
                        const text = await responseClone.text();
                        console.log('🔐 checkAuth: Raw response:', text);
                    } catch (e) {}
                    // Don't clear user, fall back to localStorage
                    const storedUser = getStoredUser();
                    if (storedUser) {
                        setUser(storedUser);
                    }
                }
            } else {
                console.log('🔐 checkAuth: API returned error, checking localStorage...');
                // API returned error - check localStorage as fallback
                const storedUser = getStoredUser();
                if (storedUser && localStorage.getItem('user_authenticated') === 'true') {
                    console.log('🔐 checkAuth: Using stored user:', storedUser.email);
                    setUser(storedUser);
                } else {
                    console.log('🔐 checkAuth: No valid stored user, clearing auth');
                    setUser(null);
                    removeStoredToken();
                    localStorage.removeItem('user_authenticated');
                    localStorage.removeItem('user_data');
                }
            }
        } catch (error) {
            console.error('🔐 checkAuth: Network error:', error);
            // Network error - use localStorage fallback
            const storedUser = getStoredUser();
            if (storedUser && localStorage.getItem('user_authenticated') === 'true') {
                console.log('🔐 checkAuth: Network error, using stored user:', storedUser.email);
                setUser(storedUser);
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
            console.log('🔐 Registration: Starting signup for', email);
            
            // Clone the request body to avoid any stream issues
            const requestBody = JSON.stringify({ email, password, name });
            
            const response = await fetch(`${API_URL}/auth/signup`, {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                body: requestBody,
                // Disable credentials for cross-origin to avoid CORS issues
                credentials: 'omit'
            });
            
            console.log('🔐 Registration: Response status', response.status);
            
            // Use clone() to safely read the response body
            const responseClone = response.clone();
            let data;
            
            try {
                data = await response.json();
            } catch (parseError) {
                // If json() fails, try text() on the clone
                const text = await responseClone.text();
                console.error('🔐 Registration: Parse error, raw response:', text);
                throw new Error(text || 'Registration failed - invalid response');
            }
            
            console.log('🔐 Registration: Response data', data);
            
            if (!response.ok) {
                throw new Error(data.detail || data.message || 'Registration failed');
            }
            
            // Store session token
            if (data.session_token) {
                setStoredToken(data.session_token);
                console.log('🔐 Registration: Session token stored');
            }
            
            // Save auth status to localStorage for persistence
            localStorage.setItem('user_authenticated', 'true');
            localStorage.setItem('user_data', JSON.stringify(data.user));
            
            setUser(data.user);
            setShowAuthModal(false);
            console.log('🔐 Registration: Success!');
            return { success: true, user: data.user };
        } catch (error) {
            console.error('🔐 Registration error:', error);
            return { success: false, error: error.message || 'Registration failed' };
        }
    };

    // Email/Password Login
    const loginWithEmail = async (email, password) => {
        try {
            console.log('🔐 Login: Starting signin for', email);
            
            // Clone the request body to avoid any stream issues
            const requestBody = JSON.stringify({ email, password });
            
            const response = await fetch(`${API_URL}/auth/signin`, {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                body: requestBody,
                // Disable credentials for cross-origin to avoid CORS issues
                credentials: 'omit'
            });
            
            console.log('🔐 Login: Response status', response.status);
            
            // Use clone() to safely read the response body
            const responseClone = response.clone();
            let data;
            
            try {
                data = await response.json();
            } catch (parseError) {
                // If json() fails, try text() on the clone
                const text = await responseClone.text();
                console.error('🔐 Login: Parse error, raw response:', text);
                throw new Error(text || 'Login failed - invalid response');
            }
            
            console.log('🔐 Login: Response data', data);
            
            if (!response.ok) {
                throw new Error(data.detail || data.message || 'Invalid email or password');
            }
            
            // Store session token
            if (data.session_token) {
                setStoredToken(data.session_token);
                console.log('🔐 Login: Session token stored');
            }
            
            // Save auth status to localStorage for persistence
            localStorage.setItem('user_authenticated', 'true');
            localStorage.setItem('user_data', JSON.stringify(data.user));
            
            setUser(data.user);
            setShowAuthModal(false);
            console.log('🔐 Login: Success!');
            return { success: true, user: data.user };
        } catch (error) {
            console.error('🔐 Login error:', error);
            return { success: false, error: error.message || 'Login failed' };
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
