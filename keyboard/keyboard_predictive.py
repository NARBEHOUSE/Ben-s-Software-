# © 2025 NARBE House – Licensed under CC BY-NC 4.0

import json
import os
import time
import threading
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime

# Define paths for predictive text data
PREDICTIVE_FILE = os.path.join(os.path.dirname(__file__), "predictive_ngrams.json")
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "predictive_config.json")

# Global variable to store JSON data (prevents reloading every keystroke)
predictive_data = {}

# ------------------------------ #
#      Configuration Settings   #
# ------------------------------ #

# Default configuration
DEFAULT_CONFIG = {
    "online_mode_enabled": True,
    "api_timeout": 5,
    "api_max_retries": 2,
    "api_vocabulary": "100k",  # 1k, 5k, 10k, 20k, 40k, 100k, 500k
    "api_safe_mode": True,
    "network_check_interval": 30,
    "cache_ttl": 300,  # 5 minutes
    "merge_strategy": "weighted",  # "weighted", "api_first", "offline_first"
    "api_weight": 0.7,  # Weight for API predictions in weighted merge
    "offline_weight": 0.3,  # Weight for offline predictions in weighted merge
    "debug_logging": False,
}

# Global configuration
config = DEFAULT_CONFIG.copy()


def load_config():
    """Load configuration from JSON file, creating default if not exists."""
    global config
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as file:
                loaded_config = json.load(file)
                # Merge with defaults to handle new config options
                config = DEFAULT_CONFIG.copy()
                config.update(loaded_config)
                print("✅ Configuration loaded successfully")
        else:
            # Create default config file
            save_config()
            print("📝 Default configuration created")
    except (json.JSONDecodeError, IOError) as e:
        print(f"⚠️ Config load error: {e}. Using defaults.")
        config = DEFAULT_CONFIG.copy()


def save_config():
    """Save current configuration to JSON file."""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as file:
            json.dump(config, file, indent=4)
    except IOError as e:
        print(f"⚠️ Config save error: {e}")


def get_config(key, default=None):
    """Get a configuration value."""
    return config.get(key, default)


def set_config(key, value):
    """Set a configuration value and save to file."""
    config[key] = value
    save_config()


def is_online_mode_enabled():
    """Check if online mode is enabled in configuration."""
    return get_config("online_mode_enabled", True)


# Load JSON data once and ensure all words are uppercase
def load_json():
    global predictive_data
    if not os.path.exists(PREDICTIVE_FILE) or os.stat(PREDICTIVE_FILE).st_size == 0:
        predictive_data = {"frequent_words": {}, "bigrams": {}, "trigrams": {}}
        return

    try:
        with open(PREDICTIVE_FILE, "r", encoding="utf-8") as file:
            predictive_data = json.load(file)

        # Convert all words to uppercase for consistency
        predictive_data["frequent_words"] = {
            k.upper(): v for k, v in predictive_data["frequent_words"].items()
        }
        predictive_data["bigrams"] = {
            k.upper(): v for k, v in predictive_data["bigrams"].items()
        }
        predictive_data["trigrams"] = {
            k.upper(): v for k, v in predictive_data["trigrams"].items()
        }

        print(
            "✅ Predictive JSON Loaded. Sample words:",
            list(predictive_data["frequent_words"].keys())[:10],
        )
    except json.JSONDecodeError:
        predictive_data = {"frequent_words": {}, "bigrams": {}, "trigrams": {}}


# Save JSON data
def save_json():
    with open(PREDICTIVE_FILE, "w", encoding="utf-8") as file:
        json.dump(predictive_data, file, indent=4)


def compute_ngram_score(data, ngram_type, candidate, current_word):
    """
    Compute a composite score for an n-gram candidate based on:
      - Its usage count.
      - Its recency (more recent uses are favored).
      - A multiplier for the n-gram type.
      - A bonus for extra letters beyond what was typed.

    Revised: If the candidate was used within the past week, it gets a huge bonus.
    """
    try:
        last_used = datetime.fromisoformat(data.get("last_used", "1970-01-01T00:00:00"))
    except Exception:
        last_used = datetime(1970, 1, 1)
    now = datetime.now()
    time_diff = (now - last_used).total_seconds()  # time difference in seconds
    recency = 1 / (time_diff + 1)  # higher value for more recent usage

    # NEW: Revised recency bonus for the past week.
    if time_diff < 3600:  # within 1 hour
        recency_bonus = 10000
    elif time_diff < 604800:  # within 1 week (604800 seconds)
        recency_bonus = 5000
    else:
        recency_bonus = 0

    multiplier = 10 if ngram_type == "trigrams" else 5
    base_score = multiplier * (data.get("count", 0) + recency) + recency_bonus
    letter_bonus = (len(candidate) - len(current_word)) * 20
    extra_letter_bonus = 40 if (len(candidate) - len(current_word)) > 3 else 0
    return base_score + letter_bonus + extra_letter_bonus


