(() => {
  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => document.querySelectorAll(sel);

  // DOM Elements
  const mainMenu = $("#mainMenu");
  const entriesScreen = $("#entriesScreen");
  const optionsScreen = $("#optionsScreen");
  const keyboardScreen = $("#keyboardScreen");
  const questionModal = $("#questionModal");
  const entryViewModal = $("#entryViewModal");
  const changeViewModal = $("#changeViewModal");
  const deleteConfirmModal = $("#deleteConfirmModal");
  const textBar = $("#textBar");
  const predictBar = $("#predictBar");
  const kb = $("#keyboard");
  const entriesList = $("#entriesList");
  const currentPeriodLabel = $("#currentPeriod");
  const datePreview = $("#datePreview");

  // Settings
  const defaultSettings = {
    theme: "default",
    highlightColor: "yellow",
    scanSpeed: "medium",
    autoScan: false
  };

  let settings = loadSettings();
  function loadSettings() {
    try {
      const v = JSON.parse(localStorage.getItem("journal_settings"));
      return { ...defaultSettings, ...v };
    } catch {
      return { ...defaultSettings };
    }
  }
  function saveSettings() {
    localStorage.setItem("journal_settings", JSON.stringify(settings));
  }

  // Theme management
  const themes = ["default", "light", "dark", "blue", "green", "purple", "orange", "red"];
  const highlightColors = ["yellow", "pink", "green", "orange", "black", "white", "purple", "red"];
  let currentThemeIndex = themes.indexOf(settings.theme) || 0;
  let currentHighlightIndex = highlightColors.indexOf(settings.highlightColor) || 0;

  function applyTheme(theme) {
    themes.forEach(t => document.body.classList.remove(`theme-${t}`));
    if (theme !== "default") {
      document.body.classList.add(`theme-${theme}`);
    }
    settings.theme = theme;
    saveSettings();
    updateDisplays();
  }

  function applyHighlightColor(color) {
    highlightColors.forEach(c => document.body.classList.remove(`highlight-${c}`));
    document.body.classList.add(`highlight-${color}`);
    settings.highlightColor = color;
    saveSettings();
    updateDisplays();
  }

  // Scan timing
  const scanSpeeds = {
    slow: { forward: 1500, backward: 3000, longPress: 2000 },
    medium: { forward: 1000, backward: 2000, longPress: 2000 },
    fast: { forward: 500, backward: 1000, longPress: 2000 }
  };
  const autoScanSpeeds = { slow: 3000, medium: 2000, fast: 1000 };

  let currentScanSpeed = settings.scanSpeed || "medium";
  let autoScanInterval = null;
  let isAutoScanning = settings.autoScan || false;

  // TTS
  function stripEmojis(text) {
    // Remove emojis, symbols, and special characters that TTS shouldn't read
    return text
      .replace(/[\u{1F300}-\u{1F9FF}]/gu, '') // Emojis
      .replace(/[\u{2600}-\u{26FF}]/gu, '')   // Misc symbols
      .replace(/[\u{2700}-\u{27BF}]/gu, '')   // Dingbats
      .replace(/[◀▶🔊🗑️⚙⏻✓✕⌫⌦—]/g, '')      // Specific icons used in the app
      .replace(/\s+/g, ' ')                    // Clean up extra spaces
      .trim();
  }

  function speak(text) {
    if (window.NarbeVoiceManager) {
      window.NarbeVoiceManager.cancel();
      let cleanText = stripEmojis(text);
      
      // Fix for short uppercase words (like "IT", "IS") being read as letters
      // If text is short (<= 4 chars) and fully uppercase, convert to lowercase
      // Exception for "I" which should be read as "I" (though lowercase "i" usually works too)
      if (cleanText && cleanText.length > 1 && cleanText.length <= 4 && cleanText === cleanText.toUpperCase()) {
        cleanText = cleanText.toLowerCase();
      }

      if (cleanText) {
        setTimeout(() => window.NarbeVoiceManager.speak(cleanText), 50);
      }
    }
  }

  // Journal Questions based on time of day
  let questions = {
    morning: [],
    afternoon: [],
    evening: []
  };

  async function loadQuestions() {
    try {
      const response = await fetch('questions.json');
      if (response.ok) {
        const data = await response.json();
        questions = data;
        console.log('Questions loaded successfully');
      } else {
        console.error('Failed to load questions');
      }
    } catch (e) {
      console.error('Error loading questions:', e);
    }
  }

  // Track used questions for today
  let usedQuestionsToday = [];
  let lastQuestionDate = null;

  function getTodayDateString() {
    const now = new Date();
    return `${now.getFullYear()}-${now.getMonth()}-${now.getDate()}`;
  }

  function loadUsedQuestions() {
    try {
      const stored = localStorage.getItem("journal_used_questions");
      if (stored) {
        const data = JSON.parse(stored);
        if (data.date === getTodayDateString()) {
          usedQuestionsToday = data.questions || [];
          lastQuestionDate = data.date;
          return;
        }
      }
    } catch (e) {}
    // Reset for new day
    usedQuestionsToday = [];
    lastQuestionDate = getTodayDateString();
    saveUsedQuestions();
  }

  function saveUsedQuestions() {
    localStorage.setItem("journal_used_questions", JSON.stringify({
      date: getTodayDateString(),
      questions: usedQuestionsToday
    }));
  }

  function getTimeBasedQuestions() {
    const hour = new Date().getHours();
    // Morning: 3am (3) to 11:59am (before 12)
    if (hour >= 3 && hour < 12) return questions.morning;
    // Afternoon: 12pm (12) to 4:59pm (before 17)
    if (hour >= 12 && hour < 17) return questions.afternoon;
    // Evening: 5pm (17) to 2:59am (before 3) - includes hours 17-23 and 0-2
    return questions.evening;
  }

  function getAvailableQuestions() {
    const timeQuestions = getTimeBasedQuestions();
    // Also check entries for today to see which questions were answered
    const todayStart = new Date();
    todayStart.setHours(0, 0, 0, 0);
    const todayEnd = new Date();
    todayEnd.setHours(23, 59, 59, 999);
    
    const answeredToday = entries
      .filter(e => {
        const d = new Date(e.date);
        return d >= todayStart && d <= todayEnd;
      })
      .map(e => e.question);
    
    // Combine used questions from this session and answered questions
    const allUsed = new Set([...usedQuestionsToday, ...answeredToday]);
    
    return timeQuestions.filter(q => !allUsed.has(q));
  }

  function getRandomQuestion() {
    // Check if it's a new day
    if (lastQuestionDate !== getTodayDateString()) {
      usedQuestionsToday = [];
      lastQuestionDate = getTodayDateString();
      saveUsedQuestions();
    }

    const available = getAvailableQuestions();
    
    if (available.length === 0) {
      // All questions used, reset and pick from all
      usedQuestionsToday = [];
      saveUsedQuestions();
      const allQuestions = getTimeBasedQuestions();
      return allQuestions[Math.floor(Math.random() * allQuestions.length)];
    }
    
    const question = available[Math.floor(Math.random() * available.length)];
    usedQuestionsToday.push(question);
    saveUsedQuestions();
    return question;
  }

  // Entry management
  let entries = [];
  let currentViewDate = new Date();
  let currentQuestion = "";
  let entryToDelete = null;
  let editingEntryId = null;

  async function loadEntries() {
    // First try to load from server
    try {
      const response = await fetch('/api/entries');
      if (response.ok) {
        const data = await response.json();
        if (data.entries) {
          entries = data.entries;
          localStorage.setItem("journal_entries", JSON.stringify(entries));
          return;
        }
      }
    } catch (e) {
      console.log('Could not load from server:', e);
    }
    
    // Fallback to localStorage
    try {
      const stored = localStorage.getItem("journal_entries");
      entries = stored ? JSON.parse(stored) : [];
    } catch {
      entries = [];
    }
  }

  function saveEntries() {
    localStorage.setItem("journal_entries", JSON.stringify(entries));
    saveEntriesToServer();
  }

  async function saveEntriesToServer() {
    try {
      await fetch('/api/save_entries', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ entries })
      });
    } catch (e) {
      console.log('Could not save to server:', e);
    }
  }

  function addEntry(question, answer) {
    const entry = {
      id: Date.now(),
      date: new Date().toISOString(),
      question: question,
      answer: answer
    };
    entries.unshift(entry);
    saveEntries();
    return entry;
  }

  function updateEntry(id, answer) {
    const entryIndex = entries.findIndex(e => e.id === id);
    if (entryIndex !== -1) {
      entries[entryIndex].answer = answer;
      saveEntries();
      return entries[entryIndex];
    }
    return null;
  }

  function deleteEntry(entryId) {
    entries = entries.filter(e => e.id !== entryId);
    saveEntries();
  }

  function formatDate(dateStr) {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', {
      weekday: 'long',
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    });
  }

  function formatShortDate(dateStr) {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric'
    });
  }

  function formatCurrentViewDate() {
    return currentViewDate.toLocaleDateString('en-US', {
      weekday: 'long',
      month: 'long',
      day: 'numeric',
      year: 'numeric'
    });
  }

  // Navigation state
  let currentScreen = "mainMenu";
  let scanIndex = -1;  // Start at -1 so nothing is highlighted until first scan
  let scanItems = [];
  let inButtonMode = false;
  let hasStartedScanning = false;  // Track if user has started scanning

  // Scanning controls
  let spacebarPressed = false;
  let returnPressed = false;
  let spacebarPressTime = null;
  let returnPressTime = null;
  let longPressTriggered = false;
  let backwardScanInterval = null;
  let backwardScanningOccurred = false;

  // Screen management
  function showScreen(screenId) {
    $$(".screen").forEach(s => s.classList.remove("active"));
    $(`#${screenId}`).classList.add("active");
    currentScreen = screenId;
    scanIndex = -1;  // Start at -1 for new screens
    hasStartedScanning = false;
    inButtonMode = false;
    updateScanItems();
    clearAllHighlights();  // Don't highlight anything initially
  }

  function updateScanItems() {
    scanItems = [];
    
    // Check for open modals first (highest priority)
    if (!deleteConfirmModal.classList.contains("hidden")) {
      scanItems = Array.from($$("#deleteConfirmModal .modal-btn"));
      return;
    }
    if (!changeViewModal.classList.contains("hidden")) {
      scanItems = Array.from($$("#changeViewModal .modal-btn"));
      return;
    }
    if (!questionModal.classList.contains("hidden")) {
      scanItems = Array.from($$("#questionModal .modal-btn"));
      return;
    }
    if (!entryViewModal.classList.contains("hidden")) {
      scanItems = Array.from($$("#entryViewModal .modal-btn"));
      return;
    }
    
    if (currentScreen === "mainMenu") {
      scanItems = Array.from($$("#mainMenu .menu-btn"));
    } else if (currentScreen === "entriesScreen") {
      // Order: Add Entry, Change View, Back (action buttons first), then entry items
      scanItems = [
        ...Array.from($$("#entriesScreen .action-btn")),
        ...Array.from($$("#entriesScreen .entry-item"))
      ];
    } else if (currentScreen === "optionsScreen") {
      scanItems = [
        ...Array.from($$("#optionsScreen .option-btn")),
        ...Array.from($$("#optionsScreen .menu-btn"))
      ];
    } else if (currentScreen === "keyboardScreen") {
      updateKeyboardScanItems();
      return;
    }
  }

  function clearAllHighlights() {
    $$(".highlighted").forEach(el => el.classList.remove("highlighted"));
  }

  function highlightCurrentItem() {
    clearAllHighlights();
    if (scanIndex >= 0 && scanItems[scanIndex]) {
      scanItems[scanIndex].classList.add("highlighted");
    }
  }

  function scanForward() {
    if (currentScreen === "keyboardScreen") {
      keyboardScanForward();
      return;
    }
    // First scan starts at 0, subsequent scans increment
    if (scanIndex < 0) {
      scanIndex = 0;
    } else {
      scanIndex = (scanIndex + 1) % scanItems.length;
    }
    hasStartedScanning = true;
    highlightCurrentItem();
    speakCurrentItem();
  }

  function scanBackward() {
    if (currentScreen === "keyboardScreen") {
      keyboardScanBackward();
      return;
    }
    // If we haven't started scanning, start at last item
    if (scanIndex < 0) {
      scanIndex = scanItems.length - 1;
    } else {
      scanIndex = (scanIndex - 1 + scanItems.length) % scanItems.length;
    }
    hasStartedScanning = true;
    highlightCurrentItem();
    speakCurrentItem();
  }

  function speakCurrentItem() {
    if (scanItems[scanIndex]) {
      const text = scanItems[scanIndex].textContent || scanItems[scanIndex].innerText;
      speak(stripEmojis(text.trim()));
    }
  }

  function selectCurrentItem() {
    if (currentScreen === "keyboardScreen") {
      keyboardSelect();
      return;
    }
    // Only select if we have a valid index
    if (scanIndex >= 0 && scanItems[scanIndex]) {
      scanItems[scanIndex].click();
    }
  }

  // Keyboard input handling
  document.addEventListener("keydown", (e) => {
    if (e.code === "Space") {
      e.preventDefault();
      startScanning();
    } else if (e.code === "Enter") {
      e.preventDefault();
      startSelecting();
    }
  });

  document.addEventListener("keyup", (e) => {
    if (e.code === "Space") {
      e.preventDefault();
      stopScanning();
    } else if (e.code === "Enter") {
      e.preventDefault();
      stopSelecting();
    }
  });

  function startScanning() {
    if (!spacebarPressed) {
      spacebarPressed = true;
      spacebarPressTime = Date.now();
      backwardScanningOccurred = false;

      const speed = scanSpeeds[currentScanSpeed];
      setTimeout(() => {
        if (spacebarPressed && (Date.now() - spacebarPressTime) >= speed.longPress) {
          backwardScanInterval = setInterval(() => {
            if (spacebarPressed) {
              backwardScanningOccurred = true;
              scanBackward();
            }
          }, speed.backward);
        }
      }, speed.longPress);
    }
  }

  function stopScanning() {
    if (spacebarPressed) {
      spacebarPressed = false;
      const pressDuration = Date.now() - spacebarPressTime;

      if (backwardScanInterval) {
        clearInterval(backwardScanInterval);
        backwardScanInterval = null;
      }

      const speed = scanSpeeds[currentScanSpeed];
      if ((pressDuration >= 250 && pressDuration <= speed.longPress) ||
          (pressDuration > speed.longPress && !backwardScanningOccurred)) {
        scanForward();
      }

      spacebarPressTime = null;
      backwardScanningOccurred = false;
    }
  }

  function startSelecting() {
    if (!returnPressed) {
      returnPressed = true;
      returnPressTime = Date.now();
      longPressTriggered = false;
      
      // Check for long press after 3 seconds (only for keyboard screen)
      if (currentScreen === "keyboardScreen") {
        setTimeout(() => {
          if (returnPressed && (Date.now() - returnPressTime) >= 3000) {
            handleKeyboardLongPress();
          }
        }, 3000);
      }
    }
  }

  function stopSelecting() {
    if (returnPressed) {
      returnPressed = false;
      const pressDuration = Date.now() - returnPressTime;

      if (!longPressTriggered && pressDuration >= 100) {
        selectCurrentItem();
      }

      returnPressTime = null;
      longPressTriggered = false;
    }
  }

  // Handle long press of Return key in keyboard screen
  function handleKeyboardLongPress() {
    longPressTriggered = true;
    clearAllHighlights();
    
    if (keyboardInRowMode) {
      // Jump to predictive text row (last row)
      keyboardRowIndex = keyboardRows.length + 1;
      keyboardInRowMode = true;
      highlightPredictiveRow();
      speakPredictions();
      console.log("Long press: Jumped to predictive text row");
    } else {
      // Return to row selection mode
      keyboardInRowMode = true;
      if (keyboardRowIndex === 0) {
        textBar.classList.add("highlighted");
        // Only speak if there's content in the buffer
        const text = keyboardBuffer.trim();
        if (text) speak(text);
      } else if (keyboardRowIndex === keyboardRows.length + 1) {
        highlightPredictiveRow();
        speakPredictions();
      } else {
        highlightKeyboardRow(keyboardRowIndex - 1);
        speakRowTitle(keyboardRowIndex - 1);
      }
      console.log("Long press: Returned to row selection mode");
    }
  }

  // Auto scan
  function startAutoScan() {
    if (autoScanInterval) return;
    const speed = autoScanSpeeds[currentScanSpeed];
    autoScanInterval = setInterval(() => scanForward(), speed);
  }

  function stopAutoScan() {
    if (autoScanInterval) {
      clearInterval(autoScanInterval);
      autoScanInterval = null;
    }
  }

  // ========== KEYBOARD FUNCTIONALITY ==========
  let keyboardBuffer = "";
  let keyboardRowIndex = 0;
  let keyboardButtonIndex = 0;
  let keyboardInRowMode = true;

  const keyboardRows = [
    ["Space", "Del Letter", "Del Word", "Clear", "Send", "Exit"],
    ["A", "B", "C", "D", "E", "F"],
    ["G", "H", "I", "J", "K", "L"],
    ["M", "N", "O", "P", "Q", "R"],
    ["S", "T", "U", "V", "W", "X"],
    ["Y", "Z", "0", "1", "2", "3"],
    ["4", "5", "6", "7", "8", "9"]
  ];

  const controlSymbols = {
    "Space": "—",
    "Del Letter": "⌫",
    "Del Word": "⌦",
    "Clear": "✕",
    "Send": "✓",
    "Exit": "⏻"
  };

  function renderKeyboard() {
    kb.innerHTML = "";
    keyboardRows.forEach((row, rIdx) => {
      row.forEach((key) => {
        const btn = document.createElement("button");
        btn.className = "key" + (rIdx === 0 ? " ctrl" : "");

        if (key === "Send") {
          btn.classList.add("send");
        } else if (key === "Exit") {
          btn.classList.add("exit-kb");
        }

        if (rIdx === 0 && controlSymbols[key]) {
          btn.innerHTML = `
            <span class="ctrl-symbol">${controlSymbols[key]}</span>
            <span class="ctrl-text">${key}</span>
          `;
        } else {
          btn.textContent = key;
        }

        btn.addEventListener("click", () => {
          if (rIdx === 0) {
            handleKeyboardControl(key);
          } else {
            insertKey(key);
          }
        });
        kb.appendChild(btn);
      });
    });
  }

  async function setKeyboardBuffer(txt) {
    keyboardBuffer = txt;
    textBar.textContent = keyboardBuffer + "|";
    adjustTextSize(keyboardBuffer + "|");
    await renderPredictions();
  }

  function adjustTextSize(text) {
    textBar.classList.remove('text-medium', 'text-small', 'text-tiny');
    const length = text.replace('|', '').length;
    if (length > 100) textBar.classList.add('text-tiny');
    else if (length > 50) textBar.classList.add('text-small');
    else if (length > 25) textBar.classList.add('text-medium');
  }

  function handleAutoPunctuation(text) {
    // Check for double space at the end
    if (!text.endsWith("  ")) return text;

    // Trim the trailing spaces for analysis
    let content = text.trim();
    
    // Case 3: Exclamation
    // If the text before the double space ends with ".", replace it with "!"
    if (content.endsWith(".")) {
         return content.slice(0, -1) + "! ";
    }

    // Case 1 & 2: Adding punctuation
    // Find the start of the current sentence.
    const sentenceEndRegex = /([.!?])\s+/g;
    let match;
    let lastEndIndex = 0;
    
    while ((match = sentenceEndRegex.exec(content)) !== null) {
        lastEndIndex = match.index + match[0].length;
    }
    
    const currentSentence = content.substring(lastEndIndex);
    const words = currentSentence.trim().split(/\s+/);
    
    if (words.length >= 3) {
        const firstWord = words[0].toLowerCase();
        const questionStarters = ["who", "what", "where", "when", "why", "how"];
        
        const lastChar = content.slice(-1);
        if (!/[.!?]/.test(lastChar)) {
             if (questionStarters.includes(firstWord)) {
                 return content + "? ";
             } else {
                 return content + ". ";
             }
        }
    }
    
    return text;
  }

  function insertKey(k) {
    if (k === " ") {
      let textWithSpace = keyboardBuffer + " ";
      let processedText = handleAutoPunctuation(textWithSpace);
      setKeyboardBuffer(processedText);
    } else {
      setKeyboardBuffer(keyboardBuffer + k);
    }
  }

  function handleKeyboardControl(key) {
    if (key === "Space") {
      insertKey(" ");
    } else if (key === "Del Letter") {
      setKeyboardBuffer(keyboardBuffer.slice(0, -1));
    } else if (key === "Del Word") {
      setKeyboardBuffer(keyboardBuffer.trimEnd().replace(/\S+\s*$/, ""));
    } else if (key === "Clear") {
      setKeyboardBuffer("");
    } else if (key === "Send") {
      submitEntry();
    } else if (key === "Exit") {
      closeKeyboard();
    }
  }

  function submitEntry() {
    const answer = keyboardBuffer.trim();
    if (answer) {
      if (editingEntryId) {
        updateEntry(editingEntryId, answer);
        speak("Entry updated!");
      } else {
        addEntry(currentQuestion, answer);
        speak("Entry saved!");
      }
      setTimeout(() => {
        closeKeyboard();
        renderEntries();
      }, 1000);
    } else {
      speak("Please type an answer first");
    }
  }

  function closeKeyboard() {
    setKeyboardBuffer("");
    editingEntryId = null;
    showScreen("entriesScreen");
    questionModal.classList.add("hidden");
    renderEntries();
  }

  function openKeyboard() {
    showScreen("keyboardScreen");
    setKeyboardBuffer("");
    renderKeyboard();
    keyboardRowIndex = 0;
    keyboardButtonIndex = 0;
    keyboardInRowMode = true;
    highlightKeyboardRow(0);
  }

  function updateKeyboardScanItems() {
    // Keyboard has special scanning logic
  }

  function keyboardScanForward() {
    if (keyboardInRowMode) {
      keyboardRowIndex = (keyboardRowIndex + 1) % (keyboardRows.length + 2);
      clearAllHighlights();
      if (keyboardRowIndex === 0) {
        textBar.classList.add("highlighted");
        // Only speak if there's content in the buffer
        const text = keyboardBuffer.trim();
        if (text) speak(text);
      } else if (keyboardRowIndex === keyboardRows.length + 1) {
        highlightPredictiveRow();
        speakPredictions();
      } else {
        highlightKeyboardRow(keyboardRowIndex - 1);
        speakRowTitle(keyboardRowIndex - 1);
      }
    } else {
      if (keyboardRowIndex === keyboardRows.length + 1) {
        const chips = predictBar.querySelectorAll(".chip");
        keyboardButtonIndex = (keyboardButtonIndex + 1) % chips.length;
        highlightPredictiveButton(keyboardButtonIndex);
        speakPredictiveButton(keyboardButtonIndex);
      } else if (keyboardRowIndex > 0) {
        keyboardButtonIndex = (keyboardButtonIndex + 1) % keyboardRows[keyboardRowIndex - 1].length;
        highlightKeyboardButton(keyboardRowIndex - 1, keyboardButtonIndex);
        speak(keyboardRows[keyboardRowIndex - 1][keyboardButtonIndex]);
      }
    }
  }

  function keyboardScanBackward() {
    if (keyboardInRowMode) {
      keyboardRowIndex = (keyboardRowIndex - 1 + (keyboardRows.length + 2)) % (keyboardRows.length + 2);
      clearAllHighlights();
      if (keyboardRowIndex === 0) {
        textBar.classList.add("highlighted");
        // Only speak if there's content in the buffer
        const text = keyboardBuffer.trim();
        if (text) speak(text);
      } else if (keyboardRowIndex === keyboardRows.length + 1) {
        highlightPredictiveRow();
        speakPredictions();
      } else {
        highlightKeyboardRow(keyboardRowIndex - 1);
        speakRowTitle(keyboardRowIndex - 1);
      }
    } else {
      if (keyboardRowIndex === keyboardRows.length + 1) {
        const chips = predictBar.querySelectorAll(".chip");
        keyboardButtonIndex = (keyboardButtonIndex - 1 + chips.length) % chips.length;
        highlightPredictiveButton(keyboardButtonIndex);
        speakPredictiveButton(keyboardButtonIndex);
      } else if (keyboardRowIndex > 0) {
        const rowLen = keyboardRows[keyboardRowIndex - 1].length;
        keyboardButtonIndex = (keyboardButtonIndex - 1 + rowLen) % rowLen;
        highlightKeyboardButton(keyboardRowIndex - 1, keyboardButtonIndex);
        speak(keyboardRows[keyboardRowIndex - 1][keyboardButtonIndex]);
      }
    }
  }

  async function keyboardSelect() {
    if (keyboardInRowMode) {
      if (keyboardRowIndex === 0) {
        const text = keyboardBuffer.trim();
        if (text) speak(text);
      } else {
        keyboardInRowMode = false;
        keyboardButtonIndex = 0;
        clearAllHighlights();
        if (keyboardRowIndex === keyboardRows.length + 1) {
          highlightPredictiveButton(0);
          speakPredictiveButton(0);
        } else {
          highlightKeyboardButton(keyboardRowIndex - 1, 0);
          speak(keyboardRows[keyboardRowIndex - 1][0]);
        }
      }
    } else {
      if (keyboardRowIndex === keyboardRows.length + 1) {
        const chips = predictBar.querySelectorAll(".chip");
        if (chips[keyboardButtonIndex] && chips[keyboardButtonIndex].textContent.trim()) {
          const word = chips[keyboardButtonIndex].textContent.trim();
          const currentPartial = getCurrentWord();
          let newBuffer = keyboardBuffer;
          if (currentPartial && !keyboardBuffer.endsWith(" ")) {
            newBuffer = keyboardBuffer.slice(0, -currentPartial.length) + word + " ";
          } else {
            if (!keyboardBuffer.endsWith(" ") && keyboardBuffer.length) newBuffer += " ";
            newBuffer += word + " ";
          }
          await setKeyboardBuffer(newBuffer);
        }
      } else {
        const key = keyboardRows[keyboardRowIndex - 1][keyboardButtonIndex];
        if (keyboardRowIndex - 1 === 0) {
          handleKeyboardControl(key);
        } else {
          insertKey(key);
        }
      }
      keyboardInRowMode = true;
      clearAllHighlights();
      if (keyboardRowIndex === keyboardRows.length + 1) {
        highlightPredictiveRow();
        speakPredictions();
      } else {
        highlightKeyboardRow(keyboardRowIndex - 1);
        speakRowTitle(keyboardRowIndex - 1);
      }
    }
  }

  function highlightKeyboardRow(rowIndex) {
    clearAllHighlights();
    const allKeys = kb.querySelectorAll(".key");
    const start = rowIndex * 6;
    for (let i = 0; i < 6; i++) {
      if (allKeys[start + i]) {
        allKeys[start + i].classList.add("highlighted");
      }
    }
  }

  function highlightKeyboardButton(rowIndex, buttonIndex) {
    clearAllHighlights();
    const allKeys = kb.querySelectorAll(".key");
    const idx = rowIndex * 6 + buttonIndex;
    if (allKeys[idx]) {
      allKeys[idx].classList.add("highlighted");
    }
  }

  function highlightPredictiveRow() {
    clearAllHighlights();
    predictBar.querySelectorAll(".chip").forEach(chip => chip.classList.add("highlighted"));
  }

  function highlightPredictiveButton(index) {
    clearAllHighlights();
    const chips = predictBar.querySelectorAll(".chip");
    if (chips[index]) chips[index].classList.add("highlighted");
  }

  function speakRowTitle(rowIndex) {
    const titles = ["controls", "a b c d e f", "g h i j k l", "m n o p q r", "s t u v w x", "y z 0 1 2 3", "4 5 6 7 8 9"];
    if (titles[rowIndex]) speak(titles[rowIndex]);
  }

  function speakPredictions() {
    const chips = predictBar.querySelectorAll(".chip");
    const words = Array.from(chips).map(c => {
      let text = c.textContent.trim();
      // Fix for short uppercase words (like "IT", "IS") being read as letters
      if (text && text.length > 1 && text.length <= 4 && text === text.toUpperCase()) {
        return text.toLowerCase();
      }
      return text;
    }).filter(t => t);
    
    if (words.length) speak(words.join(", "));
    else speak("no predictions");
  }

  function speakPredictiveButton(index) {
    const chips = predictBar.querySelectorAll(".chip");
    if (chips[index] && chips[index].textContent.trim()) {
      speak(chips[index].textContent.trim());
    }
  }

  function getCurrentWord() {
    const trimmed = keyboardBuffer.replace(/\|/g, "").trimEnd();
    const parts = trimmed.split(/\s+/);
    if (keyboardBuffer.endsWith(" ")) return "";
    return parts[parts.length - 1] || "";
  }

  async function renderPredictions() {
    let predictions = ["YES", "NO", "GOOD", "BAD", "FUN", "HAPPY"];

    if (window.predictionSystem && window.predictionSystem.getHybridPredictions) {
      try {
        predictions = await window.predictionSystem.getHybridPredictions(keyboardBuffer);
      } catch (e) {
        console.error('Error getting predictions:', e);
      }
    }

    predictBar.innerHTML = "";
    predictions.slice(0, 6).forEach(w => {
      const chip = document.createElement("button");
      chip.className = "chip";
      chip.textContent = w;
      chip.addEventListener("click", () => {
        const partial = getCurrentWord();
        let newBuf = keyboardBuffer;
        if (partial && !keyboardBuffer.endsWith(" ")) {
          newBuf = keyboardBuffer.slice(0, -partial.length) + w + " ";
        } else {
          if (!keyboardBuffer.endsWith(" ") && keyboardBuffer.length) newBuf += " ";
          newBuf += w + " ";
        }
        setKeyboardBuffer(newBuf);
      });
      predictBar.appendChild(chip);
    });

    while (predictBar.children.length < 6) {
      const chip = document.createElement("button");
      chip.className = "chip";
      chip.textContent = "";
      chip.disabled = true;
      predictBar.appendChild(chip);
    }
  }

  // ========== ENTRIES DISPLAY ==========
  function renderEntries() {
    currentPeriodLabel.textContent = formatCurrentViewDate();

    // Filter entries for current day
    const dayStart = new Date(currentViewDate);
    dayStart.setHours(0, 0, 0, 0);
    const dayEnd = new Date(currentViewDate);
    dayEnd.setHours(23, 59, 59, 999);

    const dayEntries = entries.filter(e => {
      const d = new Date(e.date);
      return d >= dayStart && d <= dayEnd;
    });

    entriesList.innerHTML = "";

    if (dayEntries.length === 0) {
      entriesList.innerHTML = '<div class="no-entries">No entries for this day</div>';
    } else {
      dayEntries.slice(0, 7).forEach(entry => {
        const item = document.createElement("button");
        item.className = "entry-item";
        item.innerHTML = `
          <span class="entry-date-label">${formatShortDate(entry.date)}</span>
          <span class="entry-preview">${entry.question}: ${entry.answer}</span>
        `;
        item.addEventListener("click", () => viewEntry(entry));
        entriesList.appendChild(item);
      });
    }

    updateScanItems();
    highlightCurrentItem();
  }

  function viewEntry(entry) {
    $("#entryViewDate").textContent = formatDate(entry.date);
    $("#entryViewQuestion").textContent = entry.question;
    $("#entryViewAnswer").textContent = entry.answer;
    entryViewModal.classList.remove("hidden");
    entryViewModal.dataset.entryId = entry.id;
    updateScanItems();
    scanIndex = -1;  // Start at -1, no highlight until first scan
    clearAllHighlights();
  }

  function navigateEntries(direction) {
    const d = new Date(currentViewDate);
    switch (direction) {
      case "prev-month":
        d.setMonth(d.getMonth() - 1);
        break;
      case "next-month":
        d.setMonth(d.getMonth() + 1);
        break;
      case "prev-week":
        d.setDate(d.getDate() - 7);
        break;
      case "next-week":
        d.setDate(d.getDate() + 7);
        break;
      case "prev-day":
        d.setDate(d.getDate() - 1);
        break;
      case "next-day":
        d.setDate(d.getDate() + 1);
        break;
      case "today":
        currentViewDate = new Date();
        renderEntries();
        return;
    }
    currentViewDate = d;
    renderEntries();
  }

  // Helper function to update the date preview in Change Date modal
  function updateDatePreview() {
    if (datePreview) {
      datePreview.textContent = formatCurrentViewDate();
    }
  }

  // ========== OPTIONS ==========
  function updateDisplays() {
    $("#themeValue").textContent = themes[currentThemeIndex].charAt(0).toUpperCase() + themes[currentThemeIndex].slice(1);
    $("#highlightValue").textContent = highlightColors[currentHighlightIndex].charAt(0).toUpperCase() + highlightColors[currentHighlightIndex].slice(1);
    $("#scanSpeedValue").textContent = currentScanSpeed.charAt(0).toUpperCase() + currentScanSpeed.slice(1);
    $("#autoScanValue").textContent = isAutoScanning ? "On" : "Off";

    if (window.NarbeVoiceManager) {
      const voice = window.NarbeVoiceManager.getCurrentVoice();
      $("#voiceValue").textContent = window.NarbeVoiceManager.getVoiceDisplayName(voice);
      $("#ttsToggleValue").textContent = window.NarbeVoiceManager.getSettings().ttsEnabled ? "On" : "Off";
    }
  }

  function handleOptionClick(setting) {
    switch (setting) {
      case "theme":
        currentThemeIndex = (currentThemeIndex + 1) % themes.length;
        applyTheme(themes[currentThemeIndex]);
        speak(themes[currentThemeIndex]);
        break;
      case "highlight":
        currentHighlightIndex = (currentHighlightIndex + 1) % highlightColors.length;
        applyHighlightColor(highlightColors[currentHighlightIndex]);
        speak(highlightColors[currentHighlightIndex]);
        break;
      case "scan-speed":
        const speeds = ["slow", "medium", "fast"];
        const idx = speeds.indexOf(currentScanSpeed);
        currentScanSpeed = speeds[(idx + 1) % speeds.length];
        settings.scanSpeed = currentScanSpeed;
        saveSettings();
        updateDisplays();
        speak(currentScanSpeed);
        if (isAutoScanning) {
          stopAutoScan();
          startAutoScan();
        }
        break;
      case "auto-scan":
        isAutoScanning = !isAutoScanning;
        settings.autoScan = isAutoScanning;
        saveSettings();
        updateDisplays();
        speak(isAutoScanning ? "Auto scan on" : "Auto scan off");
        if (isAutoScanning) startAutoScan();
        else stopAutoScan();
        break;
      case "voice":
        if (window.NarbeVoiceManager) {
          window.NarbeVoiceManager.cycleVoice();
          updateDisplays();
          const voice = window.NarbeVoiceManager.getCurrentVoice();
          speak(window.NarbeVoiceManager.getVoiceDisplayName(voice));
        }
        break;
      case "tts-toggle":
        if (window.NarbeVoiceManager) {
          const enabled = window.NarbeVoiceManager.toggleTTS();
          updateDisplays();
          if (enabled) speak("TTS enabled");
        }
        break;
    }
  }

  // ========== EVENT HANDLERS ==========
  // Main menu buttons
  $$("#mainMenu .menu-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const action = btn.dataset.action;
      if (action === "entries") {
        showScreen("entriesScreen");
        renderEntries();
        speak("Entries");
      } else if (action === "options") {
        showScreen("optionsScreen");
        speak("Options");
      } else if (action === "exit") {
        speak("Goodbye!");
        closeApp();
      }
    });
  });

  // Entries screen buttons
  $$("#entriesScreen .action-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const action = btn.dataset.action;
      if (action === "question-entry") {
        currentQuestion = getRandomQuestion();
        $("#questionText").textContent = currentQuestion;
        questionModal.classList.remove("hidden");
        speak(currentQuestion);
        updateScanItems();
        scanIndex = -1;
        clearAllHighlights();
      } else if (action === "add-entry") {
        currentQuestion = "Journal Entry";
        editingEntryId = null;
        openKeyboard();
        speak("Type your entry");
      } else if (action === "change-view") {
        changeViewModal.classList.remove("hidden");
        updateDatePreview();
        speak("Change Date");
        updateScanItems();
        scanIndex = -1;
        clearAllHighlights();
      } else if (action === "back-to-menu") {
        showScreen("mainMenu");
        speak("Journal");
      }
    });
  });

  // Helper function to check if current view date is today or in the future
  function isOnTodayOrFuture() {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const viewDate = new Date(currentViewDate);
    viewDate.setHours(0, 0, 0, 0);
    return viewDate >= today;
  }

  // Change View modal buttons
  $$("#changeViewModal .modal-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const action = btn.dataset.action;
      if (action === "view-prev-day") {
        navigateEntries("prev-day");
        updateDatePreview();
        speak(formatCurrentViewDate());
      } else if (action === "view-next-day") {
        if (!isOnTodayOrFuture()) {
          navigateEntries("next-day");
          updateDatePreview();
          speak(formatCurrentViewDate());
        } else {
          speak("Already on today");
        }
      } else if (action === "view-prev-week") {
        navigateEntries("prev-week");
        updateDatePreview();
        speak(formatCurrentViewDate());
      } else if (action === "view-next-week") {
        if (!isOnTodayOrFuture()) {
          navigateEntries("next-week");
          updateDatePreview();
          speak(formatCurrentViewDate());
        } else {
          speak("Already on today");
        }
      } else if (action === "view-prev-month") {
        navigateEntries("prev-month");
        updateDatePreview();
        speak(formatCurrentViewDate());
      } else if (action === "view-next-month") {
        if (!isOnTodayOrFuture()) {
          navigateEntries("next-month");
          updateDatePreview();
          speak(formatCurrentViewDate());
        } else {
          speak("Already on today");
        }
      } else if (action === "view-today") {
        navigateEntries("today");
        updateDatePreview();
        speak(formatCurrentViewDate());
      } else if (action === "close-view-modal") {
        changeViewModal.classList.add("hidden");
        updateScanItems();
        highlightCurrentItem();
      }
    });
  });

  // Question modal buttons
  $$("#questionModal .modal-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const action = btn.dataset.action;
      if (action === "new-question") {
        currentQuestion = getRandomQuestion();
        $("#questionText").textContent = currentQuestion;
        speak(currentQuestion);
      } else if (action === "add-answer") {
        questionModal.classList.add("hidden");
        openKeyboard();
        speak("Type your answer");
      } else if (action === "close-modal") {
        questionModal.classList.add("hidden");
        updateScanItems();
        highlightCurrentItem();
      }
    });
  });

  // Options buttons
  $$("#optionsScreen .option-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      handleOptionClick(btn.dataset.setting);
    });
  });

  $$("#optionsScreen .menu-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      showScreen("mainMenu");
      speak("Journal");
    });
  });

  // Entry view modal buttons
  $$("#entryViewModal .modal-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const action = btn.dataset.action;
      if (action === "read-entry") {
        const question = $("#entryViewQuestion").textContent;
        const answer = $("#entryViewAnswer").textContent;
        speak(`${question} ${answer}`);
      } else if (action === "edit-entry") {
        const entryId = parseInt(entryViewModal.dataset.entryId);
        const entry = entries.find(e => e.id === entryId);
        if (entry) {
          editingEntryId = entryId;
          currentQuestion = entry.question;
          entryViewModal.classList.add("hidden");
          openKeyboard();
          setKeyboardBuffer(entry.answer);
          speak("Edit your entry");
        }
      } else if (action === "delete-entry") {
        entryToDelete = parseInt(entryViewModal.dataset.entryId);
        deleteConfirmModal.classList.remove("hidden");
        speak("Are you sure you want to delete this entry?");
        updateScanItems();
        scanIndex = -1;  // Start at -1, no highlight until first scan
        clearAllHighlights();
      } else if (action === "close-entry-view") {
        entryViewModal.classList.add("hidden");
        updateScanItems();
        scanIndex = -1;
        clearAllHighlights();
      }
    });
  });

  // Delete confirmation modal buttons
  $$("#deleteConfirmModal .modal-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const action = btn.dataset.action;
      if (action === "cancel-delete") {
        deleteConfirmModal.classList.add("hidden");
        entryToDelete = null;
        updateScanItems();
        highlightCurrentItem();
      } else if (action === "confirm-delete") {
        if (entryToDelete) {
          deleteEntry(entryToDelete);
          speak("Entry deleted");
        }
        deleteConfirmModal.classList.add("hidden");
        entryViewModal.classList.add("hidden");
        entryToDelete = null;
        renderEntries();
      }
    });
  });

  // Close app
  async function closeApp() {
    try {
      await fetch('/api/close_chrome', { method: 'POST' });
    } catch (e) {
      console.log('Could not close app:', e);
      window.close();
    }
  }

  // ========== INITIALIZATION ==========
  async function init() {
    console.log("Initializing Ben's Journal App...");

    // Load entries from server/localStorage
    await loadEntries();
    await loadQuestions();
    loadUsedQuestions();

    // Apply settings
    applyTheme(settings.theme);
    applyHighlightColor(settings.highlightColor);
    currentScanSpeed = settings.scanSpeed || "medium";
    isAutoScanning = settings.autoScan || false;

    // Set view to today
    currentViewDate = new Date();

    // Wait for voice manager
    if (window.NarbeVoiceManager && window.NarbeVoiceManager.waitForVoices) {
      window.NarbeVoiceManager.waitForVoices().then(() => {
        updateDisplays();
      });
    } else {
      setTimeout(updateDisplays, 500);
    }

    // Show main menu
    showScreen("mainMenu");
    speak("Journal");

    // Start auto scan if enabled
    if (isAutoScanning) {
      startAutoScan();
    }

    console.log("Journal app initialized!");
  }

  init();
})();
