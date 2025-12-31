"""
Dinner planning using LLM to generate weekly dinner plans.
Uses available recipes from the database to create balanced weekly dinner menus.
"""

from typing import List, Optional
from google import genai

from cookplanner.config import Config
from cookplanner.models.orm import (
    list_recipes,
    get_plan_history,
    format_history_for_llm,
)
from cookplanner.models.schema import Recipe, DinnerPlan


class MealPlanner:
    """Generate weekly dinner plans using LLM and available recipes."""

    def __init__(self):
        """Initialize meal planner with Gemini client."""
        self.client = genai.Client(api_key=Config.GEMINI_API_KEY)
        self.model_name = Config.GEMINI_MODEL_NAME

    def create_dinner_plan(
        self,
        num_days: int = 7,
        servings: int = 2,
        preferences: Optional[str] = None,
        excluded_ingredients: Optional[List[str]] = None,
    ) -> DinnerPlan:
        """
        Create a weekly dinner plan using available recipes.

        Args:
            num_days: Number of days to plan (default 7)
            servings: Number of servings per dinner (default 2)
            preferences: User preferences (e.g., "vegetarian", "lots of vegetables")
            excluded_ingredients: List of ingredients to avoid

        Returns:
            DinnerPlan object with the generated plan
        """
        # Load all available recipes
        recipes = list_recipes(limit=None)

        if not recipes:
            raise ValueError("No recipes available in database. Import recipes first.")

        # Build recipe context for LLM
        recipe_context = self._build_recipe_context(recipes)

        # Create prompt for dinner planning
        prompt = self._build_dinner_plan_prompt(
            recipe_context=recipe_context,
            num_days=num_days,
            servings=servings,
            preferences=preferences,
            excluded_ingredients=excluded_ingredients,
        )

        # Generate plan using Gemini
        response = self.client.models.generate_content(
            model=self.model_name, contents=prompt
        )

        # Parse response and create DinnerPlan
        dinner_plan = self._parse_dinner_plan_response(response.text, recipes)

        return dinner_plan

    def create_dinner_plan_options(
        self,
        num_days: int = 7,
        servings: int = 2,
        num_options: int = 3,
        preferences: Optional[str] = None,
        excluded_ingredients: Optional[List[str]] = None,
        user_id: str = "default",
        use_history: bool = True,
    ) -> List[DinnerPlan]:
        """
        Create multiple dinner plan options using available recipes with history context.

        Args:
            num_days: Number of days to plan (default 7)
            servings: Number of servings per dinner (default 2)
            num_options: Number of different plan options to generate (default 3)
            preferences: User preferences (e.g., "vegetarian", "lots of vegetables")
            excluded_ingredients: List of ingredients to avoid
            user_id: User ID for retrieving plan history (default "default")
            use_history: Whether to use past plan history for recommendations (default True)

        Returns:
            List of DinnerPlan objects, one for each option
        """
        # Load all available recipes
        recipes = list_recipes(limit=None)

        if not recipes:
            raise ValueError("No recipes available in database. Import recipes first.")

        # Get plan history for context (if enabled)
        if use_history:
            history = get_plan_history(user_id, limit=10)
            history_context = format_history_for_llm(history)
        else:
            history_context = "No previous history used for this generation."

        # Build recipe context for LLM
        recipe_context = self._build_recipe_context(recipes)

        # Generate multiple options
        plans = []
        for i in range(num_options):
            # Create prompt with history and option number
            prompt = self._build_dinner_plan_options_prompt(
                recipe_context=recipe_context,
                history_context=history_context,
                num_days=num_days,
                servings=servings,
                preferences=preferences,
                excluded_ingredients=excluded_ingredients,
                option_number=i + 1,
                total_options=num_options,
                previously_generated=plans,
            )

            # Generate plan using Gemini
            response = self.client.models.generate_content(
                model=self.model_name, contents=prompt
            )

            # Parse response and create DinnerPlan
            dinner_plan = self._parse_dinner_plan_response(response.text, recipes)
            plans.append(dinner_plan)

        return plans

    def _build_recipe_context(self, recipes: List[Recipe]) -> str:
        """Build a context string with all available recipes."""
        lines = ["Available Recipes:\n"]

        for recipe in recipes:
            tags = ", ".join(recipe.tags) if recipe.tags else "no tags"
            ingredients = ", ".join([ing.name_en for ing in recipe.ingredients[:5]])
            if len(recipe.ingredients) > 5:
                ingredients += "..."

            lines.append(
                f"- ID {recipe.id}: {recipe.title_en} ({recipe.title_jp})"
                f"\n  Tags: {tags}"
                f"\n  Servings: {recipe.servings}"
                f"\n  Key ingredients: {ingredients}"
                f"\n  Summary: {recipe.summary_en[:100]}..."
                f"\n"
            )

        return "\n".join(lines)

    def _build_dinner_plan_prompt(
        self,
        recipe_context: str,
        num_days: int,
        servings: int,
        preferences: Optional[str],
        excluded_ingredients: Optional[List[str]],
    ) -> str:
        """Build the prompt for dinner planning."""
        prompt = f"""You are a dinner planning assistant. Create a {num_days}-day dinner plan using ONLY the recipes provided below.

{recipe_context}

Requirements:
- Plan dinners for {servings} people
- Use a variety of recipes to keep dinners interesting
- Consider nutritional balance across the week
- Use different recipes each day when possible
"""

        if preferences:
            prompt += f"- User preferences: {preferences}\n"

        if excluded_ingredients:
            excluded = ", ".join(excluded_ingredients)
            prompt += f"- Avoid recipes with these ingredients: {excluded}\n"

        prompt += """
Output Format (use this EXACT format):
Day 1: Recipe ID X - [Recipe Title]
Day 2: Recipe ID Y - [Recipe Title]
Day 3: Recipe ID Z - [Recipe Title]
...

REASONING:
[Explain your choices, considering variety, nutrition, and balance]

Important:
- ONLY use recipe IDs from the list above
- Include the recipe ID number for EVERY day
- Keep recipe names exactly as shown in the recipe list
"""

        return prompt

    def _build_dinner_plan_options_prompt(
        self,
        recipe_context: str,
        history_context: str,
        num_days: int,
        servings: int,
        preferences: Optional[str],
        excluded_ingredients: Optional[List[str]],
        option_number: int,
        total_options: int,
        previously_generated: List[DinnerPlan],
    ) -> str:
        """Build the prompt for dinner planning with history and variety."""
        prompt = f"""You are a dinner planning assistant. Create a {num_days}-day dinner plan using ONLY the recipes provided below.

This is option {option_number} of {total_options} different plans you will generate. Make this option distinct from the others.

{recipe_context}

{history_context}

Requirements:
- Plan dinners for {servings} people
- Use a variety of recipes to keep dinners interesting
- Consider nutritional balance across the week
- Use different recipes each day when possible
- Learn from the user's previous choices (if any) to better match their preferences
"""

        if preferences:
            prompt += f"- User preferences: {preferences}\n"

        if excluded_ingredients:
            excluded = ", ".join(excluded_ingredients)
            prompt += f"- Avoid recipes with these ingredients: {excluded}\n"

        # Add context about previously generated options to ensure variety
        if previously_generated:
            prompt += "\nPreviously generated options:\n"
            for idx, plan in enumerate(previously_generated, 1):
                recipe_ids = [str(d["recipe_id"]) for d in plan.dinners]
                prompt += f"Option {idx}: Uses recipe IDs: {', '.join(recipe_ids)}\n"
            prompt += "\nMake sure THIS option is DIFFERENT from the ones above. Use different recipes.\n"

        prompt += """
Output Format (use this EXACT format):
Day 1: Recipe ID X - [Recipe Title]
Day 2: Recipe ID Y - [Recipe Title]
Day 3: Recipe ID Z - [Recipe Title]
...

REASONING:
[Explain your choices, considering variety, nutrition, balance, and user's past preferences]

Important:
- ONLY use recipe IDs from the list above
- Include the recipe ID number for EVERY day
- Keep recipe names exactly as shown in the recipe list
- Make this option different from any previously generated options
"""

        return prompt

    def _parse_dinner_plan_response(
        self, response_text: str, recipes: List[Recipe]
    ) -> DinnerPlan:
        """Parse LLM response into structured DinnerPlan."""
        # Create recipe lookup
        recipe_lookup = {recipe.id: recipe for recipe in recipes}

        dinners = []
        reasoning = ""
        in_reasoning = False

        lines = response_text.strip().split("\n")

        for line in lines:
            line = line.strip()

            if not line:
                continue

            # Check for reasoning section
            if line.upper().startswith("REASONING:"):
                in_reasoning = True
                continue

            if in_reasoning:
                reasoning += line + "\n"
                continue

            # Parse dinner lines (Day X: Recipe ID Y - Title)
            if line.lower().startswith("day ") and ":" in line:
                parts = line.split(":", 1)
                day_label = parts[0].strip()
                recipe_text = parts[1].strip()

                # Extract recipe ID
                recipe_id = self._extract_recipe_id(recipe_text)

                if recipe_id and recipe_id in recipe_lookup:
                    recipe = recipe_lookup[recipe_id]
                    dinners.append(
                        {
                            "day": day_label,
                            "recipe_id": recipe_id,
                            "recipe_title": recipe.title_en,
                            "recipe": recipe,
                        }
                    )

        return DinnerPlan(dinners=dinners, reasoning=reasoning.strip())

    def _extract_recipe_id(self, text: str) -> Optional[int]:
        """Extract recipe ID from text like 'Recipe ID 5 - Title'."""
        import re

        # Look for patterns like "Recipe ID 5", "ID 5", or just "5 -"
        patterns = [
            r"Recipe ID (\d+)",
            r"ID (\d+)",
            r"^(\d+)\s*[-:]",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return int(match.group(1))

        return None
