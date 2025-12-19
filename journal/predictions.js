// Prediction system for journal keyboard - uses shared data with main keyboard
class HybridPredictionSystem {
  constructor() {
    this.baseData = { frequent_words: {}, bigrams: {}, trigrams: {} };
    this.userData = { frequent_words: {}, bigrams: {}, trigrams: {} };
    this.mergedData = { frequent_words: {}, bigrams: {}, trigrams: {} };
    this.dataLoaded = false;
    this.initializeData();
  }

  async initializeData() {
    this.loadUserData();
    await this.loadBaseData();
    this.mergeData();
    this.dataLoaded = true;
  }

  loadUserData() {
    try {
      const stored = localStorage.getItem('userKeyboardData');
      if (stored) {
        this.userData = JSON.parse(stored);
        console.log(`Loaded user data from localStorage: ${Object.keys(this.userData.frequent_words || {}).length} words`);
      }
    } catch (error) {
      console.error('Error loading user data from localStorage:', error);
      this.userData = { frequent_words: {}, bigrams: {}, trigrams: {} };
    }
  }

  async loadBaseData() {
    try {
      // Load from the same endpoint as new keyboard
      const response = await fetch('/web_keyboard_predictions.json');
      if (response.ok) {
        this.baseData = await response.json();
        console.log(`Loaded base data from server: ${Object.keys(this.baseData.frequent_words || {}).length} words`);
      } else {
        console.log('No base data available from server, using empty data');
        this.baseData = { frequent_words: {}, bigrams: {}, trigrams: {} };
      }
    } catch (error) {
      console.error('Error loading base data from server:', error);
      this.baseData = { frequent_words: {}, bigrams: {}, trigrams: {} };
    }
  }

  mergeData() {
    this.mergedData = {
      frequent_words: { ...this.baseData.frequent_words },
      bigrams: { ...this.baseData.bigrams },
      trigrams: { ...this.baseData.trigrams }
    };

    for (const [word, userData] of Object.entries(this.userData.frequent_words || {})) {
      if (this.mergedData.frequent_words[word]) {
        const baseCount = this.mergedData.frequent_words[word].count || 0;
        const userCount = (userData.count || 0) * 3;
        this.mergedData.frequent_words[word] = {
          count: baseCount + userCount,
          last_used: userData.last_used || this.mergedData.frequent_words[word].last_used,
          user_count: userData.count || 0
        };
      } else {
        this.mergedData.frequent_words[word] = {
          ...userData,
          count: (userData.count || 0) * 3,
          user_count: userData.count || 0
        };
      }
    }

    for (const [bigram, userData] of Object.entries(this.userData.bigrams || {})) {
      if (this.mergedData.bigrams[bigram]) {
        const baseCount = this.mergedData.bigrams[bigram].count || 0;
        const userCount = (userData.count || 0) * 3;
        this.mergedData.bigrams[bigram] = {
          count: baseCount + userCount,
          last_used: userData.last_used || this.mergedData.bigrams[bigram].last_used,
          user_count: userData.count || 0
        };
      } else {
        this.mergedData.bigrams[bigram] = {
          ...userData,
          count: (userData.count || 0) * 3,
          user_count: userData.count || 0
        };
      }
    }

    for (const [trigram, userData] of Object.entries(this.userData.trigrams || {})) {
      if (this.mergedData.trigrams[trigram]) {
        const baseCount = this.mergedData.trigrams[trigram].count || 0;
        const userCount = (userData.count || 0) * 3;
        this.mergedData.trigrams[trigram] = {
          count: baseCount + userCount,
          last_used: userData.last_used || this.mergedData.trigrams[trigram].last_used,
          user_count: userData.count || 0
        };
      } else {
        this.mergedData.trigrams[trigram] = {
          ...userData,
          count: (userData.count || 0) * 3,
          user_count: userData.count || 0
        };
      }
    }

    console.log(`Merged data: ${Object.keys(this.mergedData.frequent_words).length} words, ${Object.keys(this.mergedData.bigrams).length} bigrams, ${Object.keys(this.mergedData.trigrams).length} trigrams`);
  }

  calculateScore(data, isUserData = false) {
    const count = data.count || 0;
    const userCount = data.user_count || 0;
    const lastUsed = data.last_used ? new Date(data.last_used) : new Date(0);
    const daysSinceUse = (Date.now() - lastUsed.getTime()) / (1000 * 60 * 60 * 24);
    const recencyMultiplier = Math.max(0.5, 1 - (daysSinceUse / 365));
    const userMultiplier = userCount > 0 ? 100 : 1;
    return count * recencyMultiplier * userMultiplier;
  }

