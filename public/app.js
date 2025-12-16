/**
 * Apple Music Login - Frontend JavaScript
 * Handles MusicKit JS authentication and profile syncing
 */

// Global state
let musicKit = null;
let currentUser = null;
let developerToken = null;
let isFromExistingUsers = false; // Track if user selected from existing users

// DOM Elements
const elements = {
  // Choice section elements
  choiceSection: document.getElementById('choice-section'),
  choiceButtons: document.getElementById('choice-buttons'),
  newLoginBtn: document.getElementById('new-login-btn'),
  existingUsersBtn: document.getElementById('existing-users-btn'),
  loadingText: document.getElementById('loading-text'),
  
  // Existing users section
  existingUsersSection: document.getElementById('existing-users-section'),
  usersList: document.getElementById('users-list'),
  noUsersMessage: document.getElementById('no-users-message'),
  backToChoiceBtn: document.getElementById('back-to-choice-btn'),
  
  // Auth section elements
  authSection: document.getElementById('auth-section'),
  loginBtn: document.getElementById('login-btn'),
  musickitLoadingText: document.getElementById('musickit-loading-text'),
  backFromLoginBtn: document.getElementById('back-from-login-btn'),
  
  // Full name section elements
  fullnameSection: document.getElementById('fullname-section'),
  fullnameInput: document.getElementById('fullname-input'),
  submitFullnameBtn: document.getElementById('submit-fullname-btn'),
  
  // User section elements
  userSection: document.getElementById('user-section'),
  userName: document.getElementById('user-name'),
  userStorefront: document.getElementById('user-storefront'),
  syncBtn: document.getElementById('sync-btn'),
  logoutBtn: document.getElementById('logout-btn'),
  backToUsersBtn: document.getElementById('back-to-users-btn'),
  syncStatus: document.getElementById('sync-status'),
  statusText: document.getElementById('status-text'),
  profileResult: document.getElementById('profile-result'),
  profileGenres: document.getElementById('profile-genres'),
  profileSongs: document.getElementById('profile-songs'),
  errorSection: document.getElementById('error-section'),
  errorText: document.getElementById('error-text'),
  
  // Similarity elements
  similaritySection: document.getElementById('similarity-section'),
  findSimilarBtn: document.getElementById('find-similar-btn'),
  similarityLoading: document.getElementById('similarity-loading'),
  similarityResults: document.getElementById('similarity-results'),
  similarUsersList: document.getElementById('similar-users-list'),
  noSimilarUsers: document.getElementById('no-similar-users'),
  comparisonModal: document.getElementById('comparison-modal'),
  comparisonResult: document.getElementById('comparison-result'),
  closeModal: document.querySelector('.close-modal')
};

// API Base URL
const API_BASE = window.location.origin;

/**
 * Initialize the application
 */
async function init() {
  try {
    // Fetch developer token from server
    const response = await fetch(`${API_BASE}/api/auth/developer-token`);
    const data = await response.json();
    
    if (!data.success || !data.developerToken) {
      throw new Error('Failed to get developer token');
    }
    
    developerToken = data.developerToken;
    
    // Hide loading, show choice buttons
    elements.loadingText.style.display = 'none';
    elements.choiceButtons.style.display = 'block';
    
    // Setup event listeners for choice buttons
    setupChoiceEventListeners();
    
  } catch (error) {
    console.error('Initialization error:', error);
    showError('Failed to initialize. Please refresh the page.');
  }
}

/**
 * Setup choice section event listeners
 */
function setupChoiceEventListeners() {
  elements.newLoginBtn.addEventListener('click', showLoginSection);
  elements.existingUsersBtn.addEventListener('click', showExistingUsersSection);
  elements.backToChoiceBtn.addEventListener('click', showChoiceSection);
  elements.backFromLoginBtn.addEventListener('click', showChoiceSection);
  elements.backToUsersBtn.addEventListener('click', showExistingUsersSection);
}

/**
 * Show choice section (initial view)
 */
function showChoiceSection() {
  elements.choiceSection.style.display = 'block';
  elements.choiceButtons.style.display = 'block';
  elements.existingUsersSection.style.display = 'none';
  elements.authSection.style.display = 'none';
  elements.userSection.style.display = 'none';
  elements.errorSection.style.display = 'none';
}

