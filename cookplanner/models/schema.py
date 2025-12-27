"""
Pydantic models for recipe data validation and structured extraction.
These models define the schema for recipes extracted from cookbook images.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class Ingredient(BaseModel):
    """An ingredient in a recipe."""

    name_jp: str = Field(description="Ingredient name in Japanese")
    name_en: str = Field(description="Ingredient name in English")
    quantity: str = Field(description="Quantity/amount of ingredient")
    unit: str = Field(description="Unit of measurement (e.g., g, ml, tbsp, cups)")
    category: Optional[str] = Field(
        default=None, description="Category (e.g., produce, protein, pantry, dairy)"
    )
    sauce_reference: Optional[str] = Field(
        default=None, description="If this ingredient is associated with a sauce denoted by a letter (e.g. A, B etc), include this reference here"
    )


class Instruction(BaseModel):
    """A step in a recipe's instructions."""

    step_number: int = Field(description="Step number in the recipe")
    text_jp: str = Field(description="Instruction text in Japanese")
    text_en: str = Field(description="Instruction text in English")


class RecipeExtract(BaseModel):
    """
    Complete recipe extracted from a cookbook page.
    This model is used for both data validation and as the schema
    for Gemini Vision's structured output.
    """

    title_jp: str = Field(description="Recipe title in Japanese")
    title_en: str = Field(description="Recipe title in English")
    summary_en: str = Field(
        description="Brief summary or description of the dish in English"
    )
    servings: int = Field(description="Number of servings this recipe makes", default=2)
    tags: List[str] = Field(
        description="Tags for categorization (e.g., vegetarian, fish, easy, stir-fry, Japanese)",
        default_factory=list,
    )
    ingredients: List[Ingredient] = Field(
        description="List of ingredients needed for the recipe"
    )
    instructions: List[Instruction] = Field(
        description="Step-by-step cooking instructions"
    )

    class Config:
        """Pydantic configuration."""

        json_schema_extra = {
            "example": {
                "title_jp": "照り焼きチキン",
                "title_en": "Teriyaki Chicken",
                "summary_en": "Sweet and savory glazed chicken with vegetables",
                "servings": 4,
                "tags": ["chicken", "Japanese", "easy", "stir-fry"],
                "ingredients": [
                    {
                        "name_jp": "鶏もも肉",
                        "name_en": "chicken thigh",
                        "quantity": "400",
                        "unit": "g",
                        "category": "protein",
                    },
                    {
                        "name_jp": "醤油",
                        "name_en": "soy sauce",
                        "quantity": "3",
                        "unit": "tbsp",
                        "category": "pantry",
                        "sauce_reference": "A"
                    },
                ],
                "instructions": [
                    {
                        "step_number": 1,
                        "text_jp": "鶏肉を一口大に切る",
                        "text_en": "Cut chicken into bite-sized pieces",
                    },
                    {
                        "step_number": 2,
                        "text_jp": "フライパンで鶏肉を焼く",
                        "text_en": "Cook chicken in a frying pan",
                    },
                ],
            }
        }


class MultiRecipeExtract(BaseModel):
    """
    Container for multiple recipes found on a single page.
    Some cookbook pages may contain more than one recipe.
    """

    recipes: List[RecipeExtract] = Field(
        description="List of recipes found on this page"
    )


class Recipe(BaseModel):
    """
    Recipe model with database metadata.
    This extends RecipeExtract with additional fields from the database.
    """

    id: int
    title_jp: str
    title_en: str
    summary_en: str
    servings: int
    tags: List[str]
    source_file: str
    drive_file_id: Optional[str] = None
    page_number: Optional[int] = None
    recipe_index: int = 0
    created_at: str
    ingredients: List[Ingredient] = []
    instructions: List[Instruction] = []


class SyncFile(BaseModel):
    """Metadata for a synced file from Google Drive."""

    id: Optional[int] = None
    drive_file_id: str
    local_path: str
    last_modified: str
    sync_status: str  # 'synced', 'pending', 'error'
    file_type: str  # 'pdf', 'jpeg', 'jpg', 'png'
    error_message: Optional[str] = None
