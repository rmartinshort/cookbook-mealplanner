"""
Recipe extraction logic using Gemini Vision.
Coordinates between image processing and database storage.
"""

from pathlib import Path
from typing import List, Optional, Union

from cookplanner.extraction.gemini_client import GeminiClient
from cookplanner.models.orm import insert_recipe, check_already_extracted
from cookplanner.models.schema import RecipeExtract


class RecipeExtractor:
    """Extract recipes from images and store in database."""

    def __init__(self, gemini_client: GeminiClient = None):
        """
        Initialize recipe extractor.

        Args:
            gemini_client: Gemini client (created if not provided)
        """
        self.gemini_client = gemini_client or GeminiClient()

    def extract_from_image(
        self,
        image_path: Union[str, Path],
        expect_multiple: bool = True,
        save_to_db: bool = True,
        drive_file_id: Optional[str] = None,
    ) -> Union[int, List[int], RecipeExtract, List[RecipeExtract]]:
        """
        Extract recipe(s) from an image.

        Args:
            image_path: Path to the image file
            expect_multiple: Whether to expect multiple recipes
            save_to_db: Whether to save to database (default True)
            drive_file_id: Google Drive file ID for tracking

        Returns:
            If save_to_db=True: recipe ID(s) from database
            If save_to_db=False: RecipeExtract object(s)
        """
        image_path = Path(image_path)

        if not image_path.exists():
            raise FileNotFoundError(f"Image file not found: {image_path}")

        # Extract recipe(s) using Gemini
        print(f"Extracting recipe from: {image_path.name}")

        try:
            result = self.gemini_client.extract_recipe_from_image(
                image_path, expect_multiple=expect_multiple
            )
        except Exception as e:
            print(f"Failed to extract recipe: {e}")
            raise

        # Handle single vs multiple recipes
        if isinstance(result, list):
            recipes = result
        else:
            recipes = [result]

        if not save_to_db:
            return result

        # Save to database
        recipe_ids = []
        for i, recipe in enumerate(recipes):
            # Determine page number from filename if it's a PDF page
            page_number = self._extract_page_number(image_path)

            # Check if already extracted
            if check_already_extracted(image_path.name, page_number, i):
                page_info = (
                    f"page {page_number}, recipe {i}" if page_number else f"recipe {i}"
                )
                print(
                    f"  Recipe already extracted from {image_path.name} ({page_info})"
                )
                continue

            # Insert into database
            recipe_id = insert_recipe(
                recipe=recipe,
                source_file=image_path.name,
                drive_file_id=drive_file_id,
                page_number=page_number,
                recipe_index=i,
            )

            recipe_ids.append(recipe_id)
            page_info = (
                f"Page {page_number}, Recipe {i}" if page_number else f"Recipe {i}"
            )
            print(f"  ✓ Saved: {recipe.title_en} (ID: {recipe_id}, {page_info})")

        # Return single ID or list based on input
        if isinstance(result, list):
            return recipe_ids
        else:
            return recipe_ids[0] if recipe_ids else None

    def extract_batch(
        self,
        image_paths: List[Path],
        skip_existing: bool = True,
        expect_multiple: bool = True,
    ) -> dict:
        """
        Extract recipes from multiple images.

        Args:
            image_paths: List of image file paths
            skip_existing: Whether to skip already-extracted images

        Returns:
            Dictionary with statistics
        """
        stats = {
            "total": len(image_paths),
            "extracted": 0,
            "skipped": 0,
            "errors": 0,
            "recipe_count": 0,
        }

        for image_path in image_paths:
            try:
                # Note: Skip check happens at individual recipe level in extract_from_image
                # We don't pre-check here since we may have multiple recipes per page
                # Extract recipe(s)
                result = self.extract_from_image(
                    image_path,
                    expect_multiple=expect_multiple,  # Can be made configurable
                    save_to_db=True,
                )

                # Count recipes
                if isinstance(result, list):
                    stats["recipe_count"] += len(result)
                elif result is not None:
                    stats["recipe_count"] += 1

                stats["extracted"] += 1

            except Exception as e:
                print(f"Error extracting from {image_path.name}: {e}")
                stats["errors"] += 1

        return stats

    def _extract_page_number(self, image_path: Path) -> Optional[int]:
        """
        Extract page number from filename if present.

        Args:
            image_path: Path to image file

        Returns:
            Page number or None
        """
        # Look for pattern like "filename_page_001.jpg"
        name = image_path.stem
        parts = name.split("_")

        for i, part in enumerate(parts):
            if part == "page" and i + 1 < len(parts):
                try:
                    return int(parts[i + 1])
                except ValueError:
                    pass

        return None


def extract_recipe_from_image(
    image_path: Union[str, Path], save_to_db: bool = True
) -> Union[int, RecipeExtract]:
    """
    Convenience function to extract a recipe from an image.

    Args:
        image_path: Path to the image file
        save_to_db: Whether to save to database

    Returns:
        Recipe ID (if saved) or RecipeExtract object
    """
    extractor = RecipeExtractor()
    return extractor.extract_from_image(image_path, save_to_db=save_to_db)
