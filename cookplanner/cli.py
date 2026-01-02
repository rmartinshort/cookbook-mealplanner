"""
Command-line interface for the cookbook meal planner.
Provides commands for syncing, extracting, and managing recipes.
"""

from pathlib import Path
from typing import Optional, List
import typer
from rich.console import Console
from rich.table import Table

from cookplanner.config import Config
from cookplanner.models.db import init_database
from cookplanner.models.orm import (
    list_recipes,
    get_recipe,
    search_recipes,
    save_dinner_plan_request,
    save_dinner_plan_option,
    update_chosen_option,
)
from cookplanner.sync.file_sync import sync_from_drive
from cookplanner.extraction.extract_recipe import RecipeExtractor
from cookplanner.planning.meal_planner import MealPlanner
from cookplanner.planning.shopping_list import ShoppingListGenerator

# Create Typer app
app = typer.Typer(
    name="cookplanner", help="AI-powered meal planning from Japanese cookbooks"
)

# Rich console for pretty output
console = Console()


@app.command()
def init_db():
    """Initialize the database with required tables."""
    try:
        Config.validate()
        console.print("[bold green]Initializing database...[/bold green]")

        _ = init_database()
        db_path = Config.get_db_path()

        console.print(f"[green]✓[/green] Database initialized at: {db_path}")

    except Exception as e:
        console.print(f"[red]✗ Error:[/red] {e}")
        raise typer.Exit(code=1)


@app.command()
def sync_drive():
    """Sync cookbook files from Google Drive."""
    try:
        Config.validate()
        console.print("[bold blue]Syncing files from Google Drive...[/bold blue]")

        stats = sync_from_drive()

        console.print("\n[bold]Sync Summary:[/bold]")
        console.print(f"  New files: {stats['new']}")
        console.print(f"  Updated files: {stats['updated']}")
        console.print(f"  Skipped (unchanged): {stats['skipped']}")
        console.print(f"  Pages extracted: {stats['pages_extracted']}")
        console.print(f"  Errors: {stats['errors']}")

        if stats["errors"] > 0:
            console.print("\n[yellow]Some files had errors. Check logs above.[/yellow]")
        else:
            console.print("\n[green]✓ Sync completed successfully![/green]")

    except Exception as e:
        console.print(f"[red]✗ Error:[/red] {e}")
        raise typer.Exit(code=1)


@app.command()
def extract_recipe(
    image: str = typer.Argument(..., help="Path to image file"),
    save: bool = typer.Option(True, help="Save to database"),
):
    """Extract a recipe from a single image."""
    try:
        Config.validate()
        image_path = Path(image)

        if not image_path.exists():
            console.print(f"[red]✗ Error:[/red] Image not found: {image}")
            raise typer.Exit(code=1)

        console.print(
            f"[bold blue]Extracting recipe from:[/bold blue] {image_path.name}"
        )

        extractor = RecipeExtractor()
        result = extractor.extract_from_image(image_path, save_to_db=save)

        if save:
            console.print(f"[green]✓ Recipe saved with ID: {result}[/green]")
        else:
            # Print extracted recipe
            recipe = result
            console.print(f"\n[bold]{recipe.title_en}[/bold] ({recipe.title_jp})")
            console.print(f"Servings: {recipe.servings}")
            console.print(f"Tags: {', '.join(recipe.tags)}")
            console.print(f"\n{recipe.summary_en}")

    except Exception as e:
        console.print(f"[red]✗ Error:[/red] {e}")
        raise typer.Exit(code=1)


