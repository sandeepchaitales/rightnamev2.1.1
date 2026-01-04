import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Helmet } from 'react-helmet-async';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { 
    Search, 
    Building2, 
    Globe, 
    Users, 
    BarChart3, 
    Target,
    TrendingUp,
    Shield,
    ArrowRight,
    Loader2,
    CheckCircle2,
    ChevronDown,
    Sparkles
} from 'lucide-react';

// Logo URL - same as main tool
const LOGO_URL = "https://customer-assets.emergentagent.com/job_naming-hub/artifacts/vj8cw9xx_R.png";

// Categories
const CATEGORIES = [
    "Food & Beverage",
    "Retail",
    "Technology",
    "Healthcare",
    "Finance",
    "Education",
    "Real Estate",
    "Hospitality",
    "Fashion & Apparel",
    "Automotive",
    "E-commerce",
    "Entertainment",
    "Manufacturing",
    "Logistics",
    "Professional Services",
    "Other"
];

// Geographies
const GEOGRAPHIES = [
    "India",
    "USA",
    "UK",
    "UAE",
    "Singapore",
    "Australia",
    "Canada",
    "Germany",
    "France",
    "Japan",
    "Global"
];

// API
const API_URL = process.env.NODE_ENV === 'production' ? '/api' : `${process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001'}/api`;

