# narbe_scan_fullscreen.py
# Fullscreen NARBE Scan Keyboard (PySide6)
# - Keyboard scanning (space/enter + long-hold) like your HTML
# - KenLM predictions with local n-gram fallback
# - Results view: loads real YouTube/Google Images in a WebEngineView
#   and injects a small "narbeApi" to list/focus/click items
# - Robust: waits/polls for SPA content, auto-accepts common consent modals,
#   and keeps the bottom control bar the only interactive surface.

import os, sys, time, json, math, importlib, ctypes, tempfile, shutil, re, requests, html
from html import unescape as _unescape
import urllib.parse as up
import json as _json
import subprocess  # added
try:
    import pyttsx3
except Exception:
    pyttsx3 = None
try:
    import pythoncom
except Exception:
    pythoncom = None
# Add high-DPI env before PySide6 imports
os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
os.environ.setdefault("QT_SCALE_FACTOR_ROUNDING_POLICY", "PassThrough")
from dataclasses import dataclass
from typing import List, Optional

# HiDPI sane defaults before Qt loads
os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
os.environ.setdefault("QT_SCALE_FACTOR_ROUNDING_POLICY", "PassThrough")

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings, QWebEngineProfile
from PySide6.QtNetwork import QNetworkCookie

# ---------------- Async TTS (queue + worker thread) ----------------
try:
    import pyttsx3
    import threading, queue
    _tts_queue = queue.Queue(maxsize=8)
    _tts_ready = False
    _tts_thread = None

    def _tts_worker():
        global _tts_ready
        try:
            engine = pyttsx3.init()
            _tts_ready = True
            while True:
                txt = _tts_queue.get()
                if txt is None:
                    break
                # coalesce to the latest text to avoid backlogged chatter
                try:
                    while True:
                        nxt = _tts_queue.get_nowait()
                        if nxt is None:
                            txt = None
                            break
                        txt = nxt
                except queue.Empty:
                    pass
                if txt is None:
                    break
                try:
                    engine.stop()
                except Exception:
                    pass
                try:
                    engine.say(str(txt))
                    engine.runAndWait()
                except Exception:
                    pass
        except Exception:
            pass
        finally:
            _tts_ready = False

    _tts_thread = threading.Thread(target=_tts_worker, daemon=True)
    _tts_thread.start()
except Exception:
    _tts_queue = None
    _tts_thread = None
    _tts_ready = False

def speak(text: str):
    if not text or _tts_queue is None:
        return
    try:
        # keep the queue lean: drop older items if any
        while _tts_queue.qsize() > 1:
            try:
                _tts_queue.get_nowait()
            except Exception:
                break
        _tts_queue.put_nowait(str(text))
    except Exception:
        pass

def _stop_tts():
    try:
        if _tts_queue:
            _tts_queue.put(None)
        if _tts_thread and _tts_thread.is_alive():
            _tts_thread.join(timeout=1.2)
    except Exception:
        pass

# ---------------- KenLM + local n-gram fallback ----------------
KENLM_API = os.environ.get("KENLM_API", "https://api.imagineville.org/word/predict")
KENLM_TIMEOUT = 3  # seconds

DEFAULT_WORDS = ["yes", "no", "help", "the", "you", "to"]

def _parse_kenlm(data):
    if isinstance(data, list):
        return [str(x) for x in data]
    if isinstance(data, dict):
        for k in ("suggestions", "result", "results", "candidates"):
            if k in data and isinstance(data[k], list):
                out = []
                for item in data[k]:
                    if isinstance(item, str):
                        out.append(item)
                    elif isinstance(item, dict):
                        tok = item.get("text") or item.get("token") or item.get("word")
                        if tok: out.append(str(tok))
                return out
    return []

def fetch_kenlm(context_words, prefix, limit=6):
    # POST first
    try:
        r = requests.post(
            KENLM_API,
            json={"context": context_words or [], "prefix": prefix or "", "limit": limit},
            timeout=KENLM_TIMEOUT
        )
        if r.ok:
            out = _parse_kenlm(r.json())
            if out:
                return out[:limit]
    except Exception:
        pass
    # GET fallback
    try:
        params = {"num": str(limit), "sort": "logprob", "safe": "true", "lang": "en"}
        if prefix:
            params["prefix"] = prefix.lower()
        if context_words:
            params["left"] = " ".join(context_words).lower()
        r = requests.get(KENLM_API, params=params, timeout=KENLM_TIMEOUT)
        if r.ok:
            out = _parse_kenlm(r.json())
            if out:
                return out[:limit]
    except Exception:
        pass
    return []

def _load_local_ngrams():
    try:
        here = os.path.dirname(__file__)
        path = os.path.join(here, "predictive_ngrams.json")
        if not os.path.exists(path):
            return {}, {}, {}
        data = json.load(open(path, "r", encoding="utf-8"))
        fw  = {k.upper():v for k,v in (data.get("frequent_words") or {}).items()}
        bi  = {k.upper():v for k,v in (data.get("bigrams") or {}).items()}
        tri = {k.upper():v for k,v in (data.get("trigrams") or {}).items()}
        return fw, bi, tri
    except Exception:
        return {}, {}, {}

_FREQ, _BI, _TRI = _load_local_ngrams()

def _fallback_ngram(raw_text: str, limit=6):
    txt = (raw_text or "")
    up_txt = txt.upper().strip()
    if not up_txt:
        return DEFAULT_WORDS[:limit]
    trailing = txt.endswith(" ")
    parts = up_txt.split()
    cur = "" if trailing else (parts[-1] if parts else "")
    left = " ".join(parts[:-1]) if (not trailing and len(parts) > 1) else (" ".join(parts) if trailing else "")
    scores = {}
    if left:
        ctx = left.split()
        if len(ctx) >= 2:
            key = " ".join(ctx[-2:]) + " "
            for k, d in _TRI.items():
                if k.startswith(key):
                    nxt = k.split()[-1]
                    if (not cur) or nxt.startswith(cur):
                        scores[nxt] = scores.get(nxt, 0) + 10 * float(d.get("count", 0))
        if len(ctx) >= 1:
            key = ctx[-1] + " "
            for k, d in _BI.items():
                if k.startswith(key):
                    nxt = k.split()[-1]
                    if (not cur) or nxt.startswith(cur):
                        scores[nxt] = scores.get(nxt, 0) + 5 * float(d.get("count", 0))
    if not scores and cur:
        for w, d in _Freq.items() if False else _FREQ.items():
            if w.startswith(cur):
                scores[w] = scores.get(w, 0) + float(d.get("count", 0))
    out = [w.lower() for w,_ in sorted(scores.items(), key=lambda kv: -kv[1])]
    for w in DEFAULT_WORDS:
        if len(out) >= limit: break
        if w not in out: out.append(w)
    return out[:limit]

# ---------------- Legacy local simple suggest (used nowhere directly; kept as extra fallback) ----------------
def local_suggest(raw_text: str, limit=6):
    raw = raw_text or ""
    trailing = raw.endswith(" ")
    parts = raw.strip().split()
    if not parts:
        return DEFAULT_WORDS[:limit]
    if trailing:
        seeds = ["is","are","can","will","how","what","where","when","why","because","and","or"]
        return (seeds + DEFAULT_WORDS)[:limit]
    cur = parts[-1].lower()
    vocab = ["and","are","can","cat","cats","dog","dogs","how","what","where","when","why",
             "music","video","image","photo","photos","pictures","learn","game","funny",
             "cute","best","top","new","news","guide","tutorial","house","narbe"]
    out = [w for w in vocab if w.startswith(cur) and w != cur]
    out += [w for w in DEFAULT_WORDS if w not in out]
    return out[:limit]

# ---------------- Robust JS collectors (hidden) ----------------
CONSENT_JS = r"""(function(){
  try {
    var labels = ['Agree','I agree','Accept all','Accept','Got it','OK'];
    var btns = Array.from(document.querySelectorAll('button, input[type=button], input[type=submit]'));
    for (var i=0;i<btns.length;i++){
      var t = (btns[i].innerText || btns[i].value || '').trim().toLowerCase();
      for (var j=0;j<labels.length;j++){
        if (t === labels[j].toLowerCase()) { btns[i].click(); return true; }
      }
    }
  } catch(e) {}
  return false;
})();"""

# Images: Google(/imgres?imgurl=...), DDG (/iu/?u=...), Bing (iusc[m] JSON), plus generic fallbacks
INJECT_IMAGES = r"""
(function(){
  function isBad(u){
    try{
      var url = new URL(u, location.href);
      var h = (url.hostname||'').toLowerCase();
      var p = (url.pathname||'').toLowerCase();
      if (/encrypted\-tbn/i.test(h)) return true;
      if (/branding|logo/.test(p)) return true;
    }catch(e){}
    return /^data:/i.test(String(u||""));
  }
  function decodeDDG(u){
    try{
      var x = new URL(u, location.href);
      if ((x.hostname||'').toLowerCase().indexOf('duckduckgo.com') !== -1 && /\/iu\/?/.test(x.pathname)){
        var orig = x.searchParams.get('u') || '';
        if (orig) return decodeURIComponent(orig);
      }
    }catch(e){}
    return u;
  }
  function getOrigFromHref(href){
    try{
      var u = new URL(href, location.href);
      var cand = u.searchParams.get('imgurl') || u.searchParams.get('imgrefurl') ||
                 u.searchParams.get('mediaurl') || u.searchParams.get('murl') ||
                 u.searchParams.get('imgsrc') || u.searchParams.get('u') || '';
      if (cand) return decodeDDG(cand);
      return href;
    }catch(e){}
    return href;
  }

  var out = [], seen = {};
  // Google classic anchors
  try{
    var ga = Array.from(document.querySelectorAll('a[href^="/imgres?"]'));
    for (var i=0;i<ga.length && out.length<80;i++){
      var href = ga[i].getAttribute('href') || ga[i].href || '';
      if (!href) continue;
      try{
        var u = new URL(href, location.href);
        var img = u.searchParams.get('imgurl') || '';
        if (!img || isBad(img) || seen[img]) continue;
        seen[img]=1;
        var t = '';
        try { var im = ga[i].querySelector('img'); t = (im && im.getAttribute('alt')) || ga[i].getAttribute('title') || 'image'; } catch(e){}
        out.push({img: img, title: t || 'image', ref: location.href});
      }catch(e){}
    }
  }catch(e){}

  // DDG/Bing anchor param decodes
  try{
    var anchors = Array.from(document.querySelectorAll('a[href*="/iu/"], a[href*="imgurl="], a[href*="mediaurl="], a[href*="murl="]'));
    for (var i=0;i<anchors.length && out.length<80;i++){
      var href = anchors[i].href || anchors[i].getAttribute('href') || '';
      if (!href) continue;
      var img = getOrigFromHref(href);
      img = decodeDDG(img);
      if (!img || isBad(img) || seen[img]) continue;
      seen[img]=1;
      var t = '';
      try { var im = anchors[i].querySelector('img'); t = (im && im.getAttribute('alt')) || anchors[i].getAttribute('title') || 'image'; } catch(e){}
      out.push({img: img, title: (t||'image'), ref: location.href});
    }
  }catch(e){}

  // Bing tiles with JSON metadata
  try{
    var tiles = Array.from(document.querySelectorAll('.iusc,[m]'));
    for (var i=0;i<tiles.length && out.length<80;i++){
      var m = tiles[i].getAttribute('m') || '';
      if (!m) continue;
      try{
        var o = JSON.parse(m);
        var img = o.murl || o.purl || '';
        if (!img || isBad(img) || seen[img]) continue;
        seen[img]=1;
        out.push({img: img, title: (o.t || o.tt || 'image'), ref: (o.purl || location.href)});
      }catch(e){}
    }
  }catch(e){}

  // Fallback: any large-ish <img>
  if (!out.length){
    var imgs = Array.from(document.querySelectorAll('img[data-iurl], img[data-src], img[src^="http"], img'));
    for (var i=0;i<imgs.length && out.length<80;i++){
      var el = imgs[i]; var big = el.getAttribute('data-iurl') || el.getAttribute('data-src') || el.currentSrc || el.src || '';
      big = decodeDDG(big);
      if (!big || isBad(big) || seen[big]) continue;
      try { var w = el.naturalWidth||0, h=el.naturalHeight||0; if (w && h && (w<300 || h<200)) continue; }catch(e){}
      seen[big]=1;
      var t = el.getAttribute('alt') || 'image';
      out.push({img: big, title: t, ref: location.href});
    }
  }

  return JSON.stringify(out.slice(0, 80));
})();"""