@app.command()
def import_recipes(
    images_dir: Optional[str] = typer.Option(
        None, help="Directory with images (default: data/images)"
    ),
    skip_existing: bool = typer.Option(False, help="Skip already-extracted recipes"),
    expect_multiple: bool = typer.Option(True, help="Expect multiple recipes per page"),
):
    """Import recipes from all images in a directory."""
    try:
        Config.validate()

        if images_dir:
            images_path = Path(images_dir)
        else:
            images_path = Config.get_images_dir()

        if not images_path.exists():
            console.print(f"[red]✗ Error:[/red] Directory not found: {images_path}")
            raise typer.Exit(code=1)

        # Get all image files
        image_files = []
        for ext in ["*.jpg", "*.jpeg", "*.png"]:
            image_files.extend(images_path.glob(ext))

        if not image_files:
            console.print(f"[yellow]No image files found in {images_path}[/yellow]")
            return

        console.print(
            f"[bold blue]Found {len(image_files)} images to process[/bold blue]"
        )

        extractor = RecipeExtractor()
        stats = extractor.extract_batch(
            image_files, skip_existing=skip_existing, expect_multiple=expect_multiple
        )

        console.print("\n[bold]Import Summary:[/bold]")
        console.print(f"  Total images: {stats['total']}")
        console.print(f"  Extracted: {stats['extracted']}")
        console.print(f"  Recipes saved: {stats['recipe_count']}")
        console.print(f"  Skipped: {stats['skipped']}")
        console.print(f"  Errors: {stats['errors']}")

        if stats["errors"] > 0:
            console.print(
                "\n[yellow]Some images had errors. Check logs above.[/yellow]"
            )
        else:
            console.print("\n[green]✓ Import completed successfully![/green]")

    except Exception as e:
        console.print(f"[red]✗ Error:[/red] {e}")
        raise typer.Exit(code=1)


@app.command()
def list(
    limit: int = typer.Option(20, help="Maximum number of recipes to show"),
    tag: Optional[str] = typer.Option(None, help="Filter by tag"),
):
    """List recipes in the database."""
    try:
        recipes = list_recipes(limit=limit, tag_filter=tag)

        if not recipes:
            console.print("[yellow]No recipes found[/yellow]")
            return

        # Create table
        table = Table(title=f"Recipes ({len(recipes)} shown)")
        table.add_column("ID", style="cyan")
        table.add_column("Title (EN)", style="green")
        table.add_column("Title (JP)", style="blue")
        table.add_column("Tags", style="yellow")
        table.add_column("Source", style="magenta")

        for recipe in recipes:
            table.add_row(
                str(recipe.id),
                recipe.title_en[:40],
                recipe.title_jp[:30],
                ", ".join(recipe.tags[:3]),
                recipe.source_file[:30],
            )

        console.print(table)

    except Exception as e:
        console.print(f"[red]✗ Error:[/red] {e}")
        raise typer.Exit(code=1)


@app.command()
def show(recipe_id: int = typer.Argument(..., help="Recipe ID to display")):
    """Show detailed information for a recipe."""
    try:
        recipe = get_recipe(recipe_id)

        if not recipe:
            console.print(f"[red]✗ Recipe not found: {recipe_id}[/red]")
            raise typer.Exit(code=1)

        # Display recipe
        console.print(f"\n[bold cyan]#{recipe.id}[/bold cyan]")
        console.print(f"[bold green]{recipe.title_en}[/bold green]")
        console.print(f"[blue]{recipe.title_jp}[/blue]")
        console.print(f"\n{recipe.summary_en}")
        console.print(f"\n[bold]Servings:[/bold] {recipe.servings}")
        console.print(f"[bold]Tags:[/bold] {', '.join(recipe.tags)}")
        console.print(f"[bold]Source:[/bold] {recipe.source_file}")
        if recipe.page_number:
            console.print(f"[bold]Page:[/bold] {recipe.page_number}")

        # Ingredients - group by sauce_reference
        console.print("\n[bold yellow]Ingredients:[/bold yellow]")

        # Separate grouped and ungrouped ingredients
        grouped = {}
        ungrouped = []

        for ing in recipe.ingredients:
            if ing.sauce_reference:
                if ing.sauce_reference not in grouped:
                    grouped[ing.sauce_reference] = []
                grouped[ing.sauce_reference].append(ing)
            else:
                ungrouped.append(ing)

        # Display ungrouped ingredients first
        for ing in ungrouped:
            console.print(
                f"  • {ing.name_en} ({ing.name_jp}): {ing.quantity} {ing.unit}"
            )

        # Display grouped ingredients
        for group_label in sorted(grouped.keys()):
            console.print(f"\n  [bold magenta]Group {group_label}:[/bold magenta]")
            for ing in grouped[group_label]:
                console.print(
                    f"    • {ing.name_en} ({ing.name_jp}): {ing.quantity} {ing.unit}"
                )

        # Instructions
        console.print("\n[bold yellow]Instructions:[/bold yellow]")
        for inst in recipe.instructions:
            console.print(f"  {inst.step_number}. {inst.text_en}")
            console.print(f"     ({inst.text_jp})")

    except Exception as e:
        console.print(f"[red]✗ Error:[/red] {e}")
        raise typer.Exit(code=1)


