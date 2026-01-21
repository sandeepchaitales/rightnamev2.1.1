"""
Admin Panel Routes for RIGHTNAME
Secure admin access for prompt editing and system configuration
"""

from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from passlib.context import CryptContext
import jwt
import os
import logging
from motor.motor_asyncio import AsyncIOMotorClient

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT Settings
JWT_SECRET = os.environ.get('JWT_SECRET', 'rightname-admin-secret-key-2024-secure')
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

# Admin Router
admin_router = APIRouter(prefix="/api/admin", tags=["admin"])

# ============ SCHEMAS ============

class AdminLoginRequest(BaseModel):
    email: EmailStr
    password: str

class AdminLoginResponse(BaseModel):
    success: bool
    token: Optional[str] = None
    message: str
    admin_email: Optional[str] = None

class SystemPromptUpdate(BaseModel):
    prompt_type: str = Field(..., description="Type: 'system' or 'early_stopping'")
    content: str = Field(..., description="The prompt content")
    name: Optional[str] = Field(None, description="Optional name for the prompt version")

class ModelSettings(BaseModel):
    primary_model: str = Field(default="gpt-4o-mini", description="Primary LLM model")
    fallback_models: List[str] = Field(default=["claude-sonnet-4-20250514", "gpt-4o"], description="Fallback models in order")
    timeout_seconds: int = Field(default=35, ge=10, le=120, description="LLM timeout in seconds")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="LLM temperature")
    max_tokens: int = Field(default=8000, ge=1000, le=32000, description="Max response tokens")
    retry_count: int = Field(default=2, ge=1, le=5, description="Retries per model")

class PromptTemplate(BaseModel):
    name: str
    prompt_type: str  # 'system' or 'early_stopping'
    content: str
    is_active: bool = False
    created_at: Optional[str] = None

class TestPromptRequest(BaseModel):
    prompt_type: str  # 'system' or 'early_stopping'
    test_input: Dict[str, Any]  # Test data to evaluate

class UsageStats(BaseModel):
    total_evaluations: int
    successful_evaluations: int
    failed_evaluations: int
    average_response_time: float
    model_usage: Dict[str, int]
    daily_stats: List[Dict[str, Any]]

# ============ AUTHENTICATION ============

def create_admin_token(email: str) -> str:
    """Create JWT token for admin"""
    payload = {
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS),
        "iat": datetime.now(timezone.utc),
        "type": "admin"
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def verify_admin_token(token: str) -> dict:
    """Verify JWT token and return payload"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "admin":
            raise HTTPException(status_code=401, detail="Invalid token type")
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

async def get_current_admin(authorization: str = Header(None)) -> dict:
    """Dependency to verify admin access"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")
    
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization format")
    
    token = authorization.replace("Bearer ", "")
    return verify_admin_token(token)

# ============ DATABASE REFERENCE ============
# Will be set from server.py
db = None

def set_db(database):
    """Set database reference from main server"""
    global db
    db = database

# ============ ROUTES ============

