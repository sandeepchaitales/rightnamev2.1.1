import React from 'react';
import { useNavigate } from 'react-router-dom';
import { XCircle, ArrowLeft, HelpCircle } from 'lucide-react';

const PaymentCancel = () => {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 flex items-center justify-center p-4">
      <div className="bg-white rounded-3xl shadow-2xl p-12 max-w-md w-full text-center">
        {/* Cancel Icon */}
        <div className="w-20 h-20 bg-slate-100 rounded-full flex items-center justify-center mx-auto mb-6">
          <XCircle className="w-10 h-10 text-slate-400" />
        </div>

        <h1 className="text-2xl font-bold text-slate-900 mb-2">Payment Cancelled</h1>
        <p className="text-slate-600 mb-8">
          No worries! Your payment was cancelled and you haven't been charged.
        </p>

        {/* Options */}
        <div className="space-y-3">
          <button
            onClick={() => navigate('/')}
            className="w-full bg-gradient-to-r from-violet-600 to-purple-600 text-white py-4 px-6 rounded-2xl font-bold flex items-center justify-center gap-2 hover:shadow-lg transition-all"
          >
            <ArrowLeft className="w-5 h-5" />
            Return to Pricing
          </button>

          <button
            onClick={() => window.location.href = 'mailto:support@rightname.ai'}
            className="w-full bg-slate-100 text-slate-700 py-4 px-6 rounded-2xl font-medium flex items-center justify-center gap-2 hover:bg-slate-200 transition-all"
          >
            <HelpCircle className="w-5 h-5" />
            Need Help?
          </button>
        </div>

        <p className="text-sm text-slate-500 mt-6">
          Have questions? We're here to help you choose the right plan.
        </p>
      </div>
    </div>
  );
};

export default PaymentCancel;
