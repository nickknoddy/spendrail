"""Firebase Admin SDK service for Firestore operations."""

import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1 import AsyncClient

from app.config import get_settings
from app.logging_config import get_logger

logger = get_logger(__name__)


class FirebaseService:
    """Service for Firebase/Firestore operations."""

    def __init__(self) -> None:
        """Initialize Firebase Admin SDK."""
        self.settings = get_settings()
        self._db: AsyncClient | None = None
        self._initialized = False
        self._initialize()

    def _initialize(self) -> None:
        """Initialize Firebase Admin SDK with credentials."""
        try:
            # Check if already initialized
            if firebase_admin._apps:
                self._db = firestore.client()
                self._initialized = True
                logger.info("firebase_already_initialized")
                return

            # Try to load credentials from credentials.json file
            import os
            
            # Look for credentials.json in multiple locations
            possible_paths = [
                "/etc/secrets/credentials.json",  # Render.com secrets path
                "credentials.json",  # Current directory / app root
                "/app/credentials.json",  # Docker container path
                os.path.join(os.path.dirname(__file__), "..", "..", "..", "credentials.json"),
            ]
            
            cred = None
            for path in possible_paths:
                if os.path.exists(path):
                    cred = credentials.Certificate(path)
                    logger.info("firebase_credentials_loaded", path=path)
                    break
            
            # Fallback to application default credentials
            if cred is None:
                cred = credentials.ApplicationDefault()
                logger.info("firebase_using_default_credentials")
            
            firebase_admin.initialize_app(cred)
            
            self._db = firestore.client()
            self._initialized = True
            logger.info("firebase_initialized")

        except Exception as e:
            logger.warning(
                "firebase_init_failed",
                error=str(e),
            )
            self._initialized = False

    def is_configured(self) -> bool:
        """Check if Firebase is properly configured."""
        return self._initialized and self._db is not None

    async def update_transaction(
        self,
        transaction_id: str,
        data: dict,
    ) -> bool:
        """
        Update a document in the transactions collection.

        Args:
            transaction_id: The document ID in the transactions collection
            data: Dictionary of fields to update

        Returns:
            True if update was successful, False otherwise
        """
        if not self.is_configured():
            logger.warning("firebase_not_configured")
            return False

        try:
            doc_ref = self._db.collection("transactions").document(transaction_id)
            doc_ref.update(data)
            
            logger.info(
                "transaction_updated",
                transaction_id=transaction_id,
                fields_updated=list(data.keys()),
            )
            return True

        except Exception as e:
            logger.error(
                "transaction_update_failed",
                transaction_id=transaction_id,
                error=str(e),
            )
            return False

    async def set_transaction(
        self,
        transaction_id: str,
        data: dict,
        merge: bool = True,
    ) -> bool:
        """
        Set/create a document in the transactions collection.

        Args:
            transaction_id: The document ID in the transactions collection
            data: Dictionary of fields to set
            merge: If True, merge with existing data; if False, overwrite

        Returns:
            True if operation was successful, False otherwise
        """
        if not self.is_configured():
            logger.warning("firebase_not_configured")
            return False

        try:
            doc_ref = self._db.collection("transactions").document(transaction_id)
            doc_ref.set(data, merge=merge)
            
            logger.info(
                "transaction_set",
                transaction_id=transaction_id,
                merge=merge,
            )
            return True

        except Exception as e:
            logger.error(
                "transaction_set_failed",
                transaction_id=transaction_id,
                error=str(e),
            )
            return False

    async def get_transaction(self, transaction_id: str) -> dict | None:
        """
        Get a document from the transactions collection.

        Args:
            transaction_id: The document ID

        Returns:
            Document data as dict, or None if not found
        """
        if not self.is_configured():
            logger.warning("firebase_not_configured")
            return None

        try:
            doc_ref = self._db.collection("transactions").document(transaction_id)
            doc = doc_ref.get()
            
            if doc.exists:
                return doc.to_dict()
            return None

        except Exception as e:
            logger.error(
                "transaction_get_failed",
                transaction_id=transaction_id,
                error=str(e),
            )
            return None


# Singleton instance
_firebase_service: FirebaseService | None = None


def get_firebase_service() -> FirebaseService:
    """Get or create Firebase service singleton."""
    global _firebase_service
    if _firebase_service is None:
        _firebase_service = FirebaseService()
    return _firebase_service
