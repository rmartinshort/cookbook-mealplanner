"""
Gemini Vision API client for extracting recipes from images.
Uses structured output to ensure JSON schema compliance.
"""

from pathlib import Path
from typing import Union, List
from google import genai
from google.genai import types
from PIL import Image

from cookplanner.config import Config
from cookplanner.models.schema import RecipeExtract, MultiRecipeExtract


class GeminiClient:
    """Gemini Vision API client for recipe extraction."""

    def __init__(self, api_key: str = None, model_name: str = None):
        """
        Initialize Gemini client.

        Args:
            api_key: Gemini API key (uses config if not provided)
            model_name: Model to use (uses config if not provided)
        """
        self.api_key = api_key or Config.GEMINI_API_KEY

        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not set in configuration")

        # Initialize client with API key
        self.client = genai.Client(api_key=self.api_key)

        # Store model name - use config default if not provided
        self.model_name = model_name or Config.GEMINI_MODEL_NAME

    def extract_recipe_from_image(
        self, image_path: Union[str, Path], expect_multiple: bool = False
    ) -> Union[RecipeExtract, List[RecipeExtract]]:
        """
        Extract recipe(s) from a cookbook page image.

        Args:
            image_path: Path to the image file
            expect_multiple: Whether to expect multiple recipes on one page

        Returns:
            RecipeExtract object or list of RecipeExtract objects
        """
        # Load image
        image = Image.open(image_path)

        # Create prompt
        prompt = self._create_extraction_prompt(expect_multiple)

        # Generate content with structured output
        try:
            # Use the new API with Client
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[prompt, image],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=MultiRecipeExtract
                    if expect_multiple
                    else RecipeExtract,
                ),
            )

            # Parse response
            if expect_multiple:
                result = MultiRecipeExtract.model_validate_json(response.text)
                return result.recipes
            else:
                result = RecipeExtract.model_validate_json(response.text)
                return result

        except Exception as e:
            print(f"Error extracting recipe from {image_path}: {e}")
            raise

    def _create_extraction_prompt(self, expect_multiple: bool = False) -> str:
        """
        Create the prompt for recipe extraction.

        Args:
            expect_multiple: Whether to expect multiple recipes

        Returns:
            Prompt string
        """
        base_prompt = """
You are an expert at extracting recipes from Japanese cookbook pages.

Please analyze this image and extract ALL recipe information you can find.

For EACH recipe on the page:
1. Read and transcribe the Japanese text (title, ingredients, instructions)
2. Translate everything to English
3. Extract structured data following the schema

Important guidelines:
- **Title**: Extract both Japanese and English translations
- **Summary**: Write a brief 1-2 sentence description of the dish in English
- **Servings**: Number of servings (default to 2 if not specified)
- **Tags**: Assign relevant tags such as:
  - Protein type: vegetarian, fish, chicken, pork, beef, tofu
  - Cuisine: Japanese, Western, Chinese, Korean
  - Difficulty: easy, medium, hard
  - Cooking method: stir-fry, bake, grill, boil, steam, raw
  - Meal type: breakfast, lunch, dinner, snack, side-dish
  - Season: spring, summer, fall, winter (if relevant)
- **Ingredients**: **CRITICAL** - Create SEPARATE entries for each individual ingredient
  - **Separation Rules**:
    * If you see "各" (each) or "&" or "・" combining multiple ingredients, split them into SEPARATE ingredient objects
    * Example: "Salt & pepper (塩・こしょう): 各適量" becomes TWO entries:
      1. Salt (塩): to taste / seasoning
      2. Pepper (こしょう): to taste / seasoning
    * Example: "Garlic・Ginger tube (にんにく・しょうがチューブ): 各小さじ1" becomes TWO entries:
      1. Garlic paste (tube) (にんにくチューブ): 1 tsp / seasoning
      2. Ginger paste (tube) (しょうがチューブ): 1 tsp / seasoning

  - **For EACH individual ingredient**:
    * name_jp: Japanese name (single ingredient only)
    * name_en: English translation (single ingredient only)
    * quantity: Numeric amount as a string (e.g., "200", "1", "1/2", "2")
      - Convert "各" quantities to the per-item amount
      - For "適量" (appropriate amount) → use "to taste" in English, keep "適量" in Japanese
      - For "少々" (a pinch) → use "pinch" or "to taste"
    * unit: Clear unit (g, ml, tbsp, tsp, cup, piece, clove, etc.)
      - Use "tbsp" not "大さじ"
      - Use "tsp" not "小さじ"
      - Use standard English units
    * category: produce, protein, pantry, dairy, or seasoning
    * sauce_reference: If ingredients are grouped with letters (A, B, C, etc.), set the group letter
      - Look for patterns: "A: {ingredients}", ingredients marked with letters
      - If instructions say "Rub A into..." or "Mix B together", those ingredients belong to that group
      - Leave empty/null for ungrouped ingredients
- **Instructions**: For each step:
  - step_number: Sequential number starting from 1
  - text_jp: Instruction in Japanese
  - text_en: English translation

**CRITICAL REMINDERS**:
1. **One ingredient per entry** - Never combine multiple ingredients in a single entry
2. When you see combined ingredients with "各", "&", or "・", create separate entries
3. Use clear English units: tbsp, tsp, g, ml, cup, piece, clove
4. Convert vague amounts ("適量", "少々") to "to taste" or "pinch"
5. Each ingredient must have: individual name_jp, individual name_en, numeric quantity, clear unit

Examples of CORRECT ingredient extraction:
- Input: "Salt・pepper (塩・こしょう): 各適量"
  → Output: Two entries with sauce_reference if grouped
    1. {name_jp: "塩", name_en: "Salt", quantity: "to taste", unit: "", category: "seasoning"}
    2. {name_jp: "こしょう", name_en: "Pepper", quantity: "to taste", unit: "", category: "seasoning"}

- Input: "Garlic tube・Ginger tube (にんにくチューブ・しょうがチューブ): 各小さじ1/2"
  → Output: Two entries
    1. {name_jp: "にんにくチューブ", name_en: "Garlic paste (tube)", quantity: "1/2", unit: "tsp", category: "seasoning"}
    2. {name_jp: "しょうがチューブ", name_en: "Ginger paste (tube)", quantity: "1/2", unit: "tsp", category: "seasoning"}
"""

        if expect_multiple:
            base_prompt += "\n\nThis page may contain MULTIPLE recipes. Extract ALL of them as separate recipe objects."
        else:
            base_prompt += "\n\nExtract the recipe information from this page."

        return base_prompt

    def test_connection(self) -> bool:
        """
        Test if the API connection is working.

        Returns:
            True if connection is successful
        """
        try:
            # Simple test with a text prompt
            response = self.client.models.generate_content(
                model=self.model_name, contents="Hello"
            )
            print(response)
            return True
        except Exception as e:
            print(f"API connection test failed: {e}")
            return False


def create_gemini_client() -> GeminiClient:
    """
    Create a Gemini client using configuration.

    Returns:
        Configured GeminiClient instance
    """
    return GeminiClient()
