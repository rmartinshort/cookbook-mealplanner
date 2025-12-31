"""
ORM (Object-Relational Mapping) operations for the cookbook meal planner.
Provides CRUD operations for recipes, ingredients, and sync files.
"""

import json
from typing import List, Optional

from cookplanner.models.db import get_db
from cookplanner.models.schema import (
    RecipeExtract,
    Recipe,
    Ingredient,
    Instruction,
    SyncFile,
    DinnerPlanRequest,
    DinnerPlanOption,
    DinnerPlan,
)


def insert_recipe(
    recipe: RecipeExtract,
    source_file: str,
    drive_file_id: Optional[str] = None,
    page_number: Optional[int] = None,
    recipe_index: int = 0,
) -> int:
    """
    Insert a recipe into the database.

    Args:
        recipe: RecipeExtract object with recipe data
        source_file: Name of the source file
        drive_file_id: Google Drive file ID
        page_number: Page number in PDF (if applicable)
        recipe_index: Index of recipe on the page (0-indexed, default 0)

    Returns:
        The ID of the inserted recipe
    """
    db = get_db()

    with db.get_connection() as conn:
        cursor = conn.cursor()

        # Insert recipe
        cursor.execute(
            """
            INSERT INTO recipes (
                title_jp, title_en, summary_en, servings, tags_json,
                source_file, drive_file_id, page_number, recipe_index
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                recipe.title_jp,
                recipe.title_en,
                recipe.summary_en,
                recipe.servings,
                json.dumps(recipe.tags),
                source_file,
                drive_file_id,
                page_number,
                recipe_index,
            ),
        )

        recipe_id = cursor.lastrowid

        # Insert ingredients
        for ing in recipe.ingredients:
            cursor.execute(
                """
                INSERT INTO ingredients (
                    recipe_id, name_jp, name_en, quantity, unit, category, sauce_reference
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    recipe_id,
                    ing.name_jp,
                    ing.name_en,
                    ing.quantity,
                    ing.unit,
                    ing.category,
                    ing.sauce_reference,
                ),
            )

        # Insert instructions
        for inst in recipe.instructions:
            cursor.execute(
                """
                INSERT INTO instructions (
                    recipe_id, step_number, text_jp, text_en
                ) VALUES (?, ?, ?, ?)
            """,
                (recipe_id, inst.step_number, inst.text_jp, inst.text_en),
            )

        conn.commit()

    return recipe_id


def get_recipe(recipe_id: int) -> Optional[Recipe]:
    """
    Get a recipe by ID.

    Args:
        recipe_id: Recipe ID

    Returns:
        Recipe object or None if not found
    """
    db = get_db()

    with db.get_connection() as conn:
        cursor = conn.cursor()

        # Get recipe
        cursor.execute(
            """
            SELECT * FROM recipes WHERE id = ?
        """,
            (recipe_id,),
        )

        row = cursor.fetchone()
        if not row:
            return None

        # Get ingredients
        cursor.execute(
            """
            SELECT * FROM ingredients WHERE recipe_id = ?
        """,
            (recipe_id,),
        )
        ingredients = []
        for ing in cursor.fetchall():
            # Safely extract sauce_reference
            try:
                sauce_ref = ing["sauce_reference"]
            except (KeyError, IndexError):
                sauce_ref = None

            ingredients.append(
                Ingredient(
                    name_jp=ing["name_jp"],
                    name_en=ing["name_en"],
                    quantity=ing["quantity"],
                    unit=ing["unit"],
                    category=ing["category"],
                    sauce_reference=sauce_ref,
                )
            )

        # Get instructions
        cursor.execute(
            """
            SELECT * FROM instructions WHERE recipe_id = ? ORDER BY step_number
        """,
            (recipe_id,),
        )
        instructions = [
            Instruction(
                step_number=inst["step_number"],
                text_jp=inst["text_jp"],
                text_en=inst["text_en"],
            )
            for inst in cursor.fetchall()
        ]

        # Extract recipe_index safely
        try:
            recipe_index = row["recipe_index"]
        except (KeyError, IndexError):
            recipe_index = 0

        return Recipe(
            id=row["id"],
            title_jp=row["title_jp"],
            title_en=row["title_en"],
            summary_en=row["summary_en"],
            servings=row["servings"],
            tags=json.loads(row["tags_json"]) if row["tags_json"] else [],
            source_file=row["source_file"],
            drive_file_id=row["drive_file_id"],
            page_number=row["page_number"],
            recipe_index=recipe_index,
            created_at=row["created_at"],
            ingredients=ingredients,
            instructions=instructions,
        )


