"""
Google Drive API client for syncing cookbook files.
Uses service account authentication to access files.
"""

import io
from pathlib import Path
from typing import List, Dict, Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.errors import HttpError

from cookplanner.config import Config


class GDriveClient:
    """Google Drive API client with service account authentication."""

    # Required scopes for Drive API
    SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

    def __init__(
        self,
        service_account_file: Optional[Path] = None,
        folder_id: Optional[str] = None,
    ):
        """
        Initialize Google Drive client.

        Args:
            service_account_file: Path to service account JSON file
            folder_id: Google Drive folder ID to sync from
        """
        self.service_account_file = (
            service_account_file or Config.get_service_account_path()
        )
        self.folder_id = folder_id or Config.GDRIVE_FOLDER_ID

        if not self.service_account_file or not self.service_account_file.exists():
            raise ValueError(
                f"Service account file not found: {self.service_account_file}. "
                "Please check your configuration."
            )

        # Authenticate and build service
        self.credentials = service_account.Credentials.from_service_account_file(
            str(self.service_account_file), scopes=self.SCOPES
        )
        self.service = build("drive", "v3", credentials=self.credentials)

    def list_files(self, folder_id: Optional[str] = None) -> List[Dict]:
        """
        List all files in a Google Drive folder.

        Args:
            folder_id: Folder ID to list files from (uses config default if not provided)

        Returns:
            List of file metadata dictionaries
        """
        folder_id = folder_id or self.folder_id

        try:
            # Query for files in the folder
            query = f"'{folder_id}' in parents and trashed=false"
            results = (
                self.service.files()
                .list(
                    q=query,
                    pageSize=100,
                    fields="nextPageToken, files(id, name, mimeType, modifiedTime, size)",
                )
                .execute()
            )

            files = results.get("files", [])

            # Handle pagination if there are more files
            while "nextPageToken" in results:
                results = (
                    self.service.files()
                    .list(
                        q=query,
                        pageSize=100,
                        pageToken=results["nextPageToken"],
                        fields="nextPageToken, files(id, name, mimeType, modifiedTime, size)",
                    )
                    .execute()
                )
                files.extend(results.get("files", []))

            return files

        except HttpError as error:
            print(f"An error occurred listing files: {error}")
            raise

    def get_file_metadata(self, file_id: str) -> Dict:
        """
        Get metadata for a specific file.

        Args:
            file_id: Google Drive file ID

        Returns:
            File metadata dictionary
        """
        try:
            file = (
                self.service.files()
                .get(fileId=file_id, fields="id, name, mimeType, modifiedTime, size")
                .execute()
            )
            return file

        except HttpError as error:
            print(f"An error occurred getting file metadata: {error}")
            raise

    def download_file(self, file_id: str, destination: Path) -> bool:
        """
        Download a file from Google Drive.

        Args:
            file_id: Google Drive file ID
            destination: Local path where file should be saved

        Returns:
            True if download succeeded, False otherwise
        """
        try:
            # Ensure destination directory exists
            destination.parent.mkdir(parents=True, exist_ok=True)

            # Request file content
            request = self.service.files().get_media(fileId=file_id)

            # Download file
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)

            done = False
            while not done:
                status, done = downloader.next_chunk()
                if status:
                    progress = int(status.progress() * 100)
                    print(progress)
                    # Progress can be logged here if needed

            # Write to destination file
            with open(destination, "wb") as f:
                f.write(fh.getvalue())

            return True

        except HttpError as error:
            print(f"An error occurred downloading file {file_id}: {error}")
            return False

    def is_supported_file_type(self, mime_type: str, file_name: str) -> bool:
        """
        Check if file type is supported (PDF or image).

        Args:
            mime_type: MIME type of the file
            file_name: Name of the file

        Returns:
            True if file type is supported
        """
        supported_mimes = ["application/pdf", "image/jpeg", "image/jpg", "image/png"]

        supported_extensions = [".pdf", ".jpg", ".jpeg", ".png"]

        return mime_type in supported_mimes or any(
            file_name.lower().endswith(ext) for ext in supported_extensions
        )

    def get_file_type(self, mime_type: str, file_name: str) -> str:
        """
        Determine file type from MIME type and filename.

        Args:
            mime_type: MIME type of the file
            file_name: Name of the file

        Returns:
            File type string ('pdf', 'jpeg', 'png', etc.)
        """
        if "pdf" in mime_type.lower() or file_name.lower().endswith(".pdf"):
            return "pdf"
        elif "jpeg" in mime_type.lower() or file_name.lower().endswith(
            (".jpg", ".jpeg")
        ):
            return "jpeg"
        elif "png" in mime_type.lower() or file_name.lower().endswith(".png"):
            return "png"
        else:
            return "unknown"


def create_gdrive_client() -> GDriveClient:
    """
    Create a Google Drive client using configuration.

    Returns:
        Configured GDriveClient instance
    """
    return GDriveClient()
