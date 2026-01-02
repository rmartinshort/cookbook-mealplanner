"""
Shopping list generation by aggregating ingredients from multiple recipes.
Handles ingredient consolidation, unit conversion, and categorization.
"""

from typing import List, Dict, Optional
from collections import defaultdict
from google import genai

from cookplanner.config import Config
from cookplanner.models.orm import get_recipe


class ShoppingList:
    """Represents an aggregated shopping list."""

    def __init__(self, items: Dict[str, List[Dict]]):
        """
        Initialize shopping list.

        Args:
            items: Dictionary mapping category to list of ingredient items
        """
        self.items = items

    def get_categories(self) -> List[str]:
        """Get all categories in the shopping list."""
        return sorted(self.items.keys())

    def get_items_by_category(self, category: str) -> List[Dict]:
        """Get all items in a specific category."""
        return self.items.get(category, [])


class ShoppingListGenerator:
    """Generate shopping lists from recipes."""

    def __init__(self):
        """Initialize shopping list generator."""
        pass

    def generate_from_recipe_ids(
        self, recipe_ids: List[int], scale_servings: Optional[Dict[int, int]] = None
    ) -> ShoppingList:
        """
        Generate a shopping list from a list of recipe IDs.

        Args:
            recipe_ids: List of recipe IDs to include
            scale_servings: Optional dict mapping recipe_id to desired servings

        Returns:
            ShoppingList object with aggregated ingredients
        """
        # Load all recipes
        recipes = []
        for recipe_id in recipe_ids:
            recipe = get_recipe(recipe_id)
            if recipe:
                recipes.append(recipe)

        if not recipes:
            return ShoppingList(items={})

        # Aggregate ingredients
        aggregated = self._aggregate_ingredients(recipes, scale_servings)

        return ShoppingList(items=aggregated)

    def _aggregate_ingredients(
        self, recipes: List, scale_servings: Optional[Dict[int, int]]
    ) -> Dict[str, List[Dict]]:
        """
        Aggregate ingredients from multiple recipes.

        Groups by category and consolidates similar ingredients.
        """
        # Group ingredients by category
        by_category = defaultdict(list)

        for recipe in recipes:
            # Calculate scaling factor if needed
            scale_factor = 1.0
            if scale_servings and recipe.id in scale_servings:
                target_servings = scale_servings[recipe.id]
                scale_factor = target_servings / recipe.servings

            for ing in recipe.ingredients:
                # Determine category
                category = ing.category if ing.category else "Other"

                # Create ingredient entry
                entry = {
                    "name_en": ing.name_en,
                    "name_jp": ing.name_jp,
                    "quantity": ing.quantity,
                    "unit": ing.unit,
                    "scale_factor": scale_factor,
                    "recipe_title": recipe.title_en,
                }

                by_category[category].append(entry)

        # Consolidate similar ingredients within each category
        consolidated = {}
        for category, ingredients in by_category.items():
            consolidated[category] = self._consolidate_ingredients(ingredients)

        return consolidated

    def _consolidate_ingredients(self, ingredients: List[Dict]) -> List[Dict]:
        """
        Consolidate similar ingredients.

        For now, groups by exact name match. Could be enhanced with fuzzy matching.
        """
        # Group by ingredient name
        by_name = defaultdict(list)

        for ing in ingredients:
            key = (ing["name_en"].lower(), ing["unit"].lower() if ing["unit"] else "")
            by_name[key].append(ing)

        # Create consolidated list
        consolidated = []

        for (name_en, unit), items in by_name.items():
            if len(items) == 1:
                # Single item, no consolidation needed
                item = items[0]
                consolidated.append(
                    {
                        "name_en": item["name_en"],
                        "name_jp": item["name_jp"],
                        "quantity": self._scale_quantity(
                            item["quantity"], item["scale_factor"]
                        ),
                        "unit": item["unit"],
                        "recipes": [item["recipe_title"]],
                    }
                )
            else:
                # Multiple items with same name/unit - try to sum quantities
                total_quantity = self._sum_quantities(items)
                recipes = [item["recipe_title"] for item in items]

                # Use the first item's names
                consolidated.append(
                    {
                        "name_en": items[0]["name_en"],
                        "name_jp": items[0]["name_jp"],
                        "quantity": total_quantity,
                        "unit": items[0]["unit"],
                        "recipes": recipes,
                    }
                )

        # Sort by name
        consolidated.sort(key=lambda x: x["name_en"])

        return consolidated

    def _scale_quantity(self, quantity: str, scale_factor: float) -> str:
        """
        Scale a quantity by a factor.

        Attempts to parse numeric quantities and scale them.
        """
        if not quantity or scale_factor == 1.0:
            return quantity

        try:
            # Try to parse as a number
            qty = float(quantity)
            scaled = qty * scale_factor

            # Format nicely
            if scaled == int(scaled):
                return str(int(scaled))
            else:
                return f"{scaled:.1f}"
        except ValueError:
            # If it contains a number at the start, try to scale that
            import re

            match = re.match(r"^([\d.]+)\s*(.*)", quantity)
            if match:
                qty = float(match.group(1))
                rest = match.group(2)
                scaled = qty * scale_factor

                if scaled == int(scaled):
                    return f"{int(scaled)} {rest}".strip()
                else:
                    return f"{scaled:.1f} {rest}".strip()

            # Can't parse, return as-is
            return quantity

    def _sum_quantities(self, items: List[Dict]) -> str:
        """
        Sum quantities from multiple ingredient items.

        Returns a string representation of the total.
        """
        total = 0.0
        unit_suffix = ""

        for item in items:
            qty_str = self._scale_quantity(item["quantity"], item["scale_factor"])

            try:
                # Try to extract numeric value
                import re

                match = re.match(r"^([\d.]+)\s*(.*)", qty_str)
                if match:
                    qty = float(match.group(1))
                    if not unit_suffix and match.group(2):
                        unit_suffix = match.group(2)
                    total += qty
                else:
                    # Try to parse as plain number
                    total += float(qty_str)
            except (ValueError, AttributeError):
                # Can't sum, return first quantity with note
                return f"{qty_str} (multiple recipes)"

        # Format total
        if total == int(total):
            result = str(int(total))
        else:
            result = f"{total:.1f}"

        if unit_suffix:
            result += f" {unit_suffix}"

        return result

    def consolidate_with_llm(self, shopping_list: ShoppingList) -> str:
        """
        Use LLM to consolidate the shopping list into a practical, store-ready format.

        Args:
            shopping_list: ShoppingList object to consolidate

        Returns:
            Consolidated shopping list as formatted text
        """
        # Convert shopping list to text format
        list_text = self._format_shopping_list_for_llm(shopping_list)

        # Create prompt for LLM
        prompt = f"""You are a helpful shopping assistant. I have an aggregated shopping list from multiple recipes, but it has many issues:
- Duplicate ingredients with different quantities
- Overly precise measurements
- Similar ingredients that could be combined
- Items that appear multiple times in different forms

Please consolidate this into a practical, store-ready shopping list that I can actually use at the grocery store.

Guidelines:
1. Combine duplicate or similar ingredients (e.g., multiple "Soy sauce" entries → one "Soy sauce" entry)
2. Merge related items where it makes sense (e.g., "Beaten egg" + "Egg" → just "Eggs")
3. Round quantities to practical amounts (e.g., "2.5 tbsp" → "3 tbsp" or "30 g butter" → "small amount butter")
4. For "to taste" ingredients used multiple times, just list once
5. Use approximate, store-friendly quantities (e.g., "1-2 bunches", "about 250g", "small pack")
6. Group by category but keep it simple
7. Remove overly specific details if they don't matter for shopping

Current shopping list:
{list_text}

Please provide a consolidated, practical shopping list organized by category. Be concise and practical - I want to be able to quickly buy these items at the store."""

        # Call Gemini
        client = genai.Client(api_key=Config.GEMINI_API_KEY)
        response = client.models.generate_content(
            model=Config.GEMINI_MODEL_NAME, contents=prompt
        )

        return response.text

    def _format_shopping_list_for_llm(self, shopping_list: ShoppingList) -> str:
        """Format shopping list as text for LLM processing."""
        lines = []

        for category in shopping_list.get_categories():
            lines.append(f"\n{category}:")
            items = shopping_list.get_items_by_category(category)

            for item in items:
                qty_unit = f"{item['quantity']} {item['unit']}".strip()
                name = item["name_en"]

                if len(item["recipes"]) > 1:
                    lines.append(
                        f"  • {qty_unit} {name} (used in {len(item['recipes'])} recipes)"
                    )
                else:
                    lines.append(f"  • {qty_unit} {name}")

        return "\n".join(lines)
