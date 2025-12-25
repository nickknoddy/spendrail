"""Gemini API client service for image categorization."""

import base64
import io
import json
import time
from typing import Any

from google import genai
from google.genai import types
from PIL import Image

from app.config import get_settings
from app.core.exceptions import GeminiAPIError
from app.logging_config import get_logger
from app.models.schemas import BillDetails, BillItem, ImageCategory, ImageCategoryResponse

logger = get_logger(__name__)

# Default categorization prompt
CATEGORIZATION_PROMPT = """Analyze this image and categorize it. Provide your response as a JSON object with the following structure:

{
    "categories": [
        {
            "name": "category_name",
            "confidence": 0.95,
            "description": "Brief description of why this category applies"
        }
    ],
    "primary_category": "main_category_name",
    "bill_recognised": true,
    "bill_details": {
        "total_amount": 1234.56,
        "currency": "INR",
        "tax": 50.00,
        "vendor_name": "Store Name",
        "date": "2024-12-25",
        "items": [
            {
                "name": "Item description",
                "quantity": 2,
                "price": 100.00,
                "currency": "INR"
            }
        ]
    },
    "summary": "Brief summary of what the image contains"
}

IMPORTANT RULES:
1. bill_recognised must be a boolean (true/false), set to true if the image is a bill, receipt, invoice, or any document showing prices/transactions
2. If bill_recognised is true, you MUST include bill_details with at least total_amount
3. If bill_recognised is false, set bill_details to null
4. Extract ALL visible line items with their prices
5. Currency should be detected from the bill (INR, USD, EUR, etc.)
6. For quantity, use 1 if not explicitly shown

Categories should be specific. Only the following categories are allowed:
- food
- fuel
- medical

Provide at least 1 and up to 5 relevant categories, ordered by confidence (highest first).
Only respond with the JSON object, no additional text."""

# Allowed categories for category_matched check
ALLOWED_CATEGORIES = {"food", "fuel", "medical"}


