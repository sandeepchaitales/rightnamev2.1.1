import React, { useState } from 'react';
import { Check, Zap, Crown, ArrowRight, Sparkles, Shield, Globe, Target } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';

const PricingSection = ({ onSelectPackage, brandNames = [] }) => {
  const [loading, setLoading] = useState(null);
  const [email, setEmail] = useState('');

  const packages = [
    {
      id: 'single_report',
      name: 'Single Report',
      price: 29,
      description: 'Perfect for validating your top choice',
      credits: 1,
      features: [
        'Full trademark analysis',
        'DuPont 13-Factor confusion test',
        'Competitor landscape mapping',
        'Domain & social availability',
        '4 country market analysis'
      ],
      cta: 'Validate 1 Name',
      icon: Target
    },
    {
      id: 'founders_pack',
      name: "Founder's Pack",
      price: 49,
      originalPrice: 87,
      description: 'Most founders choose this',
      credits: 3,
      popular: true,
      savings: 38,
      features: [
        'Everything in Single Report',
        '3 complete brand reports',
        'Side-by-side comparison',
        'Winner recommendation',
        'Best value for finalists'
      ],
      cta: 'Validate 3 Names',
      icon: Crown
    }
  ];

  const handleSelectPackage = async (packageId) => {
    if (!email) {
      alert('Please enter your email to continue');
      return;
    }
    
    setLoading(packageId);
    
    try {
      const response = await fetch(`${BACKEND_URL}/api/payments/checkout/create`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          package_id: packageId,
          origin_url: window.location.origin,
          email: email,
          brand_names: brandNames
        })
      });
      
      if (!response.ok) {
        throw new Error('Failed to create checkout');
      }
      
      const data = await response.json();
      
      // Store session info for after payment
      localStorage.setItem('pending_payment', JSON.stringify({
        session_id: data.session_id,
        package_id: packageId,
        email: email
      }));
      
      // Redirect to Stripe Checkout
      window.location.href = data.checkout_url;
      
    } catch (error) {
      console.error('Checkout error:', error);
      alert('Failed to start checkout. Please try again.');
    } finally {
      setLoading(null);
    }
  };

  return (
    <div className="py-16 px-4">
      <div className="max-w-5xl mx-auto">
        {/* Header */}
        <div className="text-center mb-12">
          <div className="inline-flex items-center gap-2 bg-violet-100 text-violet-700 px-4 py-2 rounded-full text-sm font-medium mb-4">
            <Sparkles className="w-4 h-4" />
            You've narrowed down to 2-3 names. Now validate them.
          </div>
          <h2 className="text-4xl font-black text-slate-900 mb-4">
            Validate Your Brand Name in Seconds
            <br />
            <span className="text-violet-600">Not Months or Thousands</span>
          </h2>
          <p className="text-lg text-slate-600 max-w-2xl mx-auto">
            Get comprehensive trademark analysis, competitor insights, and market positioning 
            — everything you need to launch with confidence.
          </p>
        </div>

        {/* Email Input */}
        <div className="max-w-md mx-auto mb-10">
          <label className="block text-sm font-medium text-slate-700 mb-2">
            Your email for report delivery
          </label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="founder@startup.com"
            className="w-full px-4 py-3 border-2 border-slate-200 rounded-xl focus:border-violet-500 focus:outline-none text-lg"
          />
        </div>

        {/* Pricing Cards */}
        <div className="grid md:grid-cols-2 gap-8 max-w-4xl mx-auto">
          {packages.map((pkg) => {
            const Icon = pkg.icon;
            return (
              <div
                key={pkg.id}
                className={`relative bg-white rounded-3xl p-8 ${
                  pkg.popular 
                    ? 'border-2 border-violet-500 shadow-2xl shadow-violet-500/20 scale-105' 
                    : 'border border-slate-200 shadow-lg'
                }`}
              >
                {/* Popular Badge */}
                {pkg.popular && (
                  <div className="absolute -top-4 left-1/2 -translate-x-1/2">
                    <div className="bg-gradient-to-r from-violet-600 to-purple-600 text-white px-6 py-2 rounded-full text-sm font-bold flex items-center gap-2">
                      <Crown className="w-4 h-4" />
                      MOST POPULAR
                    </div>
                  </div>
                )}

                {/* Header */}
                <div className="text-center mb-6">
                  <div className={`inline-flex items-center justify-center w-14 h-14 rounded-2xl mb-4 ${
                    pkg.popular ? 'bg-violet-100' : 'bg-slate-100'
                  }`}>
                    <Icon className={`w-7 h-7 ${pkg.popular ? 'text-violet-600' : 'text-slate-600'}`} />
                  </div>
                  <h3 className="text-2xl font-bold text-slate-900">{pkg.name}</h3>
                  <p className="text-slate-500 mt-1">{pkg.description}</p>
                </div>

                {/* Price */}
                <div className="text-center mb-6">
                  <div className="flex items-center justify-center gap-3">
                    <span className="text-5xl font-black text-slate-900">${pkg.price}</span>
                    {pkg.originalPrice && (
                      <div className="flex flex-col items-start">
                        <span className="text-lg text-slate-400 line-through">${pkg.originalPrice}</span>
                        <span className="text-sm font-bold text-emerald-600">Save ${pkg.savings}</span>
                      </div>
                    )}
                  </div>
                  <p className="text-slate-500 mt-1">
                    {pkg.credits} report{pkg.credits > 1 ? 's' : ''}
                  </p>
                </div>

                {/* Features */}
                <ul className="space-y-3 mb-8">
                  {pkg.features.map((feature, idx) => (
                    <li key={idx} className="flex items-start gap-3">
                      <div className={`flex-shrink-0 w-5 h-5 rounded-full flex items-center justify-center mt-0.5 ${
                        pkg.popular ? 'bg-violet-100' : 'bg-slate-100'
                      }`}>
                        <Check className={`w-3 h-3 ${pkg.popular ? 'text-violet-600' : 'text-slate-600'}`} />
                      </div>
                      <span className="text-slate-600">{feature}</span>
                    </li>
                  ))}
                </ul>

                {/* CTA Button */}
                <button
                  onClick={() => handleSelectPackage(pkg.id)}
                  disabled={loading === pkg.id}
                  className={`w-full py-4 px-6 rounded-2xl font-bold text-lg flex items-center justify-center gap-2 transition-all ${
                    pkg.popular
                      ? 'bg-gradient-to-r from-violet-600 to-purple-600 text-white hover:shadow-lg hover:shadow-violet-500/30 hover:-translate-y-0.5'
                      : 'bg-slate-900 text-white hover:bg-slate-800'
                  } disabled:opacity-50 disabled:cursor-not-allowed`}
                >
                  {loading === pkg.id ? (
                    <>
                      <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                      Processing...
                    </>
                  ) : (
                    <>
                      {pkg.cta}
                      <ArrowRight className="w-5 h-5" />
                    </>
                  )}
                </button>
              </div>
            );
          })}
        </div>

        {/* Trust Badges */}
        <div className="flex flex-wrap items-center justify-center gap-8 mt-12 text-slate-500">
          <div className="flex items-center gap-2">
            <Shield className="w-5 h-5" />
            <span className="text-sm">Secure checkout via Stripe</span>
          </div>
          <div className="flex items-center gap-2">
            <Zap className="w-5 h-5" />
            <span className="text-sm">Reports ready in 2 minutes</span>
          </div>
          <div className="flex items-center gap-2">
            <Globe className="w-5 h-5" />
            <span className="text-sm">Multi-country analysis</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PricingSection;
