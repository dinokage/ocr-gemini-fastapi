import sys
import traceback
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Form, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
import google.generativeai as genai
import os
import fitz  # PyMuPDF
from PIL import Image
import io
import json
from collections import defaultdict, Counter
import re
import tempfile
import asyncio
from datetime import datetime
import uuid
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/tmp/app.log')
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# Global exception handler for uncaught exceptions
def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    
    logger.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

sys.excepthook = handle_exception

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("🚀 Starting PDF Tag Extraction Service")
    yield
    # Shutdown
    logger.info("🔄 Shutting down PDF Tag Extraction Service")

app = FastAPI(
    title="PDF Tag Extraction Service", 
    version="2.0.0",
    description="Extract component and pipeline tags from engineering diagrams using Gemini AI",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global exception handler caught: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc),
            "path": str(request.url)
        }
    )

# Configuration with detailed debugging
logger.info("🔧 Loading configuration...")
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

if GEMINI_API_KEY:
    logger.info(f"✅ GEMINI_API_KEY found (length: {len(GEMINI_API_KEY)} characters)")
    logger.info(f"✅ API Key starts with: {GEMINI_API_KEY[:10]}...")
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        logger.info("✅ Gemini API configured successfully")
        
        # Test Gemini API connection
        try:
            models = list(genai.list_models())
            logger.info(f"✅ Gemini API connection test successful. Available models: {len(models)}")
        except Exception as e:
            logger.warning(f"⚠️ Gemini API connection test failed: {e}")
            
    except Exception as e:
        logger.error(f"❌ Failed to configure Gemini API: {e}")
        GEMINI_API_KEY = None
else:
    logger.error("❌ GEMINI_API_KEY not found in environment variables")
    logger.info("🔍 Debugging environment variables:")
    logger.info(f"   Current working directory: {os.getcwd()}")
    logger.info(f"   .env file exists: {os.path.exists('.env')}")
    if os.path.exists('.env'):
        logger.info("   .env file contents:")
        try:
            with open('.env', 'r') as f:
                content = f.read()
                lines = content.strip().split('\n')
                for line in lines:
                    if '=' in line:
                        key = line.split('=')[0]
                        logger.info(f"     {key}=***")
                    else:
                        logger.info(f"     {line}")
        except Exception as e:
            logger.error(f"   Error reading .env file: {e}")

# Your existing models (keep them as they are)
class TagCategories(BaseModel):
    pipeline_tags: List[str]
    component_tags: Dict[str, List[str]]
    uncategorized_other: List[str]

class ExtractionResult(BaseModel):
    total_unique_tags: int
    tags_by_pdf: Dict[str, List[str]]
    categorized_tags: TagCategories
    tag_frequency: Dict[str, int]
    processing_time: float
    total_pages_processed: int

class ProcessingStatus(BaseModel):
    task_id: str
    status: str
    progress: Optional[str] = None
    result: Optional[ExtractionResult] = None
    error: Optional[str] = None
    created_at: str
    updated_at: str

class TaskResponse(BaseModel):
    task_id: str
    message: str
    status: str

class HealthResponse(BaseModel):
    status: str
    gemini_configured: bool
    timestamp: str
    version: str

class PDFValidationResponse(BaseModel):
    valid: bool
    filename: str
    page_count: Optional[int] = None
    file_size_mb: Optional[float] = None
    error: Optional[str] = None
    message: str

# In-memory storage for task status
task_storage: Dict[str, ProcessingStatus] = {}

