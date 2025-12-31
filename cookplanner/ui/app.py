"""
Streamlit web UI for Cookplan AI meal planner.
Provides an intuitive interface for generating meal plans and shopping lists.
"""

import streamlit as st
from typing import List, Optional

from cookplanner.config import Config
from cookplanner.models.schema import DinnerPlan
from cookplanner.models.orm import (
    save_dinner_plan_request,
    save_dinner_plan_option,
    update_chosen_option,
    get_recipe,
    get_plan_history,
    format_history_for_llm,
    delete_plan_history,
)
from cookplanner.planning.meal_planner import MealPlanner
from cookplanner.planning.shopping_list import ShoppingListGenerator


# Page configuration
st.set_page_config(
    page_title="Cookplan AI",
    page_icon="👩‍🍳",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Custom CSS for better styling
st.markdown(
    """
    <style>
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        text-align: center;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.2rem;
        text-align: center;
        color: #666;
        margin-bottom: 2rem;
    }
    .meal-option {
        padding: 1rem;
        border-radius: 0.5rem;
        border: 2px solid #e0e0e0;
        margin-bottom: 1rem;
    }
    .selected-option {
        border-color: #4CAF50;
        background-color: #f1f8f4;
    }
    .shopping-list {
        background-color: #f8f9fa;
        padding: 1.5rem;
        border-radius: 0.5rem;
        font-family: monospace;
        white-space: pre-wrap;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def initialize_session_state():
    """Initialize Streamlit session state variables."""
    if "plans_generated" not in st.session_state:
        st.session_state.plans_generated = None
    if "request_id" not in st.session_state:
        st.session_state.request_id = None
    if "selected_option_index" not in st.session_state:
        st.session_state.selected_option_index = None
    if "chosen_plan" not in st.session_state:
        st.session_state.chosen_plan = None
    if "shopping_list" not in st.session_state:
        st.session_state.shopping_list = None
    if "user_id" not in st.session_state:
        st.session_state.user_id = "default"
    if "history_context" not in st.session_state:
        st.session_state.history_context = None
    if "raw_shopping_list" not in st.session_state:
        st.session_state.raw_shopping_list = None
    if "show_delete_confirmation" not in st.session_state:
        st.session_state.show_delete_confirmation = False


def reset_session():
    """Reset session state for new meal plan generation."""
    st.session_state.plans_generated = None
    st.session_state.request_id = None
    st.session_state.selected_option_index = None
    st.session_state.chosen_plan = None
    st.session_state.shopping_list = None
    st.session_state.history_context = None
    st.session_state.raw_shopping_list = None


def generate_meal_plans(
    num_days: int, servings: int, num_options: int, preferences: str, use_history: bool = True
) -> List[DinnerPlan]:
    """Generate multiple meal plan options."""
    # Get and store history context for transparency (if enabled)
    if use_history:
        history = get_plan_history(st.session_state.user_id, limit=10)
        history_context = format_history_for_llm(history)
        st.session_state.history_context = history_context
    else:
        st.session_state.history_context = "History not used for this generation."

    planner = MealPlanner()

    plans = planner.create_dinner_plan_options(
        num_days=num_days,
        servings=servings,
        num_options=num_options,
        preferences=preferences if preferences else None,
        user_id=st.session_state.user_id,
        use_history=use_history,
    )

    # Save request to database
    request_id = save_dinner_plan_request(
        user_id=st.session_state.user_id,
        num_days=num_days,
        servings=servings,
        preferences=preferences if preferences else None,
        num_options=num_options,
    )

    # Save all options
    for idx, plan in enumerate(plans):
        save_dinner_plan_option(request_id=request_id, option_index=idx, plan=plan)

    st.session_state.request_id = request_id
    return plans


def generate_shopping_list(plan: DinnerPlan) -> str:
    """Generate consolidated shopping list from meal plan."""
    generator = ShoppingListGenerator()

    # Get recipe IDs
    recipe_ids = plan.get_all_recipe_ids()

    # Generate raw shopping list
    shopping_list = generator.generate_from_recipe_ids(recipe_ids)

    # Store raw list for transparency (formatted)
    raw_list_text = generator._format_shopping_list_for_llm(shopping_list)
    st.session_state.raw_shopping_list = raw_list_text

    # Consolidate with LLM
    consolidated = generator.consolidate_with_llm(shopping_list)

    return consolidated


def display_meal_plan(plan: DinnerPlan, option_number: int, show_full_reasoning: bool = False, show_recipe_details: bool = False):
    """Display a single meal plan option."""
    st.markdown(f"### Option {option_number}")

    if not plan.dinners:
        st.warning("No dinners in this plan")
        return

    # Display dinners
    for dinner in plan.dinners:
        col1, col2 = st.columns([1, 3])
        with col1:
            st.markdown(f"**{dinner['day']}**")
        with col2:
            st.markdown(f"{dinner['recipe_title']} _(ID: {dinner['recipe_id']})_")

    # Display reasoning
    if plan.reasoning:
        if show_full_reasoning:
            st.markdown("**Why this plan:**")
            st.info(plan.reasoning)
        else:
            with st.expander("💡 Why this plan?"):
                st.write(plan.reasoning)

    # Display recipe details if requested
    if show_recipe_details:
        st.markdown("**📖 Recipe Details:**")
        for dinner in plan.dinners:
            with st.expander(f"{dinner['day']}: {dinner['recipe_title']}", expanded=False):
                display_recipe_details(dinner['recipe_id'], dinner['recipe_title'])


def display_recipe_details(recipe_id: int, recipe_title: str):
    """Display detailed recipe information including ingredients and instructions."""
    recipe = get_recipe(recipe_id)

    if not recipe:
        st.error(f"Recipe {recipe_id} not found")
        return

    # Recipe header with Japanese and English titles
    st.markdown(f"#### {recipe.title_en}")
    st.markdown(f"*{recipe.title_jp}*")

    # Summary and metadata
    st.markdown(f"**Servings:** {recipe.servings}")
    if recipe.tags:
        st.markdown(f"**Tags:** {', '.join(recipe.tags)}")
    if recipe.summary_en:
        st.info(recipe.summary_en)

    # Ingredients section
    st.markdown("##### 🥘 Ingredients")

    # Group ingredients by sauce_reference
    grouped = {}
    ungrouped = []

    for ing in recipe.ingredients:
        if ing.sauce_reference:
            if ing.sauce_reference not in grouped:
                grouped[ing.sauce_reference] = []
            grouped[ing.sauce_reference].append(ing)
        else:
            ungrouped.append(ing)

    # Display ungrouped ingredients
    for ing in ungrouped:
        qty_unit = f"{ing.quantity} {ing.unit}".strip()
        st.markdown(f"- **{ing.name_en}** ({ing.name_jp}): {qty_unit}")

    # Display grouped ingredients
    for group_label in sorted(grouped.keys()):
        st.markdown(f"\n**Group {group_label}:**")
        for ing in grouped[group_label]:
            qty_unit = f"{ing.quantity} {ing.unit}".strip()
            st.markdown(f"- **{ing.name_en}** ({ing.name_jp}): {qty_unit}")

    # Instructions section
    st.markdown("##### 📝 Instructions")
    for inst in recipe.instructions:
        st.markdown(f"**{inst.step_number}.** {inst.text_en}")
        st.markdown(f"   *{inst.text_jp}*")
        st.markdown("")  # Blank line between steps


def main():
    """Main Streamlit application."""
    initialize_session_state()

    # Validate configuration
    try:
        Config.validate()
    except ValueError as e:
        st.error("❌ Configuration Error")
        st.error(str(e))
        st.info(
            "Please ensure your .env file is properly configured with GEMINI_API_KEY, "
            "GDRIVE_FOLDER_ID, and GDRIVE_SERVICE_ACCOUNT_FILE."
        )
        st.stop()

    # Header
    st.markdown('<div class="main-header">🏠👩‍🍳 Cookplan AI</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sub-header">Your AI-Powered Meal Planning Assistant</div>',
        unsafe_allow_html=True,
    )

    st.markdown("---")

    # Settings Section
    st.markdown("### 📋 Plan Settings")

    col1, col2, col3 = st.columns(3)

    with col1:
        num_days = st.selectbox(
            "Number of Days",
            options=list(range(3, 15)),
            index=4,  # Default to 7 days
            help="How many days to plan dinners for",
        )

    with col2:
        servings = st.selectbox(
            "Servings per Meal",
            options=list(range(1, 7)),
            index=1,  # Default to 2 servings
            help="Number of servings for each dinner",
        )

    with col3:
        num_options = st.selectbox(
            "Number of Options",
            options=list(range(2, 6)),
            index=1,  # Default to 3 options
            help="How many different meal plans to generate",
        )

    preferences = st.text_input(
        "Dietary Preferences (optional)",
        placeholder="e.g., vegetarian, lots of vegetables, we like ground pork dishes",
        help="Any dietary preferences or restrictions",
    )

    # History management controls
    st.markdown("### 🧠 Learning & History")
    col1, col2 = st.columns([3, 1])

    with col1:
        use_history = st.radio(
            "Plan History Usage",
            options=["Use history (AI learns from past choices)", "Don't use history (fresh start)"],
            index=0,
            help="Choose whether the AI should learn from your previous meal plan selections",
            horizontal=True,
        )
        use_history_bool = use_history.startswith("Use history")

    with col2:
        # Delete history button with confirmation
        if not st.session_state.show_delete_confirmation:
            if st.button("🗑️ Delete History", help="Permanently delete all your plan history"):
                # Check if there's any history
                history = get_plan_history(st.session_state.user_id, limit=1000)
                if len(history) == 0:
                    st.info("No history to delete.")
                else:
                    st.session_state.show_delete_confirmation = True
                    st.rerun()
        else:
            # Show confirmation button
            history = get_plan_history(st.session_state.user_id, limit=1000)
            history_count = len(history)

            col_a, col_b = st.columns(2)
            with col_a:
                if st.button(f"⚠️ Confirm Delete", type="secondary", use_container_width=True):
                    deleted_count = delete_plan_history(st.session_state.user_id)
                    st.success(f"✅ Deleted {deleted_count} plan(s)!")
                    st.session_state.show_delete_confirmation = False
                    st.rerun()
            with col_b:
                if st.button("Cancel", use_container_width=True):
                    st.session_state.show_delete_confirmation = False
                    st.rerun()
            st.caption(f"This will delete {history_count} plan(s)")

    st.markdown("---")

    # Generate button
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("Generate Meal Plans!", type="primary", use_container_width=True):
            reset_session()

            with st.spinner(f"Generating {num_options} meal plan options... This may take a minute."):
                try:
                    plans = generate_meal_plans(num_days, servings, num_options, preferences, use_history_bool)
                    st.session_state.plans_generated = plans
                    st.success(f"✅ Generated {len(plans)} meal plan options!")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error generating meal plans: {str(e)}")
                    st.stop()

    # Display generated plans
    if st.session_state.plans_generated:
        st.markdown("---")
        st.markdown("### 🍽️ Meal Plan Options")
        st.markdown("Review the options below and select your preferred plan.")

        # Radio button for selection
        option_labels = [f"Option {i+1}" for i in range(len(st.session_state.plans_generated))]
        selected_label = st.radio(
            "Choose your plan:",
            options=option_labels,
            index=st.session_state.selected_option_index if st.session_state.selected_option_index is not None else 0,
            horizontal=True,
        )
        st.session_state.selected_option_index = option_labels.index(selected_label)

        # Display all options
        for idx, plan in enumerate(st.session_state.plans_generated):
            is_selected = idx == st.session_state.selected_option_index

            with st.container():
                if is_selected:
                    st.markdown('<div class="meal-option selected-option">', unsafe_allow_html=True)
                else:
                    st.markdown('<div class="meal-option">', unsafe_allow_html=True)

                display_meal_plan(plan, idx + 1, show_full_reasoning=False, show_recipe_details=True)

                st.markdown('</div>', unsafe_allow_html=True)

        # Show AI context/prompts insight
        if st.session_state.history_context:
            with st.expander("🔍 View AI Context (What the model knows about your preferences)"):
                st.markdown("**Past Meal Plan Choices:**")
                st.text(st.session_state.history_context)
                st.markdown(
                    "*The AI uses this history to learn your preferences and suggest plans you're more likely to enjoy.*"
                )

        # Select plan button
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("✅ Select This Plan", type="primary", use_container_width=True):
                chosen_plan = st.session_state.plans_generated[st.session_state.selected_option_index]
                st.session_state.chosen_plan = chosen_plan

                # Update database with choice
                update_chosen_option(
                    st.session_state.request_id,
                    st.session_state.selected_option_index,
                )

                # Generate shopping list
                with st.spinner("Generating your shopping list..."):
                    try:
                        shopping_list = generate_shopping_list(chosen_plan)
                        st.session_state.shopping_list = shopping_list
                        st.success("✅ Plan selected! Scroll down to see your shopping list.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error generating shopping list: {str(e)}")

    # Display chosen plan and shopping list
    if st.session_state.chosen_plan:
        st.markdown("---")
        st.markdown("### ✅ Your Chosen Meal Plan")

        display_meal_plan(
            st.session_state.chosen_plan,
            st.session_state.selected_option_index + 1,
            show_full_reasoning=True,
            show_recipe_details=True,
        )

    if st.session_state.shopping_list:
        st.markdown("---")
        st.markdown("### 🛒 Shopping List")
        st.markdown(
            "Here's your consolidated shopping list. Copy this and take it to the store!"
        )

        st.markdown(
            f'<div class="shopping-list">{st.session_state.shopping_list}</div>',
            unsafe_allow_html=True,
        )

        # Copy button (via text area)
        st.text_area(
            "Copy Shopping List:",
            value=st.session_state.shopping_list,
            height=300,
            help="Click inside and press Ctrl+A, Ctrl+C to copy",
        )

        # Show AI processing insight
        if st.session_state.raw_shopping_list:
            with st.expander("🔍 View AI Processing (How the list was consolidated)"):
                st.markdown("**Raw Aggregated Shopping List (Before AI Consolidation):**")
                st.text(st.session_state.raw_shopping_list)
                st.markdown("---")
                st.markdown(
                    "*The AI consolidates this raw list by:*\n"
                    "- Combining duplicate ingredients\n"
                    "- Rounding quantities to practical amounts\n"
                    "- Merging similar items (e.g., 'egg' + 'beaten egg' → 'eggs')\n"
                    "- Making measurements store-friendly"
                )

    # Start over button (always visible at bottom if plans have been generated)
    if st.session_state.plans_generated or st.session_state.chosen_plan:
        st.markdown("---")
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("🔄 Start Over", use_container_width=True):
                reset_session()
                st.rerun()

    # Footer
    st.markdown("---")
    st.markdown(
        '<div style="text-align: center; color: #666; font-size: 0.9rem;">'
        "Powered by Gemini AI • Built with Streamlit"
        "</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
