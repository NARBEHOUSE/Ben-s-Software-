**there are many duplicate functions in this software yet to be cleaned**

# Ben's Accessibility Software

## Overview

This project enhances accessibility for individuals with physical challenges, such as Ben, who has TUBB4a-related Leukodystrophy. Ben uses a two-button system for navigation and communication. This software integrates with his setup to:

- Provide scan-and-select capabilities.
- Open specific links to favorite shows.
- Include a menu for quick phrases.
- Track and update URLs dynamically.
- Offer emergency, settings, communication, and entertainment functions.
- Consolidate communication features into `keyboard.py`, eliminating the need for a separate communication menu.

## Features

### Navigation

- **Spacebar (Single Press)**: Advances forward by one item.
- **Spacebar Disable Spacebar in Chrome (Spacebar continuously pauses videos in chrome, this causes issues. Use AutoHotKey with the script "disable_space_chrome.ahk" at Windows Startup to disable)
- **Spacebar (Held for More Than 3 Seconds)**: Continuously scans backward.
- **Keyboard Navigation**:
  - Works similarly to the main navigation.
  - Holding the `Return` key for more than 3 seconds jumps directly to predictive text for quicker word selection.

### Controls

- **Emergency Function**: Triggers an alert for immediate assistance.
- **Settings Menu**:
  - Volume Up/Down
  - Sleep Timer (60 minutes)
  - Cancel Sleep Timer
  - Turn Display Off
  - Lock Computer
  - Restart Computer
  - Shut Down Computer
- **Quick Phrase Method**: Integrated into the keyboard’s layout menu.
- **Enhanced Predictive Text**:
  - **Hybrid System**: Combines offline n-gram predictions with online API integration
  - **Offline Mode**: Local n-gram analysis for reliable predictions without internet
  - **Online Mode**: Integration with imagineville.org API for enhanced predictions
  - **Intelligent Merging**: Configurable strategies for combining offline and online predictions
  - **Automatic Fallback**: Gracefully falls back to offline mode when network is unavailable
  - **Configurable Settings**: Customizable API timeouts, merge strategies, and caching
- **Chrome Auto-Close**: Chrome minimizes or closes when needed. To close Chrome using the buttons, press `Enter-Enter-Enter`.
- **On-Screen Keyboard**:
  - Includes volume up and volume down button controls.
  - Predictive text shortcut via long `Return` press.

### Entertainment

- **Dynamic Show Tracking**: Automated via `shows.xlsx`. Populate the file with `type`, `genre`, `title`, and `URL`. Works best with:
  - Plex
  - Spotify
  - Netflix
  - Hulu
  - Disney+
  - Paramount+
  - YouTube
  - HBO Max
- **Trivia Mode**:
  - Pulls trivia data from `trivia_questions.xlsx`.
  - Populate with `category`, `question`, and `answers`, and the software auto-categorizes.
- **Games Menu**:
  - `concentration.py`: A memory game.
  - `tictactoe.py`: Classic Tic Tac Toe.
  - `wordjumble.py`: A spelling challenge game.
  - `towerdefense.py`: A tower defense strategy game
  - `bensgolf.py`: A mini golf game with Happy Gilmore soundfx.
  - `baseball.py`: A simple probability baseball game with some graphics/animation.
  - More games coming soon with Text Adventures and porting a controller for scan/select method to utilize to choose options in choose your own adventure games.
- **Pause Menu**: Holding down the `Return` key for more than six seconds opens a pause window.

## Installation

