"""
Configuration module for the cookbook meal planner.
Loads settings from environment variables and provides them to other modules.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from the project root
project_root = Path(__file__).parent.parent
env_path = project_root / ".env"
load_dotenv(env_path)


class Config:
    """Application configuration loaded from environment variables."""

    # Gemini AI
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-3-pro-image-preview")

    # Google Drive
    GDRIVE_FOLDER_ID = os.getenv("GDRIVE_FOLDER_ID")
    GDRIVE_SERVICE_ACCOUNT_FILE = os.getenv("GDRIVE_SERVICE_ACCOUNT_FILE")

    # Local paths
    LOCAL_DATA_DIR = os.getenv("LOCAL_DATA_DIR", "data")

    @classmethod
    def get_project_root(cls) -> Path:
        """Get the project root directory."""
        return project_root

    @classmethod
    def get_data_dir(cls) -> Path:
        """Get the data directory path."""
        return project_root / cls.LOCAL_DATA_DIR

    @classmethod
    def get_images_dir(cls) -> Path:
        """Get the images directory path."""
        return cls.get_data_dir() / "images"

    @classmethod
    def get_db_path(cls) -> Path:
        """Get the database file path."""
        return cls.get_data_dir() / "recipes.db"

    @classmethod
    def get_sync_state_path(cls) -> Path:
        """Get the sync state file path."""
        return cls.get_data_dir() / "sync_state.json"

    @classmethod
    def get_service_account_path(cls) -> Path:
        """Get the full path to the service account JSON file."""
        if cls.GDRIVE_SERVICE_ACCOUNT_FILE:
            # If relative path, resolve from project root
            if not Path(cls.GDRIVE_SERVICE_ACCOUNT_FILE).is_absolute():
                return project_root / cls.GDRIVE_SERVICE_ACCOUNT_FILE
            return Path(cls.GDRIVE_SERVICE_ACCOUNT_FILE)
        return None

    @classmethod
    def validate(cls) -> bool:
        """
        Validate that all required configuration is present.
        Returns True if valid, raises ValueError if not.
        """
        errors = []

        if not cls.GEMINI_API_KEY:
            errors.append("GEMINI_API_KEY is not set")

        if not cls.GDRIVE_FOLDER_ID:
            errors.append("GDRIVE_FOLDER_ID is not set")

        if not cls.GDRIVE_SERVICE_ACCOUNT_FILE:
            errors.append("GDRIVE_SERVICE_ACCOUNT_FILE is not set")
        else:
            service_account_path = cls.get_service_account_path()
            if not service_account_path.exists():
                errors.append(f"Service account file not found: {service_account_path}")

        if errors:
            raise ValueError(
                "Configuration validation failed:\n"
                + "\n".join(f"  - {error}" for error in errors)
            )

        return True


# Convenience instance for importing
config = Config()