def compute_freq_score(data):
    """
    Compute a score for a frequent-word candidate based on:
      - Its usage count.
      - Its recency (with a huge bonus if used very recently).

    Revised: If the word was used within the past week, it gets a very high bonus.
    """
    try:
        last_used = datetime.fromisoformat(data.get("last_used", "1970-01-01T00:00:00"))
    except Exception:
        last_used = datetime(1970, 1, 1)
    now = datetime.now()
    time_diff = (now - last_used).total_seconds()
    recency = 1 / (time_diff + 1)
    if time_diff < 3600:
        recency_bonus = 10000
    elif time_diff < 604800:
        recency_bonus = 5000
    else:
        recency_bonus = 0
    return data.get("count", 0) + recency * 20 + recency_bonus


def get_offline_predictions(text, num_suggestions=6):
    """
    Get predictions using only the offline n-gram system.
    This is the original prediction logic, preserved for fallback.
    """
    # Check if the text (without the "|" cursor marker) ends with a space.
    has_trailing_space = text.rstrip("|").endswith(" ")

    # Clean the input: remove the "|" marker, trim spaces, and convert to uppercase.
    cleaned = text.upper().replace("|", "").strip()
    words = cleaned.split()

    # Default suggestions if nothing is typed
    DEFAULT_WORDS = ["YES", "NO", "HELP"]

    # --- Tier 0: If no words are entered, return frequent words first ---
    if not words:
        default_predictions = []
        for word, data in predictive_data.get("frequent_words", {}).items():
            if len(word) >= 2:
                score = compute_freq_score(data)
                default_predictions.append((word, score))
        sorted_default = sorted(default_predictions, key=lambda x: -x[1])
        final_predictions = [w for w, _ in sorted_default[:num_suggestions]]
        for w in DEFAULT_WORDS:
            if w not in final_predictions:
                final_predictions.append(w)
        return final_predictions[:num_suggestions]

    # --- Determine context and current (incomplete) word ---
    if has_trailing_space:
        context = cleaned
        current_word = ""
    else:
        current_word = words[-1]
        context = " ".join(words[:-1])

    # --- Tier 1: N-gram predictions with rolling trigrams ---
    predictions_ngram = {}
    if context and (has_trailing_space or context != current_word):
        ctx_words = context.split()

        # rolling contexts
        tri_ctx = " ".join(ctx_words[-2:]) if len(ctx_words) >= 2 else context
        bi_ctx = ctx_words[-1] if len(ctx_words) >= 1 else ""

        # look up trigrams using only the last two words
        for key, data in predictive_data.get("trigrams", {}).items():
            if key.startswith(tri_ctx + " "):
                next_word = key.split()[-1]
                if (
                    (current_word == "" or next_word.startswith(current_word))
                    and len(next_word) >= 2
                    and data.get("count", 0) >= 1
                ):
                    score = compute_ngram_score(
                        data, "trigrams", next_word, current_word
                    )
                    predictions_ngram[next_word] = (
                        predictions_ngram.get(next_word, 0) + score
                    )

        # fallback to bigrams on the very last word
        for key, data in predictive_data.get("bigrams", {}).items():
            if key.startswith(bi_ctx + " "):
                next_word = key.split()[-1]
                if (
                    (current_word == "" or next_word.startswith(current_word))
                    and len(next_word) >= 2
                    and data.get("count", 0) >= 1
                ):
                    score = compute_ngram_score(
                        data, "bigrams", next_word, current_word
                    )
                    predictions_ngram[next_word] = (
                        predictions_ngram.get(next_word, 0) + score
                    )

    # --- Tier 2: Frequent word completions ---
    predictions_freq = {}
    for word, data in predictive_data.get("frequent_words", {}).items():
        if word.startswith(current_word) and word != current_word and len(word) >= 2:
            score = compute_freq_score(data)
            predictions_freq[word] = score

    # --- Tier 3: Combine candidates (n-grams first, then freq, then defaults) ---
    final_predictions = []

    if predictions_ngram:
        for w, _ in sorted(predictions_ngram.items(), key=lambda x: -x[1]):
            final_predictions.append(w)

    if len(final_predictions) < num_suggestions:
        for w, _ in sorted(predictions_freq.items(), key=lambda x: -x[1]):
            if w not in final_predictions:
                final_predictions.append(w)
            if len(final_predictions) >= num_suggestions:
                break

    for w in DEFAULT_WORDS:
        if w not in final_predictions:
            final_predictions.append(w)

    return final_predictions[:num_suggestions]


