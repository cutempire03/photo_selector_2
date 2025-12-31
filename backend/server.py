from fastapi import FastAPI, APIRouter, UploadFile, File, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, timezone
from io import BytesIO
from PIL import Image
import base64
import uuid
import os
import logging
import json
import asyncio

from openai import AsyncOpenAI

# ------------------ ENV ------------------

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "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")
MONGO_URL = os.getenv("MONGO_URL", "mongodb+srv://gustavotoledor910_db_user:EVqNJxZutgMVBYZh@cluster0.kq7hnd9.mongodb.net/")
DB_NAME = os.getenv("DB_NAME", "photo_analysis")

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY não definida")

# ------------------ APP ------------------

app = FastAPI()
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("photo-api")

# ------------------ DB ------------------

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

# ------------------ OPENAI ------------------

openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# ------------------ MODELS ------------------

class PhotoAnalysis(BaseModel):
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


class PhotoAnalysisResponse(PhotoAnalysis):
    timestamp: str


class BulkAnalysisResponse(BaseModel):
    total: int
    analyzed: int
    photos: List[PhotoAnalysisResponse]

# ------------------ AI ------------------

async def analyze_photo_with_ai(image_base64: str) -> dict:
    prompt = """
You are a professional photo quality analyzer.
Return ONLY valid JSON:

{
  "sharpness_score": 0-10,
  "noise_score": 0-10,
  "composition_score": 0-10,
  "exposure_score": 0-10,
  "overall_score": 0-10,
  "is_good": true/false,
  "analysis": "short text"
}
"""

    response = await openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_base64}"
                        },
                    },
                ],
            }
        ],
        max_tokens=300,
    )

    content = response.choices[0].message.content
    data = json.loads(content)

    return {
        "sharpness_score": float(data.get("sharpness_score", 5)),
        "noise_score": float(data.get("noise_score", 5)),
        "composition_score": float(data.get("composition_score", 5)),
        "exposure_score": float(data.get("exposure_score", 5)),
        "overall_score": float(data.get("overall_score", 5)),
        "is_good": bool(data.get("is_good", False)),
        "analysis_text": data.get("analysis", ""),
    }

# ------------------ ROUTES ------------------

@api_router.get("/")
async def root():
    return {"status": "Photo Analysis API running"}

@api_router.post("/analyze", response_model=BulkAnalysisResponse)
async def analyze_photos(files: List[UploadFile] = File(...)):
    results = []

    for file in files:
        try:
            contents = await file.read()
            image = Image.open(BytesIO(contents)).convert("RGB")

            image.thumbnail((1024, 1024))

            buffer = BytesIO()
            image.save(buffer, format="JPEG", quality=85)
            image_base64 = base64.b64encode(buffer.getvalue()).decode()

            analysis = await analyze_photo_with_ai(image_base64)

            photo = PhotoAnalysis(
                filename=file.filename,
                image_data=f"data:image/jpeg;base64,{image_base64}",
                **analysis,
            )

            doc = photo.model_dump()
            doc["timestamp"] = doc["timestamp"].isoformat()

            await db.photos.insert_one(doc)

            results.append(PhotoAnalysisResponse(**doc))

        except Exception as e:
            logger.error(f"Erro em {file.filename}: {e}")

    return BulkAnalysisResponse(
        total=len(files),
        analyzed=len(results),
        photos=results,
    )

@api_router.get("/photos", response_model=List[PhotoAnalysisResponse])
async def get_photos(filter: Optional[str] = None):
    query = {}
    if filter == "good":
        query["is_good"] = True
    elif filter == "bad":
        query["is_good"] = False

    photos = await db.photos.find(query, {"_id": 0}).to_list(1000)
    return photos

@api_router.delete("/photos/{photo_id}")
async def delete_photo(photo_id: str):
    result = await db.photos.delete_one({"id": photo_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Photo not found")
    return {"ok": True}

# ------------------ MIDDLEWARE ------------------

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown():
    client.close()
