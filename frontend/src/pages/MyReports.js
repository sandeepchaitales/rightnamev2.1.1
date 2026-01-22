import React, { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { 
  FileText, Clock, ArrowRight, ArrowLeft, ChevronLeft, ChevronRight, 
  Sparkles, LogOut, User, Home, Plus, Search, Filter, TrendingUp,
  CheckCircle, XCircle, AlertTriangle, Globe2, Building2, Calendar,
  BarChart3, Loader2, RefreshCw, ExternalLink
} from "lucide-react";
import Footer from '../components/Footer';

// Get API URL based on environment
const getApiUrl = () => {
  if (process.env.NODE_ENV === 'production') {
    return '/api';
  }
  return `${process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001'}/api`;
};

const API_URL = getApiUrl();

// Verdict Badge Component
const VerdictBadge = ({ verdict }) => {
  const getVerdictStyle = (v) => {
    const normalizedVerdict = v?.toUpperCase() || '';
    if (normalizedVerdict.includes('GO') && !normalizedVerdict.includes('CAUTION')) {
      return 'bg-emerald-100 text-emerald-700 border-emerald-300';
    } else if (normalizedVerdict.includes('CAUTION') || normalizedVerdict.includes('MODERATE')) {
      return 'bg-amber-100 text-amber-700 border-amber-300';
    } else if (normalizedVerdict.includes('REJECT') || normalizedVerdict.includes('NO')) {
      return 'bg-red-100 text-red-700 border-red-300';
    }
    return 'bg-slate-100 text-slate-700 border-slate-300';
  };

  const getVerdictIcon = (v) => {
    const normalizedVerdict = v?.toUpperCase() || '';
    if (normalizedVerdict.includes('GO') && !normalizedVerdict.includes('CAUTION')) {
      return <CheckCircle className="w-3.5 h-3.5" />;
    } else if (normalizedVerdict.includes('CAUTION') || normalizedVerdict.includes('MODERATE')) {
      return <AlertTriangle className="w-3.5 h-3.5" />;
    } else if (normalizedVerdict.includes('REJECT') || normalizedVerdict.includes('NO')) {
      return <XCircle className="w-3.5 h-3.5" />;
    }
    return null;
  };

  return (
    <Badge className={`${getVerdictStyle(verdict)} font-bold flex items-center gap-1 px-2.5 py-1`}>
      {getVerdictIcon(verdict)}
      {verdict || 'N/A'}
    </Badge>
  );
};

// Score Circle Component
const ScoreCircle = ({ score }) => {
  const getScoreColor = (s) => {
    if (s >= 75) return 'from-emerald-500 to-emerald-600 text-white';
    if (s >= 50) return 'from-amber-500 to-amber-600 text-white';
    return 'from-red-500 to-red-600 text-white';
  };

  return (
    <div className={`w-14 h-14 rounded-full bg-gradient-to-br ${getScoreColor(score)} flex items-center justify-center font-black text-lg shadow-lg`}>
      {score || 0}
    </div>
  );
};

// Report Card Component
const ReportCard = ({ report, onClick }) => {
  const formatDate = (dateStr) => {
    if (!dateStr) return 'N/A';
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', { 
      month: 'short', 
      day: 'numeric', 
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  return (
    <Card 
      className="group hover:shadow-xl transition-all duration-300 cursor-pointer border-2 hover:border-violet-300 bg-white overflow-hidden"
      onClick={onClick}
    >
      <CardContent className="p-0">
        <div className="flex flex-col md:flex-row">
          {/* Score Section */}
          <div className="bg-gradient-to-br from-slate-50 to-slate-100 p-6 flex items-center justify-center md:w-28 border-b md:border-b-0 md:border-r border-slate-200">
            <ScoreCircle score={report.namescore} />
          </div>
          
          {/* Content Section */}
          <div className="flex-1 p-5">
            <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
              <div className="flex-1">
                <div className="flex items-center gap-3 mb-2">
                  <h3 className="text-xl font-black text-slate-900 group-hover:text-violet-700 transition-colors">
                    {report.brand_name}
                  </h3>
                  <VerdictBadge verdict={report.verdict} />
                </div>
                
                <div className="flex flex-wrap items-center gap-3 text-sm text-slate-600 mb-3">
                  <span className="flex items-center gap-1.5">
                    <Building2 className="w-4 h-4 text-violet-500" />
                    {report.category || 'N/A'}
                  </span>
                  {report.countries && report.countries.length > 0 && (
                    <span className="flex items-center gap-1.5">
                      <Globe2 className="w-4 h-4 text-blue-500" />
                      {report.countries.slice(0, 2).join(', ')}
                      {report.countries.length > 2 && ` +${report.countries.length - 2}`}
                    </span>
                  )}
                  <span className="flex items-center gap-1.5">
                    <Calendar className="w-4 h-4 text-slate-400" />
                    {formatDate(report.created_at)}
                  </span>
                </div>
                
                {report.executive_summary && (
                  <p className="text-sm text-slate-500 line-clamp-2">
                    {report.executive_summary}
                  </p>
                )}
              </div>
              
              <Button 
                variant="outline" 
                size="sm" 
                className="shrink-0 border-2 hover:border-violet-500 hover:bg-violet-50 hover:text-violet-700 rounded-full font-bold group-hover:translate-x-1 transition-all"
              >
                View Report
                <ArrowRight className="w-4 h-4 ml-1" />
              </Button>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

// Empty State Component
const EmptyState = () => {
  const navigate = useNavigate();
  
  return (
    <div className="text-center py-16 px-4">
      <div className="w-24 h-24 mx-auto mb-6 bg-gradient-to-br from-violet-100 to-fuchsia-100 rounded-3xl flex items-center justify-center">
        <FileText className="w-12 h-12 text-violet-500" />
      </div>
      <h3 className="text-2xl font-black text-slate-900 mb-3">No Reports Yet</h3>
      <p className="text-slate-600 mb-6 max-w-md mx-auto">
        You haven't generated any brand evaluation reports yet. Start analyzing your brand names to see them here.
      </p>
      <Button 
        onClick={() => navigate('/')}
        className="bg-gradient-to-r from-violet-600 to-fuchsia-600 hover:from-violet-700 hover:to-fuchsia-700 text-white font-bold rounded-full px-6"
      >
        <Plus className="w-4 h-4 mr-2" />
        Create Your First Report
      </Button>
    </div>
  );
};

// Pagination Component
const Pagination = ({ currentPage, totalPages, onPageChange }) => {
  if (totalPages <= 1) return null;
  
  return (
    <div className="flex items-center justify-center gap-2 mt-8">
      <Button
        variant="outline"
        size="sm"
        disabled={currentPage === 1}
        onClick={() => onPageChange(currentPage - 1)}
        className="rounded-full"
      >
        <ChevronLeft className="w-4 h-4" />
      </Button>
      
      <span className="px-4 py-2 text-sm font-medium text-slate-600">
        Page {currentPage} of {totalPages}
      </span>
      
      <Button
        variant="outline"
        size="sm"
        disabled={currentPage === totalPages}
        onClick={() => onPageChange(currentPage + 1)}
        className="rounded-full"
      >
        <ChevronRight className="w-4 h-4" />
      </Button>
    </div>
  );
};

// Main MyReports Page
const MyReports = () => {
  const navigate = useNavigate();
  const { user, loading: authLoading, logout } = useAuth();
  
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [pagination, setPagination] = useState({
    page: 1,
    limit: 10,
    total: 0,
    total_pages: 0
  });

  // Redirect if not authenticated
  useEffect(() => {
    if (!authLoading && !user) {
      navigate('/');
    }
  }, [user, authLoading, navigate]);

  // Fetch reports
  const fetchReports = async (page = 1) => {
    try {
      setLoading(true);
      setError(null);
      
      const response = await fetch(`${API_URL}/user/reports?page=${page}&limit=10&sort=newest`, {
        credentials: 'include'
      });
      
      if (!response.ok) {
        if (response.status === 401) {
          navigate('/');
          return;
        }
        throw new Error('Failed to fetch reports');
      }
      
      const data = await response.json();
      setReports(data.reports || []);
      setPagination(data.pagination || { page: 1, limit: 10, total: 0, total_pages: 0 });
    } catch (err) {
      console.error('Error fetching reports:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (user) {
      fetchReports();
    }
  }, [user]);

  const handlePageChange = (newPage) => {
    fetchReports(newPage);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleViewReport = (report) => {
    // Store report in localStorage and navigate to dashboard
    localStorage.setItem('current_report', JSON.stringify({
      report_id: report.report_id,
      executive_summary: report.executive_summary,
      brand_scores: [{
        brand_name: report.brand_name,
        namescore: report.namescore,
        verdict: report.verdict
      }]
    }));
    localStorage.setItem('current_query', JSON.stringify({
      brand_name: report.brand_name,
      category: report.category,
      industry: report.industry,
      countries: report.countries
    }));
    
    // Navigate to dashboard to view full report
    navigate(`/dashboard?report_id=${report.report_id}`);
  };

  if (authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-50 via-violet-50 to-fuchsia-50">
        <Loader2 className="w-10 h-10 animate-spin text-violet-600" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-violet-50 to-fuchsia-50">
      {/* Header */}
      <header className="sticky top-0 z-50 bg-white/80 backdrop-blur-xl border-b border-slate-200/60">
        <div className="max-w-6xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            {/* Logo */}
            <Link to="/" className="flex items-center gap-3 group">
              <div className="relative">
                <div className="absolute inset-0 bg-gradient-to-r from-violet-600 via-fuchsia-500 to-orange-500 rounded-xl blur-lg opacity-40 group-hover:opacity-60 transition-opacity"></div>
                <div className="relative w-10 h-10 bg-gradient-to-br from-violet-600 via-fuchsia-500 to-orange-500 rounded-xl flex items-center justify-center shadow-lg">
                  <Sparkles className="w-5 h-5 text-white" />
                </div>
              </div>
              <div>
                <h1 className="text-xl font-black bg-gradient-to-r from-violet-700 via-fuchsia-600 to-orange-500 bg-clip-text text-transparent">
                  RIGHTNAME.AI
                </h1>
              </div>
            </Link>

            {/* Navigation */}
            <nav className="hidden md:flex items-center gap-6">
              <Link 
                to="/"
                className="flex items-center gap-2 text-slate-600 hover:text-violet-600 font-medium transition-colors"
              >
                <Home className="w-4 h-4" />
                Home
              </Link>
              <Link 
                to="/my-reports"
                className="flex items-center gap-2 text-violet-600 font-bold"
              >
                <FileText className="w-4 h-4" />
                My Reports
              </Link>
            </nav>

            {/* User Menu */}
            {user && (
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-2 px-4 py-2 bg-white border-2 border-slate-200 rounded-full shadow-sm">
                  {user.picture ? (
                    <img src={user.picture} alt={user.name} className="w-7 h-7 rounded-full ring-2 ring-violet-200" />
                  ) : (
                    <User className="w-5 h-5 text-slate-500" />
                  )}
                  <span className="text-sm font-bold text-slate-700 hidden sm:inline">
                    {user.name?.split(' ')[0]}
                  </span>
                </div>
                <Button 
                  variant="outline" 
                  size="sm" 
                  onClick={logout} 
                  className="text-slate-600 rounded-full border-2 hidden sm:flex"
                >
                  <LogOut className="w-4 h-4 mr-1" />
                  Sign Out
                </Button>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-6xl mx-auto px-4 py-8">
        {/* Page Header */}
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-8">
          <div>
            <h1 className="text-3xl font-black text-slate-900 mb-2">My Reports</h1>
            <p className="text-slate-600">
              {pagination.total > 0 
                ? `You have ${pagination.total} brand evaluation${pagination.total !== 1 ? 's' : ''}`
                : 'Your brand evaluations will appear here'}
            </p>
          </div>
          
          <div className="flex items-center gap-3">
            <Button
              variant="outline"
              size="sm"
              onClick={() => fetchReports(pagination.page)}
              className="rounded-full border-2"
              disabled={loading}
            >
              <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
            <Button 
              onClick={() => navigate('/')}
              className="bg-gradient-to-r from-violet-600 to-fuchsia-600 hover:from-violet-700 hover:to-fuchsia-700 text-white font-bold rounded-full"
            >
              <Plus className="w-4 h-4 mr-2" />
              New Report
            </Button>
          </div>
        </div>

        {/* Reports List */}
        {loading ? (
          <div className="flex flex-col items-center justify-center py-16">
            <Loader2 className="w-10 h-10 animate-spin text-violet-600 mb-4" />
            <p className="text-slate-600">Loading your reports...</p>
          </div>
        ) : error ? (
          <div className="text-center py-16">
            <div className="w-16 h-16 mx-auto mb-4 bg-red-100 rounded-full flex items-center justify-center">
              <XCircle className="w-8 h-8 text-red-500" />
            </div>
            <h3 className="text-xl font-bold text-slate-900 mb-2">Failed to Load Reports</h3>
            <p className="text-slate-600 mb-4">{error}</p>
            <Button 
              variant="outline" 
              onClick={() => fetchReports()}
              className="rounded-full"
            >
              <RefreshCw className="w-4 h-4 mr-2" />
              Try Again
            </Button>
          </div>
        ) : reports.length === 0 ? (
          <EmptyState />
        ) : (
          <>
            <div className="space-y-4">
              {reports.map((report) => (
                <ReportCard 
                  key={report.report_id} 
                  report={report} 
                  onClick={() => handleViewReport(report)}
                />
              ))}
            </div>
            
            <Pagination 
              currentPage={pagination.page}
              totalPages={pagination.total_pages}
              onPageChange={handlePageChange}
            />
          </>
        )}
      </main>

      <Footer />
    </div>
  );
};

export default MyReports;