class GeminiService:
    """Service for interacting with Google Gemini API."""

    def __init__(self) -> None:
        """Initialize Gemini service with API key."""
        self.settings = get_settings()
        self._client: genai.Client | None = None
        self._configure_client()

    def _configure_client(self) -> None:
        """Configure the Gemini API client."""
        if not self.settings.gemini_api_key:
            logger.warning("Gemini API key not configured")
            return

        self._client = genai.Client(api_key=self.settings.gemini_api_key)
        logger.info(
            "gemini_client_configured",
            model=self.settings.gemini_model,
        )

    def is_configured(self) -> bool:
        """Check if the Gemini client is properly configured."""
        return self._client is not None

    def _image_to_base64(self, image: Image.Image) -> str:
        """Convert PIL Image to base64 string."""
        buffer = io.BytesIO()
        # Save as PNG for consistent format
        image.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode("utf-8")
    
    def _image_to_bytes(self, image: Image.Image) -> bytes:
        """Convert PIL Image to bytes."""
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()

    async def categorize_image(
        self,
        image: Image.Image,
        filename: str,
        custom_prompt: str | None = None,
    ) -> ImageCategoryResponse:
        """
        Categorize an image using Gemini Vision API.

        Args:
            image: PIL Image object to analyze
            filename: Original filename for reference
            custom_prompt: Optional custom categorization prompt

        Returns:
            ImageCategoryResponse with categorization results

        Raises:
            GeminiAPIError: If the API call fails
        """
        if not self.is_configured():
            raise GeminiAPIError(
                "Gemini API is not configured. Please set GEMINI_API_KEY."
            )

        prompt = custom_prompt or CATEGORIZATION_PROMPT

        try:
            logger.info(
                "gemini_categorize_start",
                filename=filename,
                image_size=image.size,
                image_mode=image.mode,
            )

            # Convert image to bytes
            image_bytes = self._image_to_bytes(image)
            
            # Create image part using the new SDK
            image_part = types.Part.from_bytes(
                data=image_bytes,
                mime_type="image/png"
            )
            
            # Generate content with image - measure time
            api_start_time = time.perf_counter()
            
            response = self._client.models.generate_content(
                model=self.settings.gemini_model,
                contents=[prompt, image_part]
            )
            
            api_duration_ms = (time.perf_counter() - api_start_time) * 1000
            
            logger.info(
                "gemini_api_response",
                filename=filename,
                duration_ms=round(api_duration_ms, 2),
            )

            # Parse response
            raw_text = response.text.strip()

            # Clean up response if wrapped in markdown code block
            if raw_text.startswith("```"):
                raw_text = raw_text.split("\n", 1)[1]
                raw_text = raw_text.rsplit("```", 1)[0].strip()

            result = self._parse_response(raw_text, filename)

            logger.info(
                "gemini_categorize_success",
                filename=filename,
                primary_category=result.primary_category,
                category_matched=result.category_matched,
                num_categories=len(result.categories),
                api_duration_ms=round(api_duration_ms, 2),
            )

            return result

        except json.JSONDecodeError as e:
            logger.error(
                "gemini_parse_error",
                filename=filename,
                error=str(e),
                raw_response=raw_text[:500] if raw_text else None,
            )
            raise GeminiAPIError(
                f"Failed to parse Gemini response: {e}",
                details={"raw_response": raw_text[:500] if raw_text else None},
            ) from e

        except Exception as e:
            logger.exception(
                "gemini_categorize_error",
                filename=filename,
                error=str(e),
            )
            raise GeminiAPIError(
                f"Failed to categorize image: {e}",
                details={"error_type": type(e).__name__},
            ) from e

    def _parse_response(self, raw_text: str, filename: str) -> ImageCategoryResponse:
        """Parse the Gemini API response into structured format."""
        data: dict[str, Any] = json.loads(raw_text)

        # Confidence threshold (70%)
        CONFIDENCE_THRESHOLD = 0.7

        # Parse all categories first
        all_categories = [
            ImageCategory(
                name=cat.get("name", "unknown"),
                confidence=float(cat.get("confidence", 0.5)),
                description=cat.get("description", ""),
            )
            for cat in data.get("categories", [])
        ]

        # Filter to only include categories with confidence >= 70%
        high_confidence_categories = [
            cat for cat in all_categories if cat.confidence >= CONFIDENCE_THRESHOLD
        ]

        # Use high confidence categories if available, otherwise empty list
        categories = high_confidence_categories if high_confidence_categories else []

        # Parse bill_recognised - handle string "true"/"false" or boolean
        bill_recognised_raw = data.get("bill_recognised")
        if isinstance(bill_recognised_raw, bool):
            bill_recognised = bill_recognised_raw
        elif isinstance(bill_recognised_raw, str):
            bill_recognised = bill_recognised_raw.lower() == "true"
        else:
            bill_recognised = False

        # Parse bill_details - always return a BillDetails object
        bill_details = BillDetails()
        bill_details_raw = data.get("bill_details")
        if bill_details_raw and isinstance(bill_details_raw, dict):
            # Parse line items
            items = []
            for item in bill_details_raw.get("items", []):
                if isinstance(item, dict) and "price" in item:
                    # Convert quantity to int (Gemini may return float)
                    qty = item.get("quantity", 1)
                    items.append(BillItem(
                        name=item.get("name") or "Unknown item",
                        quantity=int(qty) if qty else 1,
                        price=float(item.get("price", 0)),
                        currency=item.get("currency") or "INR",
                    ))

            bill_details = BillDetails(
                total_amount=float(bill_details_raw["total_amount"]) if bill_details_raw.get("total_amount") else 0.0,
                currency=bill_details_raw.get("currency") or "INR",
                items=items,
                tax=float(bill_details_raw["tax"]) if bill_details_raw.get("tax") else 0.0,
                vendor_name=bill_details_raw.get("vendor_name") or "",
                date=bill_details_raw.get("date") or "",
            )

        # Check category_matched - only true if high confidence match exists
        category_matched = False
        primary_category = ""
        
        # Find the highest confidence category that matches allowed categories
        for cat in categories:
            if cat.name.lower() in ALLOWED_CATEGORIES:
                category_matched = True
                primary_category = cat.name
                break
        
        # If no match found in allowed categories, use the first high-confidence category
        if not primary_category and categories:
            primary_category = categories[0].name

        return ImageCategoryResponse(
            filename=filename,
            categories=categories,
            primary_category=primary_category,
            category_matched=category_matched,
            raw_analysis=data.get("summary", ""),
            bill_recognised=bill_recognised,
            bill_details=bill_details,
        )

    async def check_health(self) -> bool:
        """Check if Gemini API is accessible."""
        if not self.is_configured():
            return False

        try:
            # Simple health check with minimal token usage
            response = self._client.models.generate_content(
                model=self.settings.gemini_model,
                contents="Reply with 'ok'"
            )
            return "ok" in response.text.lower()
        except Exception as e:
            logger.warning("gemini_health_check_failed", error=str(e))
            return False


# Singleton instance
_gemini_service: GeminiService | None = None


def get_gemini_service() -> GeminiService:
    """Get or create Gemini service singleton."""
    global _gemini_service
    if _gemini_service is None:
        _gemini_service = GeminiService()
    return _gemini_service