def get_predictive_suggestions(text, num_suggestions=6):
    """
    Enhanced predictive suggestions supporting both offline and online modes.

    This function maintains backward compatibility while adding online prediction
    capabilities when network is available and online mode is enabled.

    Args:
        text (str): Current text input (may contain "|" cursor marker)
        num_suggestions (int): Number of suggestions to return

    Returns:
        list: List of predicted words (strings)
    """
    # Handle null/invalid input
    if text is None:
        text = ""
    # Check if online mode is enabled and available
    use_online = is_online_mode_enabled() and is_network_available()

    if get_config("debug_logging", False):
        print(
            f"🔍 Prediction mode: {'Online+Offline' if use_online else 'Offline only'}"
        )

    # Get offline predictions (always available as fallback)
    offline_predictions = get_offline_predictions_with_scores(text, num_suggestions)

    if not use_online:
        # Return offline-only predictions (original behavior)
        return [word for word, _ in offline_predictions]

    # Parse text for online API
    has_trailing_space = text.rstrip("|").endswith(" ")
    cleaned = text.upper().replace("|", "").strip()
    words = cleaned.split()

    if has_trailing_space:
        left_context = cleaned
        prefix = ""
    else:
        if words:
            prefix = words[-1]
            left_context = " ".join(words[:-1])
        else:
            prefix = ""
            left_context = ""

    # Get online predictions with error handling
    try:
        online_predictions = get_online_predictions(
            left_context, prefix, num_suggestions
        )

        # Merge predictions using configured strategy
        if online_predictions:
            merged_predictions = merge_predictions(
                offline_predictions, online_predictions, num_suggestions
            )
            if get_config("debug_logging", False):
                print(f"🔀 Merged predictions: {merged_predictions}")
            return merged_predictions
        else:
            # Fallback to offline predictions if online failed
            if get_config("debug_logging", False):
                print("⚠️ Online predictions failed, using offline fallback")
            return [word for word, _ in offline_predictions]
    except Exception as e:
        # Comprehensive error handling - always fallback to offline
        print(f"❌ Online prediction error: {e}. Falling back to offline mode.")
        return [word for word, _ in offline_predictions]


def update_word_usage(text):
    # Remove the cursor indicator from the text.
    text = text.replace("|", "")
    words = text.strip().upper().split()
    timestamp = datetime.now().isoformat()

    # Update frequent words without a length restriction.
    for word in words:
        if word in predictive_data["frequent_words"]:
            predictive_data["frequent_words"][word]["count"] += 1
            predictive_data["frequent_words"][word]["last_used"] = timestamp
        else:
            predictive_data["frequent_words"][word] = {
                "count": 1,
                "last_used": timestamp,
            }

    # Update bigrams.
    for i in range(len(words) - 1):
        bigram = f"{words[i]} {words[i+1]}"
        if bigram in predictive_data["bigrams"]:
            predictive_data["bigrams"][bigram]["count"] += 1
            predictive_data["bigrams"][bigram]["last_used"] = timestamp
        else:
            predictive_data["bigrams"][bigram] = {"count": 1, "last_used": timestamp}

    # Update trigrams.
    for i in range(len(words) - 2):
        trigram = f"{words[i]} {words[i+1]} {words[i+2]}"
        if trigram in predictive_data["trigrams"]:
            predictive_data["trigrams"][trigram]["count"] += 1
            predictive_data["trigrams"][trigram]["last_used"] = timestamp
        else:
            predictive_data["trigrams"][trigram] = {"count": 1, "last_used": timestamp}

    save_json()  # Save updates