# Videos: YouTube (watch?v=...) + ytInitialData traversal + shorts fallback
INJECT_VIDEOS = r"""
(function(){
  var out = [], seen = {};
  function push(id,title){ if (!id || seen[id]) return; seen[id]=1; out.push({videoId:id, title:(title||'video')}); }

  // Shorts
  try{
    var sh = Array.from(document.querySelectorAll('a[href^="/shorts/"]'));
    for (var i=0;i<sh.length;i++){
      var a = sh[i]; var m = (a.pathname||'').match(/\/shorts\/([^\/\?\&]+)/); var id = m && m[1] || '';
      if (!id) continue;
      var t = (a.getAttribute('title') || a.textContent || 'short').trim().replace(/\s+/g,' ');
      push(id, t);
    }
  }catch(e){}

  // ytInitialData deep walk
  if (!out.length){
    try{
      (function walk(o){
        if (!o) return;
        if (Array.isArray(o)){ for (var i=0;i<o.length;i++) walk(o[i]); return; }
        if (typeof o === 'object'){
          if (o.videoId && !o.playlistId){
            var t='';
            try {
              if (o.title && Array.isArray(o.title.runs)) t = o.title.runs.map(function(r){return r.text||'';}).join('');
              if (!t && o.title && o.title.simpleText) t = o.title.simpleText;
            }catch(e){}
            push(o.videoId, t||'video');
          }
          for (var k in o){ if (Object.prototype.hasOwnProperty.call(o,k)) walk(o[k]); }
        }
      })(window.ytInitialData);
    }catch(e){}
  }

  // DOM fallback
  if (!out.length){
    var sels = [
      'a#thumbnail[href*="/watch"]','a#video-title[href*="/watch"]','a.yt-simple-endpoint[href*="/watch"]',
      'ytd-video-renderer a[href*="/watch"]','ytd-rich-grid-media a[href*="/watch"]',
      'ytd-compact-video-renderer a[href*="/watch"]','ytd-rich-item-renderer a[href*="/watch"]','a[href^="/watch?"]'
    ];
    var anchors = [];
    for (var s=0;s<sels.length;s++){ anchors.push.apply(anchors, Array.from(document.querySelectorAll(sels[s]))); }
    for (var i=0;i<anchors.length;i++){
      var a = anchors[i]; var href = a.href || a.getAttribute('href') || '';
      if (!href) continue;
      try{
        var u = new URL(href, location.href); var id = u.searchParams.get('v') || '';
        if (!id) continue;
        var t = (a.getAttribute('title')) || (a.querySelector('#video-title') && a.querySelector('#video-title').textContent) || (a.textContent||'video');
        t = (t||'video').trim().replace(/\s+/g,' ');
        push(id, t);
      }catch(e){}
    }
  }
  return JSON.stringify(out.slice(0,30));
})();"""

# ---------------- UI scaffolding ----------------
# Replace background-color with background so it overrides gradients
FOCUS_STYLE = "border: 3px solid #FFD64D; background: rgba(255,214,77,0.10);"

@dataclass
class RowDef:
    wrap: QtWidgets.QFrame
    widgets: list
    id: str
    label: str