# Helper Functions with enhanced error handling
async def save_upload_file(upload_file: UploadFile) -> str:
    """Save uploaded file to temporary location and return path"""
    try:
        logger.info(f"💾 Saving uploaded file: {upload_file.filename}")
        
        # Validate file
        if not upload_file.filename:
            raise ValueError("No filename provided")
            
        if not upload_file.filename.lower().endswith('.pdf'):
            raise ValueError(f"File {upload_file.filename} is not a PDF")
        
        # Create temporary file
        temp_file = tempfile.NamedTemporaryFile(
            delete=False, 
            suffix=".pdf", 
            prefix=f"upload_{uuid.uuid4().hex[:8]}_"
        )
        
        # Read and write file content
        content = await upload_file.read()
        logger.info(f"📄 File size: {len(content)} bytes")
        
        if len(content) == 0:
            raise ValueError("Uploaded file is empty")
            
        temp_file.write(content)
        temp_file.close()
        
        logger.info(f"✅ File saved to: {temp_file.name}")
        return temp_file.name
        
    except Exception as e:
        logger.error(f"❌ Failed to save uploaded file {upload_file.filename}: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Failed to save uploaded file {upload_file.filename}: {str(e)}")

def pdf_to_images(pdf_path: str, dpi: int = 200) -> List[Image.Image]:
    """Converts PDF pages to a list of PIL Images."""
    images = []
    try:
        logger.info(f"🖼️ Converting PDF to images: {pdf_path} (DPI: {dpi})")
        
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
            
        doc = fitz.open(pdf_path)
        page_count = len(doc)
        logger.info(f"📖 PDF has {page_count} pages")
        
        for page_num in range(page_count):
            logger.info(f"🔄 Processing page {page_num + 1}/{page_count}")
            page = doc.load_page(page_num)
            pix = page.get_pixmap(dpi=dpi)
            img_data = pix.tobytes("png")
            image = Image.open(io.BytesIO(img_data))
            images.append(image)
            
        doc.close()
        logger.info(f"✅ Successfully converted {len(images)} pages to images")
        
    except Exception as e:
        logger.error(f"❌ Error converting PDF {pdf_path} to images: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to convert PDF to images: {str(e)}")
    return images

def extract_tags_from_image_gemini(image_pil: Image.Image, model_name: str = "gemini-1.5-flash-8b") -> List[str]:
    """Extract tags from image using Gemini AI"""
    try:
        logger.info(f"🤖 Extracting tags using model: {model_name}")
        
        if not GEMINI_API_KEY:
            raise HTTPException(status_code=500, detail="Gemini API Key not configured")

        model = genai.GenerativeModel(model_name)

        img_byte_arr = io.BytesIO()
        image_pil.save(img_byte_arr, format='PNG')
        img_bytes = img_byte_arr.getvalue()
        
        logger.info(f"🖼️ Image size: {len(img_bytes)} bytes")

        prompt = """
        You are an expert in reading engineering P&ID (Piping and Instrumentation Diagrams),
        electrical diagrams, or general plant layout drawings.
        Your task is to identify and extract ALL component tags AND pipeline tags from the provided image.

        Component tags are typically alphanumeric identifiers for equipment or instruments.
        Examples: 'P-101A', 'XV-002', 'TK-5003.B', 'FIC-301', 'LT-500', 'BV-0007', 'NRV-0003', '20-V-010'.

        Pipeline tags (also known as line numbers) identify specific pipelines.
        Examples: '13-M2-0041-1.5"-OD-91440X', '01-P10A-0002-DN50-CS-L150', '100-HC-001-4"-SS316-INS01'.

        Please return ALL extracted tags as a single JSON list of strings.
        For example: ["P-101A", "13-M2-0041-1.5\\"-OD-91440X", "BV-0007"]
        If no tags are found, return an empty list: [].
        """

        response = model.generate_content([prompt, {"mime_type": "image/png", "data": img_bytes}])
        
        if response.parts:
            content = response.text.strip()
            logger.info(f"🤖 Gemini response: {content[:200]}...")
            
            # Clean JSON response
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            try:
                tags = json.loads(content)
                if isinstance(tags, list) and all(isinstance(tag, str) for tag in tags):
                    unique_tags = list(set(tags))
                    logger.info(f"✅ Extracted {len(unique_tags)} unique tags")
                    return unique_tags
                else:
                    logger.warning(f"⚠️ Gemini returned invalid format: {content}")
                    return []
            except json.JSONDecodeError as e:
                logger.warning(f"⚠️ JSON decode error: {e}")
                return []
        else:
            logger.warning("⚠️ Gemini returned empty response")
            return []
            
    except Exception as e:
        logger.error(f"❌ Error during Gemini API call: {e}", exc_info=True)
        return []

