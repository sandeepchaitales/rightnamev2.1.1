import React, { useState } from 'react';
import { X, Eye, Lock, ChevronLeft, ChevronRight, Star, Shield, Globe, TrendingUp, AlertTriangle, CheckCircle, Target, Zap } from 'lucide-react';

// Sample report data for 3 fictional brands
const SAMPLE_REPORTS = {
  techflow: {
    id: 'techflow',
    brandName: 'TechFlow',
    category: 'SaaS / Technology',
    industry: 'Enterprise Software',
    score: 78,
    verdict: 'GO',
    verdictColor: 'emerald',
    tagline: 'Clean approval with strong digital presence',
    executiveSummary: `TechFlow demonstrates strong brand potential for the enterprise software market. The name effectively combines "Tech" (establishing sector relevance) with "Flow" (suggesting seamless operations and efficiency). 

**Key Strengths:**
• Highly distinctive and memorable
• Strong domain availability (.com, .io, .app)
• Clear B2B positioning
• Scalable across product lines

**Risk Assessment:** LOW - No significant trademark conflicts identified in primary markets. The name is sufficiently distinctive to avoid confusion with existing marks.`,
    dimensions: [
      { name: 'Brand Distinctiveness', score: 82, color: 'violet' },
      { name: 'Trademark Safety', score: 75, color: 'emerald' },
      { name: 'Digital Readiness', score: 88, color: 'blue' },
      { name: 'Scalability', score: 80, color: 'amber' },
      { name: 'Consumer Perception', score: 72, color: 'rose' },
    ],
    trademarkRisk: 'LOW',
    conflicts: [
      { name: 'TechFlowSystems Inc.', risk: 'LOW', reason: 'Different NICE class (Class 42 vs Class 9), minimal overlap' },
    ],
    domains: [
      { domain: 'techflow.com', available: false, price: '$12,500 (broker)' },
      { domain: 'techflow.io', available: true, price: '$49/year' },
      { domain: 'techflow.app', available: true, price: '$20/year' },
      { domain: 'gettechflow.com', available: true, price: '$12/year' },
    ],
    socialHandles: [
      { platform: 'Twitter/X', handle: '@techflow', available: false },
      { platform: 'Twitter/X', handle: '@techflowHQ', available: true },
      { platform: 'Instagram', handle: '@techflow', available: false },
      { platform: 'LinkedIn', handle: '/company/techflow', available: true },
    ],
    countries: ['USA', 'UK', 'Germany', 'India'],
  },
  spicebox: {
    id: 'spicebox',
    brandName: 'SpiceBox',
    category: 'Food & Beverage',
    industry: 'D2C Food Delivery',
    score: 82,
    verdict: 'GO',
    verdictColor: 'emerald',
    tagline: 'Strong cultural resonance in food sector',
    executiveSummary: `SpiceBox presents an excellent brand opportunity for the D2C food delivery space. The name evokes warmth, flavor, and the excitement of discovery - perfect for a subscription meal kit or spice delivery service.

**Key Strengths:**
• Emotionally evocative and memorable
• Strong cultural connections across markets
• Versatile for product line extensions
• Appeals to both traditional and modern consumers

**Risk Assessment:** LOW - Clear trademark path with no direct conflicts in the food category. Name has positive connotations globally.`,
    dimensions: [
      { name: 'Brand Distinctiveness', score: 85, color: 'violet' },
      { name: 'Cultural Resonance', score: 90, color: 'amber' },
      { name: 'Trademark Safety', score: 78, color: 'emerald' },
      { name: 'Scalability', score: 82, color: 'blue' },
      { name: 'Consumer Perception', score: 88, color: 'rose' },
    ],
    trademarkRisk: 'LOW',
    conflicts: [
      { name: 'Spice Box Restaurant (Local)', risk: 'LOW', reason: 'Local restaurant, different geographic market' },
    ],
    domains: [
      { domain: 'spicebox.com', available: false, price: '$8,000 (broker)' },
      { domain: 'spicebox.co', available: true, price: '$35/year' },
      { domain: 'getspicebox.com', available: true, price: '$12/year' },
      { domain: 'spicebox.kitchen', available: true, price: '$25/year' },
    ],
    socialHandles: [
      { platform: 'Twitter/X', handle: '@spicebox', available: true },
      { platform: 'Instagram', handle: '@spicebox', available: false },
      { platform: 'Instagram', handle: '@spiceboxfoods', available: true },
      { platform: 'TikTok', handle: '@spicebox', available: true },
    ],
    countries: ['India', 'USA', 'UK', 'UAE'],
  },
  luxestay: {
    id: 'luxestay',
    brandName: 'LuxeStay',
    category: 'Hotels & Hospitality',
    industry: 'Boutique Hotels',
    score: 65,
    verdict: 'CAUTION',
    verdictColor: 'amber',
    tagline: 'Trademark conflicts require careful navigation',
    executiveSummary: `LuxeStay presents a moderate-risk opportunity in the hospitality sector. While the name effectively communicates luxury accommodation, there are existing trademarks that require careful navigation.

**Key Strengths:**
• Clear luxury positioning
• Intuitive meaning globally
• Strong hospitality association

**Risk Factors:**
• Similar marks exist in hospitality sector
• "Luxe" prefix is commonly used
• May require coexistence agreements

**Recommendation:** PROCEED WITH CAUTION - Consider trademark coexistence agreement or geographic limitations. Legal review recommended before significant brand investment.`,
    dimensions: [
      { name: 'Brand Distinctiveness', score: 58, color: 'violet' },
      { name: 'Trademark Safety', score: 52, color: 'amber' },
      { name: 'Premium Perception', score: 85, color: 'emerald' },
      { name: 'Scalability', score: 70, color: 'blue' },
      { name: 'Consumer Perception', score: 78, color: 'rose' },
    ],
    trademarkRisk: 'MEDIUM',
    conflicts: [
      { name: 'LuxeStays LLC', risk: 'MEDIUM', reason: 'Same NICE class (43), vacation rentals - requires legal review' },
      { name: 'Luxe Stay Hotels', risk: 'HIGH', reason: 'Direct competitor in hospitality, active trademark' },
    ],
    domains: [
      { domain: 'luxestay.com', available: false, price: 'Not for sale' },
      { domain: 'luxestay.co', available: false, price: '$5,500 (broker)' },
      { domain: 'luxestayhotels.com', available: true, price: '$12/year' },
      { domain: 'stayluxe.com', available: true, price: '$15/year' },
    ],
    socialHandles: [
      { platform: 'Twitter/X', handle: '@luxestay', available: false },
      { platform: 'Instagram', handle: '@luxestay', available: false },
      { platform: 'Instagram', handle: '@luxestayhotels', available: true },
      { platform: 'LinkedIn', handle: '/company/luxestay', available: false },
    ],
    countries: ['USA', 'Thailand', 'Japan', 'France'],
  }
};