@admin_router.post("/login", response_model=AdminLoginResponse)
async def admin_login(request: AdminLoginRequest):
    """Admin login endpoint"""
    # Get admin from database
    admin = await db.admins.find_one({"email": request.email})
    
    if not admin:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Verify password
    if not pwd_context.verify(request.password, admin["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Create token
    token = create_admin_token(request.email)
    
    # Log login
    await db.admin_logs.insert_one({
        "action": "login",
        "admin_email": request.email,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ip": "N/A"
    })
    
    return AdminLoginResponse(
        success=True,
        token=token,
        message="Login successful",
        admin_email=request.email
    )

@admin_router.get("/verify")
async def verify_admin(admin: dict = Depends(get_current_admin)):
    """Verify admin token is valid"""
    return {"valid": True, "email": admin["email"]}

@admin_router.get("/prompts/{prompt_type}")
async def get_prompt(prompt_type: str, admin: dict = Depends(get_current_admin)):
    """Get current prompt by type (system or early_stopping)"""
    if prompt_type not in ["system", "early_stopping"]:
        raise HTTPException(status_code=400, detail="Invalid prompt type")
    
    # Get active prompt from database
    prompt = await db.prompts.find_one({"type": prompt_type, "is_active": True})
    
    if not prompt:
        # Return default prompt from file - use V2 optimized prompt
        if prompt_type == "system":
            from prompts_v2 import SYSTEM_PROMPT_V2
            content = SYSTEM_PROMPT_V2
        else:
            # Get early stopping prompt
            content = await get_early_stopping_prompt_default()
        
        return {
            "type": prompt_type,
            "content": content,
            "name": "Default (V2 Optimized)",
            "is_default": True,
            "last_modified": None,
            "character_count": len(content)
        }
    
    prompt.pop('_id', None)
    prompt["character_count"] = len(prompt.get("content", ""))
    return prompt

@admin_router.put("/prompts/{prompt_type}")
async def update_prompt(prompt_type: str, update: SystemPromptUpdate, admin: dict = Depends(get_current_admin)):
    """Update a prompt"""
    if prompt_type not in ["system", "early_stopping"]:
        raise HTTPException(status_code=400, detail="Invalid prompt type")
    
    # Deactivate current active prompt
    await db.prompts.update_many(
        {"type": prompt_type, "is_active": True},
        {"$set": {"is_active": False}}
    )
    
    # Create new active prompt
    prompt_doc = {
        "type": prompt_type,
        "content": update.content,
        "name": update.name or f"Version {datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": admin["email"],
        "is_default": False
    }
    
    await db.prompts.insert_one(prompt_doc)
    
    # Log change
    await db.admin_logs.insert_one({
        "action": "prompt_update",
        "prompt_type": prompt_type,
        "admin_email": admin["email"],
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
    
    return {"success": True, "message": f"{prompt_type} prompt updated successfully"}

@admin_router.get("/prompts/{prompt_type}/history")
async def get_prompt_history(prompt_type: str, admin: dict = Depends(get_current_admin)):
    """Get prompt version history"""
    if prompt_type not in ["system", "early_stopping"]:
        raise HTTPException(status_code=400, detail="Invalid prompt type")
    
    cursor = db.prompts.find({"type": prompt_type}).sort("created_at", -1).limit(20)
    history = []
    async for doc in cursor:
        doc.pop('_id', None)
        history.append(doc)
    
    return {"history": history}

@admin_router.post("/prompts/{prompt_type}/restore/{version_name}")
async def restore_prompt_version(prompt_type: str, version_name: str, admin: dict = Depends(get_current_admin)):
    """Restore a previous prompt version"""
    # Find the version
    version = await db.prompts.find_one({"type": prompt_type, "name": version_name})
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")
    
    # Deactivate all and activate this one
    await db.prompts.update_many(
        {"type": prompt_type},
        {"$set": {"is_active": False}}
    )
    
    await db.prompts.update_one(
        {"type": prompt_type, "name": version_name},
        {"$set": {"is_active": True}}
    )
    
    return {"success": True, "message": f"Restored {version_name}"}

@admin_router.get("/settings/model")
async def get_model_settings(admin: dict = Depends(get_current_admin)):
    """Get current model settings"""
    settings = await db.settings.find_one({"type": "model_settings"})
    
    if not settings:
        # Return defaults
        return ModelSettings().model_dump()
    
    settings.pop('_id', None)
    settings.pop('type', None)
    return settings

@admin_router.put("/settings/model")
async def update_model_settings(settings: ModelSettings, admin: dict = Depends(get_current_admin)):
    """Update model settings"""
    settings_doc = settings.model_dump()
    settings_doc["type"] = "model_settings"
    settings_doc["updated_at"] = datetime.now(timezone.utc).isoformat()
    settings_doc["updated_by"] = admin["email"]
    
    await db.settings.update_one(
        {"type": "model_settings"},
        {"$set": settings_doc},
        upsert=True
    )
    
    # Log change
    await db.admin_logs.insert_one({
        "action": "model_settings_update",
        "admin_email": admin["email"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "settings": settings_doc
    })
    
    return {"success": True, "message": "Model settings updated"}

@admin_router.get("/analytics/usage")
async def get_usage_analytics(days: int = 7, admin: dict = Depends(get_current_admin)):
    """Get usage analytics"""
    start_date = datetime.now(timezone.utc) - timedelta(days=days)
    
    # Get evaluation stats
    total = await db.evaluations.count_documents({})
    successful = await db.evaluations.count_documents({"early_stopped": {"$ne": True}})
    failed = await db.evaluations.count_documents({"status": "failed"})
    
    # Get average response time
    pipeline = [
        {"$match": {"processing_time_seconds": {"$exists": True}}},
        {"$group": {"_id": None, "avg_time": {"$avg": "$processing_time_seconds"}}}
    ]
    avg_result = await db.evaluations.aggregate(pipeline).to_list(1)
    avg_time = avg_result[0]["avg_time"] if avg_result else 0
    
    # Get model usage
    model_pipeline = [
        {"$match": {"model_used": {"$exists": True}}},
        {"$group": {"_id": "$model_used", "count": {"$sum": 1}}}
    ]
    model_results = await db.evaluations.aggregate(model_pipeline).to_list(100)
    model_usage = {r["_id"]: r["count"] for r in model_results if r["_id"]}
    
    # Get daily stats
    daily_pipeline = [
        {"$match": {"created_at": {"$gte": start_date.isoformat()}}},
        {"$group": {
            "_id": {"$substr": ["$created_at", 0, 10]},
            "count": {"$sum": 1}
        }},
        {"$sort": {"_id": 1}}
    ]
    daily_results = await db.evaluations.aggregate(daily_pipeline).to_list(30)
    daily_stats = [{"date": r["_id"], "evaluations": r["count"]} for r in daily_results]
    
    return {
        "total_evaluations": total,
        "successful_evaluations": successful,
        "failed_evaluations": failed,
        "average_response_time": round(avg_time, 2),
        "model_usage": model_usage,
        "daily_stats": daily_stats
    }

@admin_router.get("/analytics/recent")
async def get_recent_evaluations(limit: int = 20, admin: dict = Depends(get_current_admin)):
    """Get recent evaluations"""
    cursor = db.evaluations.find({}).sort("created_at", -1).limit(limit)
    evaluations = []
    async for doc in cursor:
        doc.pop('_id', None)
        # Only include essential fields
        evaluations.append({
            "report_id": doc.get("report_id"),
            "brand_names": doc.get("request", {}).get("brand_names", []),
            "category": doc.get("request", {}).get("category"),
            "verdict": doc.get("brand_scores", [{}])[0].get("verdict") if doc.get("brand_scores") else None,
            "score": doc.get("brand_scores", [{}])[0].get("namescore") if doc.get("brand_scores") else None,
            "created_at": doc.get("created_at"),
            "processing_time": doc.get("processing_time_seconds"),
            "model_used": doc.get("model_used"),
            "early_stopped": doc.get("early_stopped", False)
        })
    
    return {"evaluations": evaluations}

@admin_router.post("/test/prompt")
async def test_prompt(request: TestPromptRequest, admin: dict = Depends(get_current_admin)):
    """Test a prompt with sample input (dry run)"""
    # Get the active prompt
    prompt = await db.prompts.find_one({"type": request.prompt_type, "is_active": True})
    
    if not prompt:
        if request.prompt_type == "system":
            from prompts import SYSTEM_PROMPT
            content = SYSTEM_PROMPT
        else:
            content = await get_early_stopping_prompt_default()
    else:
        content = prompt["content"]
    
    # Return a preview of what would be sent to the LLM
    test_input = request.test_input
    
    preview = {
        "prompt_type": request.prompt_type,
        "prompt_preview": content[:2000] + "..." if len(content) > 2000 else content,
        "prompt_length": len(content),
        "test_input": test_input,
        "estimated_tokens": len(content.split()) * 1.3,  # Rough estimate
        "note": "This is a preview. Actual LLM call not made in test mode."
    }
    
    return preview

@admin_router.get("/logs")
async def get_admin_logs(limit: int = 50, admin: dict = Depends(get_current_admin)):
    """Get admin activity logs"""
    cursor = db.admin_logs.find({}).sort("timestamp", -1).limit(limit)
    logs = []
    async for doc in cursor:
        doc.pop('_id', None)
        logs.append(doc)
    
    return {"logs": logs}

# ============ EVALUATION TRACKING DASHBOARD ============

class EvaluationFilters(BaseModel):
    """Filters for evaluation search"""
    search: Optional[str] = None  # Search by brand name
    verdict: Optional[str] = None  # GO, REJECT, NO-GO, CONDITIONAL GO
    category: Optional[str] = None
    industry: Optional[str] = None
    date_from: Optional[str] = None  # ISO date string
    date_to: Optional[str] = None
    min_score: Optional[int] = None
    max_score: Optional[int] = None

@admin_router.get("/evaluations")
async def get_evaluations(
    page: int = 1,
    limit: int = 20,
    search: Optional[str] = None,
    verdict: Optional[str] = None,
    category: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    admin: dict = Depends(get_current_admin)
):
    """
    Get all evaluations with pagination, search, and filters.
    This is the main endpoint for the evaluation tracking dashboard.
    """
    # Build query filter
    query = {}
    
    # Search by brand name
    if search:
        query["$or"] = [
            {"request.brand_names": {"$regex": search, "$options": "i"}},
            {"brand_scores.brand_name": {"$regex": search, "$options": "i"}}
        ]
    
    # Filter by verdict
    if verdict:
        query["brand_scores.verdict"] = {"$regex": f"^{verdict}", "$options": "i"}
    
    # Filter by category
    if category:
        query["request.category"] = {"$regex": category, "$options": "i"}
    
    # Filter by date range
    if date_from:
        query["created_at"] = query.get("created_at", {})
        query["created_at"]["$gte"] = date_from
    if date_to:
        query["created_at"] = query.get("created_at", {})
        query["created_at"]["$lte"] = date_to
    
    # Calculate skip for pagination
    skip = (page - 1) * limit
    
    # Sort direction
    sort_direction = -1 if sort_order == "desc" else 1
    
    # Get total count for pagination
    total_count = await db.evaluations.count_documents(query)
    
    # Get evaluations
    cursor = db.evaluations.find(query).sort(sort_by, sort_direction).skip(skip).limit(limit)
    
    evaluations = []
    async for doc in cursor:
        doc.pop('_id', None)
        
        # Extract key fields for the table view
        brand_scores = doc.get("brand_scores", [{}])
        first_score = brand_scores[0] if brand_scores else {}
        request = doc.get("request", {})
        
        evaluations.append({
            "report_id": doc.get("report_id"),
            "brand_name": first_score.get("brand_name") or (request.get("brand_names", [""])[0] if request.get("brand_names") else ""),
            "category": request.get("category", "N/A"),
            "industry": request.get("industry", "N/A"),
            "countries": request.get("countries", []),
            "positioning": request.get("positioning", "N/A"),
            "namescore": first_score.get("namescore"),
            "verdict": first_score.get("verdict", "N/A"),
            "trademark_risk": first_score.get("trademark_research", {}).get("overall_risk", "N/A") if first_score.get("trademark_research") else "N/A",
            "created_at": doc.get("created_at"),
            "processing_time": doc.get("processing_time_seconds"),
            "early_stopped": doc.get("early_stopped", False),
            "rejection_reason": doc.get("rejection_reason")
        })
    
    return {
        "evaluations": evaluations,
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total_count,
            "total_pages": (total_count + limit - 1) // limit
        }
    }

@admin_router.get("/evaluations/stats")
async def get_evaluation_stats(
    days: int = 30,
    admin: dict = Depends(get_current_admin)
):
    """
    Get comprehensive statistics for the evaluation tracking dashboard.
    """
    start_date = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    
    # Total evaluations
    total = await db.evaluations.count_documents({})
    total_in_period = await db.evaluations.count_documents({"created_at": {"$gte": start_date}})
    
    # Verdict breakdown
    verdict_pipeline = [
        {"$unwind": "$brand_scores"},
        {"$group": {"_id": "$brand_scores.verdict", "count": {"$sum": 1}}}
    ]
    verdict_results = await db.evaluations.aggregate(verdict_pipeline).to_list(10)
    verdict_breakdown = {r["_id"]: r["count"] for r in verdict_results if r["_id"]}
    
    # Score distribution
    score_pipeline = [
        {"$unwind": "$brand_scores"},
        {"$match": {"brand_scores.namescore": {"$exists": True, "$ne": None}}},
        {"$bucket": {
            "groupBy": "$brand_scores.namescore",
            "boundaries": [0, 30, 50, 70, 85, 101],
            "default": "other",
            "output": {"count": {"$sum": 1}}
        }}
    ]
    score_results = await db.evaluations.aggregate(score_pipeline).to_list(10)
    score_distribution = {
        "0-29 (Poor)": 0, "30-49 (Below Avg)": 0, "50-69 (Average)": 0,
        "70-84 (Good)": 0, "85-100 (Excellent)": 0
    }
    boundary_labels = ["0-29 (Poor)", "30-49 (Below Avg)", "50-69 (Average)", "70-84 (Good)", "85-100 (Excellent)"]
    for i, r in enumerate(score_results):
        if i < len(boundary_labels):
            score_distribution[boundary_labels[i]] = r["count"]
    
    # Average score
    avg_score_pipeline = [
        {"$unwind": "$brand_scores"},
        {"$match": {"brand_scores.namescore": {"$exists": True, "$ne": None}}},
        {"$group": {"_id": None, "avg_score": {"$avg": "$brand_scores.namescore"}}}
    ]
    avg_result = await db.evaluations.aggregate(avg_score_pipeline).to_list(1)
    avg_score = round(avg_result[0]["avg_score"], 1) if avg_result else 0
    
    # Category breakdown (top 10)
    category_pipeline = [
        {"$match": {"request.category": {"$exists": True}}},
        {"$group": {"_id": "$request.category", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10}
    ]
    category_results = await db.evaluations.aggregate(category_pipeline).to_list(10)
    top_categories = [{"category": r["_id"], "count": r["count"]} for r in category_results if r["_id"]]
    
    # Daily trend (last 30 days)
    daily_pipeline = [
        {"$match": {"created_at": {"$gte": start_date}}},
        {"$group": {
            "_id": {"$substr": ["$created_at", 0, 10]},
            "count": {"$sum": 1}
        }},
        {"$sort": {"_id": 1}}
    ]
    daily_results = await db.evaluations.aggregate(daily_pipeline).to_list(31)
    daily_trend = [{"date": r["_id"], "evaluations": r["count"]} for r in daily_results]
    
    # Average processing time
    time_pipeline = [
        {"$match": {"processing_time_seconds": {"$exists": True, "$ne": None}}},
        {"$group": {"_id": None, "avg_time": {"$avg": "$processing_time_seconds"}}}
    ]
    time_result = await db.evaluations.aggregate(time_pipeline).to_list(1)
    avg_processing_time = round(time_result[0]["avg_time"], 1) if time_result else 0
    
    # Early stopped (rejected) count
    early_stopped = await db.evaluations.count_documents({"early_stopped": True})
    
    # Country popularity
    country_pipeline = [
        {"$match": {"request.countries": {"$exists": True}}},
        {"$unwind": "$request.countries"},
        {"$group": {"_id": "$request.countries", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10}
    ]
    country_results = await db.evaluations.aggregate(country_pipeline).to_list(10)
    top_countries = []
    for r in country_results:
        country = r["_id"]
        if isinstance(country, dict):
            country = country.get("name", str(country))
        top_countries.append({"country": country, "count": r["count"]})
    
    return {
        "summary": {
            "total_evaluations": total,
            "evaluations_in_period": total_in_period,
            "average_score": avg_score,
            "average_processing_time": avg_processing_time,
            "early_stopped_count": early_stopped
        },
        "verdict_breakdown": verdict_breakdown,
        "score_distribution": score_distribution,
        "top_categories": top_categories,
        "top_countries": top_countries,
        "daily_trend": daily_trend
    }

@admin_router.get("/evaluations/{report_id}")
async def get_evaluation_detail(report_id: str, admin: dict = Depends(get_current_admin)):
    """Get full details of a single evaluation"""
    evaluation = await db.evaluations.find_one({"report_id": report_id})
    
    if not evaluation:
        raise HTTPException(status_code=404, detail="Evaluation not found")
    
    evaluation.pop('_id', None)
    return evaluation

@admin_router.delete("/evaluations/{report_id}")
async def delete_evaluation(report_id: str, admin: dict = Depends(get_current_admin)):
    """Delete an evaluation"""
    result = await db.evaluations.delete_one({"report_id": report_id})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Evaluation not found")
    
    # Log the deletion
    await db.admin_logs.insert_one({
        "action": "evaluation_deleted",
        "admin_email": admin["email"],
        "report_id": report_id,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
    
    return {"success": True, "message": f"Evaluation {report_id} deleted"}

@admin_router.get("/evaluations/export/csv")
async def export_evaluations_csv(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    verdict: Optional[str] = None,
    admin: dict = Depends(get_current_admin)
):
    """Export evaluations to CSV format"""
    from fastapi.responses import StreamingResponse
    import io
    import csv
    
    # Build query
    query = {}
    if date_from:
        query["created_at"] = query.get("created_at", {})
        query["created_at"]["$gte"] = date_from
    if date_to:
        query["created_at"] = query.get("created_at", {})
        query["created_at"]["$lte"] = date_to
    if verdict:
        query["brand_scores.verdict"] = {"$regex": f"^{verdict}", "$options": "i"}
    
    # Get evaluations
    cursor = db.evaluations.find(query).sort("created_at", -1)
    
    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header row
    writer.writerow([
        "Report ID", "Brand Name", "Category", "Industry", "Countries",
        "Positioning", "NameScore", "Verdict", "Trademark Risk",
        "Created At", "Processing Time (s)", "Early Stopped"
    ])
    
    # Data rows
    async for doc in cursor:
        brand_scores = doc.get("brand_scores", [{}])
        first_score = brand_scores[0] if brand_scores else {}
        request = doc.get("request", {})
        countries = request.get("countries", [])
        countries_str = ", ".join([c.get("name", str(c)) if isinstance(c, dict) else str(c) for c in countries])
        
        writer.writerow([
            doc.get("report_id", ""),
            first_score.get("brand_name", ""),
            request.get("category", ""),
            request.get("industry", ""),
            countries_str,
            request.get("positioning", ""),
            first_score.get("namescore", ""),
            first_score.get("verdict", ""),
            first_score.get("trademark_research", {}).get("overall_risk", "") if first_score.get("trademark_research") else "",
            doc.get("created_at", ""),
            doc.get("processing_time_seconds", ""),
            doc.get("early_stopped", False)
        ])
    
    # Log export
    await db.admin_logs.insert_one({
        "action": "evaluations_exported",
        "admin_email": admin["email"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "filters": {"date_from": date_from, "date_to": date_to, "verdict": verdict}
    })
    
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=evaluations_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"}
    )

# ============ HELPER FUNCTIONS ============

async def get_early_stopping_prompt_default():
    """Get the default early stopping prompt"""
    return '''You are a trademark and brand expert. Analyze this brand name for conflicts.

BRAND NAME: {brand_name}
USER'S CATEGORY: {category}
USER'S NICE CLASS: Class {class_number} - {class_description}
TARGET MARKET: India, USA, Global

TASK: 
1. Check if "{brand_name}" already exists as a brand/company
2. If it exists, determine WHAT INDUSTRY/NICE CLASS the existing brand operates in
3. Compare: Is the existing brand in the SAME class as the user's category?

⚠️ CRITICAL RULE - SAME CLASS = CONFLICT, DIFFERENT CLASS = NO CONFLICT

RESPOND IN JSON FORMAT:
{
    "has_conflict": true/false,
    "confidence": "HIGH"/"MEDIUM"/"LOW",
    "conflicting_brand": "Name" or null,
    "conflicting_brand_industry": "Industry",
    "conflicting_brand_nice_class": <1-45>,
    "same_class_conflict": true/false,
    "reason": "Explanation"
}'''

async def initialize_admin(db_ref):
    """Initialize admin user if not exists - with race condition protection for multi-worker deployments"""
    global db
    db = db_ref
    
    try:
        # Check if admin exists
        admin = await db.admins.find_one({"email": "chaibunkcafe@gmail.com"})
        
        if not admin:
            # Use upsert to prevent race condition when multiple workers start simultaneously
            password_hash = pwd_context.hash("Sandy@2614")
            result = await db.admins.update_one(
                {"email": "chaibunkcafe@gmail.com"},
                {"$setOnInsert": {
                    "email": "chaibunkcafe@gmail.com",
                    "password_hash": password_hash,
                    "role": "super_admin",
                    "created_at": datetime.now(timezone.utc).isoformat()
                }},
                upsert=True
            )
            if result.upserted_id:
                logging.info("✅ Admin user created: chaibunkcafe@gmail.com")
            else:
                logging.info("✅ Admin user already exists (concurrent creation)")
        else:
            logging.info("✅ Admin user already exists")
    except Exception as e:
        # Don't fail startup if admin initialization fails - it's not critical
        logging.warning(f"⚠️ Admin initialization warning (non-critical): {e}")
