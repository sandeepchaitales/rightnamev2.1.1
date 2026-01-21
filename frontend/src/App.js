import React from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route, useLocation } from "react-router-dom";
import { HelmetProvider } from "react-helmet-async";
import LandingPage from "./pages/LandingPage";
import Dashboard from "./pages/Dashboard";
import AuthCallback from "./pages/AuthCallback";
import BlogPage from "./pages/BlogPage";
import BrandAuditLanding from "./pages/BrandAuditLanding";
import BrandAuditDashboard from "./pages/BrandAuditDashboard";
import AdminPanel from "./pages/AdminPanel";
import PaymentSuccess from "./pages/PaymentSuccess";
import PaymentCancel from "./pages/PaymentCancel";
import { AuthProvider } from "./contexts/AuthContext";
import AuthModal from "./components/AuthModal";
import { Toaster } from "@/components/ui/sonner";

// Router component that checks for session_id in URL
function AppRouter() {
  const location = useLocation();
  
  // Check URL fragment for session_id synchronously during render
  // This prevents race conditions by processing new session_id FIRST
  if (location.hash?.includes('session_id=')) {
    return <AuthCallback />;
  }
  
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/dashboard" element={<Dashboard />} />
      <Route path="/auth/callback" element={<AuthCallback />} />
      <Route path="/blog" element={<BlogPage />} />
      <Route path="/brand-audit" element={<BrandAuditLanding />} />
      <Route path="/brand-audit/results" element={<BrandAuditDashboard />} />
      <Route path="/admin" element={<AdminPanel />} />
      <Route path="/payment/success" element={<PaymentSuccess />} />
      <Route path="/payment/cancel" element={<PaymentCancel />} />
    </Routes>
  );
}

function App() {
  return (
    <HelmetProvider>
      <div className="App">
        <AuthProvider>
          <BrowserRouter>
            <AppRouter />
            <AuthModal />
          </BrowserRouter>
        </AuthProvider>
        <Toaster />
      </div>
    </HelmetProvider>
  );
}

export default App;