# ------------------------------ #
#    Enhanced Prediction Logic   #
# ------------------------------ #


def get_offline_predictions_with_scores(text, num_suggestions=6):
    """
    Get offline predictions with their scores for merging purposes.
    Returns list of (word, score) tuples.
    """
    # Check if the text (without the "|" cursor marker) ends with a space.
    has_trailing_space = text.rstrip("|").endswith(" ")

    # Clean the input: remove the "|" marker, trim spaces, and convert to uppercase.
    cleaned = text.upper().replace("|", "").strip()
    words = cleaned.split()

    # Default suggestions if nothing is typed
    DEFAULT_WORDS = ["YES", "NO", "HELP"]

    # --- Tier 0: If no words are entered, return frequent words first ---
    if not words:
        default_predictions = []
        for word, data in predictive_data.get("frequent_words", {}).items():
            if len(word) >= 2:
                score = compute_freq_score(data)
                default_predictions.append((word, score))
        sorted_default = sorted(default_predictions, key=lambda x: -x[1])
        result = sorted_default[:num_suggestions]
        # Add default words with base score if not enough predictions
        for w in DEFAULT_WORDS:
            if len(result) < num_suggestions and w not in [word for word, _ in result]:
                result.append((w, 1.0))
        return result[:num_suggestions]

    # --- Determine context and current (incomplete) word ---
    if has_trailing_space:
        context = cleaned
        current_word = ""
    else:
        current_word = words[-1]
        context = " ".join(words[:-1])

    # --- Tier 1: N-gram predictions with rolling trigrams ---
    predictions_ngram = {}
    if context and (has_trailing_space or context != current_word):
        ctx_words = context.split()

        # rolling contexts
        tri_ctx = " ".join(ctx_words[-2:]) if len(ctx_words) >= 2 else context
        bi_ctx = ctx_words[-1] if len(ctx_words) >= 1 else ""

        # look up trigrams using only the last two words
        for key, data in predictive_data.get("trigrams", {}).items():
            if key.startswith(tri_ctx + " "):
                next_word = key.split()[-1]
                if (
                    (current_word == "" or next_word.startswith(current_word))
                    and len(next_word) >= 2
                    and data.get("count", 0) >= 1
                ):
                    score = compute_ngram_score(
                        data, "trigrams", next_word, current_word
                    )
                    predictions_ngram[next_word] = (
                        predictions_ngram.get(next_word, 0) + score
                    )

        # fallback to bigrams on the very last word
        for key, data in predictive_data.get("bigrams", {}).items():
            if key.startswith(bi_ctx + " "):
                next_word = key.split()[-1]
                if (
                    (current_word == "" or next_word.startswith(current_word))
                    and len(next_word) >= 2
                    and data.get("count", 0) >= 1
                ):
                    score = compute_ngram_score(
                        data, "bigrams", next_word, current_word
                    )
                    predictions_ngram[next_word] = (
                        predictions_ngram.get(next_word, 0) + score
                    )

    # --- Tier 2: Frequent word completions ---
    predictions_freq = {}
    for word, data in predictive_data.get("frequent_words", {}).items():
        if word.startswith(current_word) and word != current_word and len(word) >= 2:
            score = compute_freq_score(data)
            predictions_freq[word] = score

    # --- Tier 3: Combine candidates (n-grams first, then freq, then defaults) ---
    final_predictions = []

    if predictions_ngram:
        for w, score in sorted(predictions_ngram.items(), key=lambda x: -x[1]):
            final_predictions.append((w, score))

    if len(final_predictions) < num_suggestions:
        for w, score in sorted(predictions_freq.items(), key=lambda x: -x[1]):
            if w not in [word for word, _ in final_predictions]:
                final_predictions.append((w, score))
            if len(final_predictions) >= num_suggestions:
                break

    # Add default words with base score if needed
    for w in DEFAULT_WORDS:
        if len(final_predictions) < num_suggestions and w not in [
            word for word, _ in final_predictions
        ]:
            final_predictions.append((w, 1.0))

    return final_predictions[:num_suggestions]


# ------------------------------ #
#     Network Connectivity       #
# ------------------------------ #

# Global variables for network state
_network_available = False
_last_network_check = 0
_network_check_interval = 30  # Check every 30 seconds
_network_check_lock = threading.Lock()