const BrandAuditLanding = () => {
    const navigate = useNavigate();
    const [loading, setLoading] = useState(false);
    const [formData, setFormData] = useState({
        brand_name: '',
        brand_website: '',
        competitor_1: '',
        competitor_2: '',
        category: '',
        geography: ''
    });

    const handleSubmit = async (e) => {
        e.preventDefault();
        
        // Validation
        if (!formData.brand_name || !formData.brand_website || !formData.competitor_1 || 
            !formData.competitor_2 || !formData.category || !formData.geography) {
            toast.error('Please fill in all fields');
            return;
        }

        setLoading(true);

        try {
            const response = await fetch(`${API_URL}/brand-audit`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(formData)
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Audit failed');
            }

            const result = await response.json();
            navigate('/brand-audit/results', { state: { data: result, query: formData } });
        } catch (error) {
            console.error(error);
            toast.error(
                <div className="flex flex-col gap-1">
                    <span className="font-bold">Audit Failed</span>
                    <span className="text-xs">{error.message}</span>
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
                <title>Brand Audit | RIGHTNAME - Free Brand Health Check</title>
                <meta name="description" content="Free comprehensive brand audit tool. Analyze your brand health, competitive position, and get strategic recommendations." />
            </Helmet>

            <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-violet-50">
                {/* Navigation */}
                <nav className="border-b border-slate-200 bg-white/80 backdrop-blur-sm sticky top-0 z-50">
                    <div className="max-w-7xl mx-auto px-6 py-4">
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-3 cursor-pointer" onClick={() => navigate('/')}>
                                <img src={LOGO_URL} alt="RIGHTNAME" className="h-8" />
                            </div>
                            <div className="flex items-center gap-6">
                                <Link to="/" className="text-sm font-semibold text-slate-600 hover:text-violet-600 transition-colors">Home</Link>
                                
                                {/* Tools Dropdown */}
                                <DropdownMenu>
                                    <DropdownMenuTrigger className="flex items-center gap-1 text-sm font-semibold text-slate-600 hover:text-violet-600 transition-colors outline-none">
                                        Tools
                                        <ChevronDown className="w-4 h-4" />
                                    </DropdownMenuTrigger>
                                    <DropdownMenuContent align="start" className="w-56">
                                        <DropdownMenuItem asChild>
                                            <Link to="/" className="flex items-center gap-3 cursor-pointer">
                                                <div className="p-1.5 bg-violet-100 rounded-lg">
                                                    <Sparkles className="w-4 h-4 text-violet-600" />
                                                </div>
                                                <div>
                                                    <div className="font-semibold text-slate-900">Brand Evaluation</div>
                                                    <div className="text-xs text-slate-500">For New Brands</div>
                                                </div>
                                            </Link>
                                        </DropdownMenuItem>
                                        <DropdownMenuItem asChild>
                                            <Link to="/brand-audit" className="flex items-center gap-3 cursor-pointer">
                                                <div className="p-1.5 bg-emerald-100 rounded-lg">
                                                    <BarChart3 className="w-4 h-4 text-emerald-600" />
                                                </div>
                                                <div>
                                                    <div className="font-semibold text-slate-900">Brand Audit</div>
                                                    <div className="text-xs text-slate-500">For Existing Brands</div>
                                                </div>
                                            </Link>
                                        </DropdownMenuItem>
                                    </DropdownMenuContent>
                                </DropdownMenu>
                            </div>
                        </div>
                    </div>
                </nav>

                {/* Hero Section */}
                <section className="py-16 px-6">
                    <div className="max-w-4xl mx-auto text-center">
                        <div className="inline-flex items-center gap-2 px-4 py-2 bg-emerald-100 text-emerald-700 rounded-full text-sm font-semibold mb-6">
                            <CheckCircle2 className="w-4 h-4" />
                            100% FREE Tool
                        </div>
                        <h1 className="text-5xl md:text-6xl font-black text-slate-900 mb-6">
                            Brand <span className="text-violet-600">Audit</span>
                        </h1>
                        <p className="text-xl text-slate-600 mb-8 max-w-2xl mx-auto">
                            Get institutional-grade brand analysis with competitive benchmarking, 
                            SWOT analysis, and strategic recommendations.
                        </p>

                        {/* Features Grid */}
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-12">
                            {[
                                { icon: BarChart3, label: "8-Dimension Scoring" },
                                { icon: Users, label: "Competitor Analysis" },
                                { icon: Target, label: "SWOT Analysis" },
                                { icon: TrendingUp, label: "Strategic Roadmap" }
                            ].map((feature, i) => (
                                <div key={i} className="flex flex-col items-center gap-2 p-4 bg-white rounded-xl border border-slate-200">
                                    <feature.icon className="w-6 h-6 text-violet-600" />
                                    <span className="text-sm font-medium text-slate-700">{feature.label}</span>
                                </div>
                            ))}
                        </div>
                    </div>
                </section>

                {/* Form Section */}
                <section className="pb-20 px-6">
                    <div className="max-w-2xl mx-auto">
                        <form onSubmit={handleSubmit} className="bg-white rounded-2xl border border-slate-200 shadow-xl p-8">
                            <h2 className="text-2xl font-bold text-slate-900 mb-6 flex items-center gap-2">
                                <Search className="w-6 h-6 text-violet-600" />
                                Start Your Brand Audit
                            </h2>

                            <div className="space-y-6">
                                {/* Brand Name */}
                                <div>
                                    <Label htmlFor="brand_name" className="text-slate-700 font-semibold flex items-center gap-2">
                                        <Building2 className="w-4 h-4" />
                                        Brand Name
                                    </Label>
                                    <Input
                                        id="brand_name"
                                        placeholder="e.g., Chai Bunk"
                                        value={formData.brand_name}
                                        onChange={(e) => setFormData({...formData, brand_name: e.target.value})}
                                        className="mt-2"
                                    />
                                </div>

                                {/* Brand Website */}
                                <div>
                                    <Label htmlFor="brand_website" className="text-slate-700 font-semibold flex items-center gap-2">
                                        <Globe className="w-4 h-4" />
                                        Brand Website
                                    </Label>
                                    <Input
                                        id="brand_website"
                                        placeholder="e.g., chaibunk.com"
                                        value={formData.brand_website}
                                        onChange={(e) => setFormData({...formData, brand_website: e.target.value})}
                                        className="mt-2"
                                    />
                                </div>

                                {/* Competitors */}
                                <div className="grid grid-cols-2 gap-4">
                                    <div>
                                        <Label htmlFor="competitor_1" className="text-slate-700 font-semibold flex items-center gap-2">
                                            <Users className="w-4 h-4" />
                                            Competitor 1
                                        </Label>
                                        <Input
                                            id="competitor_1"
                                            placeholder="e.g., chaayos.com"
                                            value={formData.competitor_1}
                                            onChange={(e) => setFormData({...formData, competitor_1: e.target.value})}
                                            className="mt-2"
                                        />
                                    </div>
                                    <div>
                                        <Label htmlFor="competitor_2" className="text-slate-700 font-semibold flex items-center gap-2">
                                            <Users className="w-4 h-4" />
                                            Competitor 2
                                        </Label>
                                        <Input
                                            id="competitor_2"
                                            placeholder="e.g., chaipoint.com"
                                            value={formData.competitor_2}
                                            onChange={(e) => setFormData({...formData, competitor_2: e.target.value})}
                                            className="mt-2"
                                        />
                                    </div>
                                </div>

                                {/* Category & Geography */}
                                <div className="grid grid-cols-2 gap-4">
                                    <div>
                                        <Label className="text-slate-700 font-semibold flex items-center gap-2">
                                            <Target className="w-4 h-4" />
                                            Category
                                        </Label>
                                        <Select 
                                            value={formData.category} 
                                            onValueChange={(v) => setFormData({...formData, category: v})}
                                        >
                                            <SelectTrigger className="mt-2">
                                                <SelectValue placeholder="Select category" />
                                            </SelectTrigger>
                                            <SelectContent>
                                                {CATEGORIES.map((cat) => (
                                                    <SelectItem key={cat} value={cat}>{cat}</SelectItem>
                                                ))}
                                            </SelectContent>
                                        </Select>
                                    </div>
                                    <div>
                                        <Label className="text-slate-700 font-semibold flex items-center gap-2">
                                            <Globe className="w-4 h-4" />
                                            Geography
                                        </Label>
                                        <Select 
                                            value={formData.geography} 
                                            onValueChange={(v) => setFormData({...formData, geography: v})}
                                        >
                                            <SelectTrigger className="mt-2">
                                                <SelectValue placeholder="Select geography" />
                                            </SelectTrigger>
                                            <SelectContent>
                                                {GEOGRAPHIES.map((geo) => (
                                                    <SelectItem key={geo} value={geo}>{geo}</SelectItem>
                                                ))}
                                            </SelectContent>
                                        </Select>
                                    </div>
                                </div>

                                {/* Submit Button */}
                                <Button 
                                    type="submit" 
                                    disabled={loading}
                                    className="w-full bg-gradient-to-r from-violet-600 to-fuchsia-600 hover:from-violet-700 hover:to-fuchsia-700 text-white font-bold py-6 text-lg rounded-xl"
                                >
                                    {loading ? (
                                        <>
                                            <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                                            Analyzing Brand (2-3 min)...
                                        </>
                                    ) : (
                                        <>
                                            Start Brand Audit
                                            <ArrowRight className="w-5 h-5 ml-2" />
                                        </>
                                    )}
                                </Button>

                                {loading && (
                                    <div className="bg-violet-50 border border-violet-200 rounded-xl p-4">
                                        <p className="text-sm text-violet-700 text-center">
                                            <strong>4-Phase Research in Progress:</strong><br />
                                            Brand Research → Competitive Analysis → Benchmarking → Validation
                                        </p>
                                    </div>
                                )}
                            </div>
                        </form>

                        {/* Info Cards */}
                        <div className="mt-8 grid grid-cols-1 md:grid-cols-3 gap-4">
                            <div className="bg-white rounded-xl p-4 border border-slate-200">
                                <Shield className="w-8 h-8 text-emerald-600 mb-2" />
                                <h3 className="font-bold text-slate-900">Institutional Grade</h3>
                                <p className="text-sm text-slate-600">Fortune 500 consulting-grade analysis methodology</p>
                            </div>
                            <div className="bg-white rounded-xl p-4 border border-slate-200">
                                <BarChart3 className="w-8 h-8 text-violet-600 mb-2" />
                                <h3 className="font-bold text-slate-900">8-Dimension Scoring</h3>
                                <p className="text-sm text-slate-600">Comprehensive brand health assessment</p>
                            </div>
                            <div className="bg-white rounded-xl p-4 border border-slate-200">
                                <TrendingUp className="w-8 h-8 text-amber-600 mb-2" />
                                <h3 className="font-bold text-slate-900">Strategic Roadmap</h3>
                                <p className="text-sm text-slate-600">0-6m, 6-18m, 18-36m recommendations</p>
                            </div>
                        </div>
                    </div>
                </section>

                {/* Footer */}
                <footer className="border-t border-slate-200 py-8 px-6 bg-white">
                    <div className="max-w-7xl mx-auto text-center">
                        <p className="text-slate-500 text-sm">
                            © 2025 RIGHTNAME. Free Brand Audit Tool.
                        </p>
                    </div>
                </footer>
            </div>
        </>
    );
};

export default BrandAuditLanding;