def list_recipes(
    limit: Optional[int] = None, offset: int = 0, tag_filter: Optional[str] = None
) -> List[Recipe]:
    """
    List recipes with optional filtering.

    Args:
        limit: Maximum number of recipes to return
        offset: Number of recipes to skip
        tag_filter: Filter by tag (if provided)

    Returns:
        List of Recipe objects
    """
    db = get_db()
    recipes = []

    with db.get_connection() as conn:
        cursor = conn.cursor()

        query = "SELECT * FROM recipes"
        params = []

        if tag_filter:
            query += " WHERE tags_json LIKE ?"
            params.append(f'%"{tag_filter}"%')

        query += " ORDER BY created_at DESC"

        if limit:
            query += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])

        cursor.execute(query, params)

        for row in cursor.fetchall():
            recipe = get_recipe(row["id"])
            if recipe:
                recipes.append(recipe)

    return recipes


def check_already_extracted(
    source_file: str,
    page_number: Optional[int] = None,
    recipe_index: Optional[int] = None,
) -> bool:
    """
    Check if a recipe has already been extracted from a source file/page.

    Args:
        source_file: Name of the source file
        page_number: Page number (optional)
        recipe_index: Recipe index on the page (optional, 0-indexed)

    Returns:
        True if already extracted, False otherwise
    """
    db = get_db()

    with db.get_connection() as conn:
        cursor = conn.cursor()

        if page_number is not None and recipe_index is not None:
            cursor.execute(
                """
                SELECT COUNT(*) as count FROM recipes
                WHERE source_file = ? AND page_number = ? AND recipe_index = ?
            """,
                (source_file, page_number, recipe_index),
            )
        elif page_number is not None:
            cursor.execute(
                """
                SELECT COUNT(*) as count FROM recipes
                WHERE source_file = ? AND page_number = ?
            """,
                (source_file, page_number),
            )
        else:
            cursor.execute(
                """
                SELECT COUNT(*) as count FROM recipes
                WHERE source_file = ?
            """,
                (source_file,),
            )

        result = cursor.fetchone()
        return result["count"] > 0


def search_recipes(query: str, limit: int = 20) -> List[Recipe]:
    """
    Search recipes by text in title or ingredients.

    Args:
        query: Search query
        limit: Maximum number of results

    Returns:
        List of Recipe objects
    """
    db = get_db()
    recipe_ids = set()

    with db.get_connection() as conn:
        cursor = conn.cursor()

        # Search in titles
        cursor.execute(
            """
            SELECT id FROM recipes
            WHERE title_en LIKE ? OR title_jp LIKE ?
            LIMIT ?
        """,
            (f"%{query}%", f"%{query}%", limit),
        )

        for row in cursor.fetchall():
            recipe_ids.add(row["id"])

        # Search in ingredients
        if len(recipe_ids) < limit:
            cursor.execute(
                """
                SELECT DISTINCT recipe_id FROM ingredients
                WHERE name_en LIKE ? OR name_jp LIKE ?
                LIMIT ?
            """,
                (f"%{query}%", f"%{query}%", limit - len(recipe_ids)),
            )

            for row in cursor.fetchall():
                recipe_ids.add(row["recipe_id"])

    # Get full recipe data
    recipes = []
    for recipe_id in list(recipe_ids)[:limit]:
        recipe = get_recipe(recipe_id)
        if recipe:
            recipes.append(recipe)

    return recipes


# Sync file operations