/**
 * Show login section for new Apple Music login
 */
async function showLoginSection() {
  elements.choiceSection.style.display = 'none';
  elements.existingUsersSection.style.display = 'none';
  elements.authSection.style.display = 'block';
  elements.userSection.style.display = 'none';
  isFromExistingUsers = false;
  
  // Initialize MusicKit if not already
  await initializeMusicKit();
}

/**
 * Initialize MusicKit JS
 */
async function initializeMusicKit() {
  try {
    elements.musickitLoadingText.style.display = 'block';
    elements.loginBtn.disabled = true;
    
    // Wait for MusicKit to be ready
    await waitForMusicKit();
    
    // Configure MusicKit
    await MusicKit.configure({
      developerToken: developerToken,
      app: {
        name: 'Apple Music Profile Sync',
        build: '1.0.0'
      }
    });
    
    musicKit = MusicKit.getInstance();
    
    // Check if user is already authorized
    if (musicKit.isAuthorized) {
      await handleAuthorizedUser();
      return;
    }
    
    // Enable login button
    elements.loginBtn.disabled = false;
    elements.musickitLoadingText.style.display = 'none';
    
    // Setup MusicKit event listeners
    setupMusicKitEventListeners();
    
  } catch (error) {
    console.error('MusicKit initialization error:', error);
    elements.musickitLoadingText.textContent = 'Failed to load MusicKit';
    showError('Failed to initialize MusicKit. Please refresh the page.');
  }
}

/**
 * Setup MusicKit event listeners
 */
function setupMusicKitEventListeners() {
  elements.loginBtn.addEventListener('click', handleLogin);
  elements.syncBtn.addEventListener('click', handleSync);
  elements.logoutBtn.addEventListener('click', handleLogout);
  elements.findSimilarBtn.addEventListener('click', handleFindSimilar);
  elements.closeModal.addEventListener('click', closeComparisonModal);
  
  // Close modal when clicking outside
  window.addEventListener('click', (e) => {
    if (e.target === elements.comparisonModal) {
      closeComparisonModal();
    }
  });
}

/**
 * Show existing users section
 */
async function showExistingUsersSection() {
  elements.choiceSection.style.display = 'none';
  elements.authSection.style.display = 'none';
  elements.userSection.style.display = 'none';
  elements.existingUsersSection.style.display = 'block';
  
  // Fetch and display existing users
  await loadExistingUsers();
}

/**
 * Load existing users from database
 */
async function loadExistingUsers() {
  try {
    elements.usersList.innerHTML = '<p class="loading">Loading users...</p>';
    elements.noUsersMessage.style.display = 'none';
    
    const response = await fetch(`${API_BASE}/api/users`);
    const data = await response.json();
    
    if (!data.success) {
      throw new Error(data.error || 'Failed to load users');
    }
    
    if (!data.users || data.users.length === 0) {
      elements.usersList.innerHTML = '';
      elements.noUsersMessage.style.display = 'block';
      return;
    }
    
    displayExistingUsers(data.users);
    
  } catch (error) {
    console.error('Error loading users:', error);
    elements.usersList.innerHTML = '';
    showError('Failed to load users. Please try again.');
  }
}

/**
 * Display existing users in the list
 */
function displayExistingUsers(users) {
  elements.usersList.innerHTML = '';
  
  users.forEach(user => {
    const userCard = document.createElement('div');
    userCard.className = 'existing-user-card';
    
    const lastLogin = user.lastLogin ? new Date(user.lastLogin).toLocaleDateString() : 'Never';
    
    userCard.innerHTML = `
      <div class="user-card-content">
        <div class="user-avatar">👤</div>
        <div class="user-card-info">
          <h4>${user.displayName || 'User_' + (user.appleMusicUserId || '').slice(-6)}</h4>
          <p class="user-meta">
            <span>🌍 ${(user.storefront || 'us').toUpperCase()}</span>
            <span>📅 Last: ${lastLogin}</span>
          </p>
        </div>
      </div>
      <button class="btn btn-small btn-primary select-user-btn" data-user-id="${user.appleMusicUserId}">
        Select
      </button>
    `;
    
    // Add click event for select button
    const selectBtn = userCard.querySelector('.select-user-btn');
    selectBtn.addEventListener('click', () => selectExistingUser(user));
    
    elements.usersList.appendChild(userCard);
  });
}

