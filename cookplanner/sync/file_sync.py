"""
File synchronization logic for Google Drive to local storage.
Coordinates downloading files and extracting PDF pages.
"""

from pathlib import Path
from typing import List, Dict

from cookplanner.config import Config
from cookplanner.sync.gdrive_client import GDriveClient
from cookplanner.sync.pdf_processor import PDFProcessor
from cookplanner.models.orm import upsert_sync_file, get_sync_file
from cookplanner.models.schema import SyncFile


class FileSyncer:
    """Synchronize files from Google Drive to local storage."""

    def __init__(
        self, gdrive_client: GDriveClient = None, pdf_processor: PDFProcessor = None
    ):
        """
        Initialize file syncer.

        Args:
            gdrive_client: Google Drive client (created if not provided)
            pdf_processor: PDF processor (created if not provided)
        """
        self.gdrive = gdrive_client or GDriveClient()
        self.pdf_processor = pdf_processor or PDFProcessor(dpi=300)
        self.images_dir = Config.get_images_dir()

    def sync_all(self) -> Dict[str, int]:
        """
        Sync all files from Google Drive folder.

        Returns:
            Dictionary with sync statistics (new, updated, errors, pages_extracted)
        """
        stats = {
            "new": 0,
            "updated": 0,
            "skipped": 0,
            "errors": 0,
            "pages_extracted": 0,
        }

        # Ensure images directory exists
        self.images_dir.mkdir(parents=True, exist_ok=True)

        # List all files in Drive folder
        print("Listing files from Google Drive folder...")
        try:
            files = self.gdrive.list_files()
        except Exception as e:
            print(f"Error listing files from Drive: {e}")
            return stats

        print(f"Found {len(files)} files in Drive folder")

        # Process each file
        for file_info in files:
            file_id = file_info["id"]
            file_name = file_info["name"]
            mime_type = file_info["mimeType"]
            modified_time = file_info["modifiedTime"]

            # Check if file type is supported
            if not self.gdrive.is_supported_file_type(mime_type, file_name):
                print(f"Skipping unsupported file: {file_name}")
                stats["skipped"] += 1
                continue

            # Check if file needs to be synced
            existing = get_sync_file(file_id)

            if existing and existing.last_modified == modified_time:
                print(f"Skipping unchanged file: {file_name}")
                stats["skipped"] += 1
                continue

            # Determine file type
            file_type = self.gdrive.get_file_type(mime_type, file_name)

            # Sync the file
            try:
                result = self._sync_file(file_info, file_type, existing is not None)
                if result["success"]:
                    if existing:
                        stats["updated"] += 1
                    else:
                        stats["new"] += 1
                    stats["pages_extracted"] += result["pages_extracted"]
                    print(f"✓ Synced: {file_name} ({result['pages_extracted']} pages)")
                else:
                    stats["errors"] += 1
                    print(f"✗ Error syncing: {file_name}")
            except Exception as e:
                stats["errors"] += 1
                print(f"✗ Error syncing {file_name}: {e}")

        return stats

    def _sync_file(self, file_info: Dict, file_type: str, is_update: bool) -> Dict:
        """
        Sync a single file from Drive.

        Args:
            file_info: File metadata from Drive
            file_type: Type of file (pdf, jpeg, etc.)
            is_update: Whether this is an update to existing file

        Returns:
            Dictionary with sync result
        """
        file_id = file_info["id"]
        file_name = file_info["name"]
        modified_time = file_info["modifiedTime"]

        result = {"success": False, "pages_extracted": 0}

        try:
            if file_type == "pdf":
                # Download PDF and extract pages
                result = self._sync_pdf(file_id, file_name, modified_time)
            else:
                # Download image directly
                result = self._sync_image(file_id, file_name, file_type, modified_time)

            return result

        except Exception as e:
            # Record error in database
            sync_file = SyncFile(
                drive_file_id=file_id,
                local_path="",
                last_modified=modified_time,
                sync_status="error",
                file_type=file_type,
                error_message=str(e),
            )
            upsert_sync_file(sync_file)
            raise

    def _sync_pdf(self, file_id: str, file_name: str, modified_time: str) -> Dict:
        """
        Sync a PDF file: download and extract pages.

        Args:
            file_id: Google Drive file ID
            file_name: Name of the file
            modified_time: Last modified timestamp

        Returns:
            Dictionary with sync result
        """
        # Download PDF to temporary location
        pdf_path = self.images_dir / file_name

        success = self.gdrive.download_file(file_id, pdf_path)

        if not success:
            raise Exception("Failed to download PDF")

        # Extract pages to images
        try:
            extracted_paths = self.pdf_processor.extract_pages(
                pdf_path, self.images_dir, prefix=pdf_path.stem
            )

            # Record sync in database
            sync_file = SyncFile(
                drive_file_id=file_id,
                local_path=str(pdf_path),
                last_modified=modified_time,
                sync_status="synced",
                file_type="pdf",
                error_message=None,
            )
            upsert_sync_file(sync_file)

            return {"success": True, "pages_extracted": len(extracted_paths)}

        except Exception as e:
            # Clean up PDF file if extraction failed
            if pdf_path.exists():
                pdf_path.unlink()
            raise Exception(f"Failed to extract PDF pages: {e}")

    def _sync_image(
        self, file_id: str, file_name: str, file_type: str, modified_time: str
    ) -> Dict:
        """
        Sync an image file: download directly.

        Args:
            file_id: Google Drive file ID
            file_name: Name of the file
            file_type: Type of image (jpeg, png, etc.)
            modified_time: Last modified timestamp

        Returns:
            Dictionary with sync result
        """
        # Download image
        image_path = self.images_dir / file_name

        success = self.gdrive.download_file(file_id, image_path)

        if not success:
            raise Exception("Failed to download image")

        # Record sync in database
        sync_file = SyncFile(
            drive_file_id=file_id,
            local_path=str(image_path),
            last_modified=modified_time,
            sync_status="synced",
            file_type=file_type,
            error_message=None,
        )
        upsert_sync_file(sync_file)

        return {
            "success": True,
            "pages_extracted": 1,  # One image = one "page"
        }

    def get_unprocessed_images(self) -> List[Path]:
        """
        Get list of image files that haven't been processed yet.

        Returns:
            List of image file paths
        """
        # Get all image files
        image_files = []
        for ext in ["*.jpg", "*.jpeg", "*.png"]:
            image_files.extend(self.images_dir.glob(ext))

        return sorted(image_files)


def sync_from_drive() -> Dict[str, int]:
    """
    Convenience function to sync files from Google Drive.

    Returns:
        Dictionary with sync statistics
    """
    syncer = FileSyncer()
    return syncer.sync_all()