def upsert_sync_file(sync_file: SyncFile) -> int:
    """
    Insert or update a sync file record.

    Args:
        sync_file: SyncFile object

    Returns:
        The ID of the sync file record
    """
    db = get_db()

    with db.get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO sync_files (
                drive_file_id, local_path, last_modified, sync_status, file_type, error_message
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(drive_file_id) DO UPDATE SET
                local_path = excluded.local_path,
                last_modified = excluded.last_modified,
                sync_status = excluded.sync_status,
                file_type = excluded.file_type,
                error_message = excluded.error_message,
                synced_at = CURRENT_TIMESTAMP
        """,
            (
                sync_file.drive_file_id,
                sync_file.local_path,
                sync_file.last_modified,
                sync_file.sync_status,
                sync_file.file_type,
                sync_file.error_message,
            ),
        )

        conn.commit()
        return cursor.lastrowid


def get_sync_file(drive_file_id: str) -> Optional[SyncFile]:
    """
    Get sync file metadata by Drive file ID.

    Args:
        drive_file_id: Google Drive file ID

    Returns:
        SyncFile object or None if not found
    """
    db = get_db()

    with db.get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT * FROM sync_files WHERE drive_file_id = ?
        """,
            (drive_file_id,),
        )

        row = cursor.fetchone()
        if not row:
            return None

        return SyncFile(
            id=row["id"],
            drive_file_id=row["drive_file_id"],
            local_path=row["local_path"],
            last_modified=row["last_modified"],
            sync_status=row["sync_status"],
            file_type=row["file_type"],
            error_message=row["error_message"],
        )


def list_sync_files(status: Optional[str] = None) -> List[SyncFile]:
    """
    List all synced files, optionally filtered by status.

    Args:
        status: Filter by sync status (optional)

    Returns:
        List of SyncFile objects
    """
    db = get_db()
    sync_files = []

    with db.get_connection() as conn:
        cursor = conn.cursor()

        if status:
            cursor.execute(
                """
                SELECT * FROM sync_files WHERE sync_status = ? ORDER BY synced_at DESC
            """,
                (status,),
            )
        else:
            cursor.execute("""
                SELECT * FROM sync_files ORDER BY synced_at DESC
            """)

        for row in cursor.fetchall():
            sync_files.append(
                SyncFile(
                    id=row["id"],
                    drive_file_id=row["drive_file_id"],
                    local_path=row["local_path"],
                    last_modified=row["last_modified"],
                    sync_status=row["sync_status"],
                    file_type=row["file_type"],
                    error_message=row["error_message"],
                )
            )

    return sync_files


# Dinner plan operations


def save_dinner_plan_request(
    user_id: str,
    num_days: int,
    servings: int,
    preferences: Optional[str] = None,
    num_options: int = 3,
) -> int:
    """
    Save a new dinner plan request.

    Args:
        user_id: User ID
        num_days: Number of days to plan
        servings: Servings per dinner
        preferences: Optional dietary preferences
        num_options: Number of options to generate

    Returns:
        The ID of the created request
    """
    db = get_db()

    with db.get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO dinner_plan_requests (
                user_id, num_days, servings, preferences, num_options
            ) VALUES (?, ?, ?, ?, ?)
        """,
            (user_id, num_days, servings, preferences, num_options),
        )

        conn.commit()
        return cursor.lastrowid


def save_dinner_plan_option(
    request_id: int, option_index: int, plan: DinnerPlan
) -> int:
    """
    Save a generated dinner plan option.

    Args:
        request_id: ID of the parent request
        option_index: Index of this option (0-based)
        plan: DinnerPlan object

    Returns:
        The ID of the created option
    """
    db = get_db()

    with db.get_connection() as conn:
        cursor = conn.cursor()

        # Convert plan to JSON, excluding non-serializable Recipe objects
        dinners_for_json = []
        for dinner in plan.dinners:
            # Create a copy without the Recipe object
            dinner_dict = {
                "day": dinner.get("day"),
                "recipe_id": dinner.get("recipe_id"),
                "recipe_title": dinner.get("recipe_title"),
            }
            dinners_for_json.append(dinner_dict)

        plan_json = json.dumps(
            {"dinners": dinners_for_json, "reasoning": plan.reasoning}
        )

        cursor.execute(
            """
            INSERT INTO dinner_plan_options (
                request_id, option_index, plan_json, reasoning
            ) VALUES (?, ?, ?, ?)
        """,
            (request_id, option_index, plan_json, plan.reasoning),
        )

        conn.commit()
        return cursor.lastrowid


def update_chosen_option(request_id: int, chosen_index: int) -> None:
    """
    Update a dinner plan request with the user's chosen option.

    Args:
        request_id: ID of the request
        chosen_index: Index of the chosen option (0-based)
    """
    db = get_db()

    with db.get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE dinner_plan_requests
            SET chosen_option_index = ?
            WHERE id = ?
        """,
            (chosen_index, request_id),
        )

        conn.commit()


