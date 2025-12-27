"""
PDF processing utilities for extracting pages as images.
Uses PyMuPDF for high-quality page extraction.
"""

from pathlib import Path
from typing import List, Tuple
import pymupdf


class PDFProcessor:
    """Process PDF files and extract pages as images."""

    def __init__(self, dpi: int = 300):
        """
        Initialize PDF processor.

        Args:
            dpi: Resolution for rendering pages (default 300 for high quality)
        """
        self.dpi = dpi
        # Calculate zoom factor for the DPI
        # PyMuPDF uses 72 DPI by default, so zoom = desired_dpi / 72
        self.zoom = dpi / 72.0

    def extract_pages(
        self, pdf_path: Path, output_dir: Path, prefix: str = None
    ) -> List[Path]:
        """
        Extract all pages from a PDF as individual JPEG images.

        Args:
            pdf_path: Path to the PDF file
            output_dir: Directory where images should be saved
            prefix: Optional prefix for output filenames (defaults to PDF basename)

        Returns:
            List of paths to the extracted images
        """
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        # Create output directory if it doesn't exist
        output_dir.mkdir(parents=True, exist_ok=True)

        # Use PDF filename as prefix if not provided
        if prefix is None:
            prefix = pdf_path.stem

        # Open the PDF
        doc = pymupdf.open(pdf_path)
        extracted_paths = []

        try:
            # Extract each page
            for page_num in range(len(doc)):
                page = doc[page_num]

                # Create a transformation matrix for the zoom level
                mat = pymupdf.Matrix(self.zoom, self.zoom)

                # Render page to pixmap (image)
                pix = page.get_pixmap(matrix=mat, alpha=False)

                # Generate output filename: prefix_page_001.jpg
                output_filename = f"{prefix}_page_{page_num + 1:03d}.jpg"
                output_path = output_dir / output_filename

                # Save the image
                pix.save(str(output_path), "jpeg")

                extracted_paths.append(output_path)

                # Free memory
                pix = None

        finally:
            # Close the document
            doc.close()

        return extracted_paths

    def extract_single_page(
        self, pdf_path: Path, page_num: int, output_path: Path
    ) -> Path:
        """
        Extract a single page from a PDF.

        Args:
            pdf_path: Path to the PDF file
            page_num: Page number to extract (0-indexed)
            output_path: Where to save the extracted image

        Returns:
            Path to the extracted image
        """
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        # Create output directory if needed
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Open the PDF
        doc = pymupdf.open(pdf_path)

        try:
            if page_num >= len(doc):
                raise ValueError(
                    f"Page {page_num} does not exist. PDF has {len(doc)} pages."
                )

            # Get the page
            page = doc[page_num]

            # Create transformation matrix
            mat = pymupdf.Matrix(self.zoom, self.zoom)

            # Render to pixmap
            pix = page.get_pixmap(matrix=mat, alpha=False)

            # Save
            pix.save(str(output_path), "jpeg")

        finally:
            doc.close()

        return output_path

    def get_page_count(self, pdf_path: Path) -> int:
        """
        Get the number of pages in a PDF.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            Number of pages
        """
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        doc = pymupdf.open(pdf_path)
        count = len(doc)
        doc.close()

        return count

    def get_page_info(self, pdf_path: Path) -> List[Tuple[int, int]]:
        """
        Get dimension information for all pages.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            List of (width, height) tuples for each page
        """
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        doc = pymupdf.open(pdf_path)
        info = []

        try:
            for page_num in range(len(doc)):
                page = doc[page_num]
                rect = page.rect
                info.append((int(rect.width), int(rect.height)))
        finally:
            doc.close()

        return info


def extract_pdf_pages(pdf_path: Path, output_dir: Path, dpi: int = 300) -> List[Path]:
    """
    Convenience function to extract all pages from a PDF.

    Args:
        pdf_path: Path to the PDF file
        output_dir: Directory for output images
        dpi: Resolution for rendering (default 300)

    Returns:
        List of paths to extracted images
    """
    processor = PDFProcessor(dpi=dpi)
    return processor.extract_pages(pdf_path, output_dir)
