"""
Google OAuth 2.0 Authentication Routes for RIGHTNAME.AI
Custom implementation - No Emergent branding
"""

import os
import uuid
import httpx
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Request, Response, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

# Google OAuth Configuration
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
GOOGLE_REDIRECT_URI_PATH = "/api/auth/google/callback"

# OAuth URLs
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

# Scopes for Google OAuth
GOOGLE_SCOPES = [
    "openid",
    "email",
    "profile"
]

google_oauth_router = APIRouter(prefix="/api/auth")

# Database reference (will be set by main server)
db = None

def set_google_oauth_db(database):
    global db
    db = database

class GoogleAuthResponse(BaseModel):
    user_id: str
    email: str
    name: str
    picture: Optional[str] = None


def get_redirect_uri(request: Request) -> str:
    """Construct the redirect URI based on the request origin"""
    # Get various headers that might contain the original host
    origin = request.headers.get("origin", "")
    referer = request.headers.get("referer", "")
    forwarded_host = request.headers.get("x-forwarded-host", "")
    host = request.headers.get("host", "localhost:8001")
    forwarded_proto = request.headers.get("x-forwarded-proto", "https")
    
    logging.info(f"🔐 OAuth Headers: origin={origin}, referer={referer}, host={host}, x-forwarded-host={forwarded_host}")
    
    # Priority 1: Use origin header (most reliable for the actual frontend domain)
    if origin and origin.startswith("http"):
        base_url = origin.rstrip("/")
        redirect_uri = f"{base_url}{GOOGLE_REDIRECT_URI_PATH}"
        logging.info(f"🔐 Google OAuth: Using origin header → {redirect_uri}")
        return redirect_uri
    
    # Priority 2: Extract from referer
    if referer:
        from urllib.parse import urlparse
        parsed = urlparse(referer)
        if parsed.scheme and parsed.netloc:
            base_url = f"{parsed.scheme}://{parsed.netloc}"
            redirect_uri = f"{base_url}{GOOGLE_REDIRECT_URI_PATH}"
            logging.info(f"🔐 Google OAuth: Using referer header → {redirect_uri}")
            return redirect_uri
    
    # Priority 3: Use x-forwarded-host with x-forwarded-proto
    if forwarded_host:
        scheme = forwarded_proto or "https"
        base_url = f"{scheme}://{forwarded_host}"
        redirect_uri = f"{base_url}{GOOGLE_REDIRECT_URI_PATH}"
        logging.info(f"🔐 Google OAuth: Using x-forwarded-host → {redirect_uri}")
        return redirect_uri
    
    # Priority 4: Use host header
    scheme = "http" if "localhost" in host else "https"
    base_url = f"{scheme}://{host}"
    redirect_uri = f"{base_url}{GOOGLE_REDIRECT_URI_PATH}"
    logging.info(f"🔐 Google OAuth: Using host header → {redirect_uri}")
    return redirect_uri


@google_oauth_router.get("/google/debug")
async def google_debug(request: Request):
    """Debug endpoint to check what redirect_uri would be generated"""
    origin = request.headers.get("origin", "")
    referer = request.headers.get("referer", "")
    forwarded_host = request.headers.get("x-forwarded-host", "")
    host = request.headers.get("host", "")
    forwarded_proto = request.headers.get("x-forwarded-proto", "")
    
    redirect_uri = get_redirect_uri(request)
    
    return {
        "generated_redirect_uri": redirect_uri,
        "headers": {
            "origin": origin,
            "referer": referer,
            "x-forwarded-host": forwarded_host,
            "host": host,
            "x-forwarded-proto": forwarded_proto
        },
        "expected_in_google_console": [
            "https://rightname.ai/api/auth/google/callback",
            "https://www.rightname.ai/api/auth/google/callback",
            redirect_uri
        ]
    }


@google_oauth_router.get("/google")
async def google_login(request: Request, return_url: Optional[str] = None):
    """
    Initiate Google OAuth flow
    Redirects user to Google's consent screen
    """
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=500, detail="Google OAuth not configured")
    
    # Generate state for CSRF protection
    state = uuid.uuid4().hex
    
    # Store state and return_url in a temporary session
    state_data = {
        "state": state,
        "return_url": return_url or "/",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    # Store in database for verification
    await db.oauth_states.insert_one(state_data)
    
    # Build redirect URI
    redirect_uri = get_redirect_uri(request)
    logging.info(f"🔐 Google OAuth: redirect_uri = {redirect_uri}")
    
    # Build Google authorization URL
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(GOOGLE_SCOPES),
        "state": state,
        "access_type": "offline",
        "prompt": "select_account"  # Always show account selector
    }
    
    auth_url = f"{GOOGLE_AUTH_URL}?{urlencode(params)}"
    logging.info(f"🔐 Google OAuth: Redirecting to Google")
    
    return RedirectResponse(url=auth_url)