This project uses [UV](https://docs.astral.sh/uv/) for fast Python package management and project setup.

### Prerequisites

1. **Install UV** (if not already installed):
   ```bash
   # On macOS and Linux
   curl -LsSf https://astral.sh/uv/install.sh | sh

   # On Windows
   powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

   # Or with pip
   pip install uv
   ```

2. **Python 3.8+** is required (UV will manage this automatically)

### Setup and Installation

```bash
# Clone this repository
git clone https://github.com/NARBEHOUSE/Ben-s-Software-.git

# Navigate to the project directory
cd Ben-s-Software-

# Create virtual environment and install dependencies
uv sync

# Activate the virtual environment
# On Windows:
.venv\Scripts\activate
# On macOS/Linux:
source .venv/bin/activate

# Run the main application
python comm-v10.py

# Or run the keyboard application
python keyboard/keyboard.py
```

### Alternative Installation Methods

#### Using UV Run (No Virtual Environment)
```bash
# Run directly with UV (automatically manages dependencies)
uv run comm-v10.py
uv run keyboard/keyboard.py
```

#### Development Installation
```bash
# Install with development dependencies
uv sync --extra dev

# Run tests
uv run pytest

# Format code with Black
uv run black .

# Lint code with Ruff
uv run ruff check

# Auto-fix linting issues
uv run ruff check --fix

# Type checking with MyPy
uv run mypy .

# Run all quality checks
uv run black . && uv run ruff check --fix && uv run mypy .
```

## Usage

1. **Starting the Software**:
   - Connect Ben's two-button device.
   - Launch the application with `comm-v9.py`.
2. **Navigating the Interface**:
   - Use the `Scan` button to highlight options.
   - Use the `Select` button to confirm.
3. **Opening Shows**:
   - Populate `shows.xlsx` and navigate to "Favorite Shows".
   - Select a show to resume from the last saved URL.
4. **Using Quick Phrases**:
   - Access the keyboard’s layout menu.
   - Select a phrase to display or speak with text-to-speech.

## Configuration

### Media and Games
- **Shows List**: Update `shows.xlsx` to add new shows.
- **Trivia Questions**: Update `trivia_questions.xlsx` for new trivia categories and questions.
- **Word Jumble**: Update `wordjumble.xlsx` for new words in the jumble game (2-3-4-5-6-7-8 letter words, follow pattern of input).

### Predictive Text Configuration
The enhanced predictive text system can be configured via `keyboard/predictive_config.json`:

```json
{
    "online_mode_enabled": true,
    "api_timeout": 5,
    "api_max_retries": 2,
    "api_vocabulary": "100k",
    "api_safe_mode": true,
    "network_check_interval": 30,
    "cache_ttl": 300,
    "merge_strategy": "weighted",
    "api_weight": 0.7,
    "offline_weight": 0.3,
    "debug_logging": false
}
```

**Configuration Options:**
- `online_mode_enabled`: Enable/disable online API predictions
- `api_timeout`: Timeout for API requests (seconds)
- `api_max_retries`: Number of retry attempts for failed API calls
- `api_vocabulary`: Vocabulary size for API ("1k", "5k", "10k", "20k", "40k", "100k", "500k")
- `merge_strategy`: How to combine predictions ("weighted", "api_first", "offline_first")
- `api_weight`/`offline_weight`: Weights for weighted merge strategy
- `debug_logging`: Enable detailed logging for troubleshooting

## Project Structure

```
Ben-s-Software-/
├── keyboard/                    # Enhanced predictive text keyboard system
│   ├── keyboard.py             # Main keyboard interface
│   ├── keyboard_predictive.py  # Hybrid prediction engine (offline + online)
│   ├── predictive_config.json  # Configuration for prediction system
│   └── test_predictive_enhanced.py  # Test suite for predictions
├── games/                      # Entertainment and cognitive games
│   ├── Trivia.py              # Trivia game with customizable questions
│   ├── baseball.py            # Baseball simulation game
│   ├── bensgolf.py            # Mini golf with Happy Gilmore sounds
│   ├── concentration.py       # Memory matching game
│   ├── tictactoe.py          # Classic Tic Tac Toe
│   ├── towerdefense.py       # Tower defense strategy game
│   └── wordjumble.py         # Word unscrambling game
├── data/                      # Configuration and data files
│   ├── communication.xlsx    # Communication phrases and shortcuts
│   ├── shows.xlsx            # Media content tracking
│   ├── trivia_questions.xlsx # Trivia game questions
│   └── wordjumble.xlsx       # Word jumble game data
├── images/                   # UI images and icons
├── soundfx/                  # Audio files for games and feedback
├── comm-v10.py              # Main application entry point
├── pyproject.toml           # UV project configuration
└── readme.md               # This file
```

## Dependencies

All dependencies are managed through UV and defined in `pyproject.toml`:

- **Python 3.8+** (automatically managed by UV)
- **PyAutoGUI** - GUI automation and control
- **PyTTSx3** - Text-to-Speech functionality
- **pynput** - Input monitoring and control
- **psutil** - System process management
- **requests** - HTTP requests for online predictions
- **pywin32** - Windows-specific functionality (Windows only)
- **pandas** - Data manipulation for Excel files
- **pygame** - Game development framework
- **pymunk** - Physics engine for games

## Troubleshooting

### Common Issues

**UV Installation Issues:**
- Make sure UV is properly installed and in your PATH
- On Windows: `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`
- On macOS/Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`

**Dependency Issues:**
- Run `uv sync` to ensure all dependencies are installed
- For development dependencies: `uv sync --extra dev`
- Clear cache if needed: `uv cache clean`

**Predictive Text Issues:**
- Check network connectivity for online predictions
- Verify `keyboard/predictive_config.json` settings
- Run tests: `uv run keyboard/test_predictive_enhanced.py`
- Enable debug logging in config for detailed troubleshooting

**Windows-Specific Issues:**
- Ensure pywin32 is properly installed (handled automatically by UV)
- Run as administrator if needed for system-level access
- Use the provided `run.bat` for easier Windows execution

**Permission Issues:**
- Some features may require elevated permissions
- Ensure the application has access to input devices
- Check antivirus software isn't blocking the application

### Getting Help

1. **Check the logs** - Enable debug logging in predictive text config
2. **Run the test suite** - `uv run keyboard/test_predictive_enhanced.py`
3. **Verify dependencies** - `uv run run.py` checks all dependencies
4. **Check GitHub Issues** - [Report bugs or request features](https://github.com/NARBEHOUSE/Ben-s-Software-/issues)

## Contributing

Contributions are welcome! Please fork this repository and submit a pull request.

### Development Setup
```bash
# Clone and setup for development
git clone https://github.com/NARBEHOUSE/Ben-s-Software-.git
cd Ben-s-Software-
uv sync --extra dev

# Run tests
uv run pytest

# Format code with Black
uv run black .

# Lint and fix code with Ruff
uv run ruff check --fix

# Type checking with MyPy
uv run mypy .
```

### Code Quality Standards

This project uses modern Python tooling for code quality:

- **[Black](https://black.readthedocs.io/)** - Uncompromising code formatter
- **[Ruff](https://docs.astral.sh/ruff/)** - Fast Python linter and code formatter
- **[MyPy](https://mypy.readthedocs.io/)** - Static type checker

**Code Style:**
- Line length: 88 characters (Black default)
- Python 3.8+ compatibility
- Type hints encouraged for new code
- Docstrings for public functions and classes

**Pre-commit Workflow:**
```bash
# Before committing, run:
uv run black .                    # Format code
uv run ruff check --fix          # Lint and auto-fix
uv run pytest                    # Run tests
```

## License

This project is licensed under the MIT License. See the LICENSE file for details.

## Acknowledgments

Special thanks to Ben and his family for inspiring this project and providing valuable feedback.