def check_network_connectivity(timeout=3):
    """
    Check if network connectivity is available by attempting to reach a reliable endpoint.
    Returns True if network is available, False otherwise.
    """
    try:
        # Try to reach Google's DNS server (reliable and fast)
        urllib.request.urlopen("http://8.8.8.8", timeout=timeout)
        return True
    except (urllib.error.URLError, OSError):
        try:
            # Fallback: try to reach the API endpoint directly
            urllib.request.urlopen("https://docs.imagineville.org", timeout=timeout)
            return True
        except (urllib.error.URLError, OSError):
            return False


def is_network_available():
    """
    Returns cached network availability status, checking periodically.
    Thread-safe implementation with caching to avoid frequent network checks.
    """
    global _network_available, _last_network_check

    current_time = time.time()

    with _network_check_lock:
        # Check if we need to refresh the network status
        if current_time - _last_network_check > _network_check_interval:
            _network_available = check_network_connectivity()
            _last_network_check = current_time
            print(
                f"🌐 Network status updated: {'Available' if _network_available else 'Unavailable'}"
            )

    return _network_available


# ------------------------------ #
#        API Integration         #
# ------------------------------ #

# API Configuration
API_BASE_URL = "https://api.imagineville.org"

# Cache for API results to reduce latency
_api_cache = {}
_api_cache_lock = threading.Lock()


def _make_api_request(endpoint, params, timeout=None):
    """
    Make a request to the imagineville.org API with error handling.
    Returns the JSON response or None if the request fails.
    """
    if timeout is None:
        timeout = get_config("api_timeout", 5)

    try:
        # Construct URL with parameters
        url = f"{API_BASE_URL}/{endpoint}"
        if params:
            query_string = urllib.parse.urlencode(params)
            url = f"{url}?{query_string}"

        print(f"🌐 API Request: {url}")

        # Make the request
        with urllib.request.urlopen(url, timeout=timeout) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                print(
                    f"✅ API Response received: {len(data.get('results', []))} predictions"
                )
                return data
            else:
                print(f"❌ API Error: HTTP {response.status}")
                return None

    except urllib.error.HTTPError as e:
        print(f"❌ API HTTP Error: {e.code} - {e.reason}")
        return None
    except urllib.error.URLError as e:
        print(f"❌ API URL Error: {e.reason}")
        return None
    except json.JSONDecodeError as e:
        print(f"❌ API JSON Error: {e}")
        return None
    except Exception as e:
        print(f"❌ API Unexpected Error: {e}")
        return None


def _get_cache_key(left_context, prefix):
    """Generate a cache key for API results."""
    return f"{left_context}|{prefix}".upper()


def get_online_predictions(left_context, prefix, num_suggestions=6):
    """
    Get word predictions from the imagineville.org API.

    Args:
        left_context (str): The text context to the left of the current word
        prefix (str): The partial word being typed
        num_suggestions (int): Number of suggestions to request

    Returns:
        list: List of predicted words, or empty list if API fails
    """
    try:
        if not is_network_available():
            if get_config("debug_logging", False):
                print("🔌 Network unavailable, skipping online predictions")
            return []
    except Exception as e:
        print(f"❌ Network check failed: {e}")
        return []

    # Check cache first
    cache_key = _get_cache_key(left_context, prefix)
    current_time = time.time()
    cache_ttl = get_config("cache_ttl", 300)

    with _api_cache_lock:
        if cache_key in _api_cache:
            cached_data, timestamp = _api_cache[cache_key]
            if current_time - timestamp < cache_ttl:
                print(f"💾 Using cached API result for '{prefix}'")
                return cached_data
            else:
                # Remove expired cache entry
                del _api_cache[cache_key]

    # Prepare API parameters
    params = {
        "num": min(num_suggestions, 10),  # API supports max 10
        "vocab": get_config("api_vocabulary", "100k"),
        "sort": "logprob",  # Sort by probability
        "safe": "true" if get_config("api_safe_mode", True) else "false",
        "lang": "en",
    }

    # Add context and prefix if available
    if left_context.strip():
        params["left"] = left_context.strip().lower()
    if prefix.strip():
        params["prefix"] = prefix.strip().lower()

    # Make API request with retries
    api_data = None
    max_retries = get_config("api_max_retries", 2)
    for attempt in range(max_retries + 1):
        api_data = _make_api_request("word/predict", params)
        if api_data is not None:
            break
        elif attempt < max_retries:
            print(f"🔄 API retry {attempt + 1}/{max_retries}")
            time.sleep(0.5)  # Brief delay before retry

    if api_data is None:
        print("❌ API request failed after all retries")
        return []

    # Extract predictions from API response
    predictions = []
    results = api_data.get("results", [])

    for result in results:
        # API returns 'text' field, not 'word'
        word = result.get("text", result.get("word", "")).upper()
        if word and len(word) >= 2:  # Match existing system's minimum length
            predictions.append(word)

    # Cache the results
    with _api_cache_lock:
        _api_cache[cache_key] = (predictions, current_time)
        # Clean old cache entries (simple cleanup)
        if len(_api_cache) > 100:  # Limit cache size
            oldest_key = min(_api_cache.keys(), key=lambda k: _api_cache[k][1])
            del _api_cache[oldest_key]

    print(f"🎯 Online predictions for '{prefix}': {predictions}")
    return predictions


