// --- Configuration & Constants ---
function getApiBaseUrl() {
  if (typeof window !== 'undefined' && window.APP_CONFIG && window.APP_CONFIG.API_BASE_URL) {
    return window.APP_CONFIG.API_BASE_URL;
  }
  if (typeof window !== 'undefined' && (window.VITE_API_BASE_URL || window.API_BASE_URL)) {
    return window.VITE_API_BASE_URL || window.API_BASE_URL;
  }
  if (typeof window !== 'undefined' && window.location.origin && window.location.origin !== 'null') {
    // If running on a dedicated frontend dev server (e.g. port 8000), target backend port 5000:
    if (window.location.port && window.location.port === '8000') {
      return `${window.location.protocol}//${window.location.hostname}:5000/api`;
    }
    // In production or when served by Flask directly:
    return `${window.location.origin}/api`;
  }
  return 'http://127.0.0.1:5000/api';
}

const API_BASE_URL = getApiBaseUrl();

const API_ENDPOINTS = {
  health: `${API_BASE_URL}/health`,
  destinations: `${API_BASE_URL}/destinations`,
  voices: `${API_BASE_URL}/voices`,
  generateAudioGuide: `${API_BASE_URL}/generate-audio-guide`,
};

const VOICES = {
  English: { Male: "Matthew", Female: "Alicia" },
  Hindi: { Male: "Aman", Female: "Namrita" },
  Tamil: { Male: "Murali", Female: "Abirami" }, // Abirami is verified compatible on Murf falcon-2
  Telugu: { Male: "Zion", Female: "Josie" }
};

const LOCALES = {
  English: "en-US",
  Hindi: "hi-IN",
  Tamil: "ta-IN",
  Telugu: "te-IN"
};

// --- State ---
const state = {
  place: '',
  image: '',
  length: 'Summary',
  voice: 'Male'
};

// --- DOM Elements ---
const cardsContainer = document.querySelector('.cards');
const experiencePanel = document.getElementById('experience');
const previewTitle = document.getElementById('previewTitle');
const audioSection = document.getElementById('audioSection');
const audioPlayer = document.getElementById('audioPlayer');
const transcriptText = document.getElementById('scriptText');
const generateButton = document.getElementById('generateBtn');
const generateStatus = document.getElementById('generateStatus');
const languageSelect = document.getElementById('selectLanguage');
const closeButton = document.getElementById('closeExperience');
const searchPreviewCard = document.getElementById('searchPreviewCard');
const searchPreviewImage = document.getElementById('searchPreviewImage');
const searchPreviewTitle = document.getElementById('searchPreviewTitle');
const transcriptToggle = document.getElementById('transcriptToggle');
const transcriptContent = document.getElementById('transcriptContent');
const transcriptArrow = document.getElementById('transcriptArrow');
const searchInput = document.getElementById('searchInput');
const searchButton = document.getElementById('searchBtn');

// --- Helper Functions ---
function setStatus(message, type = 'error') {
  if (!generateStatus) return;
  if (!message) {
    generateStatus.textContent = '';
    generateStatus.className = 'hidden';
    return;
  }

  generateStatus.classList.remove('hidden');
  if (type === 'loading') {
    generateStatus.className = 'mt-3 text-sm text-amber-700 font-medium flex items-center gap-2';
    generateStatus.innerHTML = '<span class="inline-block animate-spin">⏳</span> ' + message;
  } else if (type === 'success') {
    generateStatus.className = 'mt-3 text-sm text-emerald-600 font-medium flex items-center gap-1.5';
    generateStatus.innerHTML = '<span>✓</span> ' + message;
  } else if (type === 'info') {
    generateStatus.className = 'mt-3 text-sm text-blue-600 font-medium';
    generateStatus.textContent = message;
  } else {
    // error
    generateStatus.className = 'mt-3 text-sm text-rose-600 font-medium';
    generateStatus.textContent = message;
  }
}