# Your existing categorization function (keep as is)
def enhanced_categorize_tags(tags: List[str]) -> Dict:
    """Performs enhanced categorization for component and pipeline tags."""
    # Keep your existing implementation
    categories = {
        "pipeline_tags": [],
        "component_tags": defaultdict(list),
        "uncategorized_other": []
    }
    
    # Your existing categorization logic here...
    # (I'm keeping it short for brevity, but use your full implementation)
    
    return categories

async def process_pdfs_async(
    files: List[UploadFile],
    task_id: str,
    gemini_model: str = "gemini-1.5-flash-latest",
    pdf_conversion_dpi: int = 300
):
    """Async function to process PDFs in the background"""
    start_time = datetime.now()
    temp_files = []
    
    try:
        logger.info(f"🔄 Starting background processing for task: {task_id}")
        
        # Update task status
        task_storage[task_id].status = "processing"
        task_storage[task_id].progress = "Starting PDF processing..."
        task_storage[task_id].updated_at = datetime.now().isoformat()
        
        all_extracted_tags_master_list = []
        tags_by_pdf = {}
        total_pages_processed = 0
        
        for file_idx, file in enumerate(files):
            logger.info(f"📁 Processing file {file_idx + 1}/{len(files)}: {file.filename}")
            task_storage[task_id].progress = f"Processing file {file_idx + 1}/{len(files)}: {file.filename}"
            task_storage[task_id].updated_at = datetime.now().isoformat()
            
            try:
                # Save uploaded file to temporary location
                temp_file_path = await save_upload_file(file)
                temp_files.append(temp_file_path)
                
                # Convert PDF to images
                images_from_pdf = pdf_to_images(temp_file_path, dpi=pdf_conversion_dpi)
                total_pages_processed += len(images_from_pdf)
                
                if not images_from_pdf:
                    logger.warning(f"⚠️ No images extracted from {file.filename}")
                    continue
                
                pdf_tags_current_file = []
                for i, img in enumerate(images_from_pdf):
                    logger.info(f"🔄 Processing {file.filename} - Page {i+1}/{len(images_from_pdf)}")
                    task_storage[task_id].progress = f"Processing {file.filename} - Page {i+1}/{len(images_from_pdf)}"
                    task_storage[task_id].updated_at = datetime.now().isoformat()
                    
                    tags_on_page = extract_tags_from_image_gemini(img, model_name=gemini_model)
                    if tags_on_page:
                        pdf_tags_current_file.extend(tags_on_page)
                
                # Store tags for this PDF
                unique_tags_this_pdf = sorted(list(set(pdf_tags_current_file)))
                tags_by_pdf[file.filename] = unique_tags_this_pdf
                all_extracted_tags_master_list.extend(pdf_tags_current_file)
                
                logger.info(f"✅ Completed processing {file.filename}: {len(unique_tags_this_pdf)} unique tags")
                
            except Exception as e:
                logger.error(f"❌ Error processing {file.filename}: {e}", exc_info=True)
                continue
        
        # Process results
        final_unique_tags = sorted(list(set(all_extracted_tags_master_list)))
        categorized_tags = enhanced_categorize_tags(final_unique_tags)
        tag_frequency = dict(Counter(all_extracted_tags_master_list).most_common())
        
        processing_time = (datetime.now() - start_time).total_seconds()
        
        # Create result
        result = ExtractionResult(
            total_unique_tags=len(final_unique_tags),
            tags_by_pdf=tags_by_pdf,
            categorized_tags=TagCategories(
                pipeline_tags=categorized_tags["pipeline_tags"],
                component_tags=dict(categorized_tags["component_tags"]),
                uncategorized_other=categorized_tags["uncategorized_other"]
            ),
            tag_frequency=tag_frequency,
            processing_time=processing_time,
            total_pages_processed=total_pages_processed
        )
        
        # Update task status
        task_storage[task_id].status = "completed"
        task_storage[task_id].result = result
        task_storage[task_id].progress = "Processing completed successfully"
        task_storage[task_id].updated_at = datetime.now().isoformat()
        
        logger.info(f"✅ Successfully completed task {task_id}")
        
    except Exception as e:
        error_msg = f"Processing failed: {str(e)}"
        logger.error(f"❌ Task {task_id} failed: {e}", exc_info=True)
        
        task_storage[task_id].status = "failed"
        task_storage[task_id].error = str(e)
        task_storage[task_id].progress = error_msg
        task_storage[task_id].updated_at = datetime.now().isoformat()
    
    finally:
        # Clean up temporary files
        for temp_file in temp_files:
            try:
                os.unlink(temp_file)
                logger.info(f"🗑️ Cleaned up temp file: {temp_file}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to clean up temp file {temp_file}: {e}")