# ------------------------------ #
#      Result Merging & Scoring  #
# ------------------------------ #


def merge_predictions(offline_predictions, online_predictions, num_suggestions=6):
    """
    Merge offline and online predictions using the configured strategy.

    Args:
        offline_predictions (list): List of (word, score) tuples from offline system
        online_predictions (list): List of words from online API
        num_suggestions (int): Number of final suggestions to return

    Returns:
        list: Merged and ranked list of prediction words
    """
    merge_strategy = get_config("merge_strategy", "weighted")

    if merge_strategy == "api_first":
        return _merge_api_first(
            offline_predictions, online_predictions, num_suggestions
        )
    elif merge_strategy == "offline_first":
        return _merge_offline_first(
            offline_predictions, online_predictions, num_suggestions
        )
    else:  # weighted (default)
        return _merge_weighted(offline_predictions, online_predictions, num_suggestions)


def _merge_api_first(offline_predictions, online_predictions, num_suggestions):
    """Prioritize API predictions, fill remaining slots with offline predictions."""
    result = []

    # Add online predictions first
    for word in online_predictions:
        if word not in result:
            result.append(word)
            if len(result) >= num_suggestions:
                break

    # Fill remaining slots with offline predictions
    for word, _ in offline_predictions:
        if word not in result:
            result.append(word)
            if len(result) >= num_suggestions:
                break

    return result


def _merge_offline_first(offline_predictions, online_predictions, num_suggestions):
    """Prioritize offline predictions, fill remaining slots with API predictions."""
    result = []

    # Add offline predictions first
    for word, _ in offline_predictions:
        if word not in result:
            result.append(word)
            if len(result) >= num_suggestions:
                break

    # Fill remaining slots with online predictions
    for word in online_predictions:
        if word not in result:
            result.append(word)
            if len(result) >= num_suggestions:
                break

    return result


def _merge_weighted(offline_predictions, online_predictions, num_suggestions):
    """Merge predictions using weighted scoring."""
    api_weight = get_config("api_weight", 0.7)
    offline_weight = get_config("offline_weight", 0.3)

    # Create unified scoring
    unified_scores = {}

    # Add offline predictions with their scores
    max_offline_score = max([score for _, score in offline_predictions], default=1)
    for word, score in offline_predictions:
        # Normalize offline score to 0-1 range
        normalized_score = score / max_offline_score if max_offline_score > 0 else 0
        unified_scores[word] = normalized_score * offline_weight

    # Add online predictions with estimated scores
    # API returns results in probability order, so assign decreasing scores
    for i, word in enumerate(online_predictions):
        # Assign higher scores to earlier API results (they're sorted by probability)
        api_score = (
            (len(online_predictions) - i) / len(online_predictions)
            if online_predictions
            else 0
        )

        if word in unified_scores:
            # Combine scores if word appears in both sources
            unified_scores[word] += api_score * api_weight
        else:
            # New word from API
            unified_scores[word] = api_score * api_weight

    # Sort by unified score and return top predictions
    sorted_predictions = sorted(unified_scores.items(), key=lambda x: -x[1])
    return [word for word, _ in sorted_predictions[:num_suggestions]]


# Load data once when script starts
load_config()
load_json()