// --- Destination Selection ---
function selectDestination(place, image, clickedCard = null) {
  state.place = place;
  state.image = image;

  // Update UI content
  previewTitle.textContent = place;
  cardsContainer.classList.add('faded');

  // Reset previous active states
  document.querySelectorAll('.place-card').forEach(card => card.classList.remove('active'));
  searchPreviewCard.classList.add('hidden');

  // Handle Card Visibility
  if (clickedCard) {
    clickedCard.classList.add('active');
  } else {
    // If it's a search result, show the preview card
    searchPreviewImage.src = image;
    searchPreviewTitle.textContent = place;
    searchPreviewCard.classList.remove('hidden');
    searchPreviewCard.classList.add('active');
  }

  // Reset Audio Panel
  audioSection.classList.add('hidden');
  audioPlayer.removeAttribute('src');
  audioPlayer.load();
  transcriptText.textContent = '';
  setStatus('');
  generateButton.textContent = 'Generate Audio Guide';
  generateButton.disabled = false;

  // Show Panel with animation
  experiencePanel.classList.remove('hidden');
  setTimeout(() => {
    experiencePanel.classList.add('visible');
  }, 10);
}

function deselectDestination() {
  experiencePanel.classList.remove('visible');

  // Wait for animation to finish before hiding
  setTimeout(() => {
    experiencePanel.classList.add('hidden');
    cardsContainer.classList.remove('faded');
    searchPreviewCard.classList.add('hidden');
    document.querySelectorAll('.place-card').forEach(card => card.classList.remove('active'));
  }, 300);
}

// --- Search Destination ---
async function searchFeaturedDestinations() {
  const query = searchInput.value.trim();
  if (!query) {
    searchInput.setCustomValidity('Enter a destination name.');
    searchInput.reportValidity();
    return;
  }

  const queryLower = query.toLowerCase();
  const featuredCards = [...document.querySelectorAll('.place-card:not(.search-preview-card)')];
  const localMatch = featuredCards.find(card => card.dataset.place.toLowerCase() === queryLower)
    || featuredCards.find(card => card.dataset.place.toLowerCase().includes(queryLower));

  if (localMatch) {
    searchInput.setCustomValidity('');
    selectDestination(localMatch.dataset.place, localMatch.dataset.image, localMatch);
    return;
  }

  // If not found in static DOM cards, query the backend destination search API
  try {
    const res = await fetch(`${API_ENDPOINTS.destinations}?q=${encodeURIComponent(query)}`);
    if (res.ok) {
      const data = await res.json();
      if (Array.isArray(data.destinations) && data.destinations.length > 0) {
        const found = data.destinations[0];
        // Check if matching card already exists
        const cardMatch = featuredCards.find(c => c.dataset.place.toLowerCase() === found.place.toLowerCase());
        if (cardMatch) {
          searchInput.setCustomValidity('');
          selectDestination(cardMatch.dataset.place, cardMatch.dataset.image, cardMatch);
          return;
        }
        searchInput.setCustomValidity('');
        selectDestination(found.place, found.image, null);
        return;
      }
    }
  } catch (err) {
    console.warn('Backend search unavailable, proceeding with custom destination query:', err);
  }

  // Allow custom destination for AI travel guide generation
  searchInput.setCustomValidity('');
  const formattedPlace = query.replace(/\b\w/g, char => char.toUpperCase());
  const fallbackImage = 'https://images.unsplash.com/photo-1488646953014-85cb44e25828?auto=format&fit=crop&w=800&q=80';
  selectDestination(formattedPlace, fallbackImage, null);
}

// --- Event Listeners ---

// Close Button & Brand Home Navigation
closeButton.addEventListener('click', deselectDestination);
const appLogo = document.getElementById('appLogo');
if (appLogo) {
  appLogo.addEventListener('click', deselectDestination);
}

// Search Listeners
searchButton.addEventListener('click', searchFeaturedDestinations);
searchInput.addEventListener('keydown', event => {
  if (event.key === 'Enter') searchFeaturedDestinations();
});
searchInput.addEventListener('input', () => searchInput.setCustomValidity(''));

// Card Clicks
function attachCardListeners() {
  document.querySelectorAll('.place-card:not(.search-preview-card)').forEach(card => {
    card.addEventListener('click', () => {
      selectDestination(card.dataset.place, card.dataset.image, card);
    });
  });

  if (searchPreviewCard) {
    searchPreviewCard.addEventListener('click', () => {
      if (state.place) {
        selectDestination(state.place, state.image, searchPreviewCard);
      }
    });
  }
}
attachCardListeners();