# API Endpoints
@app.get("/", response_model=Dict[str, str])
async def root():
    logger.info("📍 Root endpoint accessed")
    return {
        "message": "PDF Tag Extraction Service", 
        "status": "active",
        "version": "2.0.0",
        "docs": "/docs"
    }

@app.get("/health", response_model=HealthResponse)
async def health_check():
    logger.info("💓 Health check accessed")
    return HealthResponse(
        status="healthy",
        gemini_configured=bool(GEMINI_API_KEY),
        timestamp=datetime.now().isoformat(),
        version="2.0.0"
    )

@app.post("/extract-tags", response_model=TaskResponse)
async def extract_tags(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(..., description="PDF files to process"),
    gemini_model: str = Form(default="gemini-1.5-flash-latest", description="Gemini model to use"),
    pdf_conversion_dpi: int = Form(default=300, ge=72, le=600, description="DPI for PDF conversion (72-600)")
):
    """Extract tags from uploaded PDF files."""
    try:
        logger.info(f"📬 Received extract-tags request with {len(files)} files")
        
        if not GEMINI_API_KEY:
            logger.error("❌ Gemini API Key not configured")
            raise HTTPException(status_code=500, detail="Gemini API Key not configured")
        
        if not files:
            logger.error("❌ No PDF files uploaded")
            raise HTTPException(status_code=400, detail="No PDF files uploaded")
        
        # Validate file types
        for file in files:
            logger.info(f"📄 Validating file: {file.filename}")
            if not file.filename.lower().endswith('.pdf'):
                logger.error(f"❌ File {file.filename} is not a PDF")
                raise HTTPException(status_code=400, detail=f"File {file.filename} is not a PDF")
        
        # Generate task ID
        task_id = str(uuid.uuid4())
        logger.info(f"🆔 Generated task ID: {task_id}")
        
        # Initialize task status
        current_time = datetime.now().isoformat()
        task_storage[task_id] = ProcessingStatus(
            task_id=task_id,
            status="queued",
            progress="Task queued for processing",
            created_at=current_time,
            updated_at=current_time
        )
        
        # Start background processing
        background_tasks.add_task(
            process_pdfs_async,
            files,
            task_id,
            gemini_model,
            pdf_conversion_dpi
        )
        
        logger.info(f"✅ Task {task_id} queued successfully")
        
        return TaskResponse(
            task_id=task_id,
            message="Processing started",
            status="queued"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Unexpected error in extract_tags: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# Keep your other endpoints as they are but add logging
@app.get("/status/{task_id}", response_model=ProcessingStatus)
async def get_task_status(task_id: str):
    logger.info(f"📊 Status check for task: {task_id}")
    if task_id not in task_storage:
        logger.warning(f"⚠️ Task not found: {task_id}")
        raise HTTPException(status_code=404, detail="Task not found")
    return task_storage[task_id]

if __name__ == "__main__":
    import uvicorn
    logger.info("🚀 Starting server directly")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")