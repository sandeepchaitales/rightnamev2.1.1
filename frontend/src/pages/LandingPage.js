import React, { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Helmet } from 'react-helmet-async';
import { api } from '../api';
import { useAuth } from '../contexts/AuthContext';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Loader2, Sparkles, ShieldCheck, Globe2, BrainCircuit, Search, ArrowRight, Zap, AlertCircle, LogIn, LogOut, User, CheckCircle, Star, Rocket, Target, Trophy, Heart, TrendingUp, Users, Building2, Briefcase, ChevronDown, ChevronUp, FileText, Clock, DollarSign, MessageSquare, Quote } from "lucide-react";
import { toast } from "sonner";
import { ReportCarousel } from '../components/ReportPreview';
import Footer from '../components/Footer';

// Dynamic Cycling "Trusted By" Component
const TrustedByCycler = () => {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isAnimating, setIsAnimating] = useState(false);
  
  const trustedBy = [
    { text: "Brand Consultants", icon: Users, color: "text-violet-600", bg: "bg-violet-100" },
    { text: "Startup Founders", icon: Rocket, color: "text-fuchsia-600", bg: "bg-fuchsia-100" },
    { text: "Consulting Firms", icon: Building2, color: "text-orange-500", bg: "bg-orange-100" },
    { text: "Marketing Agencies", icon: Briefcase, color: "text-emerald-600", bg: "bg-emerald-100" },
  ];

  useEffect(() => {
    const interval = setInterval(() => {
      setIsAnimating(true);
      setTimeout(() => {
        setCurrentIndex((prev) => (prev + 1) % trustedBy.length);
        setIsAnimating(false);
      }, 300);
    }, 2500);
    return () => clearInterval(interval);
  }, [trustedBy.length]);

  const current = trustedBy[currentIndex];
  const Icon = current.icon;

  return (
    <div className="flex flex-col items-center gap-1.5 mt-5">
      <p className="text-[10px] font-black text-slate-400 uppercase tracking-[0.3em]">Trusted By</p>
      <div className="relative h-9 flex items-center justify-center min-w-[200px]">
        <div 
          className={`flex items-center gap-2 px-4 py-1.5 rounded-full bg-slate-50 border border-slate-200 transition-all duration-300 ${isAnimating ? 'opacity-0 transform translate-y-2' : 'opacity-100 transform translate-y-0'}`}
        >
          <div className={`w-6 h-6 rounded-full ${current.bg} flex items-center justify-center`}>
            <Icon className={`w-3.5 h-3.5 ${current.color}`} />
          </div>
          <span className="font-bold text-slate-700 text-sm whitespace-nowrap">{current.text}</span>
        </div>
      </div>
      {/* Progress dots */}
      <div className="flex gap-1 mt-0.5">
        {trustedBy.map((_, idx) => (
          <div 
            key={idx} 
            className={`w-1 h-1 rounded-full transition-all duration-300 ${idx === currentIndex ? 'bg-violet-500 w-3' : 'bg-slate-300'}`}
          />
        ))}
      </div>
    </div>
  );
};

// Animated floating badge component
const FloatingBadge = ({ children, className, delay = 0 }) => (
  <div 
    className={`inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white border-2 shadow-lg font-bold text-sm ${className}`}
    style={{ 
      animation: `float 3s ease-in-out infinite`,
      animationDelay: `${delay}s`
    }}
  >
    {children}
  </div>
);

// Trust badge pill
const TrustPill = ({ icon: Icon, text, color }) => (
  <div className={`flex items-center gap-2 px-4 py-2 rounded-full ${color} font-bold text-sm shadow-md hover:scale-105 transition-transform cursor-default`}>
    <Icon className="w-4 h-4" />
    <span>{text}</span>
  </div>
);

const FeatureCard = ({ icon: Icon, title, description, color, emoji }) => (
  <div className={`p-6 rounded-3xl bg-white border-2 border-slate-100 shadow-sm hover:shadow-xl transition-all duration-300 hover:translate-y-[-8px] hover:border-violet-200 group relative overflow-hidden`}>
    <div className="absolute top-4 right-4 text-4xl opacity-20 group-hover:opacity-40 transition-opacity">{emoji}</div>
    <div className={`w-14 h-14 rounded-2xl ${color} flex items-center justify-center mb-5 group-hover:scale-110 group-hover:rotate-3 transition-all shadow-lg`}>
      <Icon className="w-7 h-7 text-white" />
    </div>
    <h3 className="font-black text-lg text-slate-900 mb-2">{title}</h3>
    <p className="text-sm text-slate-500 font-medium leading-relaxed">{description}</p>
  </div>
);

// FAQ Accordion Item
const FAQItem = ({ question, answer, isOpen, onClick }) => (
  <div className="border-2 border-slate-200 rounded-2xl overflow-hidden hover:border-violet-300 transition-colors">
    <button
      onClick={onClick}
      className="w-full flex items-center justify-between p-6 text-left bg-white hover:bg-slate-50 transition-colors"
    >
      <span className="font-bold text-slate-900 pr-4">{question}</span>
      {isOpen ? (
        <ChevronUp className="w-5 h-5 text-violet-600 flex-shrink-0" />
      ) : (
        <ChevronDown className="w-5 h-5 text-slate-400 flex-shrink-0" />
      )}
    </button>
    {isOpen && (
      <div className="px-6 pb-6 bg-slate-50">
        <p className="text-slate-600 leading-relaxed">{answer}</p>
      </div>
    )}
  </div>
);

