"""
Payment Routes for RIGHTNAME.AI
Stripe Checkout Integration for $29 Single Report and $49 Founder's Pack (3 Reports)
"""

import os
import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

# Import Stripe checkout from emergentintegrations
from emergentintegrations.payments.stripe.checkout import (
    StripeCheckout, 
    CheckoutSessionResponse, 
    CheckoutStatusResponse, 
    CheckoutSessionRequest
)

# MongoDB reference (set from main server.py)
db = None

def set_db(db_ref):
    global db
    db = db_ref

payment_router = APIRouter(prefix="/api/payments", tags=["payments"])

# ============ FIXED PRICING PACKAGES (Server-side only - NEVER accept from frontend) ============
PRICING_PACKAGES = {
    "single_report": {
        "id": "single_report",
        "name": "Single Report",
        "description": "Validate 1 brand name with comprehensive analysis",
        "amount": 29.00,  # $29
        "currency": "usd",
        "report_credits": 1,
        "features": [
            "Full trademark analysis",
            "DuPont 13-Factor test",
            "Competitor landscape",
            "Domain availability",
            "Social media check"
        ]
    },
    "founders_pack": {
        "id": "founders_pack",
        "name": "Founder's Pack",
        "description": "Validate 3 brand names + comparison summary",
        "amount": 49.00,  # $49
        "currency": "usd",
        "report_credits": 3,
        "popular": True,
        "savings": "$38",
        "features": [
            "Everything in Single Report",
            "3 complete reports",
            "Side-by-side comparison",
            "Winner recommendation",
            "Best value for finalists"
        ]
    }
}

# ============ REQUEST/RESPONSE MODELS ============

class CreateCheckoutRequest(BaseModel):
    package_id: str = Field(..., description="Package ID: 'single_report' or 'founders_pack'")
    origin_url: str = Field(..., description="Frontend origin URL for redirects")
    email: Optional[str] = Field(None, description="Customer email for receipt")
    brand_names: Optional[list] = Field(None, description="Brand names to validate (for reference)")

class CheckoutResponse(BaseModel):
    checkout_url: str
    session_id: str
    package: dict

class PaymentStatusResponse(BaseModel):
    status: str
    payment_status: str
    package_id: str
    report_credits: int
    amount: float
    currency: str

# ============ API ENDPOINTS ============

@payment_router.get("/packages")
async def get_pricing_packages():
    """Get available pricing packages"""
    return {
        "packages": list(PRICING_PACKAGES.values()),
        "currency": "USD",
        "currency_symbol": "$"
    }

