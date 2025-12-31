from fastapi import FastAPI, APIRouter, UploadFile, File, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
import uuid
from datetime import datetime, timezone
import base64
from io import BytesIO
from PIL import Image
import asyncio

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
emergent_key = os.environ.get('EMERGENT_LLM_KEY', '')
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get('DB_NAME', 'test_database')]

app = FastAPI()
api_router = APIRouter(prefix="/api")

class PhotoAnalysis(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    filename: str
    image_data: str
    sharpness_score: float
    noise_score: float
    composition_score: float
    exposure_score: float
    overall_score: float
    is_good: bool
    analysis_text: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class PhotoAnalysisResponse(BaseModel):
    id: str
    filename: str
    image_data: str
    sharpness_score: float
    noise_score: float
    composition_score: float
    exposure_score: float
    overall_score: float
    is_good: bool
    analysis_text: str
    timestamp: str

class BulkAnalysisResponse(BaseModel):
    total: int
    analyzed: int
    photos: List[PhotoAnalysisResponse]

async def analyze_photo_with_ai(image_base64: str, filename: str) -> dict:
    """Analyze photo quality using OpenAI GPT-4o"""
    try:
        chat = LlmChat(
            api_key=emergent_key,
            session_id=f"photo_analysis_{uuid.uuid4()}",
            system_message="""You are a professional photo quality analyzer. 
            Analyze photos for: sharpness, noise/grain, composition, and exposure.
            Return scores (0-10) for each criterion and overall assessment.
            Format your response as JSON with this structure:
            {
                "sharpness_score": 8.5,
                "noise_score": 7.0,
                "composition_score": 9.0,
                "exposure_score": 8.0,
                "overall_score": 8.1,
                "is_good": true,
                "analysis": "Brief analysis text"
            }
            Consider a photo "good" if overall_score >= 7.0"""
        ).with_model("openai", "gpt-4o")
        
        image_content = ImageContent(image_base64=image_base64)
        user_message = UserMessage(
            text="Analyze this photo's quality. Focus on sharpness, noise/grain levels, composition, and exposure. Provide scores and determine if it's a good photo.",
            file_contents=[image_content]
        )
        
        response = await chat.send_message(user_message)
        
        import json
        response_text = response.strip()
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        response_text = response_text.strip()
        
        analysis = json.loads(response_text)
        
        return {
            "sharpness_score": float(analysis.get("sharpness_score", 5.0)),
            "noise_score": float(analysis.get("noise_score", 5.0)),
            "composition_score": float(analysis.get("composition_score", 5.0)),
            "exposure_score": float(analysis.get("exposure_score", 5.0)),
            "overall_score": float(analysis.get("overall_score", 5.0)),
            "is_good": bool(analysis.get("is_good", False)),
            "analysis_text": str(analysis.get("analysis", "Analysis completed"))
        }
    except Exception as e:
        logger.error(f"AI analysis error for {filename}: {str(e)}")
        return {
            "sharpness_score": 5.0,
            "noise_score": 5.0,
            "composition_score": 5.0,
            "exposure_score": 5.0,
            "overall_score": 5.0,
            "is_good": False,
            "analysis_text": f"Analysis failed: {str(e)}"
        }

@api_router.get("/")
async def root():
    return {"message": "Photo Analysis API Ready"}

@api_router.post("/analyze", response_model=BulkAnalysisResponse)
async def analyze_photos(files: List[UploadFile] = File(...)):
    """Analyze multiple photos and return quality scores"""
    results = []
    
    for file in files:
        try:
            contents = await file.read()
            image = Image.open(BytesIO(contents))
            
            if image.mode in ('RGBA', 'LA', 'P'):
                image = image.convert('RGB')
            
            max_size = 1024
            if image.width > max_size or image.height > max_size:
                image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            
            buffer = BytesIO()
            image.save(buffer, format='JPEG', quality=85)
            image_bytes = buffer.getvalue()
            image_base64 = base64.b64encode(image_bytes).decode('utf-8')
            
            analysis = await analyze_photo_with_ai(image_base64, file.filename)
            
            photo_doc = PhotoAnalysis(
                filename=file.filename,
                image_data=f"data:image/jpeg;base64,{image_base64}",
                **analysis
            )
            
            doc = photo_doc.model_dump()
            doc['timestamp'] = doc['timestamp'].isoformat()
            
            await db.photos.insert_one(doc)
            
            results.append(PhotoAnalysisResponse(
                id=photo_doc.id,
                filename=photo_doc.filename,
                image_data=photo_doc.image_data,
                sharpness_score=photo_doc.sharpness_score,
                noise_score=photo_doc.noise_score,
                composition_score=photo_doc.composition_score,
                exposure_score=photo_doc.exposure_score,
                overall_score=photo_doc.overall_score,
                is_good=photo_doc.is_good,
                analysis_text=photo_doc.analysis_text,
                timestamp=doc['timestamp']
            ))
            
        except Exception as e:
            logger.error(f"Error processing {file.filename}: {str(e)}")
            continue
    
    return BulkAnalysisResponse(
        total=len(files),
        analyzed=len(results),
        photos=results
    )

@api_router.get("/photos", response_model=List[PhotoAnalysisResponse])
async def get_all_photos(filter: Optional[str] = None):
    """Get all analyzed photos with optional filter (good/bad)"""
    query = {}
    if filter == "good":
        query["is_good"] = True
    elif filter == "bad":
        query["is_good"] = False
    
    photos = await db.photos.find(query, {"_id": 0}).sort("timestamp", -1).to_list(1000)
    
    return [
        PhotoAnalysisResponse(
            id=photo["id"],
            filename=photo["filename"],
            image_data=photo["image_data"],
            sharpness_score=photo["sharpness_score"],
            noise_score=photo["noise_score"],
            composition_score=photo["composition_score"],
            exposure_score=photo["exposure_score"],
            overall_score=photo["overall_score"],
            is_good=photo["is_good"],
            analysis_text=photo["analysis_text"],
            timestamp=photo["timestamp"]
        )
        for photo in photos
    ]

@api_router.delete("/photos/{photo_id}")
async def delete_photo(photo_id: str):
    """Delete a photo by ID"""
    result = await db.photos.delete_one({"id": photo_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Photo not found")
    return {"message": "Photo deleted"}

@api_router.delete("/photos")
async def delete_all_photos():
    """Delete all photos"""
    result = await db.photos.delete_many({})
    return {"message": f"Deleted {result.deleted_count} photos"}

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()