@app.command()
def search(query: str = typer.Argument(..., help="Search query")):
    """Search recipes by title or ingredient."""
    try:
        recipes = search_recipes(query)

        if not recipes:
            console.print(f"[yellow]No recipes found matching '{query}'[/yellow]")
            return

        console.print(f"\n[bold]Found {len(recipes)} recipe(s):[/bold]\n")

        for recipe in recipes:
            console.print(f"[cyan]#{recipe.id}[/cyan] [green]{recipe.title_en}[/green]")
            console.print(f"  {recipe.summary_en}")
            console.print(f"  Tags: {', '.join(recipe.tags)}\n")

    except Exception as e:
        console.print(f"[red]✗ Error:[/red] {e}")
        raise typer.Exit(code=1)


@app.command()
def plan_dinners(
    days: int = typer.Option(7, help="Number of days to plan"),
    servings: int = typer.Option(2, help="Servings per dinner"),
    preferences: Optional[str] = typer.Option(None, help="Dietary preferences"),
    num_options: int = typer.Option(3, help="Number of plan options to generate"),
    user_id: str = typer.Option("default", help="User ID for tracking preferences"),
):
    """Generate multiple dinner plan options and choose one."""
    try:
        Config.validate()
        console.print(
            f"[bold blue]Generating {num_options} different {days}-day dinner plans...[/bold blue]\n"
        )

        # Generate multiple plan options
        planner = MealPlanner()
        plan_options = planner.create_dinner_plan_options(
            num_days=days,
            servings=servings,
            num_options=num_options,
            preferences=preferences,
            user_id=user_id,
        )

        if not plan_options:
            console.print("[yellow]Could not generate dinner plans[/yellow]")
            return

        # Save request to database
        request_id = save_dinner_plan_request(
            user_id=user_id,
            num_days=days,
            servings=servings,
            preferences=preferences,
            num_options=num_options,
        )

        # Save all options to database
        for idx, plan in enumerate(plan_options):
            save_dinner_plan_option(request_id=request_id, option_index=idx, plan=plan)

        # Display all options
        console.print("[bold green]Here are your dinner plan options:[/bold green]\n")

        for idx, plan in enumerate(plan_options, 1):
            console.print(f"[bold cyan]Option {idx}:[/bold cyan]")

            if not plan.dinners:
                console.print("  [yellow]No dinners in this plan[/yellow]\n")
                continue

            for dinner in plan.dinners:
                console.print(
                    f"  {dinner['day']}: {dinner['recipe_title']} "
                    f"[dim](ID: {dinner['recipe_id']})[/dim]"
                )

            # Display reasoning
            if plan.reasoning:
                console.print("\n  [bold]Why this plan:[/bold]")
                # Truncate reasoning if too long
                reasoning_lines = plan.reasoning.split("\n")[:3]
                for line in reasoning_lines:
                    console.print(f"  {line}")
                if len(plan.reasoning.split("\n")) > 3:
                    console.print("  [dim]...[/dim]")

            console.print()  # Blank line between options

        # Ask user to choose
        console.print("[bold]Which option do you prefer?[/bold]")
        choice = typer.prompt(
            f"Enter option number (1-{num_options})",
            type=int,
            default=1,
        )

        # Validate choice
        if choice < 1 or choice > num_options:
            console.print(
                f"[red]Invalid choice. Must be between 1 and {num_options}[/red]"
            )
            raise typer.Exit(code=1)

        # Update database with chosen option
        chosen_index = choice - 1  # Convert to 0-based index
        update_chosen_option(request_id, chosen_index)

        chosen_plan = plan_options[chosen_index]

        # Display chosen plan
        console.print(
            "\n[bold green]✓ Great choice! Here's your selected plan:[/bold green]\n"
        )

        for dinner in chosen_plan.dinners:
            console.print(
                f"[cyan]{dinner['day']}:[/cyan] {dinner['recipe_title']} "
                f"[dim](Recipe ID: {dinner['recipe_id']})[/dim]"
            )

        # Display full reasoning for chosen plan
        if chosen_plan.reasoning:
            console.print("\n[bold]Why this plan works:[/bold]")
            console.print(chosen_plan.reasoning)

        # Show next steps
        recipe_ids_str = " ".join(map(str, chosen_plan.get_all_recipe_ids()))
        console.print(
            f"\n[dim]Tip: Generate a shopping list with:[/dim] "
            f"[green]cookplanner shopping-list {recipe_ids_str}[/green]"
        )
        console.print(
            f"[dim]Or for a practical, consolidated list:[/dim] "
            f"[green]cookplanner shopping-list --consolidate {recipe_ids_str}[/green]"
        )

    except Exception as e:
        console.print(f"[red]✗ Error:[/red] {e}")
        raise typer.Exit(code=1)


