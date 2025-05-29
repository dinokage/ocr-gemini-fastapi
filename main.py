from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Form
# from fastapi.responses import JSONResponse
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
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

# Load environment variables from .env file
load_dotenv()

app = FastAPI(
    title="PDF Tag Extraction Service", 
    version="2.0.0",
    description="Extract component and pipeline tags from engineering diagrams using Gemini AI"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware, 
    allowed_hosts=["*"]  # Configure this properly for production
)

# Configuration with detailed debugging
print("🔧 Loading configuration...")
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

if GEMINI_API_KEY:
    print(f"✅ GEMINI_API_KEY found (length: {len(GEMINI_API_KEY)} characters)")
    print(f"✅ API Key starts with: {GEMINI_API_KEY[:10]}...")
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        print("✅ Gemini API configured successfully")
    except Exception as e:
        print(f"❌ Failed to configure Gemini API: {e}")
        GEMINI_API_KEY = None
else:
    print("❌ GEMINI_API_KEY not found in environment variables")
    print("🔍 Debugging environment variables:")
    print(f"   Current working directory: {os.getcwd()}")
    print(f"   .env file exists: {os.path.exists('.env')}")
    if os.path.exists('.env'):
        print("   .env file contents:")
        try:
            with open('.env', 'r') as f:
                content = f.read()
                # Don't print the actual key, just show the structure
                lines = content.strip().split('\n')
                for line in lines:
                    if '=' in line:
                        key = line.split('=')[0]
                        print(f"     {key}=***")
                    else:
                        print(f"     {line}")
        except Exception as e:
            print(f"   Error reading .env file: {e}")
    else:
        print("   Available environment variables containing 'GEMINI':")
        gemini_vars = {k: v for k, v in os.environ.items() if 'GEMINI' in k.upper()}
        if gemini_vars:
            for key in gemini_vars:
                print(f"     {key}=***")
        else:
            print("     None found")

# Response Models
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
    status: str  # "queued", "processing", "completed", "failed"
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

# In-memory storage for task status (use Redis in production)
task_storage: Dict[str, ProcessingStatus] = {}

# Helper Functions
async def save_upload_file(upload_file: UploadFile) -> str:
    """Save uploaded file to temporary location and return path"""
    try:
        # Create temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf", prefix=f"{upload_file.filename}_")
        
        # Read and write file content
        content = await upload_file.read()
        temp_file.write(content)
        temp_file.close()
        
        return temp_file.name
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to save uploaded file {upload_file.filename}: {str(e)}")

def pdf_to_images(pdf_path: str, dpi: int = 200) -> List[Image.Image]:
    """Converts PDF pages to a list of PIL Images."""
    images = []
    try:
        doc = fitz.open(pdf_path)
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            pix = page.get_pixmap(dpi=dpi)
            img_data = pix.tobytes("png")
            image = Image.open(io.BytesIO(img_data))
            images.append(image)
        doc.close()
    except Exception as e:
        print(f"Error converting PDF {pdf_path} to images: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to convert PDF to images: {str(e)}")
    return images

def extract_tags_from_image_gemini(image_pil: Image.Image, model_name: str = "gemini-1.5-flash-8b") -> List[str]:
    """
    Sends an image to Gemini and asks it to extract component and pipeline tags.
    Returns a list of extracted tags.
    """
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="Gemini API Key not configured")

    model = genai.GenerativeModel(model_name)

    img_byte_arr = io.BytesIO()
    image_pil.save(img_byte_arr, format='PNG')
    img_bytes = img_byte_arr.getvalue()

    prompt = """
    You are an expert in reading engineering P&ID (Piping and Instrumentation Diagrams),
    electrical diagrams, or general plant layout drawings.
    Your task is to identify and extract ALL component tags AND pipeline tags from the provided image.

    Component tags are typically alphanumeric identifiers for equipment or instruments.
    Examples: 'P-101A', 'XV-002', 'TK-5003.B', 'FIC-301', 'LT-500', 'BV-0007', 'NRV-0003', '20-V-010'.
    These often start with 2-4 letters (or a number-letter combination like 20-V), followed by a hyphen and numbers/letters.

    Pipeline tags (also known as line numbers) identify specific pipelines. They have a more complex structure.
    Examples: '13-M2-0041-1.5"-OD-91440X', '01-P10A-0002-DN50-CS-L150', '100-HC-001-4"-SS316-INS01', '1-GAS-LINE-001-SPEC'.
    These often start with numbers, include segments for area/service, sequence number,
    and often include size (e.g., 1.5", DN50, 4"), material codes, and other specifiers, all typically separated by hyphens.

    Tags can be oriented horizontally or vertically. They are usually placed near
    their respective components or along pipelines on the drawing. Distinguish them from other text like
    dimensions, notes, or titles unless those clearly follow a component or pipeline tag format.

    Pay close attention to:
    1.  Both horizontal and vertical text orientations.
    2.  Tags that might be slightly rotated or curved along a pipeline.
    3.  Tags that are tightly grouped with other tags or text.
    4.  Ensure you capture the full tag, including all prefixes, suffixes, separators (hyphens, dots, quotes for inches).

    Please return ALL extracted tags (both component and pipeline) as a single JSON list of strings.
    For example: ["P-101A", "13-M2-0041-1.5\\"-OD-91440X", "BV-0007", "NRV-0003", "20-V-010"]
    If no tags are found, return an empty list: [].
    """

    try:
        response = model.generate_content([prompt, {"mime_type": "image/png", "data": img_bytes}])
        if response.parts:
            content = response.text.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            try:
                tags = json.loads(content)
                if isinstance(tags, list) and all(isinstance(tag, str) for tag in tags):
                    return list(set(tags))  # Return unique tags
                else:
                    print(f"Warning: Gemini returned a JSON that is not a list of strings: {content}")
                    potential_tags = re.findall(r'[A-Za-z0-9\-\.\'\"\/]{3,45}', response.text)
                    return list(set(potential_tags))
            except json.JSONDecodeError:
                print(f"Error: Gemini response was not valid JSON: {response.text}")
                potential_tags = re.findall(r'[A-Za-z0-9\-\.\'\"\/]{3,45}', response.text)
                return list(set(potential_tags))
        else:
            print("Warning: Gemini returned an empty response or no text part.")
            return []
    except Exception as e:
        print(f"Error during Gemini API call: {e}")
        return []

