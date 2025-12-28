import React from 'react';
import { Link } from 'react-router-dom';
import { Mail, Twitter, Linkedin, Github, Heart } from 'lucide-react';

const Footer = () => {
  const currentYear = new Date().getFullYear();

  const footerLinks = {
    product: [
      { name: "Features", href: "/#features" },
      { name: "Pricing", href: "/pricing" },
      { name: "How It Works", href: "/#how-it-works" },
      { name: "FAQ", href: "/#faq" },
    ],
    resources: [
      { name: "Blog", href: "/blog" },
      { name: "Brand Naming Guide", href: "/blog" },
      { name: "Trademark Basics", href: "/blog" },
      { name: "Case Studies", href: "/blog" },
    ],
    company: [
      { name: "About Us", href: "#" },
      { name: "Contact", href: "mailto:hello@rightname.ai" },
      { name: "Privacy Policy", href: "#" },
      { name: "Terms of Service", href: "#" },
    ],
  };

  const socialLinks = [
    { icon: Twitter, href: "https://twitter.com/rightnameai", label: "Twitter" },
    { icon: Linkedin, href: "https://linkedin.com/company/rightname", label: "LinkedIn" },
    { icon: Mail, href: "mailto:hello@rightname.ai", label: "Email" },
  ];

  return (
    <footer className="bg-slate-900 text-white">
      {/* Main Footer */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-12">
          {/* Brand Column */}
          <div className="lg:col-span-2">
            <Link to="/" className="flex items-center gap-3 mb-6">
              <img 
                src="https://customer-assets.emergentagent.com/job_name-radar-1/artifacts/a4ppykdi_RIGHTNAME.AI.png" 
                alt="RIGHTNAME Logo" 
                className="w-12 h-12 rounded-xl"
              />
              <span className="font-black text-2xl">RIGHTNAME</span>
            </Link>
            <p className="text-slate-400 mb-6 max-w-sm">
              AI-powered brand name evaluation. Get consulting-grade trademark analysis, 
              domain availability, and strategic recommendations in 60 seconds.
            </p>
            <div className="flex items-center gap-4">
              {socialLinks.map((social, index) => (
                <a
                  key={index}
                  href={social.href}
                  target="_blank"
                  rel="noopener noreferrer"
                  aria-label={social.label}
                  className="w-10 h-10 rounded-full bg-slate-800 hover:bg-blue-600 flex items-center justify-center transition-colors"
                >
                  <social.icon className="w-5 h-5" />
                </a>
              ))}
            </div>
          </div>

          {/* Product Links */}
          <div>
            <h3 className="font-bold text-lg mb-4">Product</h3>
            <ul className="space-y-3">
              {footerLinks.product.map((link, index) => (
                <li key={index}>
                  <Link 
                    to={link.href}
                    className="text-slate-400 hover:text-white transition-colors"
                  >
                    {link.name}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          {/* Resources Links */}
          <div>
            <h3 className="font-bold text-lg mb-4">Resources</h3>
            <ul className="space-y-3">
              {footerLinks.resources.map((link, index) => (
                <li key={index}>
                  <Link 
                    to={link.href}
                    className="text-slate-400 hover:text-white transition-colors"
                  >
                    {link.name}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          {/* Company Links */}
          <div>
            <h3 className="font-bold text-lg mb-4">Company</h3>
            <ul className="space-y-3">
              {footerLinks.company.map((link, index) => (
                <li key={index}>
                  {link.href.startsWith('mailto:') ? (
                    <a 
                      href={link.href}
                      className="text-slate-400 hover:text-white transition-colors"
                    >
                      {link.name}
                    </a>
                  ) : (
                    <Link 
                      to={link.href}
                      className="text-slate-400 hover:text-white transition-colors"
                    >
                      {link.name}
                    </Link>
                  )}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>

      {/* Bottom Bar */}
      <div className="border-t border-slate-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex flex-col md:flex-row items-center justify-between gap-4">
            <p className="text-slate-400 text-sm">
              © {currentYear} RIGHTNAME. All rights reserved.
            </p>
            <p className="text-slate-400 text-sm flex items-center gap-1">
              Made with <Heart className="w-4 h-4 text-red-500 fill-current" /> for brand builders worldwide
            </p>
          </div>
        </div>
      </div>

      {/* Schema.org LocalBusiness markup for footer */}
      <script type="application/ld+json" dangerouslySetInnerHTML={{
        __html: JSON.stringify({
          "@context": "https://schema.org",
          "@type": "WebSite",
          "name": "RIGHTNAME",
          "url": "https://rightname.ai",
          "potentialAction": {
            "@type": "SearchAction",
            "target": "https://rightname.ai/?search={search_term_string}",
            "query-input": "required name=search_term_string"
          }
        })
      }} />
    </footer>
  );
};

export default Footer;