@app.command()
def shopping_list(
    recipe_ids: List[int] = typer.Argument(..., help="Recipe IDs"),
    consolidate: bool = typer.Option(
        False,
        "--consolidate",
        "-c",
        help="Use AI to consolidate into practical shopping list",
    ),
):
    """Generate a shopping list from recipe IDs."""
    try:
        if not recipe_ids:
            console.print("[red]✗ Error:[/red] Please provide at least one recipe ID")
            raise typer.Exit(code=1)

        console.print(
            f"[bold blue]Generating shopping list for {len(recipe_ids)} recipes...[/bold blue]\n"
        )

        generator = ShoppingListGenerator()
        shopping_list = generator.generate_from_recipe_ids(recipe_ids)

        if not shopping_list.items:
            console.print("[yellow]No ingredients found[/yellow]")
            return

        # If consolidate flag is set, use LLM to create practical list
        if consolidate:
            console.print(
                "[bold blue]Consolidating with AI for practical shopping...[/bold blue]\n"
            )
            consolidated_text = generator.consolidate_with_llm(shopping_list)
            console.print("[bold green]Consolidated Shopping List:[/bold green]\n")
            console.print(consolidated_text)
            return

        # Display raw aggregated shopping list by category
        console.print("[bold green]Shopping List:[/bold green]\n")

        for category in shopping_list.get_categories():
            console.print(f"[bold cyan]{category}:[/bold cyan]")

            items = shopping_list.get_items_by_category(category)
            for item in items:
                qty_unit = f"{item['quantity']} {item['unit']}".strip()
                name = f"{item['name_en']} ({item['name_jp']})"

                # Show which recipes use this ingredient
                if len(item["recipes"]) == 1:
                    console.print(f"  • {qty_unit} {name}")
                else:
                    console.print(
                        f"  • {qty_unit} {name} [dim](used in {len(item['recipes'])} recipes)[/dim]"
                    )

            console.print()  # Blank line between categories

        console.print(
            f"[dim]Total ingredients: {sum(len(shopping_list.get_items_by_category(cat)) for cat in shopping_list.get_categories())}[/dim]"
        )
        console.print(
            "\n[dim]Tip: Use --consolidate flag for AI-powered practical shopping list[/dim]"
        )

    except Exception as e:
        console.print(f"[red]✗ Error:[/red] {e}")
        raise typer.Exit(code=1)


@app.command()
def config_check():
    """Check configuration and validate setup."""
    console.print("[bold]Configuration Check[/bold]\n")

    try:
        Config.validate()
        console.print("[green]✓ All configuration is valid[/green]\n")

        console.print(f"Gemini API Key: {'*' * 20}{Config.GEMINI_API_KEY[-10:]}")
        console.print(f"Drive Folder ID: {Config.GDRIVE_FOLDER_ID}")
        console.print(f"Service Account: {Config.get_service_account_path()}")
        console.print(f"Data Directory: {Config.get_data_dir()}")
        console.print(f"Database: {Config.get_db_path()}")

        # Check if database exists
        if Config.get_db_path().exists():
            console.print("\n[green]✓ Database exists[/green]")
        else:
            console.print(
                "\n[yellow]⚠ Database not initialized. Run 'init-db' first.[/yellow]"
            )

    except ValueError as e:
        console.print(f"[red]✗ Configuration error:[/red]\n{e}")
        raise typer.Exit(code=1)


def main():
    """Main entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