/**
 * Select an existing user and show their profile
 */
async function selectExistingUser(user) {
  try {
    console.log('Selecting user:', user.appleMusicUserId);
    
    // Set current user
    currentUser = {
      userId: user.appleMusicUserId,
      displayName: user.displayName || `User_${user.appleMusicUserId.slice(-6)}`,
      storefront: user.storefront || 'us'
    };
    
    isFromExistingUsers = true;
    
    // Show user section
    showUserSectionFromExisting();
    
    // Setup event listeners if not already done
    setupUserSectionEventListeners();
    
    // Auto-sync to get latest data
    await handleSyncForExistingUser();
    
  } catch (error) {
    console.error('Error selecting user:', error);
    showError('Failed to select user. Please try again.');
  }
}

/**
 * Setup user section event listeners (for existing user flow)
 */
function setupUserSectionEventListeners() {
  // Remove existing listeners to avoid duplicates
  elements.syncBtn.replaceWith(elements.syncBtn.cloneNode(true));
  elements.logoutBtn.replaceWith(elements.logoutBtn.cloneNode(true));
  elements.findSimilarBtn.replaceWith(elements.findSimilarBtn.cloneNode(true));
  elements.closeModal.replaceWith(elements.closeModal.cloneNode(true));
  
  // Re-get elements after cloning
  const syncBtn = document.getElementById('sync-btn');
  const logoutBtn = document.getElementById('logout-btn');
  const findSimilarBtn = document.getElementById('find-similar-btn');
  const closeModal = document.querySelector('.close-modal');
  
  // Update references
  elements.syncBtn = syncBtn;
  elements.logoutBtn = logoutBtn;
  elements.findSimilarBtn = findSimilarBtn;
  elements.closeModal = closeModal;
  
  // Add listeners
  elements.syncBtn.addEventListener('click', handleSyncForExistingUser);
  elements.logoutBtn.addEventListener('click', handleLogoutExistingUser);
  elements.findSimilarBtn.addEventListener('click', handleFindSimilar);
  elements.closeModal.addEventListener('click', closeComparisonModal);
  
  // Close modal when clicking outside
  window.addEventListener('click', (e) => {
    if (e.target === elements.comparisonModal) {
      closeComparisonModal();
    }
  });
}

/**
 * Show user section when selecting from existing users
 */
function showUserSectionFromExisting() {
  elements.existingUsersSection.style.display = 'none';
  elements.choiceSection.style.display = 'none';
  elements.authSection.style.display = 'none';
  elements.userSection.style.display = 'block';
  elements.errorSection.style.display = 'none';
  elements.similaritySection.style.display = 'none';
  
  // Show back to users button
  elements.backToUsersBtn.style.display = 'inline-flex';
  
  elements.userName.textContent = currentUser.displayName || 'Apple Music User';
  elements.userStorefront.textContent = `Storefront: ${(currentUser.storefront || 'US').toUpperCase()}`;
  
  // Change logout button text
  elements.logoutBtn.innerHTML = '<span class="btn-icon">🔄</span> Switch User';
}

/**
 * Handle sync for existing user (using saved token from DB)
 */
