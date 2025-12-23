import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Loader2, Sparkles, ShieldCheck, Globe2, BrainCircuit, Search, ArrowRight, Zap, AlertCircle } from "lucide-react";
import { toast } from "sonner";

const FeatureCard = ({ icon: Icon, title, description, color }) => (
  <div className={`p-6 rounded-2xl bg-white border border-slate-100 shadow-sm hover:shadow-md transition-all duration-300 hover:translate-y-[-4px] group`}>
    <div className={`w-12 h-12 rounded-xl ${color} flex items-center justify-center mb-4 group-hover:scale-110 transition-transform`}>
      <Icon className="w-6 h-6 text-white" />
    </div>
    <h3 className="font-bold text-lg text-slate-900 mb-2">{title}</h3>
    <p className="text-sm text-slate-500 font-medium leading-relaxed">{description}</p>
  </div>
);

const LandingPage = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState({
    brand_names: '',
    industry: '',
    category: '',
    product_type: 'Digital',
    usp: '',
    brand_vibe: '',
    positioning: 'Premium',
    market_scope: 'Multi-Country',
    countries: ''
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

  // Product Type options
  const productTypes = [
    { value: "Physical", label: "Physical Product" },
    { value: "Digital", label: "Digital Product/App" },
    { value: "Service", label: "Service" },
    { value: "Hybrid", label: "Hybrid (Product + Service)" }
  ];

  // USP options
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

  // Brand Vibe options
  const brandVibes = [
    { value: "Serious", label: "Serious & Professional" },
    { value: "Playful", label: "Playful & Fun" },
    { value: "Modern", label: "Modern & Innovative" },
    { value: "Classic", label: "Classic & Timeless" },
    { value: "Luxurious", label: "Luxurious & Premium" },
    { value: "Bold", label: "Bold & Edgy" },
    { value: "Friendly", label: "Friendly & Approachable" },
    { value: "Minimalist", label: "Minimalist & Clean" },
    { value: "Adventurous", label: "Adventurous & Dynamic" },
    { value: "Trustworthy", label: "Trustworthy & Reliable" },
    { value: "Youthful", label: "Youthful & Energetic" },
    { value: "Sophisticated", label: "Sophisticated & Elegant" }
  ];

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleSelectChange = (name, value) => {
    setFormData({ ...formData, [name]: value });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      const brands = formData.brand_names.split(',').map(s => s.trim()).filter(Boolean);
      const countriesList = formData.countries.split(',').map(s => s.trim()).filter(Boolean);
      
      if (brands.length === 0) {
        toast.error("Please enter at least one brand name.");
        setLoading(false);
        return;
      }

      if (countriesList.length === 0) {
        toast.error("Please enter at least one target country.");
        setLoading(false);
        return;
      }

      const payload = {
        brand_names: brands,
        industry: formData.industry,
        category: formData.category,
        product_type: formData.product_type,
        usp: formData.usp,
        brand_vibe: formData.brand_vibe,
        positioning: formData.positioning,
        market_scope: formData.market_scope,
        countries: countriesList
      };

      const result = await api.evaluate(payload);
      navigate('/dashboard', { state: { data: result, query: payload } });
    } catch (error) {
      console.error(error);
      const errorMsg = error.response?.data?.detail || "Evaluation failed. Please try again.";
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
    <div className="min-h-screen bg-[#f8fafc] font-sans selection:bg-violet-200">
      {/* Decorative Background Elements */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-[-10%] right-[-5%] w-[500px] h-[500px] bg-violet-200/40 rounded-full blur-[100px]" />
        <div className="absolute bottom-[10%] left-[-10%] w-[400px] h-[400px] bg-cyan-200/40 rounded-full blur-[100px]" />
      </div>

      <div className="relative max-w-7xl mx-auto px-6 py-12 lg:py-20">
        
        {/* Navbar-ish Header */}
        <div className="flex justify-between items-center mb-16 lg:mb-24">
            <div className="flex items-center gap-2">
                <div className="w-10 h-10 bg-gradient-to-br from-violet-600 to-fuchsia-600 rounded-xl flex items-center justify-center shadow-lg shadow-violet-200">
                    <Sparkles className="w-6 h-6 text-white" />
                </div>
                <h1 className="text-2xl font-black bg-clip-text text-transparent bg-gradient-to-r from-violet-600 to-fuchsia-600 tracking-tight">RIGHTNAME</h1>
            </div>
            <Badge variant="outline" className="hidden md:flex border-violet-200 text-violet-700 px-4 py-1.5 rounded-full font-bold bg-white">
                v2.2 Research Mode
            </Badge>
        </div>

        <div className="grid lg:grid-cols-2 gap-16 lg:gap-24 items-center">
            
            {/* Left Content: Hero Text */}
            <div className="space-y-8 relative z-10">
                <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white border border-slate-100 shadow-sm text-sm font-bold text-slate-600">
                    <span className="relative flex h-3 w-3">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                      <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
                    </span>
                    AI-Powered Brand Consultant
                </div>
                
                <h1 className="text-5xl lg:text-7xl font-black text-slate-900 leading-[1.1] tracking-tight">
                    Validate your <br />
                    <span className="text-transparent bg-clip-text bg-gradient-to-r from-violet-600 via-fuchsia-500 to-orange-500">
                        next unicorn
                    </span>
                    <br /> in seconds.
                </h1>
                
                <p className="text-xl text-slate-500 font-medium leading-relaxed max-w-lg">
                    Don't guess. Get a consulting-grade audit on trademark risk, cultural resonance, and domain availability instantly.
                </p>

                <div className="grid grid-cols-2 gap-4 pt-4">
                    <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-full bg-green-100 flex items-center justify-center">
                            <ShieldCheck className="w-5 h-5 text-green-600" />
                        </div>
                        <span className="font-bold text-slate-700">Legal Risk Check</span>
                    </div>
                    <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center">
                            <Globe2 className="w-5 h-5 text-blue-600" />
                        </div>
                        <span className="font-bold text-slate-700">Global Culture Fit</span>
                    </div>
                    <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-full bg-purple-100 flex items-center justify-center">
                            <BrainCircuit className="w-5 h-5 text-purple-600" />
                        </div>
                        <span className="font-bold text-slate-700">AI Perception</span>
                    </div>
                    <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-full bg-orange-100 flex items-center justify-center">
                            <Search className="w-5 h-5 text-orange-600" />
                        </div>
                        <span className="font-bold text-slate-700">Domain Scout</span>
                    </div>
                </div>
            </div>

            {/* Right Content: The "Console" Form */}
            <div className="relative z-10">
                <div className="absolute -inset-1 bg-gradient-to-r from-violet-600 to-fuchsia-600 rounded-3xl blur opacity-20"></div>
                <Card className="border-0 shadow-2xl rounded-3xl overflow-hidden bg-white/80 backdrop-blur-xl relative">
                    <CardContent className="p-8">
                        <div className="flex items-center justify-between mb-8">
                            <h3 className="text-xl font-black text-slate-900 flex items-center gap-2">
                                <Zap className="w-5 h-5 text-amber-500 fill-current" />
                                Start Analysis
                            </h3>
                            <div className="flex gap-1.5">
                                <div className="w-3 h-3 rounded-full bg-red-400/30"></div>
                                <div className="w-3 h-3 rounded-full bg-amber-400/30"></div>
                                <div className="w-3 h-3 rounded-full bg-green-400/30"></div>
                            </div>
                        </div>

                        <form onSubmit={handleSubmit} className="space-y-5">
                            <div className="space-y-2">
                                <Label className="text-xs font-bold uppercase tracking-wider text-slate-500">Brand Name(s)</Label>
                                <Input 
                                    name="brand_names"
                                    value={formData.brand_names}
                                    onChange={handleChange}
                                    placeholder="e.g. LUMINA, VESTRA"
                                    className="h-12 bg-white border-slate-200 focus:border-violet-500 focus:ring-violet-200 font-bold text-lg rounded-xl"
                                    required
                                />
                            </div>

                            {/* Industry & Category Row */}
                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <Label className="text-xs font-bold uppercase tracking-wider text-slate-500">Industry</Label>
                                    <Select onValueChange={(val) => handleSelectChange('industry', val)} value={formData.industry}>
                                        <SelectTrigger className="h-11 bg-white border-slate-200 rounded-xl font-medium">
                                            <SelectValue placeholder="Select industry..." />
                                        </SelectTrigger>
                                        <SelectContent className="max-h-[300px]">
                                            {industries.map((ind) => (
                                                <SelectItem key={ind} value={ind}>{ind}</SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                </div>
                                <div className="space-y-2">
                                    <Label className="text-xs font-bold uppercase tracking-wider text-slate-500">Category</Label>
                                    <Input 
                                        name="category"
                                        value={formData.category}
                                        onChange={handleChange}
                                        placeholder="e.g. Mobile Payments"
                                        className="h-11 bg-white border-slate-200 rounded-xl font-medium"
                                        required
                                    />
                                </div>
                            </div>

                            {/* Product Type & USP Row */}
                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <Label className="text-xs font-bold uppercase tracking-wider text-slate-500">Product Type</Label>
                                    <Select onValueChange={(val) => handleSelectChange('product_type', val)} defaultValue={formData.product_type}>
                                        <SelectTrigger className="h-11 bg-white border-slate-200 rounded-xl font-medium">
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
                                    <Label className="text-xs font-bold uppercase tracking-wider text-slate-500">USP (Pick One)</Label>
                                    <Select onValueChange={(val) => handleSelectChange('usp', val)} value={formData.usp}>
                                        <SelectTrigger className="h-11 bg-white border-slate-200 rounded-xl font-medium">
                                            <SelectValue placeholder="Select USP..." />
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
                                    <Label className="text-xs font-bold uppercase tracking-wider text-slate-500">Brand Vibe</Label>
                                    <Select onValueChange={(val) => handleSelectChange('brand_vibe', val)} value={formData.brand_vibe}>
                                        <SelectTrigger className="h-11 bg-white border-slate-200 rounded-xl font-medium">
                                            <SelectValue placeholder="Select vibe..." />
                                        </SelectTrigger>
                                        <SelectContent>
                                            {brandVibes.map((vibe) => (
                                                <SelectItem key={vibe.value} value={vibe.value}>{vibe.label}</SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                </div>
                                <div className="space-y-2">
                                    <Label className="text-xs font-bold uppercase tracking-wider text-slate-500">Positioning</Label>
                                    <Select onValueChange={(val) => handleSelectChange('positioning', val)} defaultValue={formData.positioning}>
                                        <SelectTrigger className="h-11 bg-white border-slate-200 rounded-xl font-medium">
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="Mass">Mass Market</SelectItem>
                                            <SelectItem value="Premium">Premium</SelectItem>
                                            <SelectItem value="Ultra-Premium">Ultra-Premium</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </div>
                            </div>

                            {/* Market Scope & Countries Row */}
                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <Label className="text-xs font-bold uppercase tracking-wider text-slate-500">Market Scope</Label>
                                    <Select onValueChange={(val) => handleSelectChange('market_scope', val)} defaultValue={formData.market_scope}>
                                        <SelectTrigger className="h-11 bg-white border-slate-200 rounded-xl font-medium">
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
                                    <Label className="text-xs font-bold uppercase tracking-wider text-slate-500">Target Countries</Label>
                                    <Input 
                                        name="countries"
                                        value={formData.countries}
                                        onChange={handleChange}
                                        placeholder="e.g. USA, India"
                                        className="h-11 bg-white border-slate-200 rounded-xl font-medium"
                                        required
                                    />
                                </div>
                            </div>

                            <Button 
                                type="submit" 
                                className="w-full h-14 bg-slate-900 hover:bg-slate-800 text-white font-bold text-lg rounded-xl shadow-xl shadow-slate-200 transition-all hover:scale-[1.02] active:scale-[0.98] mt-4"
                                disabled={loading}
                            >
                                {loading ? (
                                    <>
                                        <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                                        Running Analysis...
                                    </>
                                ) : (
                                    <>
                                        Generate Report <ArrowRight className="ml-2 w-5 h-5" />
                                    </>
                                )}
                            </Button>
                        </form>
                    </CardContent>
                </Card>
            </div>
        </div>

        {/* Feature Grid Section */}
        <div className="mt-32">
            <div className="text-center mb-16">
                <h2 className="text-3xl font-black text-slate-900 mb-4">What we analyze</h2>
                <p className="text-slate-500 font-medium max-w-2xl mx-auto">
                    Our AI models replicate the workflow of a $50k/month brand consultancy in seconds.
                </p>
            </div>

            <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
                <FeatureCard 
                    icon={BrainCircuit}
                    title="Perception Mapping"
                    description="We map your name against 6 core brand dimensions including distinctiveness and trust."
                    color="bg-violet-500"
                />
                <FeatureCard 
                    icon={ShieldCheck}
                    title="Legal Sensitivity"
                    description="Probabilistic risk assessment for trademark conflicts across major global registries."
                    color="bg-emerald-500"
                />
                <FeatureCard 
                    icon={Globe2}
                    title="Cultural Check"
                    description="Linguistic safety checks in 10+ languages to prevent embarrassing localization fails."
                    color="bg-fuchsia-500"
                />
                <FeatureCard 
                    icon={Search}
                    title="Domain Scout"
                    description="Instant availability checks for .com and strategic alternatives."
                    color="bg-orange-500"
                />
            </div>
        </div>

        {/* Trust Footer */}
        <div className="mt-32 border-t border-slate-200 pt-12 text-center pb-12">
            <p className="text-sm font-bold text-slate-400 uppercase tracking-widest mb-6">Powered By</p>
            <div className="flex justify-center items-center gap-8 opacity-50 grayscale hover:grayscale-0 transition-all duration-500">
                 {/* Pseudo-logos text for effect */}
                 <span className="font-serif text-2xl font-bold text-slate-800">Anthropic</span>
                 <span className="font-sans text-2xl font-black text-slate-800">Emergent</span>
                 <span className="font-mono text-xl font-bold text-slate-800">React</span>
                 <span className="font-sans text-xl font-bold text-slate-800">FastAPI</span>
            </div>
        </div>

      </div>
    </div>
  );
};

export default LandingPage;