// Score color helper
const getScoreColor = (score) => {
  if (score >= 75) return 'text-emerald-600';
  if (score >= 60) return 'text-amber-600';
  return 'text-red-600';
};

const getScoreBg = (score) => {
  if (score >= 75) return 'from-emerald-500 to-teal-600';
  if (score >= 60) return 'from-amber-500 to-orange-600';
  return 'from-red-500 to-rose-600';
};

const getVerdictConfig = (verdict) => {
  const configs = {
    'GO': { bg: 'bg-emerald-100', text: 'text-emerald-700', icon: CheckCircle },
    'CAUTION': { bg: 'bg-amber-100', text: 'text-amber-700', icon: AlertTriangle },
    'REJECT': { bg: 'bg-red-100', text: 'text-red-700', icon: X },
  };
  return configs[verdict] || configs['CAUTION'];
};

// Sample Report Viewer Modal
const SampleReportViewer = ({ report, onClose }) => {
  const [currentSection, setCurrentSection] = useState(0);
  
  const sections = [
    'overview',
    'dimensions',
    'trademark',
    'domains',
    'social'
  ];

  const verdictConfig = getVerdictConfig(report.verdict);
  const VerdictIcon = verdictConfig.icon;

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-3xl max-w-4xl w-full max-h-[90vh] overflow-hidden relative">
        {/* Watermark */}
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none z-10 opacity-[0.03]">
          <div className="text-8xl font-black text-slate-900 rotate-[-30deg] select-none">
            SAMPLE REPORT
          </div>
        </div>

        {/* Header */}
        <div className="sticky top-0 bg-gradient-to-r from-slate-900 to-slate-800 text-white px-6 py-4 flex items-center justify-between z-20">
          <div className="flex items-center gap-4">
            <div className={`w-14 h-14 rounded-2xl bg-gradient-to-br ${getScoreBg(report.score)} flex items-center justify-center`}>
              <span className="text-2xl font-black text-white">{report.score}</span>
            </div>
            <div>
              <h2 className="text-xl font-bold">{report.brandName}</h2>
              <p className="text-slate-300 text-sm">{report.category}</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className={`${verdictConfig.bg} ${verdictConfig.text} px-4 py-2 rounded-full font-bold flex items-center gap-2`}>
              <VerdictIcon className="w-4 h-4" />
              {report.verdict}
            </div>
            <button
              onClick={onClose}
              className="p-2 hover:bg-white/10 rounded-xl transition-colors"
            >
              <X className="w-6 h-6" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="overflow-y-auto max-h-[calc(90vh-80px)] p-6 relative">
          {/* Section Navigation */}
          <div className="flex gap-2 mb-6 overflow-x-auto pb-2">
            {['Overview', 'Dimensions', 'Trademark', 'Domains', 'Social'].map((name, idx) => (
              <button
                key={name}
                onClick={() => setCurrentSection(idx)}
                className={`px-4 py-2 rounded-xl font-medium whitespace-nowrap transition-all ${
                  currentSection === idx
                    ? 'bg-violet-600 text-white'
                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                }`}
              >
                {name}
              </button>
            ))}
          </div>

          {/* Overview Section */}
          {currentSection === 0 && (
            <div className="space-y-6">
              <div className="bg-gradient-to-br from-slate-50 to-slate-100 rounded-2xl p-6">
                <h3 className="text-lg font-bold text-slate-900 mb-3 flex items-center gap-2">
                  <Target className="w-5 h-5 text-violet-600" />
                  Executive Summary
                </h3>
                <div className="text-slate-700 whitespace-pre-line text-sm leading-relaxed">
                  {report.executiveSummary}
                </div>
              </div>

              {/* Quick Stats */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="bg-violet-50 rounded-xl p-4 text-center">
                  <div className={`text-3xl font-black ${getScoreColor(report.score)}`}>{report.score}</div>
                  <div className="text-xs text-slate-500 mt-1">RightName Score</div>
                </div>
                <div className={`${verdictConfig.bg} rounded-xl p-4 text-center`}>
                  <div className={`text-xl font-bold ${verdictConfig.text}`}>{report.verdict}</div>
                  <div className="text-xs text-slate-500 mt-1">Verdict</div>
                </div>
                <div className="bg-blue-50 rounded-xl p-4 text-center">
                  <div className="text-xl font-bold text-blue-600">{report.trademarkRisk}</div>
                  <div className="text-xs text-slate-500 mt-1">Trademark Risk</div>
                </div>
                <div className="bg-emerald-50 rounded-xl p-4 text-center">
                  <div className="text-xl font-bold text-emerald-600">{report.countries.length}</div>
                  <div className="text-xs text-slate-500 mt-1">Markets Analyzed</div>
                </div>
              </div>
            </div>
          )}

          {/* Dimensions Section */}
          {currentSection === 1 && (
            <div className="space-y-4">
              <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                <TrendingUp className="w-5 h-5 text-violet-600" />
                Brand Dimensions Analysis
              </h3>
              {report.dimensions.map((dim, idx) => (
                <div key={idx} className="bg-slate-50 rounded-xl p-4">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-medium text-slate-700">{dim.name}</span>
                    <span className={`font-bold ${getScoreColor(dim.score)}`}>{dim.score}/100</span>
                  </div>
                  <div className="h-3 bg-slate-200 rounded-full overflow-hidden">
                    <div
                      className={`h-full bg-gradient-to-r from-${dim.color}-500 to-${dim.color}-600 rounded-full transition-all`}
                      style={{ width: `${dim.score}%` }}
                    />
                  </div>
                </div>
              ))}
              
              {/* Blurred teaser */}
              <div className="relative mt-6">
                <div className="absolute inset-0 bg-white/80 backdrop-blur-sm z-10 flex items-center justify-center rounded-xl">
                  <div className="text-center">
                    <Lock className="w-8 h-8 text-slate-400 mx-auto mb-2" />
                    <p className="text-slate-600 font-medium">3 more dimensions in full report</p>
                  </div>
                </div>
                <div className="bg-slate-50 rounded-xl p-4 opacity-50">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-medium text-slate-700">Future-Proofing</span>
                    <span className="font-bold text-slate-400">??/100</span>
                  </div>
                  <div className="h-3 bg-slate-200 rounded-full" />
                </div>
              </div>
            </div>
          )}

          {/* Trademark Section */}
          {currentSection === 2 && (
            <div className="space-y-4">
              <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                <Shield className="w-5 h-5 text-violet-600" />
                Trademark Conflict Analysis
              </h3>
              
              <div className={`p-4 rounded-xl ${
                report.trademarkRisk === 'LOW' ? 'bg-emerald-50' :
                report.trademarkRisk === 'MEDIUM' ? 'bg-amber-50' : 'bg-red-50'
              }`}>
                <div className="flex items-center gap-2 mb-2">
                  <AlertTriangle className={`w-5 h-5 ${
                    report.trademarkRisk === 'LOW' ? 'text-emerald-600' :
                    report.trademarkRisk === 'MEDIUM' ? 'text-amber-600' : 'text-red-600'
                  }`} />
                  <span className="font-bold">Overall Risk: {report.trademarkRisk}</span>
                </div>
                <p className="text-sm text-slate-600">
                  {report.conflicts.length} potential conflict(s) identified
                </p>
              </div>

              {report.conflicts.map((conflict, idx) => (
                <div key={idx} className="bg-slate-50 rounded-xl p-4">
                  <div className="flex items-start justify-between">
                    <div>
                      <h4 className="font-semibold text-slate-900">{conflict.name}</h4>
                      <p className="text-sm text-slate-600 mt-1">{conflict.reason}</p>
                    </div>
                    <span className={`px-3 py-1 rounded-full text-xs font-bold ${
                      conflict.risk === 'LOW' ? 'bg-emerald-100 text-emerald-700' :
                      conflict.risk === 'MEDIUM' ? 'bg-amber-100 text-amber-700' : 'bg-red-100 text-red-700'
                    }`}>
                      {conflict.risk}
                    </span>
                  </div>
                </div>
              ))}

              {/* Blurred DuPont Analysis teaser */}
              <div className="relative mt-6">
                <div className="absolute inset-0 bg-white/80 backdrop-blur-sm z-10 flex items-center justify-center rounded-xl">
                  <div className="text-center">
                    <Lock className="w-8 h-8 text-slate-400 mx-auto mb-2" />
                    <p className="text-slate-600 font-medium">DuPont 13-Factor Analysis in full report</p>
                  </div>
                </div>
                <div className="bg-slate-50 rounded-xl p-4 opacity-50">
                  <h4 className="font-semibold mb-2">DuPont Confusion Test</h4>
                  <div className="space-y-2">
                    <div className="h-4 bg-slate-200 rounded w-3/4" />
                    <div className="h-4 bg-slate-200 rounded w-1/2" />
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Domains Section */}
          {currentSection === 3 && (
            <div className="space-y-4">
              <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                <Globe className="w-5 h-5 text-violet-600" />
                Domain Availability
              </h3>
              
              {report.domains.map((domain, idx) => (
                <div key={idx} className="bg-slate-50 rounded-xl p-4 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className={`w-3 h-3 rounded-full ${domain.available ? 'bg-emerald-500' : 'bg-red-400'}`} />
                    <span className="font-mono font-medium text-slate-900">{domain.domain}</span>
                  </div>
                  <div className="text-right">
                    <span className={`text-sm ${domain.available ? 'text-emerald-600' : 'text-slate-500'}`}>
                      {domain.available ? 'Available' : 'Taken'}
                    </span>
                    <p className="text-xs text-slate-400">{domain.price}</p>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Social Section */}
          {currentSection === 4 && (
            <div className="space-y-4">
              <h3 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                <Zap className="w-5 h-5 text-violet-600" />
                Social Media Handles
              </h3>
              
              {report.socialHandles.map((social, idx) => (
                <div key={idx} className="bg-slate-50 rounded-xl p-4 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className={`w-3 h-3 rounded-full ${social.available ? 'bg-emerald-500' : 'bg-red-400'}`} />
                    <div>
                      <span className="font-medium text-slate-900">{social.platform}</span>
                      <p className="text-sm text-slate-500">{social.handle}</p>
                    </div>
                  </div>
                  <span className={`px-3 py-1 rounded-full text-xs font-bold ${
                    social.available ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-200 text-slate-600'
                  }`}>
                    {social.available ? 'Available' : 'Taken'}
                  </span>
                </div>
              ))}

              {/* Blurred competitor analysis teaser */}
              <div className="relative mt-6">
                <div className="absolute inset-0 bg-white/80 backdrop-blur-sm z-10 flex items-center justify-center rounded-xl">
                  <div className="text-center">
                    <Lock className="w-8 h-8 text-slate-400 mx-auto mb-2" />
                    <p className="text-slate-600 font-medium">Competitive Landscape in full report</p>
                  </div>
                </div>
                <div className="bg-slate-50 rounded-xl p-4 opacity-50">
                  <h4 className="font-semibold mb-2">Competitor Analysis</h4>
                  <div className="space-y-2">
                    <div className="h-4 bg-slate-200 rounded w-full" />
                    <div className="h-4 bg-slate-200 rounded w-2/3" />
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* CTA Footer */}
          <div className="mt-8 bg-gradient-to-r from-violet-600 to-purple-600 rounded-2xl p-6 text-white text-center">
            <h4 className="text-xl font-bold mb-2">Get Your Own Brand Report</h4>
            <p className="text-violet-100 mb-4">Full analysis with DuPont test, competitor mapping, and actionable recommendations</p>
            <button
              onClick={onClose}
              className="bg-white text-violet-600 px-6 py-3 rounded-xl font-bold hover:bg-violet-50 transition-colors"
            >
              Start Your Analysis — $29
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

// Case Studies Section Component
const CaseStudiesSection = () => {
  const [selectedReport, setSelectedReport] = useState(null);

  const reports = Object.values(SAMPLE_REPORTS);

  return (
    <div className="py-20 px-4 bg-gradient-to-br from-slate-900 via-slate-800 to-violet-900">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="text-center mb-12">
          <div className="inline-flex items-center gap-2 bg-violet-500/20 text-violet-300 px-4 py-2 rounded-full text-sm font-medium mb-4">
            <Eye className="w-4 h-4" />
            See Before You Buy
          </div>
          <h2 className="text-4xl font-black text-white mb-4">
            Sample Reports
          </h2>
          <p className="text-lg text-slate-300 max-w-2xl mx-auto">
            Explore real examples of our consulting-grade brand analysis. 
            See exactly what you get before purchasing.
          </p>
        </div>

        {/* Report Cards */}
        <div className="grid md:grid-cols-3 gap-6">
          {reports.map((report) => {
            const verdictConfig = getVerdictConfig(report.verdict);
            const VerdictIcon = verdictConfig.icon;
            
            return (
              <div
                key={report.id}
                className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-2xl p-6 hover:bg-white/10 transition-all group cursor-pointer"
                onClick={() => setSelectedReport(report)}
              >
                {/* Score Badge */}
                <div className="flex items-start justify-between mb-4">
                  <div className={`w-16 h-16 rounded-2xl bg-gradient-to-br ${getScoreBg(report.score)} flex items-center justify-center shadow-lg`}>
                    <span className="text-2xl font-black text-white">{report.score}</span>
                  </div>
                  <div className={`${verdictConfig.bg} ${verdictConfig.text} px-3 py-1 rounded-full text-sm font-bold flex items-center gap-1`}>
                    <VerdictIcon className="w-3 h-3" />
                    {report.verdict}
                  </div>
                </div>

                {/* Brand Info */}
                <h3 className="text-2xl font-bold text-white mb-1">{report.brandName}</h3>
                <p className="text-slate-400 text-sm mb-3">{report.category}</p>
                <p className="text-slate-300 text-sm mb-4">{report.tagline}</p>

                {/* Quick Stats */}
                <div className="flex flex-wrap gap-2 mb-4">
                  <span className={`px-2 py-1 rounded text-xs font-medium ${
                    report.trademarkRisk === 'LOW' ? 'bg-emerald-500/20 text-emerald-300' :
                    report.trademarkRisk === 'MEDIUM' ? 'bg-amber-500/20 text-amber-300' : 'bg-red-500/20 text-red-300'
                  }`}>
                    {report.trademarkRisk} Risk
                  </span>
                  <span className="px-2 py-1 rounded text-xs font-medium bg-blue-500/20 text-blue-300">
                    {report.countries.length} Markets
                  </span>
                </div>

                {/* View Button */}
                <button className="w-full bg-white/10 hover:bg-white/20 text-white py-3 rounded-xl font-medium flex items-center justify-center gap-2 transition-all group-hover:bg-violet-600">
                  <Eye className="w-4 h-4" />
                  View Sample Report
                </button>
              </div>
            );
          })}
        </div>

        {/* Trust Note */}
        <p className="text-center text-slate-400 text-sm mt-8">
          <Lock className="w-4 h-4 inline mr-1" />
          Sample reports are view-only. Full reports include downloadable PDF and complete analysis.
        </p>
      </div>

      {/* Report Viewer Modal */}
      {selectedReport && (
        <SampleReportViewer
          report={selectedReport}
          onClose={() => setSelectedReport(null)}
        />
      )}
    </div>
  );
};

export default CaseStudiesSection;
