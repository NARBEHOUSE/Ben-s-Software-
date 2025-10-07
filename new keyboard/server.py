import os, json, subprocess, sys
from datetime import datetime
from threading import Lock
from flask import Flask, send_from_directory, jsonify, request
import requests  # For KenLM API calls

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = BASE_DIR

# Use a separate prediction file for the web keyboard only
WEB_DATA_PATH = os.path.join(BASE_DIR, "web_keyboard_predictions.json")

# KenLM API endpoint
KENLM_API = os.environ.get("KENLM_API", "https://api.imagineville.org/word/predict")

lock = Lock()
app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="")

def load_web_data():
    """Load web keyboard specific prediction data"""
    if not os.path.exists(WEB_DATA_PATH) or os.stat(WEB_DATA_PATH).st_size == 0:
        return {"frequent_words": {}, "bigrams": {}, "trigrams": {}, "usage_tracking": {}}
    try:
        with open(WEB_DATA_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "usage_tracking" not in data:
                data["usage_tracking"] = {}
            print(f"Loaded web prediction data: {len(data.get('frequent_words', {}))} words, {len(data.get('bigrams', {}))} bigrams, {len(data.get('trigrams', {}))} trigrams")
            return data
    except Exception as e:
        print(f"Error loading web prediction data: {e}")
        return {"frequent_words": {}, "bigrams": {}, "trigrams": {}, "usage_tracking": {}}

def save_web_data(d):
    """Save web keyboard specific prediction data"""
    try:
        with open(WEB_DATA_PATH, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
        print(f"Saved web prediction data to {WEB_DATA_PATH}")
    except Exception as e:
        print(f"Error saving web prediction data: {e}")

def extract_rolling_ngrams(text):
    """Extract rolling unigrams, bigrams, and trigrams from text"""
    words = text.replace("|", "").strip().upper().split()
    timestamp = datetime.now().isoformat()
    
    ngrams = {
        "unigrams": [],
        "bigrams": [],
        "trigrams": []
    }
    
    # Extract unigrams (individual words)
    for word in words:
        ngrams["unigrams"].append(word)
    
    # Extract rolling bigrams
    for i in range(len(words) - 1):
        bigram = f"{words[i]} {words[i+1]}"
        ngrams["bigrams"].append(bigram)
    
    # Extract rolling trigrams  
    for i in range(len(words) - 2):
        trigram = f"{words[i]} {words[i+1]} {words[i+2]}"
        ngrams["trigrams"].append(trigram)
    
    print(f"DEBUG: Extracted ngrams from '{text}':")
    print(f"  Unigrams: {ngrams['unigrams']}")
    print(f"  Bigrams: {ngrams['bigrams']}")
    print(f"  Trigrams: {ngrams['trigrams']}")
    
    return ngrams, timestamp

def get_kenlm_predictions(text, num_suggestions=6):
    """Get predictions from KenLM API"""
    try:
        text = text.replace("|", "").strip()
        if not text:
            return []
        
        print(f"DEBUG: Calling KenLM API for text: '{text}'")
        
        response = requests.post(
            KENLM_API,
            json={"text": text, "num_predictions": num_suggestions},
            timeout=5
        )
        
        if response.status_code == 200:
            api_data = response.json()
            predictions = api_data.get("predictions", [])
            kenlm_predictions = [word.upper() for word in predictions[:num_suggestions]]
            print(f"DEBUG: KenLM API predictions: {kenlm_predictions}")
            return kenlm_predictions
        else:
            print(f"KenLM API error: {response.status_code}")
            return []
        
    except Exception as e:
        print(f"KenLM API failed: {e}")
        return []

def get_hybrid_predictions(buffer):
    """
    Enhanced prediction logic similar to keyboard_predictive.py:
    Web data first (with sophisticated scoring), then KenLM, then defaults
    """
    web_data = load_web_data()
    
    # Check if the text (without the "|" cursor marker) ends with a space.
    has_trailing_space = buffer.rstrip("|").endswith(" ")
    
    # Clean the input: remove the "|" marker, trim spaces, and convert to uppercase.
    cleaned = buffer.upper().replace("|", "").strip()
    words = cleaned.split() if cleaned else []
    
    print(f"DEBUG: Buffer: '{buffer}', Cleaned: '{cleaned}', Has trailing space: {has_trailing_space}")
    
    # Default words if nothing else matches
    DEFAULT_WORDS = ["YES", "NO", "HELP", "THE", "I", "YOU"]
    
    # If no words are entered, show fixed default row
    if not words:
        return DEFAULT_WORDS
    
    # Determine context and current (incomplete) word
    if has_trailing_space:
        context = cleaned
        current_word = ""
    else:
        current_word = words[-1]
        context = " ".join(words[:-1])
    
    print(f"DEBUG: Context: '{context}', Current word: '{current_word}'")
    
    # TIER 1: N-gram predictions from web data (similar to keyboard_predictive.py)
    predictions_ngram = {}
    if context and (has_trailing_space or context != current_word):
        ctx_words = context.split()
        
        # Use trigrams ONLY when at least two context words exist
        if len(ctx_words) >= 2:
            tri_ctx = " ".join(ctx_words[-2:])
            print(f"DEBUG: Checking trigrams with context: '{tri_ctx}'")
            for key, data in web_data.get("trigrams", {}).items():
                if key.startswith(tri_ctx + " "):
                    next_word = key.split()[-1]
                    if (current_word == "" or next_word.startswith(current_word)) \
                       and len(next_word) >= 2 and data.get("count", 0) >= 1:
                        # High score for trigrams
                        score = data.get("count", 1) * 1000000
                        predictions_ngram[next_word] = predictions_ngram.get(next_word, 0) + score
                        print(f"DEBUG: Found trigram match: {key} -> {next_word} (score: {score})")
        
        # Always consider bigrams for the last single word of context
        if len(ctx_words) >= 1:
            bi_ctx = ctx_words[-1]
            print(f"DEBUG: Checking bigrams with context: '{bi_ctx}'")
            for key, data in web_data.get("bigrams", {}).items():
                if key.startswith(bi_ctx + " "):
                    next_word = key.split()[-1]
                    if (current_word == "" or next_word.startswith(current_word)) \
                       and len(next_word) >= 2 and data.get("count", 0) >= 1:
                        # Medium score for bigrams
                        score = data.get("count", 1) * 500000
                        predictions_ngram[next_word] = predictions_ngram.get(next_word, 0) + score
                        print(f"DEBUG: Found bigram match: {key} -> {next_word} (score: {score})")
    
    # Trailing-space bigram fallback if no n-gram hits
    if has_trailing_space and not predictions_ngram and context:
        bi_ctx = context.split()[-1]
        print(f"DEBUG: Fallback bigram check with context: '{bi_ctx}'")
        for key, data in web_data.get("bigrams", {}).items():
            if key.startswith(bi_ctx + " "):
                next_word = key.split()[-1]
                if len(next_word) >= 2 and data.get("count", 0) >= 1:
                    score = data.get("count", 1) * 500000
                    predictions_ngram[next_word] = score
                    print(f"DEBUG: Found fallback bigram: {key} -> {next_word}")
    
    # TIER 2: Frequent word completions (only when mid-word)
    predictions_freq = {}
    if current_word:  # guard prevents dumping global words after a space
        print(f"DEBUG: Checking word completions for: '{current_word}'")
        for word, data in web_data.get("frequent_words", {}).items():
            if word.startswith(current_word) and word != current_word and len(word) >= 2:
                score = data.get("count", 1) * 100000
                predictions_freq[word] = score
                print(f"DEBUG: Found word completion: {word} (score: {score})")
    
    # TIER 3: Combine candidates (n-grams first, then freq)
    final_predictions = []
    
    if predictions_ngram:
        for w, _ in sorted(predictions_ngram.items(), key=lambda x: -x[1]):
            final_predictions.append(w)
    
    if len(final_predictions) < 6:
        for w, _ in sorted(predictions_freq.items(), key=lambda x: -x[1]):
            if w not in final_predictions:
                final_predictions.append(w)
            if len(final_predictions) >= 6:
                break
    
    print(f"DEBUG: Web predictions ({len(final_predictions)}): {final_predictions}")
    
    # TIER 4: Use KenLM API to fill remaining slots
    if len(final_predictions) < 6:
        print(f"DEBUG: Need {6 - len(final_predictions)} more predictions, calling KenLM")
        
        kenlm_text = cleaned if has_trailing_space else " ".join(context.split()) if context else ""
        if kenlm_text:
            kenlm_predictions = get_kenlm_predictions(kenlm_text, 10)
            
            for kenlm_word in kenlm_predictions:
                if len(final_predictions) >= 6:
                    break
                if kenlm_word not in final_predictions:
                    if not current_word or kenlm_word.startswith(current_word):
                        final_predictions.append(kenlm_word)
                        print(f"DEBUG: Added KenLM prediction: {kenlm_word}")
    
    # TIER 5: Pad with defaults (ordered, no duplicates)
    for w in DEFAULT_WORDS:
        if len(final_predictions) >= 6:
            break
        if w not in final_predictions:
            if not current_word or w.startswith(current_word):
                final_predictions.append(w)
    
    # Ensure exactly 6 items
    while len(final_predictions) < 6:
        final_predictions.append("")
    
    print(f"DEBUG: Final predictions: {final_predictions[:6]}")
    return final_predictions[:6]

@app.get("/")
def root():
    return send_from_directory(STATIC_DIR, "index.html")

@app.get("/api/predictive_ngrams")
def api_predictive():
    """Return web keyboard data for compatibility"""
    with lock:
        data = load_web_data()
    return jsonify(data)

@app.post("/api/hybrid_predictions")
def api_hybrid_predictions():
    """Get predictions using hybrid approach"""
    try:
        payload = request.get_json(force=True) or {}
        buffer = payload.get("buffer", "")
        
        with lock:
            predictions = get_hybrid_predictions(buffer)
        
        return jsonify(predictions)
    except Exception as e:
        print(f"Error in hybrid predictions: {e}")
        return jsonify(["YES", "NO", "HELP", "THE", "I", "YOU"]), 500

@app.post("/api/save_text")
def api_save_text():
    """Save text using rolling ngram extraction to web keyboard predictions"""
    try:
        payload = request.get_json(force=True) or {}
        text = payload.get("text", "").strip()
        
        if not text:
            return jsonify({"ok": False, "error": "No text provided"}), 400
            
        print(f"DEBUG: Saving text with rolling ngrams: '{text}'")
        
        with lock:
            data = load_web_data()
            ngrams, timestamp = extract_rolling_ngrams(text)
            
            # Update unigrams (frequent_words)
            for word in ngrams["unigrams"]:
                if word in data["frequent_words"]:
                    data["frequent_words"][word]["count"] = data["frequent_words"][word].get("count", 0) + 1
                    data["frequent_words"][word]["last_used"] = timestamp
                else:
                    data["frequent_words"][word] = {"count": 1, "last_used": timestamp}
                print(f"DEBUG: Updated unigram: {word}")
            
            # Update bigrams
            for bigram in ngrams["bigrams"]:
                if bigram in data["bigrams"]:
                    data["bigrams"][bigram]["count"] = data["bigrams"][bigram].get("count", 0) + 1
                    data["bigrams"][bigram]["last_used"] = timestamp
                else:
                    data["bigrams"][bigram] = {"count": 1, "last_used": timestamp}
                print(f"DEBUG: Updated bigram: {bigram}")
            
            # Update trigrams
            for trigram in ngrams["trigrams"]:
                if trigram in data["trigrams"]:
                    data["trigrams"][trigram]["count"] = data["trigrams"][trigram].get("count", 0) + 1
                    data["trigrams"][trigram]["last_used"] = timestamp
                else:
                    data["trigrams"][trigram] = {"count": 1, "last_used": timestamp}
                print(f"DEBUG: Updated trigram: {trigram}")
            
            save_web_data(data)
            
        return jsonify({
            "ok": True, 
            "message": f"Saved rolling ngrams from text with {len(ngrams['unigrams'])} words",
            "ngrams_saved": {
                "unigrams": len(ngrams["unigrams"]),
                "bigrams": len(ngrams["bigrams"]), 
                "trigrams": len(ngrams["trigrams"])
            }
        })
        
    except Exception as e:
        print(f"Error in save_text: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@app.post("/api/usage")
def api_usage():
    """Track usage of predictive suggestions"""
    try:
        payload = request.get_json(force=True) or {}
    except Exception:
        return jsonify({"ok": False}), 400

    buf = (payload.get("buffer") or "").replace("|", "").strip()
    context = (payload.get("context") or "").strip()
    selected_word = (payload.get("next") or "").strip()
    now = datetime.now().isoformat()

    print(f"DEBUG: Usage tracking - buffer: '{buf}', context: '{context}', selected: '{selected_word}'")

    with lock:
        data = load_web_data()
        
        # Regular usage tracking - build ngrams immediately
        if context and selected_word:
            ctx_words = context.split()
            selected_upper = selected_word.upper()
            
            # Build bigrams from the last word in context
            if len(ctx_words) >= 1:
                last_word = ctx_words[-1].upper()
                bigram_key = f"{last_word} {selected_upper}"
                
                if bigram_key not in data["bigrams"]:
                    data["bigrams"][bigram_key] = {"count": 0, "last_used": now}
                data["bigrams"][bigram_key]["count"] += 1
                data["bigrams"][bigram_key]["last_used"] = now
                print(f"DEBUG: Built bigram: '{bigram_key}' count={data['bigrams'][bigram_key]['count']}")
            
            # Build trigrams from the last two words in context
            if len(ctx_words) >= 2:
                second_last = ctx_words[-2].upper()
                last_word = ctx_words[-1].upper()
                trigram_key = f"{second_last} {last_word} {selected_upper}"
                
                if trigram_key not in data["trigrams"]:
                    data["trigrams"][trigram_key] = {"count": 0, "last_used": now}
                data["trigrams"][trigram_key]["count"] += 1
                data["trigrams"][trigram_key]["last_used"] = now
                print(f"DEBUG: Built trigram: '{trigram_key}' count={data['trigrams'][trigram_key]['count']}")

        # Track frequent words from the selected word
        if selected_word:
            word_upper = selected_word.upper()
            if word_upper not in data["frequent_words"]:
                data["frequent_words"][word_upper] = {"count": 0, "last_used": now}
            data["frequent_words"][word_upper]["count"] += 1
            data["frequent_words"][word_upper]["last_used"] = now

        save_web_data(data)

    return jsonify({"ok": True})

@app.post("/api/close_chrome")
def api_close_chrome():
    """Close Chrome browsers gracefully"""
    try:
        print("Received request to close Chrome gracefully")
        
        # Try graceful shutdown first using Windows messaging
        import ctypes
        from ctypes import wintypes
        
        user32 = ctypes.windll.user32
        
        # Find Chrome windows and send close messages
        def enum_window_callback(hwnd, lparam):
            # Get window class name
            class_name = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, class_name, 256)
            
            # Get window title
            title_length = user32.GetWindowTextLengthW(hwnd)
            if title_length > 0:
                title = ctypes.create_unicode_buffer(title_length + 1)
                user32.GetWindowTextW(hwnd, title, title_length + 1)
                
                # Be VERY specific about Chrome windows ONLY
                is_chrome_window = (
                    class_name.value == "Chrome_WidgetWin_1" and
                    (" - Google Chrome" in title.value or 
                     " - Chrome" in title.value or
                     title.value == "Google Chrome" or
                     title.value == "New Tab - Google Chrome" or
                     title.value.endswith(" - Google Chrome"))
                )
                
                if is_chrome_window:
                    print(f"Found Chrome browser window: '{title.value}' (class: {class_name.value})")
                    # Send WM_CLOSE message to close gracefully
                    user32.SendMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE = 0x0010
            
            return True
        
        # Define the callback function type
        EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        callback = EnumWindowsProc(enum_window_callback)
        
        # Enumerate all windows and close Chrome ones
        user32.EnumWindows(callback, 0)
        
        # Give Chrome time to close gracefully
        import time
        time.sleep(2)
        
        # As a fallback, only use taskkill on chrome.exe specifically
        try:
            result = subprocess.run(["taskkill", "/im", "chrome.exe"], 
                                  capture_output=True, text=True, timeout=5)
            print(f"Graceful taskkill result: {result.returncode}")
        except Exception as e:
            print(f"Graceful taskkill failed: {e}")
        
        return jsonify({"ok": True, "message": "Chrome close initiated gracefully"})
    except Exception as e:
        print(f"Error closing Chrome gracefully: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@app.post("/api/volume_control")
def api_volume_control():
    """Control system volume"""
    try:
        payload = request.get_json(force=True) or {}
        action = payload.get("action", "")  # "up" or "down"
        steps = payload.get("steps", 1)  # number of steps to change
        
        if action not in ["up", "down"]:
            return jsonify({"ok": False, "error": "Invalid action. Use 'up' or 'down'"}), 400
        
        print(f"Volume control: {action} by {steps} steps")
        
        # Use Windows volume keys
        import ctypes
        import time
        
        VK_VOLUME_UP = 0xAF
        VK_VOLUME_DOWN = 0xAE
        
        key = VK_VOLUME_UP if action == "up" else VK_VOLUME_DOWN
        
        # Send the key events for the specified number of steps
        for i in range(steps):
            ctypes.windll.user32.keybd_event(key, 0, 0, 0)  # Key down
            ctypes.windll.user32.keybd_event(key, 0, 2, 0)  # Key up
            time.sleep(0.05)  # Small delay between steps
        
        return jsonify({
            "ok": True, 
            "message": f"Volume {'increased' if action == 'up' else 'decreased'} by {steps} steps"
        })
        
    except Exception as e:
        print(f"Error controlling volume: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

if __name__ == "__main__":
    print(f"Looking for web prediction data at: {WEB_DATA_PATH}")
    print(f"KenLM API endpoint: {KENLM_API}")
    print(f"Web file exists: {os.path.exists(WEB_DATA_PATH)}")
    
    # Show web keyboard data if it exists
    if os.path.exists(WEB_DATA_PATH):
        try:
            with open(WEB_DATA_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                print(f"Loaded WEB keyboard data: {len(data.get('frequent_words', {}))} frequent words")
                print(f"Loaded WEB keyboard data: {len(data.get('bigrams', {}))} bigrams") 
                print(f"Loaded WEB keyboard data: {len(data.get('trigrams', {}))} trigrams")
                
                # Show sample data
                if data.get('frequent_words'):
                    sample_words = list(data['frequent_words'].keys())[:5]
                    print(f"Sample web words: {sample_words}")
                
                if data.get('bigrams'):
                    sample_bigrams = list(data['bigrams'].keys())[:3]
                    print(f"Sample web bigrams: {sample_bigrams}")
                    
                if data.get('trigrams'):
                    sample_trigrams = list(data['trigrams'].keys())[:3]
                    print(f"Sample web trigrams: {sample_trigrams}")
        except Exception as e:
            print(f"Error reading web data file: {e}")
    
    app.run(host="127.0.0.1", port=5000, debug=False)