class Narbe(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("NARBE Img+Vid Search")
        self.setStyleSheet("background:#0b0f14; color:#e9eef5;")
        self.setFocusPolicy(Qt.StrongFocus)

        # Fullscreen now, and keep it
        self.showFullScreen()

        # Scan state
        self.mode = "ROWS"      # ROWS | KEYS
        self.row_idx = 0
        self.key_idx = 0

        # Search history functionality
        self.search_history_mode = False  # Toggle between keyboard and history
        self.search_history = []  # List of search terms
        self.frequent_searches = {}  # Dict to track search frequency
        self._load_search_history()

        # Overlay state (slideshows)
        self.overlay_open = False
        self._overlay_idx = 0
        self.image_show = None
        self.video_show = None

        # ADD: one-shot suppression for row label TTS (used when jumping to predictive row)
        self._suppress_row_label_once = False

        # Loading overlay
        self._loading_overlay = None
        self._loading_timer = None
        self._loading_base = "Loading"
        self._loading_dots = 0

        # Timers for scanning
        self.SHORT_MIN = 250
        self.SHORT_MAX = 3000
        self.SCAN_BACK_MS = 2500  # was 1500; scan backwards every 2s while holding space
        self.space_down = False
        self.space_at = 0.0
        self.space_scanned = False
        self.space_timer = QTimer(self); self.space_timer.setInterval(self.SCAN_BACK_MS)
        self.space_timer.timeout.connect(self._space_prev)
        self.enter_down = False
        self.enter_at = 0.0
        # ADD: Enter long-hold (3s) handling
        self.ENTER_HOLD_MS = 3000
        self.enter_long_fired = False
        self.enter_timer = QTimer(self)
        self.enter_timer.setSingleShot(True)
        self.enter_timer.setInterval(self.ENTER_HOLD_MS)
        self.enter_timer.timeout.connect(self._on_enter_hold)
        # ADD: 0.5s cooldown between actionable releases
        self.INPUT_COOLDOWN_MS = 500
        self._cooldown_until_ms = 0

        # Predictions
        self._pred_current = [""]*6

        # Hidden browser (results loader)
        self._init_bg_browser()
        self.bg_task = None           # "images" | "videos" | None
        self.bg_query = ""
        self.bg_provider = "google"   # images: google -> ddg -> bing -> brave
        self.bg_deadline_ms = 0
        self.bg_timer = QTimer(self); self.bg_timer.setInterval(550)
        self.bg_timer.timeout.connect(self._bg_tick)

        # Image crawl state
        self.IMG_MAX = 50
        self._img_queue = []      # list[str] of URLs to visit
        self._img_accum = []      # list[dict] accumulating {img,title,ref}
        self._img_seen = set()    # de-dupe by final image URL

        # Build UI and focus/highlight
        self._make_ui()
        self._highlight_rows()

        # --- prediction thread + debounce ---
        self.pred_req_id = 0
        self.pred_timer = QTimer(self); self.pred_timer.setSingleShot(True); self.pred_timer.setInterval(120)
        self.pred_timer.timeout.connect(self._refresh_predictions_async)
        self.pred_thread = QtCore.QThread(self)
        self.pred_worker = PredictWorker()
        self.pred_worker.moveToThread(self.pred_thread)
        self.pred_worker.request.connect(self.pred_worker._on_request)
        self.pred_worker.ready.connect(self._on_predictions_ready)
        self.pred_thread.start()

        # Keep focus & dismiss Start/Widgets on Windows
        if sys.platform.startswith("win"):
            self._install_force_focus()

        # Event filter to catch space/enter globally
        app = QtWidgets.QApplication.instance()
        if app:
            app.installEventFilter(self)

    # ---------- Search History Management ----------
    def _get_history_file(self):
        """Get the path to the search history file"""
        try:
            here = os.path.dirname(__file__)
            return os.path.join(here, "search_history.json")
        except Exception:
            return "search_history.json"

    def _load_search_history(self):
        """Load search history from file"""
        try:
            history_file = self._get_history_file()
            if os.path.exists(history_file):
                with open(history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.search_history = data.get('history', [])
                    self.frequent_searches = data.get('frequency', {})
        except Exception:
            self.search_history = []
            self.frequent_searches = {}

    def _save_search_history(self):
        """Save search history to file"""
        try:
            history_file = self._get_history_file()
            data = {
                'history': self.search_history[-50:],  # Keep last 50 searches
                'frequency': self.frequent_searches
            }
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def _add_to_history(self, query: str):
        """Add a search query to history"""
        query = query.strip()
        if not query:
            return
        
        # Remove if already exists to move to front
        if query in self.search_history:
            self.search_history.remove(query)
        
        # Add to front of history
        self.search_history.insert(0, query)
        
        # Update frequency
        self.frequent_searches[query] = self.frequent_searches.get(query, 0) + 1
        
        # Keep only last 50 unique searches
        self.search_history = self.search_history[:50]
        
        # Save to file
        self._save_search_history()

    def _get_frequent_searches(self):
        """Get most frequent searches for top row"""
        # Sort by frequency, then by recency
        frequent = sorted(self.frequent_searches.items(), 
                         key=lambda x: (x[1], -self.search_history.index(x[0]) if x[0] in self.search_history else -999), 
                         reverse=True)
        return [item[0] for item in frequent[:6]]  # Top 6 for first row

    def _toggle_search_history_mode(self):
        """Toggle between keyboard and search history mode"""
        self.search_history_mode = not self.search_history_mode
        self._update_rows_for_history_mode()
        self._highlight_rows()
        
        if self.search_history_mode:
            speak("search history mode")
        else:
            speak("keyboard mode")

    def _update_rows_for_history_mode(self):
        """Update the button text and row content based on history mode"""
        # Update the toggle button text
        if self.search_history_mode:
            self.btn_history.setText("KEYBOARD")
        else:
            self.btn_history.setText("SEARCH HISTORY")
        
        if self.search_history_mode:
            # Populate rows with search history
            frequent = self._get_frequent_searches()
            remaining_history = [h for h in self.search_history if h not in frequent]
            
            # First row: frequent searches (up to 6)
            for i, btn in enumerate(self.row_buttons[0]):
                if i < len(frequent):
                    btn.setText(frequent[i][:18].upper())  # Increased from 12 to 18 characters
                    btn.setProperty("history_term", frequent[i])
                    # Apply smaller text styling immediately
                    btn.style().unpolish(btn); btn.style().polish(btn); btn.update()
                else:
                    btn.setText("")
                    btn.setProperty("history_term", "")
                    btn.style().unpolish(btn); btn.style().polish(btn); btn.update()
            
            # Remaining rows: other history items
            remaining_idx = 0
            for row_idx in range(1, len(self.row_buttons)):
                for btn_idx, btn in enumerate(self.row_buttons[row_idx]):
                    if remaining_idx < len(remaining_history):
                        term = remaining_history[remaining_idx]
                        btn.setText(term[:18].upper())  # Increased from 12 to 18 characters
                        btn.setProperty("history_term", term)
                        # Apply smaller text styling immediately
                        btn.style().unpolish(btn); btn.style().polish(btn); btn.update()
                        remaining_idx += 1
                    else:
                        btn.setText("")
                        btn.setProperty("history_term", "")
                        btn.style().unpolish(btn); btn.style().polish(btn); btn.update()
        else:
            # Restore original keyboard layout
            original_chars = [
                "ABCDEF", "GHIJKL", "MNOPQR", 
                "STUVWX", "YZ0123", "456789"
            ]
            for row_idx, chars in enumerate(original_chars):
                for btn_idx, char in enumerate(chars):
                    if btn_idx < len(self.row_buttons[row_idx]):
                        self.row_buttons[row_idx][btn_idx].setText(char)
                        self.row_buttons[row_idx][btn_idx].setProperty("history_term", "")
                        # Remove history styling
                        btn = self.row_buttons[row_idx][btn_idx]
                        btn.style().unpolish(btn); btn.style().polish(btn); btn.update()

    # ---------- Hidden QWebEngineView
    def _init_bg_browser(self):
        class _QuietPage(QWebEnginePage):
            def javaScriptConsoleMessage(self, level, message, line_number, source_id):
                # Silence noisy console messages
                return
        self.bg = QWebEngineView()
        self.bg.setVisible(False)
        self.bg.setPage(_QuietPage(self.bg))
        # Friendly UA to avoid hard consent walls
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
        self.bg.page().profile().setHttpUserAgent(ua)
        try:
            QWebEngineProfile.defaultProfile().setHttpUserAgent(ua)
            QWebEngineProfile.defaultProfile().setPersistentCookiesPolicy(QWebEngineProfile.ForcePersistentCookies)
        except Exception:
            pass
        try:
            self.bg.settings().setAttribute(QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture, False)
            self.bg.settings().setAutoplayPolicy(QWebEngineSettings.AutoplayPolicy.NoUserGestureRequired)
        except Exception:
            pass
        self.bg.page().loadFinished.connect(self._on_bg_loaded)
        # Ensure SafeSearch is off via cookies where engines support it
        self._install_search_cookies()

    def _set_cookie(self, domain: str, name: str, value: str, path: str = "/", secure: bool = False):
        try:
            c = QNetworkCookie(name.encode("utf-8"), value.encode("utf-8"))
            c.setDomain(domain)
            c.setPath(path)
            c.setSecure(secure)
            # persist for years so it sticks across sessions
            exp = QtCore.QDateTime.currentDateTimeUtc().addYears(5)
            try: c.setExpirationDate(exp)
            except Exception: pass
            origin = QUrl(f"https://{domain.lstrip('.')}")
            store = QWebEngineProfile.defaultProfile().cookieStore()
            store.setCookie(c, origin)
        except Exception:
            pass

    def _install_search_cookies(self):
        try:
            # Google search/images
            self._set_cookie(".google.com", "PREF", "f2=8000000&hl=en&gl=US")
            # Help avoid consent interstitials blocking results
            self._set_cookie(".google.com", "CONSENT", "YES+cb.2024")
            # YouTube restricted-mode off (for video results pages if needed)
            self._set_cookie(".youtube.com", "PREF", "f2=8000000")
            # Bing strict off
            self._set_cookie(".bing.com", "SRCHHPGUSR", "ADLT=OFF")
            self._set_cookie(".bing.com", "SRCHUSR", "ADLT=OFF")
            self._set_cookie(".bing.com", "ADLT", "OFF")
            # DuckDuckGo: SafeSearch off
            self._set_cookie(".duckduckgo.com", "kp", "-2")
            # Brave images: SafeSearch off
            self._set_cookie(".search.brave.com", "safesearch", "off")
        except Exception:
            pass

    # ---------- UI
    def _make_ui(self):
        kb = QtWidgets.QWidget(); self.kb = kb
        v = QtWidgets.QVBoxLayout(kb); v.setContentsMargins(16,16,16,16); v.setSpacing(12)

        top = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("<b>NARBE</b> Img+Vid Search"); title.setStyleSheet("font-size:20px;")
        self.status = QtWidgets.QLabel("Mode: Rows • Space=next • Enter=select"); self.status.setStyleSheet("color:#9fb6c9; font-size:12px;")
        top.addWidget(title); top.addStretch(1); top.addWidget(self.status)
        v.addLayout(top)

        # Scope style to only this frame so children can highlight
        pill = QtWidgets.QFrame()
        pill.setObjectName("pill")
        pill.setStyleSheet("#pill{background:#0f1521; border:1px solid rgba(255,255,255,0.10); border-radius:12px;}")
        pill.setAttribute(Qt.WA_StyledBackground, True)
        pv = QtWidgets.QVBoxLayout(pill); pv.setContentsMargins(8,8,8,8); pv.setSpacing(8)
        v.addWidget(pill)

        # Text row
        text_wrap = QtWidgets.QFrame(); text_wrap.setStyleSheet("QFrame{border-radius:12px;}"); text_wrap.setAttribute(Qt.WA_StyledBackground, True)
        twv = QtWidgets.QVBoxLayout(text_wrap); twv.setContentsMargins(6,6,6,6)
        self.text = QtWidgets.QLineEdit(); self.text.setPlaceholderText("Type…")
        self.text.setFocusPolicy(Qt.NoFocus)           # already there
        self.text.setAttribute(Qt.WA_InputMethodEnabled, False)  # extra safeguard
        self.text.setAlignment(Qt.AlignCenter)
        self.text.setStyleSheet("""
QLineEdit{
  background-color:#ADD8E6;
  border:2px solid #000;
  border-radius:12px;
  padding:24px;
  font-size:60px;
  font-weight:800;
  color:#000;
  text-transform: uppercase;   /* FORCE UPPERCASE */
}""")

        self.text.setMinimumHeight(100)
        self.text.setReadOnly(True)                 # scan-only input
        self.text.setFocusPolicy(Qt.NoFocus)
        self.text.setContextMenuPolicy(Qt.NoContextMenu)
        # swapped to new debounced predictions
        self.text.textChanged.connect(self._schedule_predictions)
        twv.addWidget(self.text)
        pv.addWidget(text_wrap)

        # Modes row (now with 4 buttons including history controls)
        modes_wrap = QtWidgets.QFrame()
        # ADD: ensure background/border from stylesheet are painted so highlight is visible
        modes_wrap.setAttribute(Qt.WA_StyledBackground, True)
        modes_wrap.setStyleSheet("QFrame{border-radius:12px;}")
        mv = QtWidgets.QGridLayout(modes_wrap); mv.setContentsMargins(6,6,6,6); mv.setHorizontalSpacing(8); mv.setVerticalSpacing(8)
        self.btn_vid = self._btn("VIDEO SEARCH", action="search_video", primary=True)
        self.btn_img = self._btn("IMAGE SEARCH", action="search_images", primary=True)
        self.btn_history = self._btn("SEARCH HISTORY", action="toggle_history")
        self.btn_clear_history = self._btn("CLEAR HISTORY", action="clear_history", warn=True)
        # Arrange in 2x2 grid
        mv.addWidget(self.btn_vid, 0, 0); mv.addWidget(self.btn_img, 0, 1)
        mv.addWidget(self.btn_history, 1, 0); mv.addWidget(self.btn_clear_history, 1, 1)
        pv.addWidget(modes_wrap)

        # Controls
        controls_wrap = QtWidgets.QFrame()
        controls_wrap.setStyleSheet("QFrame{border-radius:12px;}")
        controls_wrap.setAttribute(Qt.WA_StyledBackground, True)
        cw = QtWidgets.QHBoxLayout(controls_wrap); cw.setContentsMargins(6,6,6,6); cw.setSpacing(8)
        self.btn_space = self._btn("SPACE", action="space_char")
        self.btn_dl = self._btn("DEL LETTER", action="del_letter")
        self.btn_dw = self._btn("DEL WORD", action="del_word")
        self.btn_cl = self._btn("CLEAR", action="clear")
        self.btn_ex = self._btn("EXIT", action="exit", warn=True)
        for b in (self.btn_space,self.btn_dl,self.btn_dw,self.btn_cl,self.btn_ex): cw.addWidget(b)
        v.addWidget(controls_wrap)

        # Alpha rows
        self.row_frames = []; self.row_buttons = []
        def add_alpha(chars, label):
            fr = QtWidgets.QFrame()
            fr.setStyleSheet("QFrame{border-radius:12px;}")
            fr.setAttribute(Qt.WA_StyledBackground, True)
            lay = QtWidgets.QHBoxLayout(fr); lay.setContentsMargins(6,6,6,6); lay.setSpacing(8)
            btns=[]
            for ch in chars:
                b = self._btn(ch, char=ch); lay.addWidget(b); btns.append(b)
            v.addWidget(fr)
            self.row_frames.append((fr,label))
            self.row_buttons.append(btns)
        add_alpha("ABCDEF","a to f")
        add_alpha("GHIJKL","g to l")
        add_alpha("MNOPQR","m to r")
        add_alpha("STUVWX","s to x")
        add_alpha("YZ0123","y to 3")
        add_alpha("456789","4 to 9")

        # Predictions
        pred_wrap = QtWidgets.QFrame()
        pred_wrap.setStyleSheet("QFrame{border-radius:12px;}")
        pred_wrap.setAttribute(Qt.WA_StyledBackground, True)
        pl = QtWidgets.QHBoxLayout(pred_wrap); pl.setContentsMargins(6,6,6,6); pl.setSpacing(8)
        self.pred_btns = [self._btn("", pred=True) for _ in range(6)]
        for b in self.pred_btns: pl.addWidget(b)
        v.addWidget(pred_wrap)

        # Register scan rows (updated for new modes row layout)
        self.rows: List[RowDef] = []
        self.rows.append(RowDef(text_wrap, [self.text], "row_text", "text"))
        self.rows.append(RowDef(modes_wrap, [self.btn_vid,self.btn_img,self.btn_history,self.btn_clear_history], "row_modes", "search"))
        self.rows.append(RowDef(controls_wrap, [self.btn_space,self.btn_dl,self.btn_dw,self.btn_cl,self.btn_ex], "row_controls", "controls"))
        ids = ["row1","row2","row3","row4","row5","row6"]
        for idx,(fr,label) in enumerate(self.row_frames):
            self.rows.append(RowDef(fr, self.row_buttons[idx], ids[idx], label))
        self.rows.append(RowDef(pred_wrap, self.pred_btns, "predRow", "predictive text"))
        for rd in self.rows:
            rd.wrap.setObjectName(rd.id)
        # ADD: mark all row frames for property-based styling
        for rd in self.rows:
            try:
                rd.wrap.setProperty("scanRow", True)
                rd.wrap.style().unpolish(rd.wrap); rd.wrap.style().polish(rd.wrap); rd.wrap.update()
            except Exception:
                pass

        # Loading overlay (center card)
        self._loading_overlay = QtWidgets.QFrame(self)
        self._loading_overlay.setAttribute(Qt.WA_StyledBackground, True)
        self._loading_overlay.setStyleSheet("QFrame{background:rgba(11,15,20,0.85);}")
        self._loading_overlay.hide()
        ol = QtWidgets.QVBoxLayout(self._loading_overlay); ol.setContentsMargins(0,0,0,0); ol.setAlignment(Qt.AlignCenter)
        panel = QtWidgets.QFrame(); panel.setAttribute(Qt.WA_StyledBackground, True)
        panel.setStyleSheet("QFrame{background:#0f1521; border:1px solid rgba(255,255,255,0.18); border-radius:14px;}")
        pl2 = QtWidgets.QVBoxLayout(panel); pl2.setContentsMargins(24,24,24,24); pl2.setSpacing(12)
        self._loading_label = QtWidgets.QLabel("Loading…"); self._loading_label.setAlignment(Qt.AlignCenter)
        self._loading_label.setStyleSheet("color:#e9eef5; font-weight:800; font-size:20px;")
        self._loading_bar = QtWidgets.QProgressBar(); self._loading_bar.setRange(0,0); self._loading_bar.setTextVisible(False)
        self._loading_bar.setStyleSheet("QProgressBar{background:#0b111d; border:1px solid rgba(255,255,255,0.18); border-radius:10px; height:14px;} QProgressBar::chunk{background:#79c0ff; border-radius:10px;}")
        pl2.addWidget(self._loading_label, 0, Qt.AlignCenter); pl2.addWidget(self._loading_bar)
        ol.addWidget(panel, 0, Qt.AlignCenter)
        self._loading_timer = QTimer(self); self._loading_timer.setInterval(380); self._loading_timer.timeout.connect(self._tick_loading)

        self.setCentralWidget(kb)

    def _btn(self, text, action: Optional[str]=None, char: Optional[str]=None, pred: bool=False, primary: bool=False, warn: bool=False):
        b = QtWidgets.QPushButton(text)
        if primary:
            b.setProperty("variant", "primary")
        if warn:
            b.setProperty("variant", "warn")
        b.setProperty("action", action)
        b.setProperty("char", char)
        b.setProperty("pred", pred)
        b.setProperty("scanKey", True)
        b.clicked.connect(lambda _=False, btn=b: self._perform(btn))
        b.setMinimumHeight(52)
        return b

    # ---------- scanning visuals (property-based) ----------
    def _highlight_rows(self):
        # clear any key focus across all rows
        for rd in self.rows:
            for w in rd.widgets:
                if isinstance(w, QtWidgets.QPushButton):
                    w.setProperty("focused", False)
                    w.style().unpolish(w); w.style().polish(w); w.update()
            rd.wrap.setProperty("focused", False)
            rd.wrap.style().unpolish(rd.wrap); rd.wrap.style().polish(rd.wrap); rd.wrap.update()

        # focus current row only in ROWS mode (and when no overlay)
        if self.mode == "ROWS" and not self.overlay_open:
            rd = self.rows[self.row_idx]
            rd.wrap.setProperty("focused", True)
            rd.wrap.style().unpolish(rd.wrap); rd.wrap.style().polish(rd.wrap); rd.wrap.update()

        # ADD: allow a one-time suppression of row label TTS (used for predictive row jump)
        if self._suppress_row_label_once:
            self._suppress_row_label_once = False
            return

        self._speak_row_label()

    def _highlight_keys(self):
        # clear all row highlights
        for rd in self.rows:
            rd.wrap.setProperty("focused", False)
            rd.wrap.style().unpolish(rd.wrap); rd.wrap.style().polish(rd.wrap); rd.wrap.update()

        # mark only current key as focused
        cur = self.rows[self.row_idx]
        for i, w in enumerate(cur.widgets):
            if isinstance(w, QtWidgets.QPushButton):
                w.setProperty("focused", i == self.key_idx)
                w.style().unpolish(w); w.style().polish(w); w.update()

        self._speak_key_label()

    # ---------- event filter (capture space/enter globally)
    def eventFilter(self, obj, ev):
        try:
            if ev.type() == QtCore.QEvent.KeyPress and isinstance(ev, QtGui.QKeyEvent):
                if ev.key() in (Qt.Key_Space, Qt.Key_Return, Qt.Key_Enter):
                    self.keyPressEvent(ev); return True
            if ev.type() == QtCore.QEvent.KeyRelease and isinstance(ev, QtGui.QKeyEvent):
                if ev.key() in (Qt.Key_Space, Qt.Key_Return, Qt.Key_Enter):
                    self.keyReleaseEvent(ev); return True
        except Exception:
            pass
        return super().eventFilter(obj, ev)

    def keyPressEvent(self, e: QtGui.QKeyEvent):
        if e.isAutoRepeat(): return
        if e.key() == Qt.Key_Space:
            e.accept()
            if not self.space_down:
                self.space_down = True
                self.space_at = time.time()
                self.space_scanned = False
                self.space_timer.start()
        elif e.key() in (Qt.Key_Return, Qt.Key_Enter):
            e.accept()
            if not self.enter_down:
                self.enter_down = True
                self.enter_at = time.time()
                # ADD: start long-hold timer (ignore when overlay is open)
                if not self.overlay_open:
                    try: self.enter_timer.start()
                    except Exception: pass
        else:
            super().keyPressEvent(e)

    def keyReleaseEvent(self, e: QtGui.QKeyEvent):
        if e.isAutoRepeat(): return
        # Overlay scanning (prev/next/close)
        if self.overlay_open and e.key() in (Qt.Key_Space, Qt.Key_Return, Qt.Key_Enter):
            if e.key() == Qt.Key_Space:
                if not self.space_down: return
                held = (time.time() - self.space_at)*1000.0
                self.space_down = False; self.space_timer.stop()
                if self._in_cooldown(): return
                if self.SHORT_MIN <= held < self.SHORT_MAX:
                    self._overlay_focus_next()
                    self._arm_cooldown()
            else:
                if not self.enter_down: return
                self.enter_down = False
                if self._in_cooldown(): return
                self._overlay_activate()
                self._arm_cooldown()
            return

        if e.key() == Qt.Key_Space:
            e.accept()
            if not self.space_down: return
            held = (time.time() - self.space_at)*1000.0
            self.space_down = False; self.space_timer.stop()
            if self._in_cooldown(): return
            if self.SHORT_MIN <= held < self.SHORT_MAX and not self.space_scanned:
                if self.mode == "ROWS":
                    self._scan_rows_next()
                else:
                    self._scan_keys_next()
                self._arm_cooldown()
            return
        elif e.key() in (Qt.Key_Return, Qt.Key_Enter):
            e.accept()
            if not self.enter_down: return
            self.enter_down = False
            # ADD: stop hold timer and swallow if long-hold already acted
            try:
                if self.enter_timer.isActive():
                    self.enter_timer.stop()
            except Exception:
                pass
            if self.enter_long_fired:
                self.enter_long_fired = False
                return
            if self._in_cooldown(): return
            # ...existing short-press enter behavior...
            if self.mode == "KEYS":
                self._activate_key()
                self.mode = "ROWS"
                self._highlight_rows()
            else:
                self._enter_row()
            self._arm_cooldown()
        else:
            super().keyReleaseEvent(e)

    def _space_prev(self):
        self.space_scanned = True
        if self.overlay_open:
            # When an overlay is up, long-hold space should scan the overlay controls backward
            self._overlay_focus_prev()
            return
        if self.mode == "ROWS":
            self._scan_rows_prev()
        else:
            self._scan_keys_prev()

    def _scan_rows_next(self):
        self.row_idx = (self.row_idx + 1) % len(self.rows)
        self._highlight_rows()
    def _scan_rows_prev(self):
        self.row_idx = (self.row_idx - 1 + len(self.rows)) % len(self.rows)
        self._highlight_rows()
    def _enter_row(self):
        rd = self.rows[self.row_idx]

        # If it's the text row, just speak the text instead of entering key mode
        if rd.id == "row_text":
            v = self.text.text().strip()
            if v:
                speak(v)
            else:
                speak("empty")
            return

        # Otherwise, go into KEYS mode
        for r in self.rows:
            r.wrap.setProperty("focused", False)
            r.wrap.style().unpolish(r.wrap); r.wrap.style().polish(r.wrap); r.wrap.update()
        self.mode = "KEYS"
        self.key_idx = 0
        self._highlight_keys()
    def _scan_keys_next(self):
        rd = self.rows[self.row_idx]
        self.key_idx = (self.key_idx + 1) % len(rd.widgets)
        self._highlight_keys()
    def _scan_keys_prev(self):
        rd = self.rows[self.row_idx]
        self.key_idx = (self.key_idx - 1 + len(rd.widgets)) % len(rd.widgets)
        self._highlight_keys()
    def _activate_key(self):
        # before leaving KEYS, clear key focus
        cur = self.rows[self.row_idx]
        for w in cur.widgets:
            if isinstance(w, QtWidgets.QPushButton):
                w.setProperty("focused", False)
                w.style().unpolish(w); w.style().polish(w); w.update()
        # perform
        rd = self.rows[self.row_idx]
        w = rd.widgets[self.key_idx]
        if isinstance(w, QtWidgets.QPushButton):
            self._perform(w)

    # ADD: Enter 3s hold handler
    def _on_enter_hold(self):
        if not self.enter_down or self.overlay_open:
            return
        try:
            if self.mode == "KEYS":
                # revert to row select mode
                self.mode = "ROWS"
                self._highlight_rows()
                speak("rows")
                self.enter_long_fired = True
                return
            if self.mode == "ROWS":
                # jump to predictive row and read each word
                pred_idx = next((i for i, rd in enumerate(self.rows) if rd.id == "predRow"), None)
                if pred_idx is not None:
                    self.row_idx = pred_idx
                    # ADD: suppress the "predictive text" label once; only speak the words
                    self._suppress_row_label_once = True
                    self._highlight_rows()  # will not speak row label due to suppression
                    self._read_pred_row()
                    self.enter_long_fired = True
        except Exception:
            pass

    # ADD: speak each prediction with small delays to avoid TTS queue coalescing
    def _read_pred_row(self):
        try:
            words = [b.text().strip() for b in getattr(self, "pred_btns", []) if (b.text() or "").strip()]
            delay = 200
            step = 1000  # Increased from 900 to 1000ms to prevent TTS queue coalescing
            for i, w in enumerate(words):
                QtCore.QTimer.singleShot(delay + i * step, lambda ww=w: speak(ww))
        except Exception:
            pass

    # ADD: cooldown helpers
    def _now_ms(self) -> int:
        return int(time.time() * 1000)

    def _in_cooldown(self) -> bool:
        return self._now_ms() < self._cooldown_until_ms

    def _arm_cooldown(self):
        self._cooldown_until_ms = self._now_ms() + self.INPUT_COOLDOWN_MS

    # ---------- actions
    def _perform(self, btn: QtWidgets.QPushButton):
        action = btn.property("action")
        ch = btn.property("char")
        is_pred = bool(btn.property("pred"))
        history_term = btn.property("history_term")

        # Handle history term selection
        if history_term and self.search_history_mode:
            # Add the full history term to text box
            current_text = self.text.text().strip()
            if current_text:
                self.text.setText(current_text + " " + history_term + " ")
            else:
                self.text.setText(history_term + " ")
            speak(history_term)
            self._schedule_predictions()
            return

        if ch:
            self.text.setText((self.text.text() + ch).upper())
            speak(ch)
            self._schedule_predictions()
            return
        if is_pred:
            v = self.text.text()
            has_sp = v.endswith(" ")
            trimmed = v.rstrip()
            parts = trimmed.split() if trimmed else []
            current = parts[-1] if parts else ""
            before = " ".join(parts[:-1]) if len(parts)>1 else ""
            pred = btn.text()
            if has_sp or current=="":
                newv = (trimmed + " " + pred + " ")
            elif pred.lower().startswith(current.lower()):
                newv = ((before + " " if before else "") + pred + " ")
            else:
                newv = (trimmed + " " + pred + " ")
            normalized = " ".join(newv.split())
            if not normalized.endswith(" "): normalized += " "
            self.text.setText(normalized)
            speak(pred)
            self._schedule_predictions()
            return

        if action == "space_char":
            self.text.setText(self.text.text() + " ")
            speak("space")
            self._schedule_predictions(); return
        if action == "del_letter":
            speak("delete letter")
            self.text.setText(self.text.text()[:-1])
            self._schedule_predictions(); return
        if action == "del_word":
            speak("delete word")
            v = self.text.text()
            trimmed = v.rstrip()
            if not trimmed:
                self.text.setText("")
            else:
                idx = trimmed.rfind(" ")
                if idx == -1:
                    # only one word present -> clear all
                    self.text.setText("")
                else:
                    # keep previous words and exactly one trailing space
                    self.text.setText(trimmed[:idx+1])
            self._schedule_predictions(); return
        if action == "clear":
            speak("clear")
            self.text.setText("")
            self._schedule_predictions(); return
        if action == "exit":
            speak("exit")
            self._launch_comm_v10()  # launch Comm-v10.py in root
            QtCore.QTimer.singleShot(0, QtWidgets.QApplication.quit)
            return

        if action == "toggle_history":
            self._toggle_search_history_mode()
            return

        if action == "clear_history":
            speak("clear search history")
            self.search_history = []
            self.frequent_searches = {}
            self._save_search_history()
            if self.search_history_mode:
                self._update_rows_for_history_mode()
            return

        if action == "search_images":
            q = (self.text.text() or "").strip()
            if not q: return
            self._add_to_history(q)  # Add to search history
            speak("search images")
            self._show_loading("images")
            self._start_images(q)
            return

        if action == "search_video":
            q = (self.text.text() or "").strip()
            if not q: return
            self._add_to_history(q)  # Add to search history
            speak("search video")
            self._show_loading("videos")
            self._start_videos(q)
            return

    # ---- predictions (new: debounced + threaded KenLM) ----
    def _apply_predictions(self):
        # compatibility shim for any stray callers; just schedule the async path
        self._schedule_predictions()

    def _schedule_predictions(self):
        self.pred_timer.start()

    def _refresh_predictions_async(self):
        self.pred_req_id += 1
        rid = self.pred_req_id
        txt = self.text.text()
        try:
            self.pred_worker.request.emit(rid, txt)
        except Exception:
            # synchronous last resort
            self._on_predictions_ready(rid, txt, _fallback_ngram(txt, 6))

    @QtCore.Slot(int, str, list)
    def _on_predictions_ready(self, rid: int, text: str, words: list):
        if rid != self.pred_req_id:
            return  # stale
        arr = (words or [])[:6]
        for i, b in enumerate(self.pred_btns):
            b.setText(arr[i].upper() if i < len(arr) else "")
        self._pred_current = arr

    def _launch_comm_v10(self):
        # Start Comm-v10.py in the project root folder
        try:
            root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            script = os.path.join(root, "Comm-v10.py")
            if os.path.isfile(script):
                args = [sys.executable or "python", script]
                creationflags = 0
                if sys.platform.startswith("win"):
                    # CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS (safe fallback)
                    creationflags = 0x00000008 | 0x00000008
                try:
                    subprocess.Popen(args, cwd=root, creationflags=creationflags)
                except Exception:
                    subprocess.Popen(args, cwd=root)
        except Exception:
            try:
                if sys.platform.startswith("win"):
                    os.startfile(os.path.join(root, "Comm-v10.py"))
            except Exception:
                pass

    # ---------- Loading overlay
    def _show_loading(self, what="results"):
        self._loading_base = f"Loading {what}"
        self._loading_dots = 0
        self._loading_overlay.setParent(self)
        self._loading_overlay.raise_()
        self._loading_overlay.setGeometry(self.rect())
        self._loading_label.setText(self._loading_base + "…")
        self._loading_overlay.show()
        if not self._loading_timer.isActive():
            self._loading_timer.start()

    def _hide_loading(self):
        try:
            if self._loading_timer.isActive():
                self._loading_timer.stop()
        except Exception:
            pass
        self._loading_overlay.hide()

    def _tick_loading(self):
        try:
            self._loading_overlay.setGeometry(self.rect())
            self._loading_dots = (self._loading_dots + 1) % 4
            self._loading_label.setText(self._loading_base + "." * self._loading_dots)
        except Exception:
            pass

    # ---------- Searches (hidden)
    def _start_images(self, query: str):
        self.bg_task = "images"
        self.bg_query = query
        self.bg_provider = "google"
        self.bg_deadline_ms = QtCore.QDateTime.currentMSecsSinceEpoch() + 25000

        q_enc = QtCore.QUrl.toPercentEncoding(query).data().decode()

        # Prefer large photo-like results and paginate (ijn=0,1,2)
        google_pages = [
            f"https://www.google.com/search?tbm=isch&hl=en&safe=off&tbs=isz:l,itp:photo&udm=2&ijn={i}&q={q_enc}"
            for i in (0, 1, 2)
        ]

        # If query looks like a handle/brand, try site-biased Google Images pages up front
        site_bias = []
        low = (query or "").lower()
        if any(s in low for s in ["beaminbenny", "@beaminbenny", "benny"]):
            site_bias = [
                f"https://www.google.com/search?tbm=isch&hl=en&safe=off&tbs=isz:l,itp:photo&udm=2&ijn=0&q={QtCore.QUrl.toPercentEncoding('site:instagram.com ' + query).data().decode()}",
                f"https://www.google.com/search?tbm=isch&hl=en&safe=off&tbs=isz:l,itp:photo&udm=2&ijn=0&q={QtCore.QUrl.toPercentEncoding('site:tiktok.com ' + query).data().decode()}",
                f"https://www.google.com/search?tbm=isch&hl=en&safe=off&tbs=isz:l,itp:photo&udm=2&ijn=0&q={QtCore.QUrl.toPercentEncoding('site:youtube.com ' + query).data().decode()}",
            ]

        # Other engines as absolute fallbacks
        ddg = f"https://duckduckgo.com/?q={q_enc}&iar=images&iax=images&ia=images&kp=-2"
        bing = f"https://www.bing.com/images/search?q={q_enc}&FORM=HDRSC2&safeSearch=off&adlt=off"
        brave = f"https://search.brave.com/images?q={q_enc}&source=web&spellcheck=1&safesearch=off"

        # Build visit queue: site-bias -> Google pages -> DDG -> Bing -> Brave
        self._img_queue = site_bias + google_pages + [ddg, bing, brave]
        self._img_accum = []
        self._img_seen = set()

        # Kick off
        if self._img_queue:
            self.bg.setUrl(QUrl(self._img_queue.pop(0)))
        if not self.bg_timer.isActive():
            self.bg_timer.start()

    def _start_videos(self, query: str):
        self.bg_task = "videos"
        self.bg_query = query
        self.bg_deadline_ms = QtCore.QDateTime.currentMSecsSinceEpoch() + 25000
        url = f"https://www.youtube.com/results?search_query={QtCore.QUrl.toPercentEncoding(query).data().decode()}&hl=en"
        self.bg.setUrl(QUrl(url))
        if not self.bg_timer.isActive():
            self.bg_timer.start()

    def _on_bg_loaded(self, ok: bool):
        # Add debugging for page load status
        print(f"DEBUG: Page loaded, ok={ok}, current URL: {self.bg.url().toString()}")
        if self.bg_task:
            print(f"DEBUG: Loading task: {self.bg_task}, query: {self.bg_query}")

    def _bg_tick(self):
        now = QtCore.QDateTime.currentMSecsSinceEpoch()
        
        # Add current status debugging
        current_url = self.bg.url().toString()
        print(f"DEBUG: Tick - task={self.bg_task}, provider={self.bg_provider}, URL={current_url[:100]}...")
        
        if now > self.bg_deadline_ms:
            # timed out -> fallback or give up
            print(f"DEBUG: Timeout reached for {self.bg_task} on {self.bg_provider}")
            if self.bg_task == "images":
                if self.bg_provider == "google":
                    # Fallback to DuckDuckGo Images (kp=-2 disables safe search)
                    self.bg_provider = "ddg"
                    u = f"https://duckduckgo.com/?q={QtCore.QUrl.toPercentEncoding(self.bg_query).data().decode()}&iar=images&iax=images&ia=images&kp=-2"
                    print(f"DEBUG: Falling back to DDG: {u}")
                    self.bg.setUrl(QUrl(u))
                    self.bg_deadline_ms = now + 22000
                    return
                elif self.bg_provider == "ddg":
                    # Fallback to Bing images with safesearch off
                    self.bg_provider = "bing"
                    u = f"https://www.bing.com/images/search?q={QtCore.QUrl.toPercentEncoding(self.bg_query).data().decode()}&FORM=HDRSC2&safeSearch=off&adlt=off"
                    print(f"DEBUG: Falling back to Bing: {u}")
                    self.bg.setUrl(QUrl(u))
                    self.bg_deadline_ms = now + 22000
                    return
                elif self.bg_provider == "bing":
                    # Fallback to Brave images (explicitly permissive)
                    self.bg_provider = "brave"
                    u = f"https://search.brave.com/images?q={QtCore.QUrl.toPercentEncoding(self.bg_query).data().decode()}&source=web&spellcheck=1&safesearch=off"
                    print(f"DEBUG: Falling back to Brave: {u}")
                    self.bg.setUrl(QUrl(u))
                    self.bg_deadline_ms = now + 22000
                    return
            # Out of options
            print(f"DEBUG: No more fallbacks, giving up on {self.bg_task}")
            self.bg_timer.stop()
            self._hide_loading()
            return

        # Give pages more time to load before injecting JS - increase from every 550ms to less frequent
        elapsed = now - (self.bg_deadline_ms - 25000)  # time since start
        if elapsed < 3000:  # Wait at least 3 seconds before first JS injection
            print(f"DEBUG: Waiting for page to load, elapsed: {elapsed}ms")
            return

        # Nudge hydration and accept consent
        try:
            self.bg.page().runJavaScript(CONSENT_JS, 0)
        except Exception:
            pass
        try:
            self.bg.page().runJavaScript(
                "try{ window.scrollBy(0, Math.max(1400, document.body.scrollHeight/1.5)); setTimeout(()=>window.scrollTo(0,0), 180);}catch(e){}", 0
            )
        except Exception:
            pass

        if self.bg_task == "images":
            self.bg.page().runJavaScript(INJECT_IMAGES, 0, self._bg_handle_images)
        elif self.bg_task == "videos":
            self.bg.page().runJavaScript(INJECT_VIDEOS, 0, self._bg_handle_videos)

    def _bg_handle_images(self, json_str):
        print(f"DEBUG: Image extraction returned: {len(json_str or '')} chars")
        try:
            items = json.loads(json_str or "[]")
            print(f"DEBUG: Parsed {len(items)} image items")
        except Exception as e:
            print(f"DEBUG: JSON parse error: {e}")
            items = []

        # De-dupe and accumulate up to IMG_MAX
        for it in items:
            u = (it.get("img") or "").strip()
            if not u or u in self._img_seen:
                continue
            self._img_seen.add(u)
            self._img_accum.append(it)
            if len(self._img_accum) >= self.IMG_MAX:
                break

        print(f"DEBUG: Total accumulated images: {len(self._img_accum)}")

        # Enough collected: prefetch and stop
        if len(self._img_accum) >= self.IMG_MAX:
            self.bg_timer.stop()
            self._prefetch_images(self._img_accum[:self.IMG_MAX])
            return

        # Otherwise move to next queued URL to broaden coverage
        if self._img_queue:
            next_url = self._img_queue.pop(0)
            print(f"DEBUG: Moving to next URL: {next_url}")
            self.bg.setUrl(QUrl(next_url))
            now = QtCore.QDateTime.currentMSecsSinceEpoch()
            self.bg_deadline_ms = now + 22000
        else:
            # No more sources; if we have some, use them; else keep polling until deadline fallback
            if self._img_accum:
                print(f"DEBUG: No more URLs, using {len(self._img_accum)} accumulated images")
                self.bg_timer.stop()
                self._prefetch_images(self._img_accum)
            # else: keep polling; _bg_tick deadline will hide loading when timeouts occur

    def _bg_handle_videos(self, json_str):
        print(f"DEBUG: Video extraction returned: {len(json_str or '')} chars")
        try:
            vids = json.loads(json_str or "[]")
            print(f"DEBUG: Parsed {len(vids)} video items")
            if vids:
                print(f"DEBUG: First video: {vids[0]}")
        except Exception as e:
            print(f"DEBUG: JSON parse error: {e}")
            vids = []
        if vids:
            self.bg_timer.stop()
            if self.video_show is None:
                self.video_show = _VideoSlideshow(self)
            self.video_show.open_list(vids[:30])
            self._hide_loading()
            self.overlay_open = True
            self._overlay_idx = 0
            self._overlay_apply()
        else:
            # keep polling; YouTube can be slow to hydrate
            print("DEBUG: No videos found, continuing to poll...")
            pass

    # ---------- Image prefetch
    def _prefetch_images(self, items):
        # clean temp dir
        try: self._cleanup_img_temp_dir()
        except Exception: pass
        try:
            self._img_temp_dir = tempfile.mkdtemp(prefix="narbe_imgs_")
        except Exception:
            self._img_temp_dir = None
        self._img_fetch_thread = QtCore.QThread(self)
        self._img_fetch_worker = _ImageFetchWorker(items, self._img_temp_dir)
        self._img_fetch_worker.moveToThread(self._img_fetch_thread)
        self._img_fetch_thread.started.connect(self._img_fetch_worker.run)
        self._img_fetch_worker.finished.connect(self._on_images_ready)
        self._img_fetch_worker.finished.connect(self._img_fetch_thread.quit)
        self._img_fetch_worker.finished.connect(self._img_fetch_worker.deleteLater)
        self._img_fetch_thread.finished.connect(self._img_fetch_thread.deleteLater)
        self._img_fetch_thread.start()

    def _on_images_ready(self, ready_items):
        self._img_fetch_thread = None
        self._img_fetch_worker = None
        items = ready_items or []
        # Filter out entries without a real file (extra safety)
        try:
            items = [it for it in items if os.path.isfile(it.get("file") or "")]
        except Exception:
            pass
        if not items:
            self._hide_loading()
            return
        if self.image_show is None:
            self.image_show = _ImageSlideshow(self)
        self.image_show.open_list(items)
        self._hide_loading()
        self.overlay_open = True
        self._overlay_idx = 1
        self._overlay_apply()

    def _cleanup_img_temp_dir(self):
        try:
            if getattr(self, "_img_fetch_thread", None) and self._img_fetch_thread.isRunning():
                return
        except Exception:
            pass
        try:
            if getattr(self, "_img_temp_dir", None) and os.path.isdir(self._img_temp_dir):
                shutil.rmtree(self._img_temp_dir, ignore_errors=True)
        except Exception:
            pass
        self._img_temp_dir = None

    # ---------- Overlay scan helpers
    def _overlay_buttons(self):
        try:
            if self.image_show and self.image_show.isVisible():
                return list(getattr(self.image_show, "buttons", []) or [])
            if self.video_show and self.video_show.isVisible():
                return list(getattr(self.video_show, "buttons", []) or [])
        except Exception:
            pass
        return []

    def _overlay_apply(self):
        btns = self._overlay_buttons()
        if not btns: return
        self._overlay_idx = max(0, min(self._overlay_idx, len(btns)-1))
        # property-based focus for overlay buttons
        for i, b in enumerate(btns):
            try:
                b.setProperty("focused", i == self._overlay_idx)
                b.style().unpolish(b); b.style().polish(b); b.update()
            except Exception:
                pass
        try:
            cur = btns[self._overlay_idx]
            lbl = (cur.text() or "").strip() or "button"
            speak(lbl)
        except Exception:
            pass

    def _overlay_focus_next(self):
        btns = self._overlay_buttons()
        if not btns: return
        self._overlay_idx = (self._overlay_idx + 1) % len(btns)
        self._overlay_apply()

    def _overlay_focus_prev(self):
        btns = self._overlay_buttons()
        if not btns:
            return
        self._overlay_idx = (self._overlay_idx - 1 + len(btns)) % len(btns)
        self._overlay_apply()

    def _overlay_activate(self):
        btns = self._overlay_buttons()
        if not btns: return
        btn = btns[self._overlay_idx]
        act = btn.property("action") or ""
        try:
            if act == "img_prev" and self.image_show and self.image_show.isVisible():
                self.image_show.prev(); speak("previous"); return
            if act == "img_next" and self.image_show and self.image_show.isVisible():
                self.image_show.next(); speak("next"); return
            if act == "img_close" and self.image_show and self.image_show.isVisible():
                self.image_show.close(); speak("close"); return
            if act == "vd_prev"  and self.video_show and self.video_show.isVisible():
                self.video_show.prev(); speak("previous"); return
            if act == "vd_next"  and self.video_show and self.video_show.isVisible():
                self.video_show.next(); speak("next"); return
            if act == "vd_close" and self.video_show and self.video_show.isVisible():
                self.video_show.close(); speak("close"); return
            btn.click()
            speak((btn.text() or "").strip() or "button")
        except Exception:
            try: btn.click()
            except Exception: pass

    # ---------- Row/key speech helpers ----------
    def _speak_row_label(self):
        rd = self.rows[self.row_idx]
        if rd.id == "row_text":
            return
        if rd.id in ("row1","row2","row3","row4","row5","row6"):
            if self.search_history_mode:
                # In history mode, speak the actual search terms in the buttons
                if rd.id == "row1":
                    # Speak "frequent searches" first, then the terms
                    terms = []
                    for btn in self.row_buttons[0]:
                        term = btn.property("history_term")
                        if term:
                            terms.append(term)
                    if terms:
                        speak("frequent searches: " + ", ".join(terms))
                    else:
                        speak("frequent searches empty")
                else:
                    # For other rows, just speak the search terms
                    row_index = int(rd.id.replace("row", "")) - 1  # Convert row1->0, row2->1, etc.
                    terms = []
                    for btn in self.row_buttons[row_index]:
                        term = btn.property("history_term")
                        if term:
                            terms.append(term)
                    if terms:
                        speak(", ".join(terms))
                    else:
                        speak("empty")
            else:
                # Normal keyboard mode
                row_names = {
                    "row1": "a b c d e f",
                    "row2": "g h i j k l",
                    "row3": "m n o p q r",
                    "row4": "s t u v w x",
                    "row5": "y z zero one two three",
                    "row6": "four five six seven eight nine",
                }
                speak(row_names.get(rd.id, rd.label))
            return
        if rd.id == "row_modes": speak("search")
        elif rd.id == "row_controls": speak("controls")
        elif rd.id == "predRow": speak("predictive text")

    def _speak_key_label(self):
        cur = self.rows[self.row_idx]
        try:
            w = cur.widgets[self.key_idx]
            if isinstance(w, QtWidgets.QPushButton):
                label = (w.text() or "").strip()
                if label: speak(label)
        except Exception:
            pass

    # ---------- Windows kiosk helpers (force focus + close Start/Widgets)
    def _install_force_focus(self):
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        self.showFullScreen()
        try: self._hwnd = int(self.winId())
        except Exception: self._hwnd = None

        self._ff_timer = QTimer(self); self._ff_timer.setInterval(600)
        self._ff_timer.timeout.connect(self._force_focus_tick); self._ff_timer.start()

        self._start_timer = QTimer(self); self._start_timer.setInterval(800)
        self._start_timer.timeout.connect(self._dismiss_start_menu); self._start_timer.start()

        self._fs_timer = QTimer(self); self._fs_timer.setInterval(2000)
        self._fs_timer.timeout.connect(self._ensure_fullscreen_tick); self._fs_timer.start()

    def _force_focus_tick(self):
        if not getattr(self, "_hwnd", None): return
        try:
            user32 = ctypes.windll.user32; kernel32 = ctypes.windll.kernel32
            fg = user32.GetForegroundWindow()
            if not fg: return
            pid = ctypes.c_ulong(0); user32.GetWindowThreadProcessId(fg, ctypes.byref(pid))
            if pid.value == os.getpid(): return
            fg_tid = user32.GetWindowThreadProcessId(fg, None); cur_tid = kernel32.GetCurrentThreadId()
            user32.AttachThreadInput(fg_tid, cur_tid, True)
            SWP_NOMOVE, SWP_NOSIZE, HWND_TOPMOST = 0x0002, 0x0001, -1
            user32.SetWindowPos(self._hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE)
            user32.ShowWindow(self._hwnd, 5)
            user32.SetForegroundWindow(self._hwnd); user32.SetFocus(self._hwnd)
            user32.AttachThreadInput(fg_tid, cur_tid, False)
        except Exception: pass

    def _dismiss_start_menu(self):
        try:
            user32 = ctypes.windll.user32
            fg = user32.GetForegroundWindow()
            if not fg:
                return
            buf = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(fg, buf, 256)
            k = buf.value
            overlay_classes = (
                "Windows.UI.Core.CoreWindow",  # Widgets / Search flyouts
                "XamlExplorerHostIslandWindow",
                "ImmersiveLauncher",           # Start menu
            )
            if k in overlay_classes:
                VK_ESCAPE, KEYEVENTF_KEYUP = 0x1B, 0x0002
                # send ESC key to dismiss overlay
                user32.keybd_event(VK_ESCAPE, 0, 0, 0)
                user32.keybd_event(VK_ESCAPE, 0, KEYEVENTF_KEYUP, 0)
        except Exception:
            pass

    def _ensure_fullscreen_tick(self):
        try:
            if not self.isFullScreen():
                self.showFullScreen()
        except Exception:
            pass

    def closeEvent(self, e: QtGui.QCloseEvent):
        super().closeEvent(e)
        for t in (getattr(self, "_ff_timer", None),
                  getattr(self, "_start_timer", None),
                  getattr(self, "_fs_timer", None),
                  getattr(self, "_loading_timer", None),
                  getattr(self, "bg_timer", None)):
            try:
                if t and t.isActive(): t.stop()
            except Exception: pass
        try:
            if self._img_fetch_thread and self._img_fetch_thread.isRunning():
                self._img_fetch_thread.quit(); self._img_fetch_thread.wait(1000)
        except Exception: pass
        try:
            if self.pred_thread and self.pred_thread.isRunning():
                self.pred_thread.quit(); self.pred_thread.wait(1000)
        except Exception: pass
        # REPLACED: stop TTS cleanly
        try:
            _stop_tts()
        except Exception:
            pass
        self._cleanup_img_temp_dir()

# ---------- Predict worker (KenLM + fallback) ----------
class PredictWorker(QtCore.QObject):
    request = QtCore.Signal(int, str)       # (id, text)
    ready   = QtCore.Signal(int, str, list) # (id, text, predictions)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.request.connect(self._on_request)

    @QtCore.Slot(int, str)
    def _on_request(self, req_id: int, text: str):
        raw = text or ""
        ends_space = raw.endswith(" ")
        words = raw.strip().split()
        if ends_space:
            context, prefix = words[-2:], ""
        else:
            prefix = (words[-1] if words else "")
            context = words[:-1][-2:]
        try:
            preds = fetch_kenlm(context, prefix, limit=6)
            if not preds:
                preds = _fallback_ngram(raw, limit=6)
            preds = [p.lower() for p in preds if p]
        except Exception:
            try:
                preds = _fallback_ngram(raw, limit=6)
            except Exception:
                preds = local_suggest(raw, 6)

        # ADD: hardcoded injections before KenLM suggestions when prefix is exactly 'n' or 'b'
        try:
            inj = []
            pl = (prefix or "").strip().lower()
            if pl == "n":
                inj.append("narbe")
            elif pl == "b":
                inj.append("beaminbenny")
            if inj:
                seen = set()
                final = []
                for w in inj + preds:
                    wl = (w or "").lower()
                    if not wl or wl in seen:
                        continue
                    seen.add(wl)
                    final.append(w)
                preds = final[:6]
        except Exception:
            pass

        self.ready.emit(req_id, text, preds)

# ---------- Image prefetch worker ----------
class _ImageFetchWorker(QtCore.QObject):
    finished = QtCore.Signal(list)
    def __init__(self, items, outdir):
        super().__init__(); self.items = items or []; self.outdir = outdir
    @QtCore.Slot()
    def run(self):
        out = []
        try:
            import os, hashlib, tempfile
            try: import requests
            except Exception: requests = None
            ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
            for it in self.items:
                try:
                    url = (it.get("img") or "").strip()
                    if not url: continue
                    # ...existing code building ref and headers...
                    ref = ""
                    try:
                        from urllib.parse import urlparse
                        pu = urlparse(url); ref = f"{pu.scheme}://{pu.netloc}/" if pu.scheme and pu.netloc else ""
                    except Exception: pass
                    data = b""
                    ctype = ""
                    if requests:
                        headers = {"User-Agent": ua}
                        if ref: headers["Referer"] = ref
                        r = requests.get(url, timeout=12, headers=headers)
                        if not r.ok: continue
                        ctype = (r.headers.get("Content-Type") or "").lower()
                        data = r.content or b""
                    else:
                        continue

                    # Determine extension - now including GIF support
                    low_url = url.lower().split("?")[0]
                    ext_hint = ""
                    if low_url.endswith(".png"): ext_hint = "png"
                    elif low_url.endswith(".jpg") or low_url.endswith(".jpeg"): ext_hint = "jpg"
                    elif low_url.endswith(".gif"): ext_hint = "gif"
                    elif low_url.endswith(".webp"): ext_hint = "webp"

                    # Skip only webp (can be flaky), but allow gifs now
                    if "webp" in ctype or ext_hint == "webp":
                        continue  # skip webp (can be flaky in some environments)

                    # Allow jpg/png/gif; default to jpg
                    out_ext = ".jpg"
                    if "png" in ctype or ext_hint == "png":
                        out_ext = ".png"
                    elif "gif" in ctype or ext_hint == "gif":
                        out_ext = ".gif"

                    # Simple byte-size guard (accept reasonable sizes, allow larger for GIFs)
                    if not (20_000 <= len(data) <= 15_000_000):  # Increased limit for animated GIFs
                        continue

                    h = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
                    fpath = os.path.join(self.outdir or tempfile.gettempdir(), h + out_ext)
                    with open(fpath, "wb") as f: f.write(data)
                    o = dict(it); o["file"] = fpath; out.append(o)
                except Exception:
                    continue
        except Exception:
            pass
        self.finished.emit(out)

# ---------- Image slideshow ----------
class _ImageSlideshow(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent, QtCore.Qt.FramelessWindowHint)
        self.setModal(True); self.setWindowModality(Qt.ApplicationModal)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self.items = []; self.idx = 0
        self.current_movie = None  # Track current QMovie for GIFs
        v = QtWidgets.QVBoxLayout(self); v.setContentsMargins(24,24,24,24); v.setSpacing(8)
        bg = QtWidgets.QFrame(); bg.setStyleSheet("QFrame{background:rgba(0,0,0,0.94); border-radius:14px;}")
        gl = QtWidgets.QVBoxLayout(bg); gl.setContentsMargins(12,12,12,12); gl.setSpacing(8)
        self.label = QtWidgets.QLabel(""); self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet("QLabel{background:#000; border-radius:8px;}"); self.label.setMinimumSize(480,320)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        gl.addWidget(self.label, 1)
        bar = QtWidgets.QFrame(); bl = QtWidgets.QHBoxLayout(bar); bl.setContentsMargins(6,6,6,6); bl.setSpacing(8)
        def mk(txt, act):
            b = QtWidgets.QPushButton(txt)
            b.setProperty("action", act)
            b.setProperty("scanKey", True)
            return b
        self.btn_prev = mk("previous","img_prev"); self.btn_next = mk("next","img_next"); self.btn_close= mk("close","img_close")
        self.buttons = [self.btn_prev, self.btn_next, self.btn_close]
        for b in self.buttons: bl.addWidget(b)
        gl.addWidget(bar, 0); v.addWidget(bg, 1)
        self.btn_prev.clicked.connect(self.prev); self.btn_next.clicked.connect(self.next); self.btn_close.clicked.connect(self.close)

    def open_list(self, items):
        self.items = items or []; self.idx = 0
        self._show_current()
        try:
            p = self.parent(); self.resize(p.size()); self.move(p.pos())
        except Exception: pass
        self.show()

    def _show_current(self):
        if not self.items: return
        
        # Stop any current animation
        if self.current_movie:
            self.current_movie.stop()
            self.current_movie = None
            
        it = self.items[self.idx]; local_file = it.get("file") or ""
        if local_file:
            try:
                # Check if it's a GIF by file extension
                if local_file.lower().endswith('.gif'):
                    # Use QMovie for animated GIFs
                    self.current_movie = QtGui.QMovie(local_file)
                    if self.current_movie.isValid():
                        # Scale the movie to fit the label
                        target = self.label.size() if (self.label.size().width() >= 10 and self.label.size().height() >= 10) else self.size()
                        self.current_movie.setScaledSize(target)
                        self.label.setMovie(self.current_movie)
                        self.current_movie.start()
                        return
                    else:
                        # If QMovie fails, fall back to QPixmap (will show first frame)
                        self.current_movie = None
                
                # Use QPixmap for static images (JPG, PNG) or as GIF fallback
                pm = QtGui.QPixmap(local_file)
                if not pm.isNull():
                    target = self.label.size() if (self.label.size().width() >= 10 and self.label.size().height() >= 10) else self.size()
                    self.label.setPixmap(pm.scaled(target, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                    return
            except Exception: 
                pass

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self.current_movie and self.current_movie.isValid():
            # Rescale animated GIF
            target = self.label.size()
            self.current_movie.setScaledSize(target)
        else:
            # Rescale static image
            pm = self.label.pixmap()
            if pm:
                target = self.label.size()
                self.label.setPixmap(pm.scaled(target, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def prev(self):
        if not self.items: return
        self.idx = (self.idx - 1 + len(self.items)) % len(self.items); self._show_current()

    def next(self):
        if not self.items: return
        self.idx = (self.idx + 1) % len(self.items); self._show_current()

    def closeEvent(self, e: QtGui.QCloseEvent):
        # Stop any running animation
        if self.current_movie:
            self.current_movie.stop()
            self.current_movie = None
        super().closeEvent(e)
        try:
            p = self.parent()
            if p:
                p.overlay_open = False; p.setFocus(); p._cleanup_img_temp_dir()
        except Exception: pass

    def keyReleaseEvent(self, e: QtGui.QKeyEvent):
        if e.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space, Qt.Key_Escape):
            self.close()
        else:
            super().keyReleaseEvent(e)

# ---------- Video slideshow ----------
class _VideoSlideshow(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent, QtCore.Qt.FramelessWindowHint)
        self.setModal(True); self.setWindowModality(Qt.ApplicationModal)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self.items = []; self.idx = 0
        v = QtWidgets.QVBoxLayout(self); v.setContentsMargins(24,24,24,24); v.setSpacing(8)
        bg = QtWidgets.QFrame(); bg.setStyleSheet("QFrame{background:rgba(0,0,0,0.94); border-radius:14px;}")
        gl = QtWidgets.QVBoxLayout(bg); gl.setContentsMargins(12,12,12,12); gl.setSpacing(8)
        self.web = QWebEngineView()
        self.web.setStyleSheet("QWebEngineView{background:#000; border-radius:8px;}"); self.web.setMinimumSize(480,320)
        try:
            self.web.settings().setAttribute(QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture, False)
            self.web.settings().setAutoplayPolicy(QWebEngineSettings.AutoplayPolicy.NoUserGestureRequired)
        except Exception: pass
        gl.addWidget(self.web, 1)
        bar = QtWidgets.QFrame(); bl = QtWidgets.QHBoxLayout(bar); bl.setContentsMargins(6,6,6,6); bl.setSpacing(8)
        def mk(txt, act):
            b = QtWidgets.QPushButton(txt)
            b.setProperty("action", act)
            b.setProperty("scanKey", True)
            return b
        self.btn_prev   = mk("previous","vd_prev")
        self.btn_next   = mk("next","vd_next")
        self.btn_close  = mk("close","vd_close")
        self.buttons = [self.btn_prev, self.btn_next, self.btn_close]
        for b in self.buttons: bl.addWidget(b)
        gl.addWidget(bar, 0); v.addWidget(bg, 1)
        self.btn_prev.clicked.connect(self.prev); self.btn_next.clicked.connect(self.next); self.btn_close.clicked.connect(self.close)

    def open_list(self, items):
        self.items = items or []; self.idx = 0
        self._build_player_html()
        try:
            p = self.parent(); self.resize(p.size()); self.move(p.pos())
        except Exception: pass
        self.show()

    def _build_player_html(self):
        ids = [str(x.get("videoId") or "").strip() for x in (self.items or []) if (x.get("videoId") or "").strip()]
        import json as _json
        ids_js = _json.dumps(ids)
        tpl = """<!doctype html><html><head><meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<style>
  html,body{margin:0;height:100%;background:#000;}
  #wrap{position:fixed;inset:0;display:flex;align-items:center;justify-content:center;background:#000;}
  #player{width:100%;height:100%;}
</style>
</head><body>
<div id="wrap"><div id="player"></div></div>
<script>
(function(){
  var tag = document.createElement('script');
  tag.src = "https://www.youtube.com/iframe_api"; tag.async = true;
  document.head.appendChild(tag);
  var player, idx = 0, playlist = PLAYLIST_IDS;
  function loadIdx(i){ if (!playlist.length) return; idx = ( (i % playlist.length) + playlist.length ) % playlist.length; try { player.loadVideoById(playlist[idx]); } catch(e){} }
  function ensureLoud(){ try{ player.unMute(); player.setVolume(85); }catch(e){} }
  window.onYouTubeIframeAPIReady = function(){
    player = new YT.Player('player', {
      host: 'https://www.youtube-nocookie.com',
      videoId: (playlist[0]||''),
      playerVars: { autoplay: 1, controls: 0, rel: 0, modestbranding: 1, playsinline: 1, fs: 0, enablejsapi: 1 },
      events: {
        onReady: function(){ try { ensureLoud(); player.playVideo(); } catch (e) {} ; setTimeout(ensureLoud, 300); },
        onError: function(){ try { loadIdx(idx+1); } catch(e){} },
        onStateChange: function(ev){
          try{
            if (ev && (ev.data === YT.PlayerState.UNSTARTED || ev.data === YT.PlayerState.CUED || ev.data === YT.PlayerState.PAUSED)) { ensureLoud(); player.playVideo(); }
            else if (ev && ev.data === YT.PlayerState.ENDED) { loadIdx(idx+1); }
            else if (ev && ev.data === YT.PlayerState.PLAYING) { ensureLoud(); }
          }catch(e){}
        }
      }
    });
  };
  window.narbePlayerApi = {
    next: function(){ loadIdx(idx+1); },
    prev: function(){ loadIdx(idx-1); },
    pause: function(){ try{ player.pauseVideo(); }catch(e){} },
    stop: function(){ try{ player.stopVideo && player.stopVideo(); }catch(e){} }
  };
})();
</script>
</body></html>"""
        html = tpl.replace("PLAYLIST_IDS", ids_js)
        self.web.setHtml(html, QUrl("https://www.youtube.com"))

    def prev(self):
        if not self.items: return
        self.idx = (self.idx - 1) % len(self.items)
        self.exec_js("narbePlayerApi && narbePlayerApi.prev();")

    def next(self):
        if not self.items: return
        self.idx = (self.idx + 1) % len(self.items)
        self.exec_js("narbePlayerApi && narbePlayerApi.next();")

    def exec_js(self, code: str):
        try: self.web.page().runJavaScript(code)
        except Exception: pass

    def shutdown(self):
        try: self.exec_js("narbePlayerApi && (narbePlayerApi.stop && narbePlayerApi.stop(), narbePlayerApi.pause && narbePlayerApi.pause());")
        except Exception: pass
        try: self.web.page().triggerAction(QWebEnginePage.Stop)
        except Exception: pass
        try: self.web.setUrl(QUrl("about:blank"))
        except Exception: pass

    def closeEvent(self, e: QtGui.QCloseEvent):
        try: self.shutdown()
        except Exception: pass
        try:
            p = self.parent()
            if p:
                p.overlay_open = False; p.setFocus()
        except Exception: pass
        super().closeEvent(e)

    def keyReleaseEvent(self, e: QtGui.QKeyEvent):
        if e.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space, Qt.Key_Escape):
            self.close()
        else:
            super().keyReleaseEvent(e)

# ---- main ----
def main():
    try:
        QtGui.QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
    except Exception: pass
    app = QtWidgets.QApplication(sys.argv)

    # Global styles: base rows, base buttons, variants, and focused highlight
    app.setStyleSheet(app.styleSheet() + f"""
    /* Row base and highlight */
    QFrame[scanRow="true"] {{
      background:#0f1521; border:1px solid rgba(255,255,255,0.10); border-radius:12px;
    }}
    QFrame[scanRow="true"][focused="true"] {{
      {FOCUS_STYLE}
    }}
    /* Button base */
    QPushButton[scanKey="true"] {{
      border:1px solid rgba(124,203,255,0.35);
      background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #15354d, stop:1 #0f2a41);
      color:#e9f5ff; font-size:16px; font-weight:600; border-radius:12px; padding:10px;
    }}
    /* Smaller text for search history buttons */
    QPushButton[scanKey="true"][history_term] {{
      font-size:12px; padding:6px 4px; font-weight:500;
    }}
    /* Button variants */
    QPushButton[scanKey="true"][variant="primary"] {{
      border:1px solid rgba(124,203,255,0.50);
      background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #1a4463, stop:1 #133750);
    }}
    QPushButton[scanKey="true"][variant="warn"] {{
      border:1px solid rgba(255,170,0,0.35);
      background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #3a1d0a, stop:1 #2a1407);
      color:#ffd79a;
    }}
    /* Focused button highlight */
    QPushButton[scanKey="true"][focused="true"] {{
      {FOCUS_STYLE}
    }}
    """)

    w = Narbe()
    w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()