def enhanced_categorize_tags(tags: List[str]) -> Dict:
    """
    Performs enhanced categorization for component and pipeline tags.
    """
    categories = {
        "pipeline_tags": [],
        "component_tags": defaultdict(list),
        "uncategorized_other": []
    }

    # Pipeline regex pattern
    pipeline_regex = re.compile(
        r"^\d+[\w\-]*" +  # Line number prefix
        r"-[\w\.\-]+" +    # Service/Area code
        r"-\d+[\w\-]*" +   # Sequence number
        r"(?:" +
            r"(?:-[\d\.]+\"(?:[A-Z\-\d]*)?|-DN\d+|-[\d\.]+MM|-[\d\.]+INCH?)" +
            r"(?:-[\w\-]+)*" +
        r"|" +
            r"(?:-[\w\-]+){1,}" +
        r")$",
        re.IGNORECASE
    )

    # Component prefix mapping
    component_prefix_map = {
        "P": "Pumps",
        "BV": "Ball Valves",
        "GV": "Gate Valves",
        "CV": "Control Valves",
        "NRV": "Non-Return Valves (Check Valves)",
        "RV": "Relief Valves (General)",
        "PSV": "Pressure Safety Valves",
        "PRV": "Pressure Relief Valves",
        "V": "Valves (Generic/Unspecified)",
        "XV": "Valves (On/Off / Solenoid)",
        "HV": "Valves (Hand Operated)",
        "FV": "Flow Control Valves",
        "LV": "Level Control Valves",
        "PV": "Pressure Control Valves",
        "TV": "Temperature Control Valves",
        "MOV": "Motor Operated Valves",
        "T": "Tanks/Vessels (General)",
        "TK": "Tanks/Vessels",
        "VSL": "Vessels",
        "E": "Heat Exchangers",
        "C": "Compressors/Columns",
        "COL": "Columns",
        "R": "Reactors",
        "MIX": "Mixers",
        "AG": "Agitators",
        "F": "Flow Instruments (General)",
        "FI": "Flow Indicators",
        "FT": "Flow Transmitters",
        "FE": "Flow Elements",
        "FIC": "Flow Indicating Controllers",
        "FC": "Flow Controllers",
        "L": "Level Instruments (General)",
        "LI": "Level Indicators",
        "LT": "Level Transmitters",
        "LG": "Level Gauges",
        "LIC": "Level Indicating Controllers",
        "LC": "Level Controllers",
        "PI": "Pressure Instruments (General)",
        "PT": "Pressure Transmitters",
        "PIC": "Pressure Indicating Controllers",
        "PC": "Pressure Controllers",
        "TI": "Temperature Instruments (General)",
        "TT": "Temperature Transmitters",
        "TE": "Temperature Elements",
        "TIC": "Temperature Indicating Controllers",
        "TC": "Temperature Controllers",
        "A": "Analyzers (General)",
        "AI": "Analyzer Indicators",
        "AT": "Analyzer Transmitters",
        "AE": "Analyzer Elements",
        "H": "Heaters/Furnaces",
        "HTR": "Heaters",
        "MTR": "Motors",
        "INST": "General Instruments (Fallback)",
    }

    for tag in sorted(list(set(tags))):
        is_pipeline = False
        if pipeline_regex.match(tag):
            categories["pipeline_tags"].append(tag)
            is_pipeline = True

        if not is_pipeline:
            categorized_as_component = False
            # Try to match longer prefixes first
            match_comp = re.match(r"([A-Z0-9]+(?:-[A-Z])?|[A-Z]{2,4})[\-0-9]", tag, re.IGNORECASE)
            if match_comp:
                prefix = match_comp.group(1).upper()
                if prefix in component_prefix_map:
                    categories["component_tags"][component_prefix_map[prefix]].append(tag)
                    categorized_as_component = True

            # Fallback to single letter prefix
            if not categorized_as_component:
                match_single_comp = re.match(r"([A-Z])[\-0-9]", tag, re.IGNORECASE)
                if match_single_comp:
                    prefix = match_single_comp.group(1).upper()
                    if prefix in component_prefix_map:
                        categories["component_tags"][component_prefix_map[prefix]].append(tag)
                        categorized_as_component = True

            if not categorized_as_component:
                categories["uncategorized_other"].append(tag)

    # Sort tags within each category
    categories["pipeline_tags"].sort()
    for comp_cat_key in categories["component_tags"]:
        categories["component_tags"][comp_cat_key].sort()
    categories["uncategorized_other"].sort()

    return categories