async function handleSyncForExistingUser() {
  try {
    elements.syncBtn.disabled = true;
    elements.syncStatus.style.display = 'block';
    elements.profileResult.style.display = 'none';
    elements.statusText.textContent = 'Syncing your listening profile...';
    document.querySelector('.status-icon').textContent = '⏳';
    document.querySelector('.status-icon').classList.remove('success');
    
    const response = await fetch(`${API_BASE}/api/sync/${currentUser.userId}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        storefront: currentUser.storefront || 'us'
      })
    });
    
    const data = await response.json();
    
    if (!response.ok) {
      // Check if it's a token expiry issue
      if (response.status === 401) {
        throw new Error('Token expired. Please use "New Login" to refresh your token.');
      }
      throw new Error(data.detail || data.error || 'Sync failed');
    }
    
    if (!data.success) {
      throw new Error(data.error || 'Sync failed');
    }
    
    // Show success
    document.querySelector('.status-icon').textContent = '✅';
    document.querySelector('.status-icon').classList.add('success');
    elements.statusText.textContent = 'Profile synced successfully!';
    
    // Show results
    elements.profileResult.style.display = 'block';
    
    // Show similarity section but keep results hidden until button clicked
    elements.similaritySection.style.display = 'block';
    elements.similarityResults.style.display = 'none';
    elements.noSimilarUsers.style.display = 'none';
    
    // Display genres
    elements.profileGenres.innerHTML = '';
    (data.topGenres || []).forEach(genre => {
      const tag = document.createElement('span');
      tag.className = 'genre-tag';
      tag.textContent = genre;
      elements.profileGenres.appendChild(tag);
    });
    
    elements.profileSongs.textContent = `Processed ${data.songsProcessed || 0} songs`;
    
  } catch (error) {
    console.error('Sync error:', error);
    document.querySelector('.status-icon').textContent = '❌';
    elements.statusText.textContent = error.message || 'Sync failed. Token may have expired.';
    
    // Show a re-login option if token expired
    if (error.message && error.message.includes('Token expired')) {
      showTokenExpiredMessage();
    }
  } finally {
    elements.syncBtn.disabled = false;
  }
}

/**
 * Show token expired message with re-login option
 */
function showTokenExpiredMessage() {
  const statusCard = document.querySelector('.status-card');
  if (statusCard) {
    const reloginBtn = document.createElement('button');
    reloginBtn.className = 'btn btn-small btn-primary';
    reloginBtn.style.marginTop = '12px';
    reloginBtn.innerHTML = '<span class="btn-icon">🔄</span> Re-login with Apple Music';
    reloginBtn.onclick = async () => {
      // Go to login section
      currentUser = null;
      showLoginSection();
    };
    
    // Remove existing re-login button if any
    const existingBtn = statusCard.querySelector('.btn-primary');
    if (existingBtn) existingBtn.remove();
    
    statusCard.appendChild(reloginBtn);
  }
}

/**
 * Handle logout for existing user (go back to users list)
 */
function handleLogoutExistingUser() {
  currentUser = null;
  isFromExistingUsers = false;
  
  // Reset UI
  elements.userSection.style.display = 'none';
  elements.syncStatus.style.display = 'none';
  elements.profileResult.style.display = 'none';
  elements.similaritySection.style.display = 'none';
  elements.backToUsersBtn.style.display = 'none';
  
  // Show existing users section
  showExistingUsersSection();
}

/**
 * Wait for MusicKit JS to load
 */
function waitForMusicKit() {
  return new Promise((resolve) => {
    if (window.MusicKit) {
      resolve();
    } else {
      document.addEventListener('musickitloaded', resolve);
    }
  });
}

/**
 * Handle login button click
 */
async function handleLogin() {
  try {
    elements.loginBtn.disabled = true;
    elements.loginBtn.innerHTML = '<span class="btn-icon">⏳</span> Signing in...';
    
    // Authorize with Apple Music
    const userToken = await musicKit.authorize();
    
    if (!userToken) {
      throw new Error('Authorization failed');
    }
    
    // Send user token to server
    const response = await fetch(`${API_BASE}/api/auth/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        userToken: userToken,
        storefront: musicKit.storefrontId || 'us'
      })
    });
    
    const data = await response.json();
    
    if (!data.success) {
      throw new Error(data.error || 'Login failed');
    }
    
    currentUser = data.user;
    isFromExistingUsers = false;
    
    // Check if it's a new user
    if (data.user.isNewUser) {
      // Show fullname input section for new users
      showFullnameSection(userToken);
    } else {
      // Show user section for existing users
      showUserSection();
      
      // Setup event listeners for new login
      setupMusicKitEventListeners();
    }
    
  } catch (error) {
    console.error('Login error:', error);
    showError('Login failed. Please try again.');
    elements.loginBtn.disabled = false;
    elements.loginBtn.innerHTML = '<span class="btn-icon">🎵</span> Sign in with Apple Music';
  }
}

/**
 * Handle already authorized user
 */
