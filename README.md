# Spend-Rail: Image Categorization API

A production-ready FastAPI application that uses Google's Gemini AI to automatically categorize uploaded images.

## Features

- 🖼️ **Image Categorization** - Upload images and get intelligent categorization using Gemini AI
- ⚡ **Async Processing** - Background task processing for non-blocking uploads
- 🔒 **Production Ready** - CORS, request logging, error handling, request ID tracking
- 📊 **Structured Logging** - JSON logging for production, colorful console output for development
- 🏥 **Health Checks** - Built-in health and readiness endpoints

## Quick Start

### Prerequisites

- Python 3.12+
- [UV](https://docs.astral.sh/uv/) package manager
- [Gemini API Key](https://aistudio.google.com/app/apikey) from Google AI Studio

### Installation

```bash
# Clone and enter the project directory
cd spend-rail

# Install dependencies with UV
uv sync

# Copy environment template and configure
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY
```

### Configuration

Edit `.env` file:

```env
# Required: Your Gemini API key
GEMINI_API_KEY=your-api-key-here

# Optional: Customize these settings
UPLOAD_DIR=uploads
MAX_FILE_SIZE_MB=10
LOG_LEVEL=INFO
```

### Running the Server

```bash
# Development mode (with hot reload)
uv run uvicorn src.app.main:app --reload

# Or with explicit host/port
uv run uvicorn src.app.main:app --host 0.0.0.0 --port 8000 --reload
```

## API Endpoints

### Health Checks

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Basic health check |
| `/health/ready` | GET | Readiness check (includes Gemini API status) |

### Image Categorization

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/images/categorize` | POST | Synchronous image categorization |
| `/api/v1/images/categorize/async` | POST | Async categorization (returns task ID) |
| `/api/v1/images/task/{task_id}` | GET | Check async task status |

## Usage Examples

### Categorize an Image (Synchronous)

```bash
curl -X POST \
  http://localhost:8000/api/v1/images/categorize \
  -F "file=@receipt.jpg"
```

Response:
```json
{
  "success": true,
  "filename": "receipt.jpg",
  "categories": [
    {"name": "receipt", "confidence": 0.95, "description": "A printed receipt from a store"},
    {"name": "document", "confidence": 0.7, "description": "Contains text and numbers"}
  ],
  "primary_category": "receipt",
  "raw_analysis": "Store receipt showing purchase details",
  "processed_at": "2024-12-25T11:30:00"
}
```

### Categorize an Image (Async)

```bash
# Submit for processing
curl -X POST \
  http://localhost:8000/api/v1/images/categorize/async \
  -F "file=@large_image.png"

# Response: {"task_id": "abc-123-...", "status": "pending", ...}

# Poll for results
curl http://localhost:8000/api/v1/images/task/abc-123-...
```

## API Documentation

Once running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

## Project Structure

```
spend-rail/
├── src/app/
│   ├── main.py              # FastAPI application
│   ├── config.py            # Settings management
│   ├── logging_config.py    # Structured logging
│   ├── api/                 # API endpoints
│   ├── core/                # Exceptions, utilities
│   ├── middleware/          # CORS, logging, error handling
│   ├── models/              # Pydantic schemas
│   ├── services/            # Gemini client, image processor
│   └── tasks/               # Background task management
├── uploads/                 # Uploaded images (gitignored)
├── pyproject.toml          # UV/Python dependencies
└── .env                    # Environment configuration
```

## Supported Image Formats

- JPEG/JPG
- PNG
- WebP
- HEIC/HEIF

Maximum file size: 10MB (configurable via `MAX_FILE_SIZE_MB`)

## License

MIT