// How It Works Step
const HowItWorksStep = ({ number, title, description, icon: Icon, color }) => (
  <div className="relative flex flex-col items-center text-center p-6">
    <div className={`w-16 h-16 ${color} rounded-2xl flex items-center justify-center mb-4 shadow-lg`}>
      <Icon className="w-8 h-8 text-white" />
    </div>
    <div className="absolute -top-2 -left-2 w-8 h-8 bg-slate-900 text-white rounded-full flex items-center justify-center font-black text-sm">
      {number}
    </div>
    <h3 className="font-black text-lg text-slate-900 mb-2">{title}</h3>
    <p className="text-slate-500 text-sm">{description}</p>
  </div>
);

// Testimonial Card
const TestimonialCard = ({ quote, author, role, company, avatar }) => (
  <Card className="border-2 border-slate-200 hover:border-violet-300 transition-all duration-300 hover:shadow-xl">
    <CardContent className="p-6">
      <Quote className="w-8 h-8 text-violet-300 mb-4" />
      <p className="text-slate-700 mb-6 leading-relaxed italic">&ldquo;{quote}&rdquo;</p>
      <div className="flex items-center gap-3">
        <div className="w-12 h-12 rounded-full bg-gradient-to-br from-violet-500 to-fuchsia-500 flex items-center justify-center text-white font-bold text-lg">
          {avatar}
        </div>
        <div>
          <p className="font-bold text-slate-900">{author}</p>
          <p className="text-sm text-slate-500">{role}, {company}</p>
        </div>
      </div>
    </CardContent>
  </Card>
);

// Use Case Card
const UseCaseCard = ({ icon: Icon, title, description, color }) => (
  <div className="p-6 rounded-2xl bg-white border-2 border-slate-200 hover:border-violet-300 transition-all duration-300 hover:shadow-lg">
    <div className={`w-12 h-12 ${color} rounded-xl flex items-center justify-center mb-4`}>
      <Icon className="w-6 h-6 text-white" />
    </div>
    <h3 className="font-bold text-slate-900 mb-2">{title}</h3>
    <p className="text-slate-500 text-sm">{description}</p>
  </div>
);