async function handleAuthorizedUser() {
  try {
    const userToken = musicKit.musicUserToken;
    
    if (!userToken) return;
    
    // Verify with server
    const response = await fetch(`${API_BASE}/api/auth/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        userToken: userToken,
        storefront: musicKit.storefrontId || 'us'
      })
    });
    
    const data = await response.json();
    
    if (data.success) {
      currentUser = data.user;
      isFromExistingUsers = false;
      showUserSection();
      setupMusicKitEventListeners();
    }
  } catch (error) {
    console.error('Auto-login error:', error);
  }
}

/**
 * Show fullname section for new users
 */
function showFullnameSection(userToken) {
  elements.choiceSection.style.display = 'none';
  elements.authSection.style.display = 'none';
  elements.existingUsersSection.style.display = 'none';
  elements.userSection.style.display = 'none';
  elements.fullnameSection.style.display = 'block';
  elements.errorSection.style.display = 'none';
  
  // Clear any previous input
  elements.fullnameInput.value = '';
  elements.fullnameInput.focus();
  
  // Setup submit handler
  const submitHandler = async () => {
    await handleFullnameSubmit(userToken);
  };
  
  // Remove old listeners and add new one
  elements.submitFullnameBtn.replaceWith(elements.submitFullnameBtn.cloneNode(true));
  elements.submitFullnameBtn = document.getElementById('submit-fullname-btn');
  elements.submitFullnameBtn.addEventListener('click', submitHandler);
  
  // Also submit on Enter key
  elements.fullnameInput.removeEventListener('keypress', handleFullnameEnter);
  elements.fullnameInput.addEventListener('keypress', handleFullnameEnter);
}

/**
 * Handle Enter key in fullname input
 */
function handleFullnameEnter(e) {
  if (e.key === 'Enter') {
    elements.submitFullnameBtn.click();
  }
}

/**
 * Handle fullname submission
 */
async function handleFullnameSubmit(userToken) {
  const fullName = elements.fullnameInput.value.trim();
  
  if (!fullName || fullName.length < 2) {
    showError('Please enter a valid name (at least 2 characters)');
    return;
  }
  
  try {
    elements.submitFullnameBtn.disabled = true;
    elements.submitFullnameBtn.innerHTML = '<span class="btn-icon">⏳</span> Saving...';
    
    // Update user with full name
    const response = await fetch(`${API_BASE}/api/users/${currentUser.userId}/update-name`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        displayName: fullName
      })
    });
    
    const data = await response.json();
    
    if (!data.success) {
      throw new Error(data.error || 'Failed to save name');
    }
    
    // Update current user with the new name
    currentUser.displayName = fullName;
    
    // Show user section
    elements.fullnameSection.style.display = 'none';
    showUserSection();
    
    // Setup event listeners
    setupMusicKitEventListeners();
    
  } catch (error) {
    console.error('Error saving fullname:', error);
    showError('Failed to save name. Please try again.');
    elements.submitFullnameBtn.disabled = false;
    elements.submitFullnameBtn.innerHTML = '<span class="btn-icon">✓</span> Continue';
  }
}

/**
 * Show user section after login
 */
function showUserSection() {
  elements.choiceSection.style.display = 'none';
  elements.authSection.style.display = 'none';
  elements.existingUsersSection.style.display = 'none';
  elements.fullnameSection.style.display = 'none';
  elements.userSection.style.display = 'block';
  elements.errorSection.style.display = 'none';
  elements.similaritySection.style.display = 'none';
  
  // Hide back to users button for new login
  elements.backToUsersBtn.style.display = 'none';
  
  elements.userName.textContent = currentUser.displayName || 'Apple Music User';
  elements.userStorefront.textContent = `Storefront: ${(currentUser.storefront || 'US').toUpperCase()}`;
  
  // Reset logout button text
  elements.logoutBtn.innerHTML = '<span class="btn-icon">🚪</span> Sign Out';
}

/**
 * Handle sync button click
 */
async function handleSync() {
  try {
    elements.syncBtn.disabled = true;
    elements.syncStatus.style.display = 'block';
    elements.profileResult.style.display = 'none';
    elements.statusText.textContent = 'Syncing your listening profile...';
    document.querySelector('.status-icon').textContent = '⏳';
    document.querySelector('.status-icon').classList.remove('success');
    
    const response = await fetch(`${API_BASE}/api/sync/${currentUser.userId}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        storefront: currentUser.storefront || 'us'
      })
    });
    
    const data = await response.json();
    
    if (!data.success) {
      throw new Error(data.error || 'Sync failed');
    }
    
    // Show success
    document.querySelector('.status-icon').textContent = '✅';
    document.querySelector('.status-icon').classList.add('success');
    elements.statusText.textContent = 'Profile synced successfully!';
    
    // Show results
    elements.profileResult.style.display = 'block';
    
    // Show similarity section but keep results hidden until button clicked
    elements.similaritySection.style.display = 'block';
    elements.similarityResults.style.display = 'none';
    elements.noSimilarUsers.style.display = 'none';
    
    // Display genres
    elements.profileGenres.innerHTML = '';
    (data.topGenres || []).forEach(genre => {
      const tag = document.createElement('span');
      tag.className = 'genre-tag';
      tag.textContent = genre;
      elements.profileGenres.appendChild(tag);
    });
    
    elements.profileSongs.textContent = `Processed ${data.songsProcessed || 0} songs`;
    
  } catch (error) {
    console.error('Sync error:', error);
    document.querySelector('.status-icon').textContent = '❌';
    document.querySelector('.status-icon').classList.add('success');
    elements.statusText.textContent = 'Sync failed. Please try again.';
  } finally {
    elements.syncBtn.disabled = false;
  }
}

