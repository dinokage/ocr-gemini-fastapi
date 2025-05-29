# PDF Tag Extraction Service

A FastAPI-based service that extracts component and pipeline tags from engineering diagrams (P&IDs) using Google's Gemini AI. Upload PDF files directly and get intelligently categorized tags with detailed analysis.

## 🚀 Features

- **Direct File Upload**: No base64 encoding needed - just upload PDF files directly
- **Intelligent Tag Recognition**: Extracts both component tags (P-101A, BV-001) and pipeline tags (13-M2-0041-1.5"-OD-91440X)
- **Smart Categorization**: Automatically categorizes tags by type (pumps, valves, instruments, etc.)
- **Asynchronous Processing**: Handle multiple large PDFs efficiently with background processing
- **Real-time Progress Tracking**: Monitor processing status with detailed progress updates
- **Dual Processing Modes**: Quick sync processing for single files, async for multiple files
- **PDF Validation**: Validate PDFs before processing to catch issues early
- **RESTful API**: Clean, well-documented API endpoints
- **Docker Support**: Easy deployment with Docker and Docker Compose

## 📋 Prerequisites

- Python 3.8+
- Google Gemini API Key ([Get one here](https://makersuite.google.com/app/apikey))

## 🛠️ Installation & Setup

### Option 1: Quick Setup (Recommended)

1. **Clone and navigate to the project:**
   ```bash
   git clone https://github.com/dinokage/ocr-gemini-fastapi
   cd ocr-gemini-fastapi
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the setup script:**
   ```bash
   python setup_env.py
   ```
   This interactive script will:
   - Guide you through API key setup
   - Create the `.env` file
   - Test your configuration
   - Verify Gemini API connection

4. **Start the server:**
   ```bash
   python main.py
   # or
   uvicorn main:app --reload
   ```

### Option 2: Manual Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Create `.env` file:**
   ```bash
   echo "GEMINI_API_KEY=your_actual_api_key_here" > .env
   ```

3. **Start the server:**
   ```bash
   python main.py
   ```

### Option 3: Docker Setup

1. **Using Docker Compose (Recommended):**
   ```bash
   # Create .env file first
   echo "GEMINI_API_KEY=your_actual_api_key_here" > .env
   
   # Start with Docker Compose
   docker-compose up --build
   ```

2. **Using Docker directly:**
   ```bash
   docker build -t pdf-extractor .
   docker run -p 8000:8000 -e GEMINI_API_KEY=your_key pdf-extractor
   ```

## 🔧 Troubleshooting Setup

If you encounter API key issues:

1. **Run the debug script:**
   ```bash
   python debug_env.py
   ```

2. **Common fixes:**
   - Ensure `.env` file is in the same directory as `main.py`
   - No spaces around the `=` sign in `.env` file
   - API key should start with `AIza` and be 39 characters long
   - Install `python-dotenv`: `pip install python-dotenv`

## 🌐 API Usage

### Service Health Check
```bash
curl http://localhost:8000/health
```

### Process Multiple PDFs (Async)
```bash
curl -X POST "http://localhost:8000/extract-tags" \
  -F "files=@diagram1.pdf" \
  -F "files=@diagram2.pdf" \
  -F "gemini_model=gemini-1.5-flash-latest" \
  -F "pdf_conversion_dpi=300"
```

### Quick Single PDF Test (Sync)
```bash
curl -X POST "http://localhost:8000/test-single-pdf" \
  -F "file=@diagram.pdf" \
  -F "pdf_conversion_dpi=300"
```

### Validate PDF Before Processing
```bash
curl -X POST "http://localhost:8000/validate-pdf" \
  -F "file=@diagram.pdf"
```

## 🐍 Python Client Usage

```python
from example_client import PDFTagExtractorClient

# Initialize client
client = PDFTagExtractorClient("http://localhost:8000")

# Check service health
health = client.health_check()
print(f"Service ready: {health['gemini_configured']}")

# Quick single file processing
results = client.extract_tags_sync("diagram.pdf")
print(f"Found {results['total_unique_tags']} unique tags")

# Multiple files with progress tracking
task_id = client.extract_tags_async(["diagram1.pdf", "diagram2.pdf"])
results = client.wait_for_completion(task_id)

# Display results summary
from example_client import print_results_summary
print_results_summary(results)
```

## 📮 Postman Testing

1. **Import Collection:** Use the provided collection JSON in the Postman guide
2. **Set Environment:** `base_url = http://localhost:8000`
3. **Upload Files:** Use form-data with `files` field set to File type
4. **Monitor Progress:** Use the status and result endpoints

See the [detailed Postman guide](postman_guide.md) for step-by-step instructions.

## 📊 API Endpoints

| Endpoint | Method | Purpose | Response Type |
|----------|--------|---------|---------------|
| `/` | GET | Service information | JSON |
| `/health` | GET | Service health check | JSON |
| `/extract-tags` | POST | Process multiple PDFs (async) | Task ID |
| `/test-single-pdf` | POST | Process single PDF (sync) | Results |
| `/validate-pdf` | POST | Validate PDF file | Validation info |
| `/status/{task_id}` | GET | Check processing status | Status info |
| `/result/{task_id}` | GET | Get extraction results | Results |
| `/tasks` | GET | List all tasks | Task list |
| `/task/{task_id}` | DELETE | Delete task | Confirmation |

## 📋 Request Parameters

### Extract Tags Parameters
- `files`: PDF files to process (multipart/form-data)
- `gemini_model`: Gemini model to use (default: "gemini-1.5-flash-latest")
- `pdf_conversion_dpi`: DPI for PDF conversion (72-600, default: 300)

### File Constraints
- **File Types**: PDF only (`.pdf` extension required)
- **File Size**: Maximum 50MB per file
- **Processing**: Multiple files supported in single request

## 🏷️ Supported Tag Types

### Component Tags
The service recognizes and categorizes various component types:

- **Pumps**: `P-101A`, `P-200B`
- **Valves**: 
  - Ball Valves: `BV-001`, `BV-002`
  - Gate Valves: `GV-003`, `GV-004`
  - Control Valves: `CV-005`, `XV-006`
  - Relief Valves: `PSV-007`, `PRV-008`
- **Instruments**:
  - Flow: `FIC-301`, `FT-302`, `FE-303`
  - Level: `LT-500`, `LIC-501`, `LG-502`
  - Pressure: `PT-600`, `PIC-601`, `PI-602`
  - Temperature: `TT-700`, `TIC-701`, `TE-702`
- **Equipment**: `TK-001` (tanks), `E-001` (exchangers), `C-001` (compressors)

### Pipeline Tags
Complex pipeline identifiers with structure:
`{line_number}-{service}-{sequence}-{specifications}`

**Examples:**
- `13-M2-0041-1.5"-OD-91440X`
- `01-P10A-0002-DN50-CS-L150`
- `100-HC-001-4"-SS316-INS01`

## 📈 Response Format

```json
{
  "total_unique_tags": 150,
  "tags_by_pdf": {
    "diagram1.pdf": ["P-101A", "BV-001", "FIC-301"],
    "diagram2.pdf": ["P-102B", "XV-002", "LT-500"]
  },
  "categorized_tags": {
    "pipeline_tags": ["13-M2-0041-1.5\"-OD-91440X"],
    "component_tags": {
      "Pumps": ["P-101A", "P-102B"],
      "Ball Valves": ["BV-001", "BV-002"],
      "Flow Indicating Controllers": ["FIC-301"]
    },
    "uncategorized_other": ["MISC-001"]
  },
  "tag_frequency": {
    "P-101A": 3,
    "BV-001": 2,
    "FIC-301": 1
  },
  "processing_time": 45.67,
  "total_pages_processed": 12
}
```

## ⚙️ Configuration Options

### Environment Variables
```bash
GEMINI_API_KEY=your_gemini_api_key          # Required
LOG_LEVEL=INFO                              # Optional
MAX_FILE_SIZE=50MB                          # Optional
MAX_CONCURRENT_TASKS=5                      # Optional
```

### Processing Settings
- **DPI Range**: 72-600 (higher = better quality, slower processing)
- **Recommended DPI**: 300 for balance of quality and speed
- **Model Options**: `gemini-1.5-flash-latest`, `gemini-1.5-flash-8b`

## 🚀 Performance Optimization

### Processing Speed Tips
1. **Use appropriate DPI**: 150-200 for draft, 300 for production, 400+ for high quality
2. **File size matters**: Smaller files process faster
3. **Page count**: More pages = longer processing time
4. **Batch wisely**: Process multiple smaller files rather than one large file

### Expected Processing Times
- **1-5 pages**: 30-60 seconds
- **6-15 pages**: 1-3 minutes  
- **16+ pages**: 3+ minutes

*Times vary based on diagram complexity and server resources.*

## 🏭 Production Deployment

### Docker Production Setup
```yaml
# docker-compose.prod.yml
version: '3.8'
services:
  pdf-extractor:
    build: .
    ports:
      - "8000:8000"
    environment:
      - GEMINI_API_KEY=${GEMINI_API_KEY}
      - REDIS_URL=redis://redis:6379
    depends_on:
      - redis
    restart: always
    
  redis:
    image: redis:7-alpine
    restart: always
    
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
    depends_on:
      - pdf-extractor
```

### Production Recommendations
1. **Use Redis**: Replace in-memory task storage with Redis
2. **Add Authentication**: Implement API key authentication
3. **Load Balancer**: Use nginx for load balancing
4. **Monitoring**: Add logging and health monitoring
5. **File Storage**: Use cloud storage for temporary files
6. **Rate Limiting**: Implement request rate limiting
7. **SSL/HTTPS**: Use SSL certificates for secure communication

## 🔍 Monitoring & Debugging

### Health Monitoring
```bash
# Check service health
curl http://localhost:8000/health

# List all active tasks
curl http://localhost:8000/tasks
```

### Debugging Tools
```bash
# Debug environment setup
python debug_env.py

# Test single PDF processing
curl -X POST "http://localhost:8000/test-single-pdf" -F "file=@test.pdf"
```

### Common Issues & Solutions

| Issue | Symptom | Solution |
|-------|---------|----------|
| API Key Not Found | "GEMINI_API_KEY not found" error | Run `python setup_env.py` |
| PDF Not Processing | Task stays in "queued" status | Check PDF validity with `/validate-pdf` |
| Slow Processing | Long processing times | Reduce DPI or split large PDFs |
| Memory Issues | Server crashes | Reduce concurrent tasks, increase server memory |
| Poor Tag Recognition | Missing tags in results | Increase DPI, ensure PDF has clear text |

## 🔒 Security Considerations

- **API Key Protection**: Never commit API keys to version control
- **File Upload Limits**: 50MB max file size to prevent abuse
- **Input Validation**: All files validated before processing
- **Temporary File Cleanup**: Automatic cleanup of uploaded files
- **Rate Limiting**: Consider implementing rate limiting in production

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes and add tests
4. Commit changes: `git commit -am 'Add new feature'`
5. Push to branch: `git push origin feature-name`
6. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support & Help

### Getting Help
- **Setup Issues**: Run `python debug_env.py` for detailed diagnostics
- **API Questions**: Check the interactive docs at `http://localhost:8000/docs`
- **Performance Issues**: See the Performance Optimization section above

### Resources
- [Gemini API Documentation](https://ai.google.dev/docs)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Postman Testing Guide](postman_guide.md)

### Reporting Issues
When reporting issues, please include:
1. Python version and OS
2. Output of `python debug_env.py`
3. Server startup logs
4. Steps to reproduce the issue

---

## 📚 Quick Start Checklist

- [ ] Clone the repository
- [ ] Install dependencies: `pip install -r requirements.txt`
- [ ] Get Gemini API key from [Google AI Studio](https://makersuite.google.com/app/apikey)
- [ ] Run setup script: `python setup_env.py`
- [ ] Start server: `python main.py`
- [ ] Test health: `curl http://localhost:8000/health`
- [ ] Upload a test PDF using Postman or Python client
- [ ] Review the extracted tags and categories

**Ready to extract tags from your engineering diagrams! 🎉**