// Option Toggles (Guide Length)
const lengthButtons = document.querySelectorAll('[data-group="length"] button');
lengthButtons.forEach(btn => {
  btn.addEventListener('click', () => {
    lengthButtons.forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    state.length = btn.dataset.value;
  });
});

// Option Toggles (Voice Gender)
const voiceButtons = document.querySelectorAll('[data-group="voice"] button');
voiceButtons.forEach(btn => {
  btn.addEventListener('click', () => {
    voiceButtons.forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    state.voice = btn.dataset.value;
  });
});

// --- Generate Audio Guide Logic ---
generateButton.addEventListener('click', async () => {
  generateButton.disabled = true;
  generateButton.textContent = 'Generating Audio...';
  setStatus('Connecting to AI travel engine... Generating audio guide.', 'loading');

  try {
    const selectedLanguage = languageSelect.value;
    const selectedVoice = state.voice;
    const voiceId = VOICES[selectedLanguage]?.[selectedVoice];
    const locale = LOCALES[selectedLanguage];

    if (!state.place) {
      throw new Error('Please select or search for a destination first.');
    }
    if (!voiceId || !locale) {
      throw new Error('Selected language or voice is not supported.');
    }

    const response = await fetch(API_ENDPOINTS.generateAudioGuide, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        place: state.place,
        answerType: state.length,
        language: selectedLanguage,
        voiceId,
        locale
      })
    });

    let data;
    try {
      data = await response.json();
    } catch {
      throw new Error('The server returned an unreadable response format. Please try again.');
    }

    if (!response.ok) {
      throw new Error(data.error || `Server responded with status ${response.status}.`);
    }

    if (typeof data.description !== 'string' || !data.description.trim()) {
      throw new Error('The server returned an empty travel guide. Please try again.');
    }

    // Update UI with Result
    transcriptText.textContent = data.description;
    audioSection.classList.remove('hidden');

    if (typeof data.audioBase64 === 'string' && data.audioBase64.length > 0) {
      const mimeType = data.audioMimeType || 'audio/mpeg';
      audioPlayer.src = `data:${mimeType};base64,${data.audioBase64}`;
      audioPlayer.load();
      audioPlayer.classList.remove('hidden');
      setStatus('Audio guide generated successfully! Press play to listen.', 'success');
    } else {
      audioPlayer.removeAttribute('src');
      audioPlayer.load();
      audioPlayer.classList.add('hidden');
      setStatus('Guide text is ready, but audio could not be synthesized.', 'info');
    }
  } catch (err) {
    console.error('Error generating audio guide:', err);
    let errorMessage = err instanceof Error ? err.message : 'The guide could not be generated.';
    if (err.name === 'TypeError' || err.message.includes('fetch') || err.message.includes('Failed to fetch')) {
      errorMessage = `Cannot connect to backend server at ${API_BASE_URL}. Ensure the Flask backend is running.`;
    }
    setStatus(errorMessage, 'error');
  } finally {
    generateButton.textContent = 'Generate Audio Guide';
    generateButton.disabled = false;
  }
});

// Audio playback error handler
audioPlayer.addEventListener('error', () => {
  if (!audioPlayer.currentSrc) return;
  setStatus('The guide was generated, but the browser could not play this audio format.', 'error');
});

// Transcript Toggle
transcriptToggle.addEventListener('click', () => {
  transcriptContent.classList.toggle('hidden');
  transcriptArrow.classList.toggle('rotate-180');
});

// --- Startup Health Check ---
async function checkBackendHealth() {
  try {
    const res = await fetch(API_ENDPOINTS.health);
    if (res.ok) {
      const data = await res.json();
      console.log('✓ Travel Guide Backend connected successfully:', data);
    } else {
      console.warn('Backend health check returned non-200 status:', res.status);
    }
  } catch (err) {
    console.warn(`Backend health check failed (${API_ENDPOINTS.health}). Make sure Flask is running:`, err.message);
  }
}
checkBackendHealth();