/**
 * Handle logout
 */
async function handleLogout() {
  try {
    if (musicKit) {
      await musicKit.unauthorize();
    }
    
    currentUser = null;
    isFromExistingUsers = false;
    
    // Reset UI
    elements.userSection.style.display = 'none';
    elements.syncStatus.style.display = 'none';
    elements.profileResult.style.display = 'none';
    elements.similaritySection.style.display = 'none';
    elements.backToUsersBtn.style.display = 'none';
    elements.loginBtn.disabled = false;
    elements.loginBtn.innerHTML = '<span class="btn-icon">🎵</span> Sign in with Apple Music';
    
    // Go back to choice section
    showChoiceSection();
    
  } catch (error) {
    console.error('Logout error:', error);
  }
}

/**
 * Show error message
 */
function showError(message) {
  elements.errorSection.style.display = 'block';
  elements.errorText.textContent = message;
  
  // Auto-hide after 5 seconds
  setTimeout(() => {
    elements.errorSection.style.display = 'none';
  }, 5000);
}

/**
 * Handle find similar users button click
 */
async function handleFindSimilar() {
  try {
    elements.findSimilarBtn.disabled = true;
    elements.similarityLoading.style.display = 'block';
    elements.similarityResults.style.display = 'none';
    elements.noSimilarUsers.style.display = 'none';
    
    console.log(`🔍 Finding similar users for: ${currentUser.userId}`);
    
    const response = await fetch(`${API_BASE}/api/users/${currentUser.userId}/similar`);
    const data = await response.json();
    
    if (!data.success) {
      throw new Error(data.error || 'Failed to find similar users');
    }
    
    elements.similarityLoading.style.display = 'none';
    
    if (data.similarUsers && data.similarUsers.length > 0) {
      displaySimilarUsers(data.similarUsers);
      elements.similarityResults.style.display = 'block';
    } else {
      elements.noSimilarUsers.style.display = 'block';
    }
    
  } catch (error) {
    console.error('Error finding similar users:', error);
    elements.similarityLoading.style.display = 'none';
    showError('Failed to find similar users. Please try again.');
  } finally {
    elements.findSimilarBtn.disabled = false;
  }
}

/**
 * Display similar users in the UI
 */
function displaySimilarUsers(similarUsers) {
  elements.similarUsersList.innerHTML = '';
  
  similarUsers.forEach((user, index) => {
    const userCard = document.createElement('div');
    userCard.className = 'similar-user-card';
    
    // Determine similarity level
    let similarityClass = 'low';
    let similarityEmoji = '🔵';
    if (user.similarityPercent >= 70) {
      similarityClass = 'high';
      similarityEmoji = '🟢';
    } else if (user.similarityPercent >= 40) {
      similarityClass = 'medium';
      similarityEmoji = '🟡';
    }
    
    // Build genres display
    const genresHtml = user.genres && user.genres.length > 0 
      ? `<div class="user-genres">${user.genres.slice(0, 4).map(g => `<span class="genre-tag small">${g}</span>`).join('')}</div>`
      : '';
    
    // Build artists display
    const artistsHtml = user.artists && user.artists.length > 0
      ? `<p class="user-artists">🎤 ${user.artists.slice(0, 3).join(', ')}</p>`
      : '';
    
    userCard.innerHTML = `
      <div class="user-card-header">
        <div class="user-avatar">👤</div>
        <div class="user-info-brief">
          <h5>User ${user.userId.slice(-6)}</h5>
          <span class="similarity-badge ${similarityClass}">${similarityEmoji} ${user.similarityPercent}% Match</span>
        </div>
      </div>
      ${genresHtml}
      ${artistsHtml}
      <button class="btn btn-small" onclick="compareWithUser('${user.userId}')">
        Compare Details
      </button>
    `;
    
    elements.similarUsersList.appendChild(userCard);
  });
}