@google_oauth_router.get("/google/callback")
async def google_callback(
    request: Request,
    response: Response,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None
):
    """
    Handle Google OAuth callback
    Exchange code for tokens and create/update user
    """
    # Handle errors from Google
    if error:
        logging.error(f"🔐 Google OAuth error: {error}")
        return RedirectResponse(url="/?auth_error=" + error)
    
    if not code or not state:
        logging.error("🔐 Google OAuth: Missing code or state")
        return RedirectResponse(url="/?auth_error=missing_params")
    
    # Verify state
    state_doc = await db.oauth_states.find_one({"state": state})
    if not state_doc:
        logging.error("🔐 Google OAuth: Invalid state")
        return RedirectResponse(url="/?auth_error=invalid_state")
    
    # Delete used state
    await db.oauth_states.delete_one({"state": state})
    
    return_url = state_doc.get("return_url", "/")
    
    try:
        # Exchange code for tokens
        redirect_uri = get_redirect_uri(request)
        
        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "client_id": GOOGLE_CLIENT_ID,
                    "client_secret": GOOGLE_CLIENT_SECRET,
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code"
                }
            )
            
            if token_response.status_code != 200:
                logging.error(f"🔐 Google OAuth token error: {token_response.text}")
                return RedirectResponse(url="/?auth_error=token_error")
            
            tokens = token_response.json()
            access_token = tokens.get("access_token")
            
            # Get user info from Google
            userinfo_response = await client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"}
            )
            
            if userinfo_response.status_code != 200:
                logging.error(f"🔐 Google OAuth userinfo error: {userinfo_response.text}")
                return RedirectResponse(url="/?auth_error=userinfo_error")
            
            userinfo = userinfo_response.json()
        
        # Extract user data
        google_id = userinfo.get("id")
        email = userinfo.get("email")
        name = userinfo.get("name")
        picture = userinfo.get("picture")
        
        logging.info(f"🔐 Google OAuth: User authenticated - {email}")
        
        # Check if user exists
        existing_user = await db.users.find_one({"email": email})
        
        if existing_user:
            user_id = existing_user["user_id"]
            # Update user info if changed
            await db.users.update_one(
                {"user_id": user_id},
                {"$set": {
                    "name": name,
                    "picture": picture,
                    "google_id": google_id,
                    "last_login": datetime.now(timezone.utc).isoformat()
                }}
            )
        else:
            # Create new user
            user_id = f"user_{uuid.uuid4().hex[:12]}"
            await db.users.insert_one({
                "user_id": user_id,
                "email": email,
                "name": name,
                "picture": picture,
                "google_id": google_id,
                "auth_provider": "google",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "last_login": datetime.now(timezone.utc).isoformat(),
                "report_credits": 0
            })
            logging.info(f"🔐 Google OAuth: New user created - {user_id}")
        
        # Create session
        session_token = uuid.uuid4().hex
        expires_at = datetime.now(timezone.utc) + timedelta(days=30)
        
        # Remove old sessions
        await db.user_sessions.delete_many({"user_id": user_id})
        
        # Create new session
        await db.user_sessions.insert_one({
            "session_token": session_token,
            "user_id": user_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": expires_at.isoformat()
        })
        
        # Build redirect URL with session token in URL
        # This approach is more reliable than cookies for cross-domain scenarios
        # The frontend will extract the token and store it in localStorage
        
        # Encode user info for the redirect
        import base64
        user_info = {
            "session_token": session_token,
            "user_id": user_id,
            "email": email,
            "name": name,
            "picture": picture
        }
        encoded_user = base64.urlsafe_b64encode(json.dumps(user_info).encode()).decode()
        
        # Build redirect with token
        if return_url and return_url != "/" and not return_url.startswith("http"):
            final_redirect = f"{return_url}?auth_token={encoded_user}"
        else:
            final_redirect = f"/?auth_token={encoded_user}"
        
        response = RedirectResponse(url=final_redirect, status_code=302)
        
        # Also set cookie as backup (for same-domain scenarios)
        is_localhost = "localhost" in str(request.url) or "127.0.0.1" in str(request.url)
        
        response.set_cookie(
            key="session_token",
            value=session_token,
            httponly=False,  # Allow JS access for debugging
            secure=not is_localhost,
            samesite="lax",
            max_age=60 * 60 * 24 * 30,
            path="/",
            domain=None
        )
        
        logging.info(f"🔐 Google OAuth: Session created for {email}, redirecting to {final_redirect}")
        
        return response
        
    except Exception as e:
        logging.error(f"🔐 Google OAuth exception: {str(e)}")
        return RedirectResponse(url="/?auth_error=server_error")


@google_oauth_router.get("/google/status")
async def google_oauth_status():
    """Check if Google OAuth is configured"""
    return {
        "configured": bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET),
        "client_id_present": bool(GOOGLE_CLIENT_ID),
        "client_secret_present": bool(GOOGLE_CLIENT_SECRET)
    }