async def process_pdfs_async(
    files: List[UploadFile],
    task_id: str,
    gemini_model: str = "gemini-1.5-flash-latest",
    pdf_conversion_dpi: int = 300
):
    """Async function to process PDFs in the background"""
    start_time = datetime.now()
    temp_files = []  # Track temporary files for cleanup
    
    try:
        # Update task status
        task_storage[task_id].status = "processing"
        task_storage[task_id].progress = "Starting PDF processing..."
        task_storage[task_id].updated_at = datetime.now().isoformat()
        
        all_extracted_tags_master_list = []
        tags_by_pdf = {}
        total_pages_processed = 0
        
        for file_idx, file in enumerate(files):
            task_storage[task_id].progress = f"Processing file {file_idx + 1}/{len(files)}: {file.filename}"
            task_storage[task_id].updated_at = datetime.now().isoformat()
            
            # Save uploaded file to temporary location
            temp_file_path = await save_upload_file(file)
            temp_files.append(temp_file_path)
            
            try:
                # Convert PDF to images
                images_from_pdf = pdf_to_images(temp_file_path, dpi=pdf_conversion_dpi)
                total_pages_processed += len(images_from_pdf)
                
                if not images_from_pdf:
                    continue
                
                pdf_tags_current_file = []
                for i, img in enumerate(images_from_pdf):
                    task_storage[task_id].progress = f"Processing {file.filename} - Page {i+1}/{len(images_from_pdf)}"
                    task_storage[task_id].updated_at = datetime.now().isoformat()
                    
                    tags_on_page = extract_tags_from_image_gemini(img, model_name=gemini_model)
                    if tags_on_page:
                        pdf_tags_current_file.extend(tags_on_page)
                
                # Store tags for this PDF
                unique_tags_this_pdf = sorted(list(set(pdf_tags_current_file)))
                tags_by_pdf[file.filename] = unique_tags_this_pdf
                all_extracted_tags_master_list.extend(pdf_tags_current_file)
                
            except Exception as e:
                print(f"Error processing {file.filename}: {e}")
                # Continue with other files even if one fails
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
        
    except Exception as e:
        task_storage[task_id].status = "failed"
        task_storage[task_id].error = str(e)
        task_storage[task_id].progress = f"Processing failed: {str(e)}"
        task_storage[task_id].updated_at = datetime.now().isoformat()
    
    finally:
        # Clean up temporary files
        for temp_file in temp_files:
            try:
                os.unlink(temp_file)
            except:
                pass

# API Endpoints
@app.get("/", response_model=Dict[str, str])
async def root():
    return {
        "message": "PDF Tag Extraction Service", 
        "status": "active",
        "version": "2.0.0",
        "docs": "/docs"
    }

@app.get("/health", response_model=HealthResponse)
async def health_check():
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
    """
    Extract tags from uploaded PDF files.
    Returns a task ID for tracking progress.
    """
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="Gemini API Key not configured")
    
    if not files:
        raise HTTPException(status_code=400, detail="No PDF files uploaded")
    
    # Validate file types
    for file in files:
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail=f"File {file.filename} is not a PDF")
        
        # Check file size (optional - adjust as needed)
        if hasattr(file, 'size') and file.size and file.size > 50 * 1024 * 1024:  # 50MB limit
            raise HTTPException(status_code=400, detail=f"File {file.filename} is too large (max 50MB)")
    
    # Generate task ID
    task_id = str(uuid.uuid4())
    
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
    
    return TaskResponse(
        task_id=task_id,
        message="Processing started",
        status="queued"
    )