/**
 * Compare current user with another user
 */
async function compareWithUser(otherUserId) {
  try {
    console.log(`📊 Comparing with user: ${otherUserId}`);
    
    const response = await fetch(`${API_BASE}/api/users/${currentUser.userId}/compare/${otherUserId}`);
    const data = await response.json();
    
    if (!data.success) {
      throw new Error(data.error || 'Failed to compare users');
    }
    
    displayComparison(data);
    elements.comparisonModal.style.display = 'flex';
    
  } catch (error) {
    console.error('Error comparing users:', error);
    showError('Failed to compare users. Please try again.');
  }
}

/**
 * Display comparison results in modal
 */
function displayComparison(data) {
  const { similarity, commonInterests, user1Details, user2Details } = data;
  
  let html = `
    <div class="comparison-header">
      <div class="comparison-score">
        <span class="big-score">${similarity}%</span>
        <span class="score-label">Music Match</span>
      </div>
    </div>
    
    <div class="comparison-body">
  `;
  
  // Common Interests Section
  html += `<div class="comparison-section">
    <h4>🤝 Common Interests</h4>`;
  
  if (commonInterests.genres.length > 0) {
    html += `<div class="interest-row">
      <span class="interest-label">🎸 Genres:</span>
      <span class="interest-values">${commonInterests.genres.join(', ')}</span>
    </div>`;
  }
  
  if (commonInterests.artists.length > 0) {
    html += `<div class="interest-row">
      <span class="interest-label">🎤 Artists:</span>
      <span class="interest-values">${commonInterests.artists.join(', ')}</span>
    </div>`;
  }
  
  if (commonInterests.songs.length > 0) {
    html += `<div class="interest-row">
      <span class="interest-label">🎵 Songs:</span>
      <span class="interest-values">${commonInterests.songs.join(', ')}</span>
    </div>`;
  }
  
  if (commonInterests.albums.length > 0) {
    html += `<div class="interest-row">
      <span class="interest-label">💿 Albums:</span>
      <span class="interest-values">${commonInterests.albums.join(', ')}</span>
    </div>`;
  }
  
  if (commonInterests.genres.length === 0 && commonInterests.artists.length === 0 && 
      commonInterests.songs.length === 0 && commonInterests.albums.length === 0) {
    html += `<p class="no-common">No exact matches, but similar tastes!</p>`;
  }
  
  html += `</div>`;
  
  // Your Profile Section
  html += `<div class="comparison-section">
    <h4>👤 Your Profile</h4>
    <div class="profile-details">`;
  
  if (user1Details.genres.length > 0) {
    html += `<p><strong>Genres:</strong> ${user1Details.genres.slice(0, 5).join(', ')}</p>`;
  }
  if (user1Details.artists.length > 0) {
    html += `<p><strong>Artists:</strong> ${user1Details.artists.slice(0, 5).join(', ')}</p>`;
  }
  
  html += `</div></div>`;
  
  // Other User Profile Section
  html += `<div class="comparison-section">
    <h4>👥 Their Profile</h4>
    <div class="profile-details">`;
  
  if (user2Details.genres.length > 0) {
    html += `<p><strong>Genres:</strong> ${user2Details.genres.slice(0, 5).join(', ')}</p>`;
  }
  if (user2Details.artists.length > 0) {
    html += `<p><strong>Artists:</strong> ${user2Details.artists.slice(0, 5).join(', ')}</p>`;
  }
  
  html += `</div></div></div>`;
  
  elements.comparisonResult.innerHTML = html;
}

/**
 * Close comparison modal
 */
function closeComparisonModal() {
  elements.comparisonModal.style.display = 'none';
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', init);