def get_plan_history(
    user_id: str, limit: int = 10
) -> List[tuple[DinnerPlanRequest, List[DinnerPlanOption]]]:
    """
    Get dinner plan history for a user.

    Args:
        user_id: User ID
        limit: Maximum number of requests to return

    Returns:
        List of tuples: (request, list of options)
    """
    db = get_db()
    history = []

    with db.get_connection() as conn:
        cursor = conn.cursor()

        # Get requests
        cursor.execute(
            """
            SELECT * FROM dinner_plan_requests
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        """,
            (user_id, limit),
        )

        requests = cursor.fetchall()

        for req_row in requests:
            # Get options for this request
            cursor.execute(
                """
                SELECT * FROM dinner_plan_options
                WHERE request_id = ?
                ORDER BY option_index
            """,
                (req_row["id"],),
            )

            options = []
            for opt_row in cursor.fetchall():
                # Parse the plan JSON
                plan_data = json.loads(opt_row["plan_json"])

                options.append(
                    DinnerPlanOption(
                        id=opt_row["id"],
                        request_id=opt_row["request_id"],
                        option_index=opt_row["option_index"],
                        plan_json=opt_row["plan_json"],
                        reasoning=opt_row["reasoning"],
                    )
                )

            request = DinnerPlanRequest(
                id=req_row["id"],
                user_id=req_row["user_id"],
                num_days=req_row["num_days"],
                servings=req_row["servings"],
                preferences=req_row["preferences"],
                num_options=req_row["num_options"],
                chosen_option_index=req_row["chosen_option_index"],
                created_at=req_row["created_at"],
            )

            history.append((request, options))

    return history


def format_history_for_llm(
    history: List[tuple[DinnerPlanRequest, List[DinnerPlanOption]]]
) -> str:
    """
    Format plan history into a text summary for LLM context.

    Args:
        history: List of (request, options) tuples from get_plan_history

    Returns:
        Formatted text summary of past choices
    """
    if not history:
        return "No previous dinner plans found."

    lines = ["Previous Dinner Plans:"]

    for i, (request, options) in enumerate(history, 1):
        lines.append(f"\n{i}. Request from {request.created_at}:")
        lines.append(f"   - {request.num_days} days, {request.servings} servings")

        if request.preferences:
            lines.append(f"   - Preferences: {request.preferences}")

        # Find chosen option
        if request.chosen_option_index is not None:
            chosen_option = next(
                (
                    opt
                    for opt in options
                    if opt.option_index == request.chosen_option_index
                ),
                None,
            )

            if chosen_option:
                lines.append(f"   - User CHOSE option #{request.chosen_option_index + 1}:")

                # Parse and display the chosen plan
                plan_data = json.loads(chosen_option.plan_json)
                for dinner in plan_data.get("dinners", []):
                    lines.append(
                        f"     * {dinner.get('day')}: {dinner.get('recipe_title')}"
                    )

                lines.append(f"   - Reasoning: {chosen_option.reasoning}")
        else:
            lines.append("   - No option was chosen")

    return "\n".join(lines)
