(() => {
  const $ = (sel) => document.querySelector(sel);
  const textBar = $("#textBar");
  const predictBar = $("#predictBar");
  const kb = $("#keyboard");
  const settingsMenu = $("#settingsMenu");

  const defaultSettings = {
    baseUrl: "http://127.0.0.1:5000",
    jsonPath: "/api/predictive_ngrams",
    autocapI: true,
    theme: "default",
    scanSpeed: "medium",
    voiceIndex: 0
  };

  let settings = loadSettings();
  function loadSettings() {
    try { 
      const v = JSON.parse(localStorage.getItem("kb_settings")); 
      return { ...defaultSettings, ...v }; 
    }
    catch { 
      return { ...defaultSettings }; 
    }
  }
  function saveSettings() {
    localStorage.setItem("kb_settings", JSON.stringify(settings));
  }

  // TTS functionality with voice management
  let ttsEngine = null;
  let availableVoices = [];
  let englishVoices = [];
  let currentVoiceIndex = 0;

  function initTTS() {
    if ('speechSynthesis' in window) {
      ttsEngine = window.speechSynthesis;
      
      function loadVoices() {
        availableVoices = ttsEngine.getVoices();
        if (availableVoices.length > 0) {
          // Filter for English voices only
          englishVoices = availableVoices.filter(voice => 
            voice.lang.startsWith('en-') || voice.lang === 'en'
          );
          
          console.log(`Found ${englishVoices.length} English voices:`, englishVoices.map(v => v.name));
          
          currentVoiceIndex = settings.voiceIndex || 0;
          // Ensure index is within bounds
          if (currentVoiceIndex >= englishVoices.length) {
            currentVoiceIndex = 0;
          }
          updateVoiceDisplay();
        }
      }
      
      loadVoices();
      if (ttsEngine.onvoiceschanged !== undefined) {
        ttsEngine.onvoiceschanged = loadVoices;
      }
    } else {
      console.warn("Speech synthesis not supported");
    }
  }

  function speak(text) {
    if (!ttsEngine) return;
    
    ttsEngine.cancel();
    
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1.0;
    utterance.pitch = 1.0;
    utterance.volume = 1.0;
    
    if (englishVoices.length > 0 && englishVoices[currentVoiceIndex]) {
      utterance.voice = englishVoices[currentVoiceIndex];
    }
    
    console.log(`TTS: ${text}`);
    ttsEngine.speak(utterance);
  }

  function getVoiceDisplayName(voice) {
    if (!voice) return "Default";
    
    const name = voice.name.toLowerCase();
    
    // Count voices by provider and gender for numbering
    const providerVoices = englishVoices.filter(v => {
      const vName = v.name.toLowerCase();
      if (name.includes('google')) return vName.includes('google');
      if (name.includes('microsoft')) return vName.includes('microsoft');
      if (name.includes('apple')) return vName.includes('apple');
      if (name.includes('samsung')) return vName.includes('samsung');
      return false;
    });
    
    let provider = "Unknown";
    if (name.includes('google')) provider = "Google";
    else if (name.includes('microsoft')) provider = "Microsoft";
    else if (name.includes('apple')) provider = "Apple";
    else if (name.includes('samsung')) provider = "Samsung";
    
    // Determine gender based on common patterns
    let gender = "Voice";
    if (name.includes('female') || name.includes('woman') || name.includes('girl') ||
        name.includes('zira') || name.includes('cortana') || name.includes('hazel') ||
        name.includes('susan') || name.includes('karen') || name.includes('heather') ||
        name.includes('linda') || name.includes('julie') || name.includes('catherine')) {
      gender = "Female";
    } else if (name.includes('male') || name.includes('man') || name.includes('boy') ||
               name.includes('david') || name.includes('mark') || name.includes('richard') ||
               name.includes('george') || name.includes('james') || name.includes('kevin') ||
               name.includes('paul') || name.includes('sean') || name.includes('benjamin')) {
      gender = "Male";
    }
    
    // Find the index of this voice within its provider/gender group
    const sameTypeVoices = providerVoices.filter(v => {
      const vName = v.name.toLowerCase();
      const vGender = (vName.includes('female') || vName.includes('woman') || 
                       vName.includes('zira') || vName.includes('cortana') ||
                       vName.includes('hazel') || vName.includes('susan') ||
                       vName.includes('karen') || vName.includes('heather') ||
                       vName.includes('linda') || vName.includes('julie') ||
                       vName.includes('catherine')) ? "Female" : 
                      (vName.includes('male') || vName.includes('man') ||
                       vName.includes('david') || vName.includes('mark') ||
                       vName.includes('richard') || vName.includes('george') ||
                       vName.includes('james') || vName.includes('kevin') ||
                       vName.includes('paul') || vName.includes('sean') ||
                       vName.includes('benjamin')) ? "Male" : "Voice";
      return vGender === gender;
    });
    
    const voiceNumber = sameTypeVoices.findIndex(v => v.name === voice.name) + 1;
    
    return `${provider} ${gender} ${voiceNumber}`;
  }

  // Scan timing configuration
  const scanSpeeds = {
    slow: { forward: 1500, backward: 3000, longPress: 4000 },
    medium: { forward: 1000, backward: 2000, longPress: 3000 },
    fast: { forward: 500, backward: 1000, longPress: 2000 }
  };

  let currentScanSpeed = settings.scanSpeed || "medium";

  // Theme management
  const themes = ["default", "light", "dark", "blue", "green", "purple", "orange"];
  let currentThemeIndex = themes.indexOf(settings.theme) || 0;

  function applyTheme(theme) {
    themes.forEach(t => document.body.classList.remove(`theme-${t}`));
    if (theme !== "default") {
      document.body.classList.add(`theme-${theme}`);
    }
    settings.theme = theme;
    saveSettings();
    updateThemeDisplay();
  }

  // Settings menu state
  let inSettingsMode = false;
  let settingsRowIndex = 0;
  let settingsItems = [];

  // Scanning state
  let inRowSelectionMode = true;
  let currentRowIndex = 0;
  let currentButtonIndex = 0;
  let spacebarPressed = false;
  let returnPressed = false;
  let spacebarPressTime = null;
  let returnPressTime = null;
  let longPressTriggered = false;
  let backwardScanInterval = null;

  // Text state
  let buffer = "";
  let ttsUseCount = 0;

  function setBuffer(txt) {
    buffer = txt;
    textBar.textContent = buffer + "|";
    ttsUseCount = 0;
    refreshPredictive();
  }

  // Keyboard layout
  const rows = [
    ["Space", "Del Letter", "Del Word", "Clear", "Settings", "Exit"],
    ["A","B","C","D","E","F"],
    ["G","H","I","J","K","L"],
    ["M","N","O","P","Q","R"],
    ["S","T","U","V","W","X"],
    ["Y","Z","0","1","2","3"],
    ["4","5","6","7","8","9"]
  ];

  function renderKeyboard() {
    kb.innerHTML = "";
    rows.forEach((row, rIdx) => {
      row.forEach((key) => {
        const btn = document.createElement("button");
        btn.className = "key" + (rIdx === 0 ? " ctrl" : "");
        
        if (key === "Settings") {
          btn.classList.add("settings");
        } else if (key === "Exit") {
          btn.classList.add("exit");
        }
        
        btn.textContent = key;
        btn.addEventListener("click", () => {
          if (rIdx === 0) {
            handleControl(key);
          } else {
            insertKey(key);
          }
        });
        kb.appendChild(btn);
      });
    });
    highlightTextBox();
  }

  // Keyboard event binding
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
      console.log("Spacebar pressed");
      
      const speed = scanSpeeds[currentScanSpeed];
      
      setTimeout(() => {
        if (spacebarPressed && (Date.now() - spacebarPressTime) >= speed.longPress) {
          console.log("Long press detected - starting backward scanning");
          backwardScanInterval = setInterval(() => {
            if (spacebarPressed) {
              if (inSettingsMode) {
                scanSettingsBackward();
              } else {
                scanBackward();
              }
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
      console.log(`Spacebar released after ${pressDuration}ms`);
      
      if (backwardScanInterval) {
        clearInterval(backwardScanInterval);
        backwardScanInterval = null;
      }
      
      const speed = scanSpeeds[currentScanSpeed];
      
      if (pressDuration >= 250 && pressDuration <= speed.longPress) {
        console.log("Short press - scanning forward");
        if (inSettingsMode) {
          scanSettingsForward();
        } else {
          scanForward();
        }
      }
      
      spacebarPressTime = null;
    }
  }

  function startSelecting() {
    if (!returnPressed) {
      returnPressed = true;
      returnPressTime = Date.now();
      longPressTriggered = false;
      console.log("Return pressed");
      
      setTimeout(() => {
        if (returnPressed && (Date.now() - returnPressTime) >= 3000) {
          handleLongPress();
        }
      }, 3000);
    }
  }

  function stopSelecting() {
    if (returnPressed) {
      returnPressed = false;
      const pressDuration = Date.now() - returnPressTime;
      console.log(`Return released after ${pressDuration}ms`);
      
      if (!longPressTriggered && pressDuration >= 100) {
        console.log("Short press - selecting");
        selectButton();
      }
      
      returnPressTime = null;
      longPressTriggered = false;
    }
  }

  function handleLongPress() {
    longPressTriggered = true;
    clearAllHighlights();
    
    if (inRowSelectionMode) {
      currentRowIndex = 1;
      inRowSelectionMode = true;
      highlightPredictiveRow();
      console.log("Long press: Jumped to predictive text row");
      readPredictiveTTS();
    } else {
      inRowSelectionMode = true;
      if (currentRowIndex === 0) {
        highlightTextBox();
      } else if (currentRowIndex === 1) {
        highlightPredictiveRow();
        speakRowTitle(rows.length);
      } else {
        highlightRow(currentRowIndex - 2);
        speakRowTitle(currentRowIndex - 2);
      }
      console.log("Long press: Returned to row selection mode");
    }
  }

  function scanForward() {
    if (inRowSelectionMode) {
      const prevRow = currentRowIndex;
      currentRowIndex = (currentRowIndex + 1) % (rows.length + 2);
      console.log(`Scanning forward to row ${currentRowIndex}`);
      
      clearAllHighlights();
      if (currentRowIndex === 0) {
        highlightTextBox();
      } else if (currentRowIndex === 1) {
        highlightPredictiveRow();
        speakRowTitle(rows.length);
      } else {
        highlightRow(currentRowIndex - 2);
        speakRowTitle(currentRowIndex - 2);
      }
    } else {
      const prevButton = currentButtonIndex;
      if (currentRowIndex === 0) {
        return;
      } else if (currentRowIndex === 1) {
        const chips = predictBar.querySelectorAll(".chip");
        currentButtonIndex = (currentButtonIndex + 1) % chips.length;
        highlightPredictiveButton(currentButtonIndex, prevButton);
        speakPredictiveButtonLabel(currentButtonIndex);
      } else {
        currentButtonIndex = (currentButtonIndex + 1) % rows[currentRowIndex - 2].length;
        highlightButton(currentButtonIndex, prevButton);
        speakButtonLabel(currentButtonIndex);
      }
    }
  }

  function scanBackward() {
    if (inRowSelectionMode) {
      const prevRow = currentRowIndex;
      currentRowIndex = (currentRowIndex - 1 + (rows.length + 2)) % (rows.length + 2);
      console.log(`Scanning backward to row ${currentRowIndex}`);
      
      clearAllHighlights();
      if (currentRowIndex === 0) {
        highlightTextBox();
      } else if (currentRowIndex === 1) {
        highlightPredictiveRow();
        speakRowTitle(rows.length);
      } else {
        highlightRow(currentRowIndex - 2);
        speakRowTitle(currentRowIndex - 2);
      }
    } else {
      const prevButton = currentButtonIndex;
      if (currentRowIndex === 0) {
        return;
      } else if (currentRowIndex === 1) {
        const chips = predictBar.querySelectorAll(".chip");
        currentButtonIndex = (currentButtonIndex - 1 + chips.length) % chips.length;
        highlightPredictiveButton(currentButtonIndex, prevButton);
        speakPredictiveButtonLabel(currentButtonIndex);
      } else {
        currentButtonIndex = (currentButtonIndex - 1 + rows[currentRowIndex - 2].length) % rows[currentRowIndex - 2].length;
        highlightButton(currentButtonIndex, prevButton);
        speakButtonLabel(currentButtonIndex);
      }
    }
  }

  function selectButton() {
    if (inSettingsMode) {
      selectSettingsItem();
      return;
    }
    
    if (inRowSelectionMode) {
      if (currentRowIndex === 0) {
        const text = buffer.replace(/\|/g, "").trim();
        if (text) {
          speak(text);
          ttsUseCount++;
          console.log(`TTS use count: ${ttsUseCount} for text: "${text}"`);
          
          if (ttsUseCount >= 3) {
            console.log("3x TTS usage detected - saving text to predictive data");
            saveTextToPredictive(text);
            ttsUseCount = 0;
          }
        }
      } else if (currentRowIndex === 1) {
        inRowSelectionMode = false;
        currentButtonIndex = 0;
        clearAllHighlights();
        const chips = predictBar.querySelectorAll(".chip");
        if (chips.length > 0) {
          highlightPredictiveButton(0);
          speakPredictiveButtonLabel(0);
        }
      } else {
        inRowSelectionMode = false;
        currentButtonIndex = 0;
        clearAllHighlights();
        highlightButton(0);
        speakButtonLabel(0);
      }
    } else {
      if (currentRowIndex === 0) {
        return;
      } else if (currentRowIndex === 1) {
        const chips = predictBar.querySelectorAll(".chip");
        if (chips[currentButtonIndex] && chips[currentButtonIndex].textContent.trim()) {
          const word = chips[currentButtonIndex].textContent.trim();
          const currentPartialWord = currentWord();
          let newBuffer = buffer;
          
          if (currentPartialWord && !buffer.endsWith(" ")) {
            newBuffer = buffer.slice(0, -currentPartialWord.length) + word + " ";
          } else {
            if (!buffer.endsWith(" ") && buffer.length) newBuffer += " ";
            newBuffer += word + " ";
          }
          
          setBuffer(newBuffer);
          pingUsage("", word);
        }
      } else {
        const key = rows[currentRowIndex - 2][currentButtonIndex];
        if (currentRowIndex - 2 === 0) {
          handleControl(key);
        } else {
          insertKey(key);
        }
      }
      
      inRowSelectionMode = true;
      clearAllHighlights();
      if (currentRowIndex === 0) {
        highlightTextBox();
      } else if (currentRowIndex === 1) {
        highlightPredictiveRow();
      } else {
        highlightRow(currentRowIndex - 2);
      }
    }
  }

  async function saveTextToPredictive(text) {
    try {
      console.log(`DEBUG: Calling /api/save_text with text: "${text}"`);
      const response = await fetch(settings.baseUrl + "/api/save_text", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: text })
      });
      
      if (response.ok) {
        const result = await response.json();
        console.log("Text saved to predictive data successfully:", result);
        refreshPredictive();
      } else {
        console.error("Error saving text - HTTP status:", response.status);
      }
    } catch (error) {
      console.error("Error saving text to predictive data:", error);
    }
  }

  function clearAllHighlights() {
    textBar.classList.remove("highlighted");
    const allKeys = kb.querySelectorAll(".key");
    allKeys.forEach(key => key.classList.remove("highlighted"));
    const allChips = predictBar.querySelectorAll(".chip");
    allChips.forEach(chip => chip.classList.remove("highlighted"));
  }

  function highlightTextBox() {
    clearAllHighlights();
    textBar.classList.add("highlighted");
  }

  function highlightRow(rowIndex) {
    clearAllHighlights();
    const rowStart = rowIndex * 6;
    const allKeys = kb.querySelectorAll(".key");
    
    for (let i = 0; i < 6; i++) {
      if (allKeys[rowStart + i]) {
        allKeys[rowStart + i].classList.add("highlighted");
      }
    }
  }

  function highlightButton(buttonIndex, prevButtonIndex = null) {
    const rowStart = (currentRowIndex - 2) * 6;
    const allKeys = kb.querySelectorAll(".key");
    
    if (prevButtonIndex !== null && allKeys[rowStart + prevButtonIndex]) {
      allKeys[rowStart + prevButtonIndex].classList.remove("highlighted");
    }
    
    if (allKeys[rowStart + buttonIndex]) {
      allKeys[rowStart + buttonIndex].classList.add("highlighted");
    }
  }

  function highlightPredictiveRow() {
    clearAllHighlights();
    const allChips = predictBar.querySelectorAll(".chip");
    allChips.forEach(chip => chip.classList.add("highlighted"));
  }

  function highlightPredictiveButton(buttonIndex, prevButtonIndex = null) {
    const chips = predictBar.querySelectorAll(".chip");
    
    if (prevButtonIndex !== null && chips[prevButtonIndex]) {
      chips[prevButtonIndex].classList.remove("highlighted");
    }
    
    if (chips[buttonIndex]) {
      chips[buttonIndex].classList.add("highlighted");
    }
  }

  function speakRowTitle(rowIndex) {
    const rowTitles = [
      "controls", 
      "a b c d e f", 
      "g h i j k l", 
      "m n o p q r", 
      "s t u v w x", 
      "y z 0 1 2 3", 
      "4 5 6 7 8 9", 
      "predictive text"
    ];
    
    if (rowIndex < rowTitles.length) {
      speak(rowTitles[rowIndex]);
    }
  }

  function speakButtonLabel(buttonIndex) {
    const label = rows[currentRowIndex - 2][buttonIndex];
    let spokenLabel = label.toLowerCase();
    
    if (spokenLabel === "del letter") spokenLabel = "delete letter";
    if (spokenLabel === "del word") spokenLabel = "delete word";
    
    speak(spokenLabel);
  }

  function speakPredictiveButtonLabel(buttonIndex) {
    const chips = predictBar.querySelectorAll(".chip");
    if (chips[buttonIndex] && chips[buttonIndex].textContent.trim()) {
      speak(chips[buttonIndex].textContent.toLowerCase());
    }
  }

  function readPredictiveTTS() {
    const chips = predictBar.querySelectorAll(".chip");
    chips.forEach(chip => {
      if (chip.textContent.trim()) {
        speak(chip.textContent.toLowerCase());
      }
    });
  }

  // Settings menu functions
  function openSettings() {
    inSettingsMode = true;
    settingsMenu.classList.remove("hidden");
    kb.style.display = "none";
    predictBar.style.display = "none";
    textBar.style.display = "none"; // Hide text bar too
    
    settingsItems = Array.from(settingsMenu.querySelectorAll(".settings-item"));
    settingsRowIndex = 0;
    highlightSettingsItem(0);
    
    updateThemeDisplay();
    updateScanSpeedDisplay();
    updateVoiceDisplay();
    
    // Add mouse event listeners to settings items
    settingsItems.forEach((item, index) => {
      // Mouse click handler
      item.addEventListener('click', () => {
        settingsRowIndex = index;
        highlightSettingsItem(settingsRowIndex);
        selectSettingsItem();
      });
      
      // Mouse hover handler
      item.addEventListener('mouseenter', () => {
        settingsRowIndex = index;
        highlightSettingsItem(settingsRowIndex);
        
        // Speak the setting name on hover
        const label = item.querySelector(".setting-label").textContent;
        speak(label.toLowerCase());
      });
    });
  }

  function closeSettings() {
    inSettingsMode = false;
    settingsMenu.classList.add("hidden");
    kb.style.display = "grid";
    predictBar.style.display = "grid";
    textBar.style.display = "flex"; // Show text bar again
    
    // Remove mouse event listeners from settings items
    settingsItems.forEach(item => {
      // Clone the node to remove all event listeners
      const newItem = item.cloneNode(true);
      item.parentNode.replaceChild(newItem, item);
    });
    
    inRowSelectionMode = true;
    currentRowIndex = 0;
    highlightTextBox();
  }

  function highlightSettingsItem(index) {
    settingsItems.forEach(item => item.classList.remove("highlighted"));
    if (settingsItems[index]) {
      settingsItems[index].classList.add("highlighted");
    }
  }

  function scanSettingsForward() {
    settingsRowIndex = (settingsRowIndex + 1) % settingsItems.length;
    highlightSettingsItem(settingsRowIndex);
    
    const item = settingsItems[settingsRowIndex];
    const label = item.querySelector(".setting-label").textContent;
    speak(label.toLowerCase());
  }

  function scanSettingsBackward() {
    settingsRowIndex = (settingsRowIndex - 1 + settingsItems.length) % settingsItems.length;
    highlightSettingsItem(settingsRowIndex);
    
    const item = settingsItems[settingsRowIndex];
    const label = item.querySelector(".setting-label").textContent;
    speak(label.toLowerCase());
  }

  function selectSettingsItem() {
    const item = settingsItems[settingsRowIndex];
    const setting = item.dataset.setting;
    
    switch (setting) {
      case "volume-up":
        changeVolume(10);
        speak("volume increased");
        break;
        
      case "volume-down":
        changeVolume(-10);
        speak("volume decreased");
        break;
        
      case "theme":
        cycleTheme();
        break;
        
      case "scan-speed":
        cycleScanSpeed();
        break;
        
      case "voice":
        cycleVoice();
        break;
        
      case "close":
        closeSettings();
        speak("settings closed");
        break;
    }
  }

  function changeVolume(delta) {
    const steps = Math.abs(delta / 2); // Convert percentage to steps (2% per step, so 10% = 5 steps)
    const action = delta > 0 ? "up" : "down";
    
    // Call the server API to control system volume
    fetch(settings.baseUrl + "/api/volume_control", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ 
        action: action, 
        steps: steps 
      })
    })
    .then(response => response.json())
    .then(result => {
      if (result.ok) {
        console.log(`Volume control successful: ${result.message}`);
      } else {
        console.error(`Volume control failed: ${result.error}`);
      }
    })
    .catch(error => {
      console.error("Error calling volume control API:", error);
    });
  }

  function cycleTheme() {
    currentThemeIndex = (currentThemeIndex + 1) % themes.length;
    const newTheme = themes[currentThemeIndex];
    applyTheme(newTheme);
    speak(newTheme);
  }

  function updateThemeDisplay() {
    const themeValue = $("#themeValue");
    if (themeValue) {
      themeValue.textContent = themes[currentThemeIndex];
    }
  }

  function cycleScanSpeed() {
    const speeds = ["slow", "medium", "fast"];
    const currentIndex = speeds.indexOf(currentScanSpeed);
    const nextIndex = (currentIndex + 1) % speeds.length;
    currentScanSpeed = speeds[nextIndex];
    
    settings.scanSpeed = currentScanSpeed;
    saveSettings();
    updateScanSpeedDisplay();
    speak(currentScanSpeed);
  }

  function updateScanSpeedDisplay() {
    const speedValue = $("#scanSpeedValue");
    if (speedValue) {
      speedValue.textContent = currentScanSpeed.charAt(0).toUpperCase() + currentScanSpeed.slice(1);
    }
  }

  function cycleVoice() {
    if (englishVoices.length === 0) {
      speak("no english voices available");
      return;
    }
    
    currentVoiceIndex = (currentVoiceIndex + 1) % englishVoices.length;
    settings.voiceIndex = currentVoiceIndex;
    saveSettings();
    updateVoiceDisplay();
    
    const voice = englishVoices[currentVoiceIndex];
    const displayName = getVoiceDisplayName(voice);
    speak(`voice changed to ${displayName}`);
  }

  function updateVoiceDisplay() {
    const voiceValue = $("#voiceValue");
    if (voiceValue && englishVoices.length > 0 && englishVoices[currentVoiceIndex]) {
      const voice = englishVoices[currentVoiceIndex];
      const displayName = getVoiceDisplayName(voice);
      voiceValue.textContent = displayName;
    } else if (voiceValue) {
      voiceValue.textContent = "Default";
    }
  }

  function handleControl(key) {
    if (key === "Space") return insertKey(" ");
    if (key === "Del Letter") { setBuffer(buffer.slice(0, -1)); return; }
    if (key === "Del Word")   { setBuffer(buffer.trimEnd().replace(/\S+\s*$/, "")); return; }
    if (key === "Clear")      { setBuffer(""); return; }
    if (key === "Settings")   { 
      openSettings();
      return; 
    }
    if (key === "Exit")       { 
      console.log("Exit button pressed, closing Chrome...");
      fetch(settings.baseUrl + "/api/close_chrome", { 
        method: "POST",
        headers: { "Content-Type": "application/json" }
      })
        .then(response => {
          console.log("Chrome close request sent successfully");
        })
        .catch(error => {
          console.error("Error closing Chrome:", error);
          window.close();
        });
      return; 
    }
  }

  function insertKey(k) {
    if (settings.autocapI && k.length === 1) {
      const prev = buffer.slice(-1);
      if ((k === "i" || k === "I") && (!prev || /\s/.test(prev))) k = "I";
    }
    setBuffer(buffer + k);
    pingUsage("", "");
  }

  let predictive = { frequent_words: {}, bigrams: {}, trigrams: {} };

  async function refreshPredictive() {
    try {
      const res = await fetch(settings.baseUrl + settings.jsonPath);
      if (!res.ok) throw new Error("HTTP " + res.status);
      predictive = await res.json();
    } catch (e) {
      // silent
    }
    renderPredictions();
  }

  function currentWord() {
    const trimmed = buffer.replace(/\|/g, "").trimEnd();
    const parts = trimmed.split(/\s+/);
    if (buffer.endsWith(" ")) return "";
    return parts[parts.length - 1] || "";
  }

  function renderPredictions() {
    fetch(settings.baseUrl + "/api/hybrid_predictions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ buffer: buffer })
    })
    .then(response => response.json())
    .then(predictions => {
      predictBar.innerHTML = "";
      predictions.slice(0, 6).forEach((w, index) => {
        const chip = document.createElement("button");
        chip.className = "chip";
        chip.textContent = w;
        chip.disabled = !w;
        chip.addEventListener("click", () => {
          if (!w) return;
          
          const currentPartialWord = currentWord();
          let newBuffer = buffer;
          let context = "";
          
          if (currentPartialWord && !buffer.endsWith(" ")) {
            const beforePartial = buffer.slice(0, -currentPartialWord.length);
            newBuffer = beforePartial + w + " ";
            const words = beforePartial.replace(/\|/g, "").trim().split(/\s+/);
            context = words.filter(word => word.length > 0).join(" ");
          } else {
            if (!buffer.endsWith(" ") && buffer.length) newBuffer += " ";
            newBuffer += w + " ";
            const words = buffer.replace(/\|/g, "").trim().split(/\s+/);
            context = words.filter(word => word.length > 0).join(" ");
          }
          
          setBuffer(newBuffer);
          console.log(`DEBUG: Sending usage - context: "${context}", selected: "${w}"`);
          pingUsage(context, w);
        });
        predictBar.appendChild(chip);
      });
    })
    .catch(error => {
      console.error("Error fetching predictions:", error);
    });
  }

  async function pingUsage(ctx = "", next = "") {
    try {
      await fetch(settings.baseUrl + "/api/usage", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ buffer, context: ctx, next })
      });
    } catch {}
  }

  textBar.addEventListener("click", () => {
    const text = buffer.replace(/\|/g, "").trim();
    if (text) {
      speak(text);
      ttsUseCount++;
      console.log(`TTS use count: ${ttsUseCount} for text: "${text}"`);
      
      if (ttsUseCount >= 3) {
        console.log("3x TTS usage detected - saving text to predictive data");
        saveTextToPredictive(text);
        ttsUseCount = 0;
      }
    }
  });

  function init() {
    initTTS();
    applyTheme(settings.theme);
    currentScanSpeed = settings.scanSpeed || "medium";
    renderKeyboard();
    setBuffer("");
    refreshPredictive();
  }

  init();
})();