const LandingPage = () => {
  const navigate = useNavigate();
  const { user, loading: authLoading, loginWithGoogle, logout, openAuthModal } = useAuth();
  const [loading, setLoading] = useState(false);
  const [openFAQ, setOpenFAQ] = useState(null);
  const [formData, setFormData] = useState({
    brand_names: '',
    industry: '',
    category: '',
    product_type: 'Digital',
    usp: '',
    brand_vibe: '',
    positioning: 'Premium',
    market_scope: 'Multi-Country',
    countries: '',
    // NEW: Enhanced input fields for better accuracy (Improvements #2 & #3)
    known_competitors: '',
    product_keywords: '',
    problem_statement: ''
  });

  // Industry options
  const industries = [
    "Technology & Software",
    "E-commerce & Retail",
    "Finance & Banking",
    "Healthcare & Pharma",
    "Food & Beverage",
    "Fashion & Apparel",
    "Beauty & Cosmetics",
    "Travel & Hospitality",
    "Real Estate & Property",
    "Education & EdTech",
    "Media & Entertainment",
    "Automotive",
    "Manufacturing",
    "Agriculture",
    "Energy & Utilities",
    "Logistics & Supply Chain",
    "Professional Services",
    "Non-Profit & NGO",
    "Sports & Fitness",
    "Home & Living",
    "Pet Care",
    "Kids & Baby",
    "Jewelry & Accessories",
    "Art & Crafts",
    "Gaming",
    "Telecom",
    "Insurance",
    "Legal Services",
    "HR & Recruitment",
    "Marketing & Advertising",
    "Other"
  ];

  const productTypes = [
    { value: "Physical", label: "Physical Product" },
    { value: "Digital", label: "Digital Product/App" },
    { value: "Service", label: "Service" },
    { value: "Hybrid", label: "Hybrid (Product + Service)" }
  ];

  const uspOptions = [
    { value: "Price", label: "Price - Best value for money" },
    { value: "Quality", label: "Quality - Superior craftsmanship" },
    { value: "Speed", label: "Speed - Fastest delivery/service" },
    { value: "Reliability", label: "Reliability - Always dependable" },
    { value: "Design", label: "Design - Aesthetically superior" },
    { value: "Personal Touch", label: "Personal Touch - Customized experience" },
    { value: "Health", label: "Health - Better for wellbeing" },
    { value: "Eco-Friendly", label: "Eco-Friendly - Sustainable choice" },
    { value: "Pure", label: "Pure - Natural/Organic" },
    { value: "No Hassle", label: "No Hassle - Convenience first" }
  ];

  const brandVibes = [
    { value: "Serious", label: "Serious & Professional" },
    { value: "Playful", label: "Playful & Fun" },
    { value: "Luxurious", label: "Luxurious & Premium" },
    { value: "Minimalist", label: "Minimalist & Clean" },
    { value: "Bold", label: "Bold & Edgy" },
    { value: "Warm", label: "Warm & Friendly" },
    { value: "Innovative", label: "Innovative & Futuristic" },
    { value: "Traditional", label: "Traditional & Classic" },
    { value: "Youthful", label: "Youthful & Energetic" },
    { value: "Trustworthy", label: "Trustworthy & Reliable" }
  ];

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleSelectChange = (name, value) => {
    setFormData({ ...formData, [name]: value });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formData.brand_names.trim()) {
      toast.error("Please enter at least one brand name");
      return;
    }
    setLoading(true);
    try {
      const brandNames = formData.brand_names.split(',').map(n => n.trim()).filter(n => n);
      const countries = formData.countries.split(',').map(c => c.trim()).filter(c => c);
      
      const payload = {
        brand_names: brandNames,
        industry: formData.industry || 'General',
        category: formData.category || 'General',
        product_type: formData.product_type,
        usp: formData.usp || '',
        brand_vibe: formData.brand_vibe || '',
        positioning: formData.positioning,
        market_scope: formData.market_scope,
        countries: countries.length > 0 ? countries : ['USA'],
        // NEW: Enhanced input fields (Improvements #2 & #3)
        known_competitors: formData.known_competitors ? formData.known_competitors.split(',').map(c => c.trim()).filter(c => c) : [],
        product_keywords: formData.product_keywords ? formData.product_keywords.split(',').map(k => k.trim()).filter(k => k) : [],
        problem_statement: formData.problem_statement || ''
      };

      const result = await api.evaluate(payload);
      navigate('/dashboard', { state: { data: result, query: payload } });
    } catch (error) {
      console.error(error);
      let errorMsg = "Evaluation failed. Please try again.";
      
      // Handle different error formats
      const detail = error.response?.data?.detail;
      if (detail) {
        if (typeof detail === 'string') {
          errorMsg = detail;
        } else if (Array.isArray(detail)) {
          // Pydantic validation errors come as array of objects
          errorMsg = detail.map(err => err.msg || err.message || JSON.stringify(err)).join(', ');
        } else if (typeof detail === 'object') {
          errorMsg = detail.msg || detail.message || JSON.stringify(detail);
        }
      }
      
      toast.error(
        <div className="flex flex-col gap-1">
            <span className="font-bold">Analysis Failed</span>
            <span className="text-xs">{errorMsg}</span>
        </div>,
        { duration: 5000 }
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Helmet>
        <title>RIGHTNAME | AI-Powered Brand Name Evaluation & Trademark Check</title>
        <meta name="description" content="Evaluate brand names instantly with AI. Check trademark conflicts, domain availability, social handles & get a consulting-grade NameScore report in 60 seconds. First report FREE!" />
        <link rel="canonical" href="https://rightname.ai" />
      </Helmet>
      
    <div className="min-h-screen bg-gradient-to-br from-violet-50 via-white to-fuchsia-50 font-sans selection:bg-violet-200 overflow-x-hidden">
      {/* Add floating animation keyframes */}
      <style>{`
        @keyframes float {
          0%, 100% { transform: translateY(0px); }
          50% { transform: translateY(-10px); }
        }
        @keyframes pulse-ring {
          0% { transform: scale(0.8); opacity: 1; }
          100% { transform: scale(2); opacity: 0; }
        }
        @keyframes gradient-x {
          0%, 100% { background-position: 0% 50%; }
          50% { background-position: 100% 50%; }
        }
        @keyframes fadeInUp {
          0% { opacity: 0; transform: translateY(20px); }
          100% { opacity: 1; transform: translateY(0); }
        }
      `}</style>

      {/* Animated Background Elements */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-[-20%] right-[-10%] w-[600px] h-[600px] bg-gradient-to-br from-violet-300/30 to-fuchsia-300/30 rounded-full blur-[120px] animate-pulse" />
        <div className="absolute bottom-[-10%] left-[-10%] w-[500px] h-[500px] bg-gradient-to-br from-cyan-300/30 to-blue-300/30 rounded-full blur-[120px] animate-pulse" style={{ animationDelay: '1s' }} />
        <div className="absolute top-[40%] left-[20%] w-[300px] h-[300px] bg-gradient-to-br from-amber-200/20 to-orange-200/20 rounded-full blur-[100px] animate-pulse" style={{ animationDelay: '2s' }} />
        
        {/* Floating decorative elements */}
        <div className="absolute top-[15%] left-[10%] text-6xl opacity-10 animate-bounce" style={{ animationDuration: '3s' }}>✨</div>
        <div className="absolute top-[25%] right-[15%] text-5xl opacity-10 animate-bounce" style={{ animationDuration: '4s', animationDelay: '1s' }}>🚀</div>
        <div className="absolute bottom-[30%] left-[5%] text-4xl opacity-10 animate-bounce" style={{ animationDuration: '3.5s', animationDelay: '0.5s' }}>💎</div>
        <div className="absolute bottom-[20%] right-[10%] text-5xl opacity-10 animate-bounce" style={{ animationDuration: '4.5s', animationDelay: '1.5s' }}>⚡</div>
      </div>

      <div className="relative max-w-7xl mx-auto px-6 py-8 lg:py-12">
        
        {/* Header with Navigation */}
        <div className="flex justify-between items-center mb-12 lg:mb-16">
            <div className="flex items-center gap-3">
                <img 
                  src="https://customer-assets.emergentagent.com/job_name-radar-1/artifacts/a4ppykdi_RIGHTNAME.AI.png" 
                  alt="RIGHTNAME Logo" 
                  className="w-12 h-12 rounded-2xl shadow-xl shadow-violet-300/50 hover:scale-110 transition-transform cursor-pointer"
                />
                <h1 className="text-2xl lg:text-3xl font-black bg-clip-text text-transparent bg-gradient-to-r from-violet-600 via-fuchsia-500 to-orange-500 tracking-tight">RIGHTNAME</h1>
            </div>
            
            {/* Navigation Links */}
            <nav className="hidden md:flex items-center gap-6">
              <Link to="/" className="text-sm font-semibold text-violet-600">Home</Link>
              <Link to="/pricing" className="text-sm font-semibold text-slate-600 hover:text-violet-600 transition-colors">Pricing</Link>
              <Link to="/blog" className="text-sm font-semibold text-slate-600 hover:text-violet-600 transition-colors">Blog</Link>
              <a href="#faq" className="text-sm font-semibold text-slate-600 hover:text-violet-600 transition-colors">FAQ</a>
            </nav>
            
            <div className="flex items-center gap-3">
                {authLoading ? (
                    <div className="w-10 h-10 rounded-full bg-slate-100 animate-pulse" />
                ) : user ? (
                    <div className="flex items-center gap-3">
                        <div className="flex items-center gap-2 px-4 py-2 bg-white border-2 border-slate-200 rounded-full shadow-sm">
                            {user.picture ? (
                                <img src={user.picture} alt={user.name} className="w-7 h-7 rounded-full ring-2 ring-violet-200" />
                            ) : (
                                <User className="w-5 h-5 text-slate-500" />
                            )}
                            <span className="text-sm font-bold text-slate-700 hidden sm:inline">{user.name?.split(' ')[0]}</span>
                        </div>
                        <Button variant="outline" size="sm" onClick={logout} className="text-slate-600 rounded-full border-2">
                            <LogOut className="w-4 h-4 mr-1" />
                            <span className="hidden sm:inline">Sign Out</span>
                        </Button>
                    </div>
                ) : (
                    <Button onClick={() => openAuthModal()} className="bg-gradient-to-r from-violet-600 via-fuchsia-500 to-orange-500 hover:from-violet-700 hover:via-fuchsia-600 hover:to-orange-600 text-white font-bold shadow-xl shadow-violet-300/50 rounded-full px-6 hover:scale-105 transition-transform">
                        <LogIn className="w-4 h-4 mr-2" />
                        Sign In
                    </Button>
                )}
            </div>
        </div>

        <div className="grid lg:grid-cols-2 gap-12 lg:gap-20 items-center">
            
            {/* Left Content: Hero Text */}
            <div className="space-y-8 relative z-10">
                <div className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full bg-white border-2 border-violet-200 shadow-lg text-sm font-black text-violet-700">
                    <span className="relative flex h-3 w-3">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                      <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
                    </span>
                    🤖 AI-Powered Brand Intelligence
                </div>
                
                <h1 className="text-5xl lg:text-7xl font-black text-slate-900 leading-[1.05] tracking-tight">
                    Is Your Startup <br />
                    <span 
                      className="text-transparent bg-clip-text bg-gradient-to-r from-violet-600 via-fuchsia-500 to-orange-500"
                      style={{ 
                        backgroundSize: '200% auto',
                        animation: 'gradient-x 3s linear infinite'
                      }}
                    >
                        Name Legally Safe?
                    </span>
                    <br /> 
                    <span className="inline-flex items-center">
                      Let AI Prove It
                      <span className="ml-3 text-5xl animate-bounce">🚀</span>
                    </span>
                </h1>
                
                <p className="text-xl text-slate-600 font-medium leading-relaxed max-w-lg">
                    Get instant, <span className="text-violet-600 font-bold">consulting-grade</span> <span className="text-slate-900 font-black">BRAND NAME ANALYSIS</span> on trademark risk, cultural resonance, and domain availability. <span className="text-fuchsia-600 font-bold">No guesswork.</span>
                </p>

                {/* Quick Stats */}
                <div className="flex items-center gap-6 pt-2">
                    <div className="text-center">
                        <div className="text-3xl font-black text-violet-600">50K+</div>
                        <div className="text-xs font-bold text-slate-500 uppercase tracking-wider">Names Analyzed</div>
                    </div>
                    <div className="w-px h-12 bg-slate-200"></div>
                    <div className="text-center">
                        <div className="text-3xl font-black text-fuchsia-600">30s</div>
                        <div className="text-xs font-bold text-slate-500 uppercase tracking-wider">Avg. Report Time</div>
                    </div>
                    <div className="w-px h-12 bg-slate-200"></div>
                    <div className="text-center">
                        <div className="text-3xl font-black text-orange-500">98%</div>
                        <div className="text-xs font-bold text-slate-500 uppercase tracking-wider">Accuracy</div>
                    </div>
                </div>

                {/* Feature Pills */}
                <div className="flex flex-wrap gap-3 pt-4">
                    <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-emerald-50 border border-emerald-200">
                        <ShieldCheck className="w-4 h-4 text-emerald-600" />
                        <span className="font-bold text-sm text-emerald-700">Legal Risk Check</span>
                    </div>
                    <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-blue-50 border border-blue-200">
                        <Globe2 className="w-4 h-4 text-blue-600" />
                        <span className="font-bold text-sm text-blue-700">Global Culture Fit</span>
                    </div>
                    <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-violet-50 border border-violet-200">
                        <BrainCircuit className="w-4 h-4 text-violet-600" />
                        <span className="font-bold text-sm text-violet-700">AI Perception</span>
                    </div>
                    <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-orange-50 border border-orange-200">
                        <Search className="w-4 h-4 text-orange-600" />
                        <span className="font-bold text-sm text-orange-700">Domain Scout</span>
                    </div>
                </div>
            </div>

            {/* Right Content: The Form */}
            <div className="relative z-10">
                <div className="absolute -inset-2 bg-gradient-to-r from-violet-600 via-fuchsia-500 to-orange-500 rounded-[2rem] blur opacity-30 group-hover:opacity-40 transition-opacity"></div>
                <Card className="border-2 border-white/50 shadow-2xl rounded-[2rem] overflow-hidden bg-white/90 backdrop-blur-xl relative">
                    <CardContent className="p-8">
                        <div className="flex items-center justify-between mb-8">
                            <h3 className="text-xl font-black text-slate-900 flex items-center gap-2">
                                <div className="w-8 h-8 bg-gradient-to-br from-amber-400 to-orange-500 rounded-lg flex items-center justify-center">
                                    <Zap className="w-5 h-5 text-white" />
                                </div>
                                Start Analysis
                            </h3>
                            <div className="flex gap-2">
                                <div className="w-3 h-3 rounded-full bg-red-400 shadow-sm"></div>
                                <div className="w-3 h-3 rounded-full bg-amber-400 shadow-sm"></div>
                                <div className="w-3 h-3 rounded-full bg-green-400 shadow-sm"></div>
                            </div>
                        </div>

                        <form onSubmit={handleSubmit} className="space-y-5">
                            <div className="space-y-2">
                                <Label className="text-xs font-black uppercase tracking-wider text-slate-500">Brand Name(s) ✨</Label>
                                <Input 
                                    name="brand_names"
                                    value={formData.brand_names}
                                    onChange={handleChange}
                                    placeholder="e.g. LUMINA, VESTRA"
                                    className="h-14 bg-slate-50 border-2 border-slate-200 focus:border-violet-500 focus:ring-violet-200 font-bold text-lg rounded-xl hover:border-violet-300 transition-colors"
                                    required
                                />
                            </div>

                            {/* Industry & Category Row */}
                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <Label className="text-xs font-black uppercase tracking-wider text-slate-500">Industry</Label>
                                    <Select onValueChange={(val) => handleSelectChange('industry', val)} value={formData.industry}>
                                        <SelectTrigger className="h-12 bg-slate-50 border-2 border-slate-200 rounded-xl font-medium hover:border-violet-300 transition-colors">
                                            <SelectValue placeholder="Select..." />
                                        </SelectTrigger>
                                        <SelectContent className="max-h-[300px]">
                                            {industries.map((ind) => (
                                                <SelectItem key={ind} value={ind}>{ind}</SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                </div>
                                <div className="space-y-2">
                                    <Label className="text-xs font-black uppercase tracking-wider text-slate-500">Category</Label>
                                    <Input 
                                        name="category"
                                        value={formData.category}
                                        onChange={handleChange}
                                        placeholder="e.g. DTC Skincare"
                                        className="h-12 bg-slate-50 border-2 border-slate-200 rounded-xl font-medium hover:border-violet-300 transition-colors"
                                    />
                                </div>
                            </div>

                            {/* Product Type & USP Row */}
                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <Label className="text-xs font-black uppercase tracking-wider text-slate-500">Product Type</Label>
                                    <Select onValueChange={(val) => handleSelectChange('product_type', val)} value={formData.product_type}>
                                        <SelectTrigger className="h-12 bg-slate-50 border-2 border-slate-200 rounded-xl font-medium hover:border-violet-300 transition-colors">
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            {productTypes.map((pt) => (
                                                <SelectItem key={pt.value} value={pt.value}>{pt.label}</SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                </div>
                                <div className="space-y-2">
                                    <Label className="text-xs font-black uppercase tracking-wider text-slate-500">USP</Label>
                                    <Select onValueChange={(val) => handleSelectChange('usp', val)} value={formData.usp}>
                                        <SelectTrigger className="h-12 bg-slate-50 border-2 border-slate-200 rounded-xl font-medium hover:border-violet-300 transition-colors">
                                            <SelectValue placeholder="Select..." />
                                        </SelectTrigger>
                                        <SelectContent>
                                            {uspOptions.map((usp) => (
                                                <SelectItem key={usp.value} value={usp.value}>{usp.label}</SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                </div>
                            </div>

                            {/* Brand Vibe & Positioning Row */}
                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <Label className="text-xs font-black uppercase tracking-wider text-slate-500">Brand Vibe</Label>
                                    <Select onValueChange={(val) => handleSelectChange('brand_vibe', val)} value={formData.brand_vibe}>
                                        <SelectTrigger className="h-12 bg-slate-50 border-2 border-slate-200 rounded-xl font-medium hover:border-violet-300 transition-colors">
                                            <SelectValue placeholder="Select..." />
                                        </SelectTrigger>
                                        <SelectContent>
                                            {brandVibes.map((vibe) => (
                                                <SelectItem key={vibe.value} value={vibe.value}>{vibe.label}</SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                </div>
                                <div className="space-y-2">
                                    <Label className="text-xs font-black uppercase tracking-wider text-slate-500">Positioning</Label>
                                    <Select onValueChange={(val) => handleSelectChange('positioning', val)} value={formData.positioning}>
                                        <SelectTrigger className="h-12 bg-slate-50 border-2 border-slate-200 rounded-xl font-medium hover:border-violet-300 transition-colors">
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="Budget">Budget</SelectItem>
                                            <SelectItem value="Mid-Range">Mid-Range</SelectItem>
                                            <SelectItem value="Premium">Premium</SelectItem>
                                            <SelectItem value="Luxury">Luxury</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </div>
                            </div>

                            {/* Market Scope & Countries Row */}
                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <Label className="text-xs font-black uppercase tracking-wider text-slate-500">Market Scope</Label>
                                    <Select onValueChange={(val) => handleSelectChange('market_scope', val)} value={formData.market_scope}>
                                        <SelectTrigger className="h-12 bg-slate-50 border-2 border-slate-200 rounded-xl font-medium hover:border-violet-300 transition-colors">
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="Single Country">Single Country</SelectItem>
                                            <SelectItem value="Multi-Country">Multi-Country</SelectItem>
                                            <SelectItem value="Global">Global</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </div>
                                <div className="space-y-2">
                                    <Label className="text-xs font-black uppercase tracking-wider text-slate-500">Countries 🌍</Label>
                                    <Input 
                                        name="countries"
                                        value={formData.countries}
                                        onChange={handleChange}
                                        placeholder="USA, India, UK"
                                        className="h-12 bg-slate-50 border-2 border-slate-200 rounded-xl font-medium hover:border-violet-300 transition-colors"
                                    />
                                </div>
                            </div>

                            {/* NEW: Enhanced Accuracy Fields (Improvements #2 & #3) */}
                            <div className="border-t-2 border-dashed border-slate-200 pt-4 mt-2">
                                <div className="flex items-center gap-2 mb-3">
                                    <Target className="w-4 h-4 text-violet-500" />
                                    <span className="text-xs font-black uppercase tracking-wider text-violet-600">Enhanced Accuracy (Optional)</span>
                                </div>
                                
                                {/* Known Competitors & Product Keywords */}
                                <div className="grid grid-cols-2 gap-4">
                                    <div className="space-y-2">
                                        <Label className="text-xs font-black uppercase tracking-wider text-slate-500">Known Competitors 🎯</Label>
                                        <Input 
                                            name="known_competitors"
                                            value={formData.known_competitors}
                                            onChange={handleChange}
                                            placeholder="PhonePe, Paytm, GPay"
                                            className="h-12 bg-slate-50 border-2 border-slate-200 rounded-xl font-medium hover:border-violet-300 transition-colors"
                                        />
                                        <p className="text-[10px] text-slate-400">Top 3-5 competitors in your market</p>
                                    </div>
                                    <div className="space-y-2">
                                        <Label className="text-xs font-black uppercase tracking-wider text-slate-500">Product Keywords 🔑</Label>
                                        <Input 
                                            name="product_keywords"
                                            value={formData.product_keywords}
                                            onChange={handleChange}
                                            placeholder="UPI, wallet, payments"
                                            className="h-12 bg-slate-50 border-2 border-slate-200 rounded-xl font-medium hover:border-violet-300 transition-colors"
                                        />
                                        <p className="text-[10px] text-slate-400">Key terms describing your product</p>
                                    </div>
                                </div>
                            </div>

                            <Button 
                                type="submit" 
                                className="w-full h-14 bg-gradient-to-r from-violet-600 via-fuchsia-500 to-orange-500 hover:from-violet-700 hover:via-fuchsia-600 hover:to-orange-600 text-white text-lg font-black rounded-xl shadow-xl shadow-violet-300/50 hover:shadow-2xl hover:shadow-violet-400/50 hover:scale-[1.02] transition-all"
                                disabled={loading}
                            >
                                {loading ? (
                                    <>
                                        <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                                        Analyzing Magic... ✨
                                    </>
                                ) : (
                                    <>
                                        Generate Report
                                        <ArrowRight className="ml-2 h-5 w-5" />
                                    </>
                                )}
                            </Button>
                            
                            {/* Trusted By - Under Generate Report */}
                            <TrustedByCycler />
                        </form>
                    </CardContent>
                </Card>
            </div>
        </div>

        {/* Report Preview Carousel */}
        <ReportCarousel />

        {/* Feature Grid Section */}
        <div className="mt-28">
            <div className="text-center mb-16">
                <Badge className="mb-4 bg-violet-100 text-violet-700 border-violet-200 px-4 py-1.5 text-sm font-black">
                  💡 What We Analyze
                </Badge>
                <h2 className="text-4xl font-black text-slate-900 mb-4">
                  Everything a <span className="text-violet-600">$50k consultant</span> does.
                  <br />
                  <span className="text-fuchsia-600">In 30 seconds.</span>
                </h2>
                <p className="text-slate-500 font-medium max-w-2xl mx-auto text-lg">
                    Our AI replicates the complete workflow of premium brand consultancies.
                </p>
            </div>

            <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
                <FeatureCard 
                    icon={BrainCircuit}
                    title="Perception Mapping"
                    description="Map your name against 6 core brand dimensions including distinctiveness and trust."
                    color="bg-gradient-to-br from-violet-500 to-violet-600"
                    emoji="🧠"
                />
                <FeatureCard 
                    icon={ShieldCheck}
                    title="Legal Sensitivity"
                    description="Probabilistic risk assessment for trademark conflicts across global registries."
                    color="bg-gradient-to-br from-emerald-500 to-emerald-600"
                    emoji="⚖️"
                />
                <FeatureCard 
                    icon={Globe2}
                    title="Cultural Check"
                    description="Linguistic safety checks in 10+ languages to prevent embarrassing fails."
                    color="bg-gradient-to-br from-fuchsia-500 to-fuchsia-600"
                    emoji="🌍"
                />
                <FeatureCard 
                    icon={Search}
                    title="Domain Scout"
                    description="Instant availability for .com and strategic alternatives based on your industry."
                    color="bg-gradient-to-br from-orange-500 to-orange-600"
                    emoji="🔍"
                />
            </div>
        </div>

        {/* How It Works Section */}
        <div id="how-it-works" className="mt-28">
          <div className="text-center mb-16">
            <Badge className="mb-4 bg-emerald-100 text-emerald-700 border-emerald-200 px-4 py-1.5 text-sm font-black">
              🚀 How It Works
            </Badge>
            <h2 className="text-4xl font-black text-slate-900 mb-4">
              Three Steps to{' '}
              <span className="text-emerald-600">Brand Clarity</span>
            </h2>
            <p className="text-slate-500 font-medium max-w-2xl mx-auto text-lg">
              From idea to actionable insights in under 60 seconds.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-8 relative">
            {/* Connector Line */}
            <div className="hidden md:block absolute top-8 left-1/4 right-1/4 h-1 bg-gradient-to-r from-violet-300 via-fuchsia-300 to-orange-300 rounded-full" />
            
            <HowItWorksStep
              number="1"
              icon={FileText}
              title="Enter Brand Names"
              description="Add up to 3 brand name options you're considering. Include your industry and target market for context."
              color="bg-gradient-to-br from-violet-500 to-violet-600"
            />
            <HowItWorksStep
              number="2"
              icon={BrainCircuit}
              title="AI Analysis"
              description="Our AI checks trademark databases, domain availability, social handles, and cultural implications in real-time."
              color="bg-gradient-to-br from-fuchsia-500 to-fuchsia-600"
            />
            <HowItWorksStep
              number="3"
              icon={Target}
              title="Get Your Report"
              description="Receive a consulting-grade NameScore report with actionable recommendations and risk assessment."
              color="bg-gradient-to-br from-orange-500 to-orange-600"
            />
          </div>
        </div>

        {/* Use Cases Section */}
        <div className="mt-28">
          <div className="text-center mb-16">
            <Badge className="mb-4 bg-blue-100 text-blue-700 border-blue-200 px-4 py-1.5 text-sm font-black">
              👥 Who It Is For
            </Badge>
            <h2 className="text-4xl font-black text-slate-900 mb-4">
              Built for{' '}
              <span className="text-blue-600">Brand Builders</span>
            </h2>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
            <UseCaseCard
              icon={Rocket}
              title="Startup Founders"
              description="Validate your brand before investing in design, marketing, and legal registration."
              color="bg-gradient-to-br from-violet-500 to-violet-600"
            />
            <UseCaseCard
              icon={Users}
              title="Brand Consultants"
              description="Speed up client projects with AI-powered preliminary analysis and professional reports."
              color="bg-gradient-to-br from-blue-500 to-blue-600"
            />
            <UseCaseCard
              icon={Building2}
              title="Marketing Agencies"
              description="Add brand validation as a premium service. Generate unlimited reports for clients."
              color="bg-gradient-to-br from-emerald-500 to-emerald-600"
            />
            <UseCaseCard
              icon={Briefcase}
              title="Enterprise Teams"
              description="Standardize brand evaluation across product launches and market expansions."
              color="bg-gradient-to-br from-orange-500 to-orange-600"
            />
          </div>
        </div>

        {/* Testimonials Section */}
        <div className="mt-28">
          <div className="text-center mb-16">
            <Badge className="mb-4 bg-fuchsia-100 text-fuchsia-700 border-fuchsia-200 px-4 py-1.5 text-sm font-black">
              ⭐ Success Stories
            </Badge>
            <h2 className="text-4xl font-black text-slate-900 mb-4">
              Loved by{' '}
              <span className="text-fuchsia-600">500+ Founders</span>
            </h2>
          </div>

          <div className="grid md:grid-cols-3 gap-6">
            <TestimonialCard
              quote="RIGHTNAME saved us from a $50k trademark dispute. The AI caught a conflict our lawyers missed initially."
              author="Sarah Chen"
              role="Founder"
              company="TechFlow AI"
              avatar="SC"
            />
            <TestimonialCard
              quote="We use RIGHTNAME for every client project now. The reports are more comprehensive than what we used to deliver manually."
              author="Marcus Johnson"
              role="Brand Director"
              company="Spark Agency"
              avatar="MJ"
            />
            <TestimonialCard
              quote="The cultural analysis feature is incredible. It flagged issues with our name in 3 markets we hadn't considered."
              author="Priya Sharma"
              role="CEO"
              company="GlobalEats"
              avatar="PS"
            />
          </div>
        </div>

        {/* Pricing Preview */}
        <div className="mt-28 bg-gradient-to-br from-slate-50 to-violet-50/30 rounded-3xl p-12 border-2 border-slate-200">
          <div className="text-center mb-12">
            <Badge className="mb-4 bg-emerald-100 text-emerald-700 border-emerald-200 px-4 py-1.5 text-sm font-black">
              💰 Simple Pricing
            </Badge>
            <h2 className="text-4xl font-black text-slate-900 mb-4">
              Start{' '}
              <span className="text-emerald-600">Free</span>, Scale as You Grow
            </h2>
            <p className="text-slate-500 font-medium max-w-2xl mx-auto text-lg">
              No subscriptions. No hidden fees. Pay only when you need more reports.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-8 max-w-4xl mx-auto">
            <div className="bg-white rounded-2xl p-6 border-2 border-emerald-200 text-center">
              <div className="text-4xl mb-2">🎁</div>
              <h3 className="font-black text-xl text-slate-900 mb-1">Free Trial</h3>
              <p className="text-3xl font-black text-emerald-600 mb-2">$0</p>
              <p className="text-slate-500 text-sm">First report free</p>
            </div>
            <div className="bg-white rounded-2xl p-6 border-2 border-blue-200 text-center">
              <div className="text-4xl mb-2">📄</div>
              <h3 className="font-black text-xl text-slate-900 mb-1">Single Report</h3>
              <p className="text-3xl font-black text-blue-600 mb-2">$29</p>
              <p className="text-slate-500 text-sm">Per evaluation</p>
            </div>
            <div className="bg-white rounded-2xl p-6 border-2 border-violet-300 text-center relative overflow-hidden">
              <div className="absolute top-0 right-0 bg-violet-600 text-white text-xs font-bold px-3 py-1 rounded-bl-xl">BEST VALUE</div>
              <div className="text-4xl mb-2">👑</div>
              <h3 className="font-black text-xl text-slate-900 mb-1">3-Report Bundle</h3>
              <p className="text-3xl font-black text-violet-600 mb-2">$49</p>
              <p className="text-slate-500 text-sm">Save $38</p>
            </div>
          </div>

          <div className="text-center mt-8">
            <Link to="/pricing">
              <Button className="bg-violet-600 hover:bg-violet-700 text-white font-bold px-8 py-6 rounded-xl text-lg">
                View Full Pricing <ArrowRight className="ml-2 w-5 h-5" />
              </Button>
            </Link>
          </div>
        </div>

        {/* FAQ Section */}
        <div id="faq" className="mt-28">
          <div className="text-center mb-16">
            <Badge className="mb-4 bg-orange-100 text-orange-700 border-orange-200 px-4 py-1.5 text-sm font-black">
              ❓ FAQ
            </Badge>
            <h2 className="text-4xl font-black text-slate-900 mb-4">
              Frequently Asked{' '}
              <span className="text-orange-600">Questions</span>
            </h2>
          </div>

          <div className="max-w-3xl mx-auto space-y-4">
            {[
              {
                q: "What is RIGHTNAME?",
                a: "RIGHTNAME is an AI-powered brand name evaluation tool that provides consulting-grade analysis of brand names. It checks trademark conflicts, domain availability, social media handles, and generates a comprehensive NameScore report in under 60 seconds."
              },
              {
                q: "How much does RIGHTNAME cost?",
                a: "Your first report is completely FREE with no credit card required. After that, single reports cost $29 each, or you can get a bundle of 3 reports for $49 (saving $38)."
              },
              {
                q: "What does a RIGHTNAME report include?",
                a: "Each report includes: NameScore Index (0-100), Trademark Risk Matrix, Domain Availability Check, Social Handle Availability, Competitive Landscape Analysis, Cultural & Linguistic Analysis, Registration Timeline & Costs, Mitigation Strategies, and Alternative Name Suggestions."
              },
              {
                q: "How long does it take to generate a report?",
                a: "Most reports are generated in 45-90 seconds. Our AI performs real-time trademark searches, domain checks, and comprehensive analysis to deliver consulting-grade insights quickly."
              },
              {
                q: "Is RIGHTNAME accurate for trademark checking?",
                a: "RIGHTNAME uses real-time web searches of trademark databases, phonetic similarity algorithms, and AI analysis to identify potential conflicts. While it provides comprehensive preliminary screening, we recommend consulting a trademark attorney for official legal advice before registration."
              },
              {
                q: "Can I evaluate multiple brand names at once?",
                a: "Yes! Each report can analyze up to 3 brand name options with side-by-side comparison and recommendations to help you choose the best option."
              },
              {
                q: "Which countries do you support?",
                a: "We support trademark analysis for 15+ countries including USA, India, UK, Canada, Australia, Germany, France, Japan, China, Brazil, UAE, Singapore, and more. Each report includes country-specific registration costs and timelines."
              }
            ].map((faq, index) => (
              <FAQItem
                key={index}
                question={faq.q}
                answer={faq.a}
                isOpen={openFAQ === index}
                onClick={() => setOpenFAQ(openFAQ === index ? null : index)}
              />
            ))}
          </div>
        </div>

        {/* CTA Section */}
        <div className="mt-28 relative">
          <div className="absolute inset-0 bg-gradient-to-r from-violet-600 via-fuchsia-500 to-orange-500 rounded-[2rem] blur-xl opacity-20"></div>
          <div className="relative bg-gradient-to-r from-violet-600 via-fuchsia-500 to-orange-500 rounded-[2rem] p-12 text-center text-white overflow-hidden">
            <div className="absolute top-4 left-4 text-6xl opacity-20">✨</div>
            <div className="absolute bottom-4 right-4 text-6xl opacity-20">🚀</div>
            <h2 className="text-3xl lg:text-4xl font-black mb-4">Ready to find your perfect name?</h2>
            <p className="text-lg text-white/80 mb-8 max-w-xl mx-auto">Join thousands of founders who have validated their brand names with RIGHTNAME.</p>
            <Button 
              onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
              className="bg-white text-violet-700 hover:bg-slate-100 font-black text-lg px-8 py-6 rounded-xl shadow-xl hover:scale-105 transition-transform"
            >
              Start Free Analysis <ArrowRight className="ml-2 w-5 h-5" />
            </Button>
          </div>
        </div>

      </div>
      
      {/* Footer */}
      <Footer />
    </div>
    </>
  );
};

export default LandingPage;