@payment_router.post("/checkout/create", response_model=CheckoutResponse)
async def create_checkout_session(request: CreateCheckoutRequest, http_request: Request):
    """
    Create a Stripe Checkout session for the selected package.
    Amount is determined server-side only for security.
    """
    # Validate package exists
    if request.package_id not in PRICING_PACKAGES:
        raise HTTPException(status_code=400, detail=f"Invalid package: {request.package_id}")
    
    package = PRICING_PACKAGES[request.package_id]
    
    # Get Stripe API key
    stripe_api_key = os.environ.get("STRIPE_API_KEY")
    if not stripe_api_key:
        raise HTTPException(status_code=500, detail="Payment system not configured")
    
    # Build dynamic URLs from frontend origin
    origin = request.origin_url.rstrip('/')
    success_url = f"{origin}/payment/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{origin}/payment/cancel"
    
    # Initialize Stripe checkout
    webhook_url = f"{str(http_request.base_url).rstrip('/')}/api/webhook/stripe"
    stripe_checkout = StripeCheckout(api_key=stripe_api_key, webhook_url=webhook_url)
    
    # Create metadata for tracking
    metadata = {
        "package_id": request.package_id,
        "package_name": package["name"],
        "report_credits": str(package["report_credits"]),
        "customer_email": request.email or "",
        "brand_names": ",".join(request.brand_names) if request.brand_names else "",
        "source": "rightname_checkout"
    }
    
    try:
        # Create checkout session with server-defined amount
        checkout_request = CheckoutSessionRequest(
            amount=package["amount"],
            currency=package["currency"],
            success_url=success_url,
            cancel_url=cancel_url,
            metadata=metadata
        )
        
        session: CheckoutSessionResponse = await stripe_checkout.create_checkout_session(checkout_request)
        
        # Store transaction record BEFORE redirecting to Stripe
        transaction_doc = {
            "session_id": session.session_id,
            "package_id": request.package_id,
            "package_name": package["name"],
            "amount": package["amount"],
            "currency": package["currency"],
            "report_credits": package["report_credits"],
            "customer_email": request.email,
            "brand_names": request.brand_names or [],
            "payment_status": "pending",
            "status": "initiated",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        await db.payment_transactions.insert_one(transaction_doc)
        logging.info(f"💳 Checkout session created: {session.session_id} for {package['name']}")
        
        return CheckoutResponse(
            checkout_url=session.url,
            session_id=session.session_id,
            package=package
        )
        
    except Exception as e:
        logging.error(f"❌ Stripe checkout error: {e}")
        raise HTTPException(status_code=500, detail=f"Payment initialization failed: {str(e)}")

@payment_router.get("/checkout/status/{session_id}")
async def get_checkout_status(session_id: str, http_request: Request):
    """
    Check payment status and update database.
    Frontend should poll this after returning from Stripe.
    """
    stripe_api_key = os.environ.get("STRIPE_API_KEY")
    if not stripe_api_key:
        raise HTTPException(status_code=500, detail="Payment system not configured")
    
    # Initialize Stripe checkout
    webhook_url = f"{str(http_request.base_url).rstrip('/')}/api/webhook/stripe"
    stripe_checkout = StripeCheckout(api_key=stripe_api_key, webhook_url=webhook_url)
    
    try:
        # Get status from Stripe
        status: CheckoutStatusResponse = await stripe_checkout.get_checkout_status(session_id)
        
        # Find existing transaction
        transaction = await db.payment_transactions.find_one({"session_id": session_id})
        
        if not transaction:
            raise HTTPException(status_code=404, detail="Transaction not found")
        
        # Check if already processed (prevent double-crediting)
        if transaction.get("payment_status") == "paid" and transaction.get("credits_granted"):
            return PaymentStatusResponse(
                status="complete",
                payment_status="paid",
                package_id=transaction["package_id"],
                report_credits=transaction["report_credits"],
                amount=transaction["amount"],
                currency=transaction["currency"]
            )
        
        # Update transaction based on Stripe status
        update_data = {
            "status": status.status,
            "payment_status": status.payment_status,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        # If payment successful, grant credits
        if status.payment_status == "paid" and not transaction.get("credits_granted"):
            update_data["credits_granted"] = True
            update_data["credits_granted_at"] = datetime.now(timezone.utc).isoformat()
            
            # Create or update user credits
            customer_email = transaction.get("customer_email") or status.metadata.get("customer_email", "guest")
            
            await db.user_credits.update_one(
                {"email": customer_email},
                {
                    "$inc": {"report_credits": transaction["report_credits"]},
                    "$set": {"updated_at": datetime.now(timezone.utc).isoformat()},
                    "$setOnInsert": {"created_at": datetime.now(timezone.utc).isoformat()}
                },
                upsert=True
            )
            
            logging.info(f"✅ Payment successful! Granted {transaction['report_credits']} credits to {customer_email}")
        
        # Update transaction
        await db.payment_transactions.update_one(
            {"session_id": session_id},
            {"$set": update_data}
        )
        
        return PaymentStatusResponse(
            status=status.status,
            payment_status=status.payment_status,
            package_id=transaction["package_id"],
            report_credits=transaction["report_credits"],
            amount=transaction["amount"],
            currency=transaction["currency"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"❌ Status check error: {e}")
        raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")

@payment_router.get("/credits/{email}")
async def get_user_credits(email: str):
    """Get remaining report credits for a user"""
    user = await db.user_credits.find_one({"email": email.lower()})
    
    if not user:
        return {"email": email, "report_credits": 0, "has_credits": False}
    
    return {
        "email": email,
        "report_credits": user.get("report_credits", 0),
        "has_credits": user.get("report_credits", 0) > 0
    }

@payment_router.post("/use-credit")
async def use_report_credit(email: str, report_id: str):
    """Deduct one report credit after generating a report"""
    user = await db.user_credits.find_one({"email": email.lower()})
    
    if not user or user.get("report_credits", 0) <= 0:
        raise HTTPException(status_code=402, detail="No report credits available")
    
    # Deduct credit
    result = await db.user_credits.update_one(
        {"email": email.lower(), "report_credits": {"$gt": 0}},
        {
            "$inc": {"report_credits": -1},
            "$push": {
                "used_reports": {
                    "report_id": report_id,
                    "used_at": datetime.now(timezone.utc).isoformat()
                }
            },
            "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}
        }
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=402, detail="Failed to use credit")
    
    return {"success": True, "message": "Credit used successfully"}

# ============ STRIPE WEBHOOK ============

@payment_router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events"""
    stripe_api_key = os.environ.get("STRIPE_API_KEY")
    if not stripe_api_key:
        raise HTTPException(status_code=500, detail="Payment system not configured")
    
    try:
        body = await request.body()
        signature = request.headers.get("Stripe-Signature")
        
        webhook_url = f"{str(request.base_url).rstrip('/')}/api/webhook/stripe"
        stripe_checkout = StripeCheckout(api_key=stripe_api_key, webhook_url=webhook_url)
        
        webhook_response = await stripe_checkout.handle_webhook(body, signature)
        
        logging.info(f"📩 Webhook received: {webhook_response.event_type} for session {webhook_response.session_id}")
        
        # Update transaction based on webhook
        if webhook_response.payment_status == "paid":
            transaction = await db.payment_transactions.find_one({"session_id": webhook_response.session_id})
            
            if transaction and not transaction.get("credits_granted"):
                customer_email = transaction.get("customer_email") or webhook_response.metadata.get("customer_email", "guest")
                
                await db.user_credits.update_one(
                    {"email": customer_email},
                    {
                        "$inc": {"report_credits": transaction["report_credits"]},
                        "$set": {"updated_at": datetime.now(timezone.utc).isoformat()},
                        "$setOnInsert": {"created_at": datetime.now(timezone.utc).isoformat()}
                    },
                    upsert=True
                )
                
                await db.payment_transactions.update_one(
                    {"session_id": webhook_response.session_id},
                    {"$set": {
                        "payment_status": "paid",
                        "credits_granted": True,
                        "credits_granted_at": datetime.now(timezone.utc).isoformat()
                    }}
                )
                
                logging.info(f"✅ Webhook: Granted {transaction['report_credits']} credits via webhook")
        
        return {"received": True}
        
    except Exception as e:
        logging.error(f"❌ Webhook error: {e}")
        return {"received": True, "error": str(e)}
