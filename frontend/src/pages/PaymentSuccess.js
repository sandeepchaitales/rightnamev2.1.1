import React, { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { CheckCircle, Loader2, ArrowRight, AlertCircle } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';

const PaymentSuccess = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [status, setStatus] = useState('checking'); // checking, success, failed
  const [paymentData, setPaymentData] = useState(null);
  const [pollCount, setPollCount] = useState(0);

  const sessionId = searchParams.get('session_id');

  useEffect(() => {
    if (!sessionId) {
      setStatus('failed');
      return;
    }

    const pollPaymentStatus = async () => {
      try {
        const response = await fetch(`${BACKEND_URL}/api/payments/checkout/status/${sessionId}`);
        
        if (!response.ok) {
          throw new Error('Failed to check status');
        }

        const data = await response.json();
        setPaymentData(data);

        if (data.payment_status === 'paid') {
          setStatus('success');
          // Store credits info
          const pendingPayment = JSON.parse(localStorage.getItem('pending_payment') || '{}');
          localStorage.setItem('user_credits', JSON.stringify({
            email: pendingPayment.email,
            credits: data.report_credits
          }));
          localStorage.removeItem('pending_payment');
        } else if (data.status === 'expired') {
          setStatus('failed');
        } else if (pollCount < 5) {
          // Continue polling
          setPollCount(prev => prev + 1);
          setTimeout(pollPaymentStatus, 2000);
        } else {
          setStatus('failed');
        }
      } catch (error) {
        console.error('Status check error:', error);
        if (pollCount < 5) {
          setPollCount(prev => prev + 1);
          setTimeout(pollPaymentStatus, 2000);
        } else {
          setStatus('failed');
        }
      }
    };

    pollPaymentStatus();
  }, [sessionId, pollCount]);

  if (status === 'checking') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-violet-50 to-purple-50 flex items-center justify-center p-4">
        <div className="bg-white rounded-3xl shadow-2xl p-12 max-w-md w-full text-center">
          <Loader2 className="w-16 h-16 text-violet-600 animate-spin mx-auto mb-6" />
          <h1 className="text-2xl font-bold text-slate-900 mb-2">Confirming Payment...</h1>
          <p className="text-slate-600">Please wait while we verify your payment.</p>
        </div>
      </div>
    );
  }

  if (status === 'failed') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-red-50 to-orange-50 flex items-center justify-center p-4">
        <div className="bg-white rounded-3xl shadow-2xl p-12 max-w-md w-full text-center">
          <div className="w-20 h-20 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-6">
            <AlertCircle className="w-10 h-10 text-red-600" />
          </div>
          <h1 className="text-2xl font-bold text-slate-900 mb-2">Payment Issue</h1>
          <p className="text-slate-600 mb-6">
            We couldn't confirm your payment. If you were charged, please contact support.
          </p>
          <button
            onClick={() => navigate('/')}
            className="bg-slate-900 text-white px-6 py-3 rounded-xl font-bold hover:bg-slate-800"
          >
            Return Home
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-emerald-50 to-teal-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-3xl shadow-2xl p-12 max-w-md w-full text-center">
        {/* Success Icon */}
        <div className="w-20 h-20 bg-emerald-100 rounded-full flex items-center justify-center mx-auto mb-6 animate-bounce">
          <CheckCircle className="w-10 h-10 text-emerald-600" />
        </div>

        <h1 className="text-3xl font-black text-slate-900 mb-2">Payment Successful! 🎉</h1>
        <p className="text-slate-600 mb-6">
          Thank you for your purchase. You now have{' '}
          <span className="font-bold text-violet-600">
            {paymentData?.report_credits || 0} report credit{paymentData?.report_credits !== 1 ? 's' : ''}
          </span>
        </p>

        {/* Purchase Summary */}
        <div className="bg-slate-50 rounded-2xl p-6 mb-8 text-left">
          <h3 className="font-bold text-slate-900 mb-3">Purchase Summary</h3>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-slate-600">Package</span>
              <span className="font-medium">{paymentData?.package_id === 'founders_pack' ? "Founder's Pack" : 'Single Report'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-600">Amount</span>
              <span className="font-medium">${paymentData?.amount || 0}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-600">Credits</span>
              <span className="font-bold text-violet-600">{paymentData?.report_credits || 0} reports</span>
            </div>
          </div>
        </div>

        {/* CTA */}
        <button
          onClick={() => navigate('/')}
          className="w-full bg-gradient-to-r from-violet-600 to-purple-600 text-white py-4 px-6 rounded-2xl font-bold text-lg flex items-center justify-center gap-2 hover:shadow-lg hover:shadow-violet-500/30 transition-all"
        >
          Start Validating Names
          <ArrowRight className="w-5 h-5" />
        </button>

        <p className="text-sm text-slate-500 mt-4">
          Your credits are ready to use. Enter a brand name to get started!
        </p>
      </div>
    </div>
  );
};

export default PaymentSuccess;
