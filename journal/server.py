import os, json, subprocess
from threading import Lock
from flask import Flask, send_from_directory, jsonify, request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = BASE_DIR

# Journal entries file
ENTRIES_PATH = os.path.join(BASE_DIR, "entries.json")

# Shared keyboard predictions file (in new keyboard folder)
KEYBOARD_DIR = os.path.join(os.path.dirname(BASE_DIR), "new keyboard")
WEB_PREDICTIONS_PATH = os.path.join(KEYBOARD_DIR, "web_keyboard_predictions.json")

lock = Lock()
app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="")

def get_default_entries():
    return {"entries": []}

def get_default_predictions():
    return {"frequent_words": {}, "bigrams": {}, "trigrams": {}}

def load_entries():
    if not os.path.exists(ENTRIES_PATH) or os.stat(ENTRIES_PATH).st_size == 0:
        data = get_default_entries()
        save_entries(data)
        return data
    try:
        with open(ENTRIES_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading entries: {e}")
        data = get_default_entries()
        save_entries(data)
        return data

def save_entries(data):
    try:
        with open(ENTRIES_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving entries: {e}")

def load_keyboard_predictions():
    """Load shared keyboard predictions from new keyboard folder"""
    if not os.path.exists(WEB_PREDICTIONS_PATH) or os.stat(WEB_PREDICTIONS_PATH).st_size == 0:
        return get_default_predictions()
    try:
        with open(WEB_PREDICTIONS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading keyboard predictions: {e}")
        return get_default_predictions()

def save_keyboard_predictions(data):
    """Save to shared keyboard predictions file"""
    try:
        with open(WEB_PREDICTIONS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Saved keyboard predictions to {WEB_PREDICTIONS_PATH}")
    except Exception as e:
        print(f"Error saving keyboard predictions: {e}")

@app.route("/")
def root():
    try:
        return send_from_directory(STATIC_DIR, "index.html")
    except Exception as e:
        return f"Error serving index.html: {str(e)}", 500

@app.route("/web_keyboard_predictions.json")
def serve_predictions_file():
    """Serve the shared predictions file directly"""
    with lock:
        data = load_keyboard_predictions()
    return jsonify(data)

@app.route("/<path:filename>")
def static_files(filename):
    try:
        return send_from_directory(STATIC_DIR, filename)
    except Exception as e:
        return f"File not found: {filename}", 404

@app.get("/api/keyboard_predictions")
def api_get_keyboard_predictions():
    """Get shared keyboard predictions"""
    with lock:
        data = load_keyboard_predictions()
    return jsonify(data)

@app.post("/api/save_prediction")
def api_save_prediction():
    """Save prediction data to shared keyboard file"""
    try:
        payload = request.get_json(force=True) or {}
        word = payload.get("word", "").strip().upper()
        
        if not word:
            return jsonify({"ok": False, "error": "No word provided"}), 400
        
        with lock:
            data = load_keyboard_predictions()
            timestamp = payload.get("timestamp") or "2024-01-01T00:00:00.000Z"
            
            if word not in data["frequent_words"]:
                data["frequent_words"][word] = {"count": 0, "last_used": timestamp}
            
            data["frequent_words"][word]["count"] += 1
            data["frequent_words"][word]["last_used"] = timestamp
            
            save_keyboard_predictions(data)
        
        return jsonify({"ok": True, "message": f"Saved word: {word}"})
    except Exception as e:
        print(f"Error saving prediction: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@app.post("/api/save_ngram")
def api_save_ngram():
    """Save n-gram data to shared keyboard file"""
    try:
        payload = request.get_json(force=True) or {}
        context = payload.get("context", "").strip().upper()
        next_word = payload.get("next_word", "").strip().upper()
        
        if not context or not next_word:
            return jsonify({"ok": False, "error": "Context and next_word required"}), 400
        
        with lock:
            data = load_keyboard_predictions()
            timestamp = payload.get("timestamp") or "2024-01-01T00:00:00.000Z"
            
            ctx_words = context.split()
            
            # Save bigram
            if len(ctx_words) >= 1:
                bigram_key = f"{ctx_words[-1]} {next_word}"
                if bigram_key not in data["bigrams"]:
                    data["bigrams"][bigram_key] = {"count": 0, "last_used": timestamp}
                data["bigrams"][bigram_key]["count"] += 1
                data["bigrams"][bigram_key]["last_used"] = timestamp
            
            # Save trigram
            if len(ctx_words) >= 2:
                trigram_key = f"{ctx_words[-2]} {ctx_words[-1]} {next_word}"
                if trigram_key not in data["trigrams"]:
                    data["trigrams"][trigram_key] = {"count": 0, "last_used": timestamp}
                data["trigrams"][trigram_key]["count"] += 1
                data["trigrams"][trigram_key]["last_used"] = timestamp
            
            save_keyboard_predictions(data)
        
        return jsonify({"ok": True, "message": f"Saved n-gram for: {next_word}"})
    except Exception as e:
        print(f"Error saving n-gram: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@app.get("/api/entries")
def api_get_entries():
    with lock:
        data = load_entries()
    return jsonify(data)

@app.post("/api/save_entries")
def api_save_entries():
    try:
        payload = request.get_json(force=True) or {}
        entries = payload.get("entries", [])
        with lock:
            save_entries({"entries": entries})
        return jsonify({"ok": True, "message": "Entries saved"})
    except Exception as e:
        print(f"Error saving entries: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@app.post("/api/close_chrome")
def api_close_chrome():
    """Close Chrome browsers gracefully"""
    try:
        print("Received request to close app")
        
        import ctypes
        from ctypes import wintypes
        
        user32 = ctypes.windll.user32
        
        def enum_window_callback(hwnd, lparam):
            class_name = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, class_name, 256)
            
            title_length = user32.GetWindowTextLengthW(hwnd)
            if title_length > 0:
                title = ctypes.create_unicode_buffer(title_length + 1)
                user32.GetWindowTextW(hwnd, title, title_length + 1)
                
                is_chrome_window = (
                    class_name.value == "Chrome_WidgetWin_1" and
                    (" - Google Chrome" in title.value or 
                     " - Chrome" in title.value or
                     title.value == "Google Chrome" or
                     title.value.endswith(" - Google Chrome"))
                )
                
                if is_chrome_window:
                    print(f"Found Chrome window: '{title.value}'")
                    user32.SendMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE
            
            return True
        
        EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        callback = EnumWindowsProc(enum_window_callback)
        user32.EnumWindows(callback, 0)
        
        import time
        time.sleep(1)
        
        try:
            subprocess.run(["taskkill", "/im", "chrome.exe"], 
                          capture_output=True, text=True, timeout=5)
        except Exception as e:
            print(f"Taskkill failed: {e}")
        
        return jsonify({"ok": True, "message": "App closing"})
    except Exception as e:
        print(f"Error closing app: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

if __name__ == "__main__":
    print(f"Starting Ben's Journal Server...")
    print(f"Base directory: {BASE_DIR}")
    print(f"Keyboard predictions path: {WEB_PREDICTIONS_PATH}")
    
    if os.path.exists(STATIC_DIR):
        files = os.listdir(STATIC_DIR)
        print(f"Files in directory: {files}")
    
    print(f"Entries will be stored at: {ENTRIES_PATH}")
    
    # Initialize entries file if needed
    with lock:
        load_entries()
    
    print("Server starting on http://127.0.0.1:5001")
    app.run(host="127.0.0.1", port=5001, debug=True)
