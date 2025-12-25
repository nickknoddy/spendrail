"""Image processing utilities for file validation and manipulation."""

import io
from pathlib import Path

import aiofiles
from fastapi import UploadFile
from PIL import Image

from app.config import get_settings
from app.core.exceptions import FileTooLargeError, UnsupportedFileTypeError
from app.logging_config import get_logger

logger = get_logger(__name__)


class ImageProcessor:
    """Service for processing and validating uploaded images."""

    def __init__(self) -> None:
        """Initialize image processor with settings."""
        self.settings = get_settings()

    def get_file_extension(self, filename: str) -> str:
        """Extract and normalize file extension."""
        return Path(filename).suffix.lower().lstrip(".")

    def validate_file_type(self, filename: str) -> str:
        """
        Validate that the file type is allowed.

        Args:
            filename: Original filename

        Returns:
            Normalized file extension

        Raises:
            UnsupportedFileTypeError: If file type is not allowed
        """
        extension = self.get_file_extension(filename)

        if extension not in self.settings.allowed_extensions_list:
            raise UnsupportedFileTypeError(
                file_type=extension,
                allowed_types=self.settings.allowed_extensions_list,
            )

        return extension

    async def validate_file_size(self, file: UploadFile) -> int:
        """
        Validate that the file size is within limits.

        Args:
            file: Uploaded file object

        Returns:
            File size in bytes

        Raises:
            FileTooLargeError: If file exceeds maximum size
        """
        # Read file content to check size
        content = await file.read()
        size_bytes = len(content)
        size_mb = size_bytes / (1024 * 1024)

        # Reset file pointer for later reading
        await file.seek(0)

        if size_bytes > self.settings.max_file_size_bytes:
            raise FileTooLargeError(
                max_size_mb=self.settings.max_file_size_mb,
                actual_size_mb=size_mb,
            )

        logger.debug(
            "file_size_validated",
            filename=file.filename,
            size_bytes=size_bytes,
            size_mb=round(size_mb, 2),
        )

        return size_bytes

    async def read_image(self, file: UploadFile) -> Image.Image:
        """
        Read an uploaded file as a PIL Image.

        Args:
            file: Uploaded file object

        Returns:
            PIL Image object
        """
        content = await file.read()
        await file.seek(0)

        image = Image.open(io.BytesIO(content))

        # Convert to RGB if necessary (handles RGBA, P mode, etc.)
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")

        logger.debug(
            "image_loaded",
            filename=file.filename,
            size=image.size,
            mode=image.mode,
        )

        return image

    async def save_image(
        self,
        file: UploadFile,
        filename: str | None = None,
    ) -> Path:
        """
        Save uploaded image to the upload directory.

        Args:
            file: Uploaded file object
            filename: Optional custom filename (defaults to original)

        Returns:
            Path to saved file
        """
        # Ensure upload directory exists
        upload_dir = self.settings.upload_path
        upload_dir.mkdir(parents=True, exist_ok=True)

        # Use original filename or provided one
        save_name = filename or file.filename or "image"
        save_path = upload_dir / save_name

        # Read and save content
        content = await file.read()
        await file.seek(0)

        async with aiofiles.open(save_path, "wb") as f:
            await f.write(content)

        logger.info(
            "image_saved",
            filename=save_name,
            path=str(save_path),
            size_bytes=len(content),
        )

        return save_path

    async def process_upload(self, file: UploadFile) -> tuple[Image.Image, str, int]:
        """
        Validate and process an uploaded image file.

        Args:
            file: Uploaded file object

        Returns:
            Tuple of (PIL Image, filename, file size in bytes)

        Raises:
            UnsupportedFileTypeError: If file type is not allowed
            FileTooLargeError: If file exceeds maximum size
        """
        filename = file.filename or "unknown"

        # Validate file type
        self.validate_file_type(filename)

        # Validate file size
        file_size = await self.validate_file_size(file)

        # Read as PIL Image
        image = await self.read_image(file)

        logger.info(
            "upload_processed",
            filename=filename,
            size_bytes=file_size,
            image_size=image.size,
        )

        return image, filename, file_size


# Singleton instance
_image_processor: ImageProcessor | None = None


def get_image_processor() -> ImageProcessor:
    """Get or create ImageProcessor singleton."""
    global _image_processor
    if _image_processor is None:
        _image_processor = ImageProcessor()
    return _image_processor
