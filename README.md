# 🏠 Housewife AI - Japanese Cookbook Meal Planner

AI-powered meal planning system that extracts recipes from Japanese cookbooks and generates personalized weekly dinner plans with consolidated shopping lists.

## ✨ Features

- 🤖 **AI Recipe Extraction**: Extract recipes from cookbook images using Google Gemini Vision
- 📅 **Smart Meal Planning**: Generate multiple dinner plan options with AI reasoning
- 🧠 **Learning System**: System learns from your choices to improve future recommendations
- 🛒 **Smart Shopping Lists**: Auto-generate consolidated shopping lists with AI optimization
- 🖥️ **Web UI**: User-friendly Streamlit interface (no command-line knowledge required)
- 💻 **CLI Tools**: Powerful command-line interface for advanced users
- 🌐 **Bilingual Support**: Handles Japanese and English recipe content

## 📋 Prerequisites

- Python 3.9 or higher
- Google Gemini API key ([Get one here](https://makersuite.google.com/app/apikey))
- Google Drive API credentials (for syncing cookbook files)
- Japanese cookbook images or PDFs

## 🚀 Quick Start (Local Testing)

### 1. Clone and Setup

```bash
# Clone the repository
git clone <repository-url>
cd cookbook-mealplanner

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your credentials
nano .env  # or use your preferred editor
```

Required environment variables in `.env`:
```bash
# Gemini AI Configuration
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL_NAME=gemini-3-pro-image-preview

# Google Drive Configuration (for syncing cookbook files)
GDRIVE_FOLDER_ID=your_drive_folder_id_here
GDRIVE_SERVICE_ACCOUNT_FILE=credentials/your-service-account.json

# Local Data Storage
LOCAL_DATA_DIR=data
```

### 4. Set Up Google Drive Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable the Google Drive API
4. Create a service account and download the JSON key
5. Save the JSON key to `credentials/your-service-account.json`
6. Share your Google Drive folder with the service account email

### 5. Initialize Database

```bash
python -m cookplanner init-db
```

### 6. Import Recipes

You have two options:

**Option A: Sync from Google Drive** (recommended for ongoing use)
```bash
python -m cookplanner sync-drive
```

**Option B: Import local images** (for testing)
```bash
# Place cookbook images in data/images/
python -m cookplanner import-recipes
```

### 7. Launch Web UI

```bash
# Option 1: Using launcher script
python run_ui.py

# Option 2: Direct Streamlit command
streamlit run cookplanner/ui/app.py

# Option 3: Custom port
streamlit run cookplanner/ui/app.py --server.port 8502
```

The web UI will automatically open in your browser at `http://localhost:8501`

## 🖥️ Using the Web UI

### Workflow

1. **Select Parameters**
   - Choose number of days (3-14)
   - Choose servings per meal (1-6)
   - Choose number of plan options (2-5)
   - Optionally add dietary preferences

2. **Generate Plans**
   - Click "Generate Meal Plans"
   - Wait for AI to generate multiple options
   - Review each option with reasoning

3. **Select Your Plan**
   - Choose your preferred option
   - Click "Select This Plan"
   - Your choice is saved for future learning

4. **Get Shopping List**
   - System automatically generates shopping list
   - List is consolidated using AI for practicality
   - Copy and take it to the store!

## 💻 CLI Commands

For advanced users who prefer the command line:

### View Available Recipes

```bash
# List all recipes
python -m cookplanner list

# List with tag filter
python -m cookplanner list --tag vegetarian

# Search recipes
python -m cookplanner search "chicken"

# Show recipe details
python -m cookplanner show 5
```

### Generate Meal Plans

```bash
# Generate dinner plan (old single-option mode)
python -m cookplanner plan-dinners --days 7 --servings 2

# Generate multiple options with preferences
python -m cookplanner plan-dinners \
  --days 5 \
  --servings 2 \
  --num-options 3 \
  --preferences "balanced, simple recipes. We like ground pork dishes"
```

### Generate Shopping Lists

```bash
# Basic shopping list
python -m cookplanner shopping-list 1 5 10

# AI-consolidated shopping list (recommended)
python -m cookplanner shopping-list --consolidate 1 5 10
```

### Other Commands

```bash
# Check configuration
python -m cookplanner config-check

# Extract single recipe
python -m cookplanner extract-recipe path/to/image.jpg

# Sync from Google Drive
python -m cookplanner sync-drive
```

## 📁 Project Structure

```
cookbook-mealplanner/
├── cookplanner/              # Main package
│   ├── cli.py               # Command-line interface
│   ├── config.py            # Configuration management
│   ├── models/              # Data models and database
│   │   ├── db.py           # Database schema and setup
│   │   ├── orm.py          # Database operations
│   │   └── schema.py       # Pydantic models
│   ├── extraction/          # Recipe extraction from images
│   │   ├── extract_recipe.py
│   │   └── gemini_client.py
│   ├── planning/            # Meal planning logic
│   │   ├── meal_planner.py
│   │   └── shopping_list.py
│   ├── sync/                # Google Drive sync
│   │   └── file_sync.py
│   └── ui/                  # Web interface
│       ├── __init__.py
│       └── app.py          # Streamlit application
├── data/                    # Local data (gitignored)
│   ├── images/             # Recipe images
│   └── recipes.db          # SQLite database
├── credentials/            # API credentials (gitignored)
├── .env                    # Environment config (gitignored)
├── .env.example           # Example environment config
├── requirements.txt       # Python dependencies
├── run_ui.py             # Web UI launcher
└── README.md             # This file
```

## 🧪 Testing Locally

### Verification Checklist

- [ ] Virtual environment activated
- [ ] Dependencies installed (`pip install -r requirements.txt`)
- [ ] `.env` file configured with valid API keys
- [ ] Google Drive service account set up
- [ ] Database initialized (`init-db`)
- [ ] At least 10 recipes imported
- [ ] Web UI loads without errors
- [ ] Can generate 3 meal plan options
- [ ] Can select a plan
- [ ] Shopping list generates correctly
- [ ] Second plan generation shows learning (uses history)

### Test Workflow

```bash
# 1. Verify configuration
python -m cookplanner config-check

# 2. Check recipes are available
python -m cookplanner list --limit 10

# 3. Test CLI meal planning
python -m cookplanner plan-dinners --days 3 --num-options 2

# 4. Test web UI
python run_ui.py
# Try generating plans through the UI
```

## 🔧 Troubleshooting

### "Configuration validation failed"
- **Solution**: Check your `.env` file has all required variables
- Verify API keys are correct
- Ensure service account JSON file exists at specified path

### "No recipes available in database"
- **Solution**: Run `python -m cookplanner import-recipes` or `sync-drive`
- Check that images exist in `data/images/`
- Verify Google Drive sync is working

### "Object of type Recipe is not JSON serializable"
- **Solution**: This has been fixed in the latest version
- If you still see it, update to the latest code

### Port 8501 already in use
- **Solution**: Use a different port:
  ```bash
  streamlit run cookplanner/ui/app.py --server.port 8502
  ```

### LLM requests timing out
- **Solution**: Check your internet connection
- Verify Gemini API key is valid
- Try reducing the number of recipes in database for faster processing

### Import errors
- **Solution**: Make sure you're in the project root directory
- Activate the virtual environment
- Reinstall dependencies: `pip install -r requirements.txt`

## 🗄️ Database Management

### Reset Database
```bash
python -c "from cookplanner.models.db import Database; db = Database(); db.reset_db()"
```

### View Database Contents
```python
import sqlite3
from cookplanner.config import Config

conn = sqlite3.connect(Config.get_db_path())
cursor = conn.cursor()

# See all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
print(cursor.fetchall())

# Count recipes
cursor.execute("SELECT COUNT(*) FROM recipes")
print(f"Recipes: {cursor.fetchone()[0]}")
```

## 🎯 Advanced Usage

### Custom Model Selection

Edit `.env` to use different Gemini models:
```bash
# Options: gemini-3-pro-image-preview, gemini-2.0-flash-exp, gemini-1.5-pro
GEMINI_MODEL_NAME=gemini-2.0-flash-exp
```

### Multi-User Support

The system supports multiple users through the `user_id` parameter:
```bash
python -m cookplanner plan-dinners --user-id alice
```

In the UI, users are currently tracked as "default" but this can be extended.

### Batch Recipe Extraction

```bash
# Extract from all images in directory
python -m cookplanner import-recipes --images-dir path/to/images

# Skip already extracted
python -m cookplanner import-recipes --skip-existing
```

## 📊 How It Works

1. **Recipe Extraction**: Gemini Vision analyzes cookbook images and extracts structured recipe data (ingredients, instructions, tags)
2. **Database Storage**: Recipes stored in SQLite with full-text search capabilities
3. **Meal Planning**: LLM generates multiple dinner plan options considering variety, nutrition, and user history
4. **Choice Learning**: System tracks which plans users select to improve future recommendations
5. **Shopping List Generation**: Aggregates ingredients across recipes, then uses LLM to consolidate into practical shopping list

## 🤝 Contributing

This is a personal project, but suggestions and improvements are welcome!

## 📄 License

See LICENSE file for details.

## 🙏 Acknowledgments

- Powered by Google Gemini AI
- Built with Streamlit, Typer, and Rich
- Inspired by the need to make Japanese cookbook recipes more accessible

---

**Happy meal planning! 🍽️**