  async getHybridPredictions(buffer) {
    const hasTrailingSpace = buffer.replace('|', '').endsWith(' ');
    const cleaned = buffer.toUpperCase().replace('|', '').trim();
    const words = cleaned ? cleaned.split(' ') : [];

    const DEFAULT_WORDS = ["YES", "NO", "HELP", "THE", "I", "YOU"];

    if (!words.length) {
      return DEFAULT_WORDS;
    }

    let context = '';
    let currentWord = '';

    if (hasTrailingSpace) {
      context = cleaned;
      currentWord = '';
    } else {
      currentWord = words[words.length - 1];
      context = words.slice(0, -1).join(' ');
    }

    const existingWords = new Set(words.map(w => w.toUpperCase()));
    let finalPredictions = [];

    const shouldExcludeWord = (word) => {
      const upperWord = word.toUpperCase();
      if (hasTrailingSpace && existingWords.has(upperWord)) {
        return true;
      }
      return false;
    };

    // PRIORITY 1: Recently used words from userData (HIGHEST PRIORITY)
    if (currentWord && currentWord.length >= 1) {
      const userWordMatches = Object.entries(this.userData.frequent_words || {})
        .filter(([word]) => word.startsWith(currentWord) && word !== currentWord && !shouldExcludeWord(word))
        .map(([word, data]) => ({ word, score: 999999999 + (data.count || 0) * 1000000, isUser: true }))
        .sort((a, b) => b.score - a.score);

      for (const match of userWordMatches) {
        if (finalPredictions.length < 6 && !finalPredictions.some(p => p === match.word)) {
          finalPredictions.push(match.word);
        }
      }
    }

    // PRIORITY 2: N-gram predictions from merged data
    const predictionsNgram = {};

    if (context && (hasTrailingSpace || context !== currentWord)) {
      const ctxWords = context.split(' ');

      // Trigrams - highest priority
      if (ctxWords.length >= 2) {
        const triCtx = ctxWords.slice(-2).join(' ');
        for (const [key, data] of Object.entries(this.mergedData.trigrams || {})) {
          const trigramParts = key.split(' ');
          if (trigramParts.length === 3) {
            const trigramContext = trigramParts.slice(0, 2).join(' ');
            const nextWord = trigramParts[2];
            if (trigramContext === triCtx) {
              if ((!currentWord || nextWord.startsWith(currentWord)) && !shouldExcludeWord(nextWord)) {
                const score = this.calculateScore(data) * 10000000;
                predictionsNgram[nextWord] = (predictionsNgram[nextWord] || 0) + score;
              }
            }
          }
        }
      }

      // Also check if we have exactly 2 words and look for trigrams starting with those words
      if (ctxWords.length === 2 && hasTrailingSpace) {
        const exactContext = ctxWords.join(' ');
        for (const [key, data] of Object.entries(this.mergedData.trigrams || {})) {
          if (key.startsWith(exactContext + ' ')) {
            const nextWord = key.split(' ').pop();
            if (nextWord && !shouldExcludeWord(nextWord)) {
              const score = this.calculateScore(data) * 50000000;
              predictionsNgram[nextWord] = (predictionsNgram[nextWord] || 0) + score;
            }
          }
        }
      }

      // Bigrams - medium priority
      if (ctxWords.length >= 1) {
        const biCtx = ctxWords[ctxWords.length - 1];
        for (const [key, data] of Object.entries(this.mergedData.bigrams || {})) {
          if (key.startsWith(biCtx + ' ')) {
            const nextWord = key.split(' ').pop();
            if ((!currentWord || nextWord.startsWith(currentWord)) && !shouldExcludeWord(nextWord)) {
              const score = this.calculateScore(data) * 500000;
              predictionsNgram[nextWord] = (predictionsNgram[nextWord] || 0) + score;
            }
          }
        }
      }
    }

    const sortedNgrams = Object.entries(predictionsNgram)
      .sort((a, b) => b[1] - a[1])
      .map(([word]) => word);

    for (const word of sortedNgrams) {
      if (finalPredictions.length < 6 && !finalPredictions.includes(word)) {
        finalPredictions.push(word);
      }
    }

    // PRIORITY 3: Other frequent word completions (for partial words)
    if (currentWord && currentWord.length >= 1 && finalPredictions.length < 6) {
      const otherMatches = Object.entries(this.mergedData.frequent_words || {})
        .filter(([word]) => word.startsWith(currentWord) && word !== currentWord && !finalPredictions.includes(word) && !(word in (this.userData.frequent_words || {})) && !shouldExcludeWord(word))
        .map(([word, data]) => ({ word, score: this.calculateScore(data) }))
        .sort((a, b) => b.score - a.score);

      for (const match of otherMatches) {
        if (finalPredictions.length < 6) {
          finalPredictions.push(match.word);
        }
      }
    }

    // PRIORITY 4: Most frequent words (when after a space with no partial word)
    if (hasTrailingSpace && !currentWord && finalPredictions.length < 6) {
      const sortedWords = Object.entries(this.mergedData.frequent_words || {})
        .filter(([word]) => !finalPredictions.includes(word) && !shouldExcludeWord(word))
        .map(([word, data]) => ({ word, score: this.calculateScore(data) }))
        .sort((a, b) => b.score - a.score)
        .slice(0, 20 - finalPredictions.length);

      for (const match of sortedWords) {
        if (finalPredictions.length < 6) {
          finalPredictions.push(match.word);
        }
      }
    }

    // PRIORITY 5: Default words
    for (const word of DEFAULT_WORDS) {
      if (finalPredictions.length >= 6) break;
      if (!finalPredictions.includes(word) && !shouldExcludeWord(word)) {
        if (currentWord) {
          if (word.startsWith(currentWord)) {
            finalPredictions.push(word);
          }
        } else {
          finalPredictions.push(word);
        }
      }
    }

    while (finalPredictions.length < 6) {
      finalPredictions.push('');
    }

    return finalPredictions.slice(0, 6);
  }

