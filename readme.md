**there are mant duplicate functions in this software yet to be cleaned**

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
- **Predictive Text**: Allows faster and more intuitive text entry.
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

```bash
# Clone this repository
git clone https://github.com/acroz3n/ben-s-software.git

# Navigate to the project directory
cd ben-accessibility-software

# Install required dependencies
pip install -r requirements.txt

# Run the application
comm-v9.py
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

- **Shows List**: Update `shows.xlsx` to add new shows.
- **Trivia Questions**: Update `trivia_questions.xlsx` for new trivia categories and questions.
- **Word Jumble**: Update `wordjumble.xlsx` for new words in the jumble game (2-3-4-5-6-7-8 letter words, follow pattern of input).

## Dependencies

- **Python 3.8+**
- **PyAutoGUI**
- **PyTTSx3** (Text-to-Speech)
- **Flask** (Optional for Web Interface)
- **Pygame** (For future game development)
- **Pymunk** (For physics-based interactions in future games)

## Contributing

Contributions are welcome! Please fork this repository and submit a pull request.

## License

This project is licensed under the MIT License. See the LICENSE file for details.

## Acknowledgments

Special thanks to Ben and his family for inspiring this project and providing valuable feedback.