@app.get("/status/{task_id}", response_model=ProcessingStatus)
async def get_task_status(task_id: str):
    """Get the status of a tag extraction task"""
    if task_id not in task_storage:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return task_storage[task_id]

@app.get("/result/{task_id}", response_model=ExtractionResult)
async def get_extraction_result(task_id: str):
    """Get the result of a completed tag extraction task"""
    if task_id not in task_storage:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = task_storage[task_id]
    
    if task.status == "processing" or task.status == "queued":
        raise HTTPException(status_code=202, detail="Task still processing")
    elif task.status == "failed":
        raise HTTPException(status_code=500, detail=f"Task failed: {task.error}")
    elif task.status == "completed" and task.result:
        return task.result
    else:
        raise HTTPException(status_code=500, detail="Unknown task state")

@app.delete("/task/{task_id}")
async def delete_task(task_id: str):
    """Delete a task and its results from memory"""
    if task_id not in task_storage:
        raise HTTPException(status_code=404, detail="Task not found")
    
    del task_storage[task_id]
    return {"message": "Task deleted successfully", "task_id": task_id}

@app.get("/tasks")
async def list_tasks():
    """List all tasks and their statuses"""
    return {
        "tasks": [
            {
                "task_id": task_id,
                "status": task.status,
                "progress": task.progress,
                "created_at": task.created_at,
                "updated_at": task.updated_at
            }
            for task_id, task in task_storage.items()
        ],
        "total_tasks": len(task_storage)
    }

@app.post("/validate-pdf", response_model=PDFValidationResponse)
async def validate_pdf(file: UploadFile = File(..., description="PDF file to validate")):
    """Validate that the uploaded file is a valid PDF"""
    if not file.filename.lower().endswith('.pdf'):
        return PDFValidationResponse(
            valid=False,
            filename=file.filename,
            error="File is not a PDF",
            message="File validation failed - not a PDF file"
        )
    
    try:
        # Save file temporarily
        temp_file_path = await save_upload_file(file)
        
        try:
            # Try to open with PyMuPDF to validate
            doc = fitz.open(temp_file_path)
            page_count = len(doc)
            doc.close()
            
            # Get file size
            file_size_mb = os.path.getsize(temp_file_path) / (1024 * 1024)
            
            return PDFValidationResponse(
                valid=True,
                filename=file.filename,
                page_count=page_count,
                file_size_mb=round(file_size_mb, 2),
                message="PDF is valid and can be processed"
            )
        finally:
            # Clean up temporary file
            os.unlink(temp_file_path)
            
    except Exception as e:
        return PDFValidationResponse(
            valid=False,
            filename=file.filename,
            error=str(e),
            message="PDF validation failed"
        )

# Additional utility endpoint for testing
@app.post("/test-single-pdf", response_model=ExtractionResult)
async def test_single_pdf(
    file: UploadFile = File(..., description="Single PDF file to test"),
    gemini_model: str = Form(default="gemini-1.5-flash-latest"),
    pdf_conversion_dpi: int = Form(default=300, ge=72, le=600)
):
    """
    Process a single PDF synchronously for quick testing.
    Note: This endpoint blocks until processing is complete.
    """
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="Gemini API Key not configured")
    
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail=f"File {file.filename} is not a PDF")
    
    start_time = datetime.now()
    temp_file_path = None
    
    try:
        # Save uploaded file
        temp_file_path = await save_upload_file(file)
        
        # Convert PDF to images
        images_from_pdf = pdf_to_images(temp_file_path, dpi=pdf_conversion_dpi)
        
        if not images_from_pdf:
            raise HTTPException(status_code=400, detail="Could not extract any pages from PDF")
        
        # Extract tags from all pages
        all_tags = []
        for img in images_from_pdf:
            tags_on_page = extract_tags_from_image_gemini(img, model_name=gemini_model)
            if tags_on_page:
                all_tags.extend(tags_on_page)
        
        # Process results
        unique_tags = sorted(list(set(all_tags)))
        categorized_tags = enhanced_categorize_tags(unique_tags)
        tag_frequency = dict(Counter(all_tags).most_common())
        
        processing_time = (datetime.now() - start_time).total_seconds()
        
        return ExtractionResult(
            total_unique_tags=len(unique_tags),
            tags_by_pdf={file.filename: unique_tags},
            categorized_tags=TagCategories(
                pipeline_tags=categorized_tags["pipeline_tags"],
                component_tags=dict(categorized_tags["component_tags"]),
                uncategorized_other=categorized_tags["uncategorized_other"]
            ),
            tag_frequency=tag_frequency,
            processing_time=processing_time,
            total_pages_processed=len(images_from_pdf)
        )
        
    finally:
        # Clean up temporary file
        if temp_file_path:
            try:
                os.unlink(temp_file_path)
            except:
                pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)