  async recordLocalWord(word) {
    try {
      const cleanWord = word.replace(/[.,?!]/g, "");
      if (!cleanWord) return;

      const upperWord = cleanWord.toUpperCase();
      const timestamp = new Date().toISOString();

      if (!this.userData.frequent_words[upperWord]) {
        this.userData.frequent_words[upperWord] = { count: 0, last_used: timestamp };
      }
      this.userData.frequent_words[upperWord].count++;
      this.userData.frequent_words[upperWord].last_used = timestamp;

      this.saveUserData();
      await this.saveToServer(upperWord, timestamp);
      this.mergeData();
    } catch (error) {
      console.error('Error recording word:', error);
    }
  }

  async recordNgram(context, nextWord) {
    try {
      const cleanContext = context.replace(/[.,?!]/g, "");
      const cleanNextWord = nextWord.replace(/[.,?!]/g, "");
      
      if (!cleanNextWord) return;

      const ctxWords = cleanContext.toUpperCase().split(' ').filter(w => w);
      const nextUpper = cleanNextWord.toUpperCase();
      const timestamp = new Date().toISOString();

      if (ctxWords.length >= 1) {
        const bigramKey = `${ctxWords[ctxWords.length - 1]} ${nextUpper}`;
        if (!this.userData.bigrams[bigramKey]) {
          this.userData.bigrams[bigramKey] = { count: 0, last_used: timestamp };
        }
        this.userData.bigrams[bigramKey].count++;
        this.userData.bigrams[bigramKey].last_used = timestamp;
      }

      if (ctxWords.length >= 2) {
        const trigramKey = `${ctxWords.slice(-2).join(' ')} ${nextUpper}`;
        if (!this.userData.trigrams[trigramKey]) {
          this.userData.trigrams[trigramKey] = { count: 0, last_used: timestamp };
        }
        this.userData.trigrams[trigramKey].count++;
        this.userData.trigrams[trigramKey].last_used = timestamp;
      }

      this.saveUserData();
      await this.saveNgramToServer(cleanContext, cleanNextWord, timestamp);
      this.mergeData();
    } catch (error) {
      console.error('Error recording ngram:', error);
    }
  }

  async saveToServer(word, timestamp) {
    try {
      const response = await fetch('/api/save_prediction', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ word, timestamp })
      });
      if (!response.ok) {
        console.error('Failed to save word to server');
      }
    } catch (error) {
      console.error('Error saving to server:', error);
    }
  }

  async saveNgramToServer(context, nextWord, timestamp) {
    try {
      const response = await fetch('/api/save_ngram', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ context, next_word: nextWord, timestamp })
      });
      if (!response.ok) {
        console.error('Failed to save n-gram to server');
      }
    } catch (error) {
      console.error('Error saving n-gram to server:', error);
    }
  }

  saveUserData() {
    try {
      const THREE_MONTHS = 90 * 24 * 60 * 60 * 1000;
      const now = Date.now();
      
      for (const [word, data] of Object.entries(this.userData.frequent_words)) {
        if (data.last_used) {
          const lastUsed = new Date(data.last_used).getTime();
          if (now - lastUsed > THREE_MONTHS && (data.count || 0) < 3) {
            delete this.userData.frequent_words[word];
          }
        }
      }
      
      localStorage.setItem('userKeyboardData', JSON.stringify(this.userData));
    } catch (error) {
      console.error('Error saving user data:', error);
    }
  }

  clearUserData() {
    this.userData = { frequent_words: {}, bigrams: {}, trigrams: {} };
    localStorage.removeItem('userKeyboardData');
    this.mergeData();
  }
}

window.predictionSystem = new HybridPredictionSystem();
