function showTab(tabName) {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    event.target.classList.add('active');
    document.getElementById(`${tabName}-tab`).classList.add('active');
}

const checkBtn = document.getElementById('checkBtn');
const checkTextBtn = document.getElementById('checkTextBtn');
const urlInput = document.getElementById('youtubeUrl');
const textInput = document.getElementById('textInput');
const loading = document.getElementById('loading');
const loadingText = document.getElementById('loadingText');
const results = document.getElementById('results');
const errorDiv = document.getElementById('error');
const transcriptDiv = document.getElementById('transcript');
const claimsDiv = document.getElementById('claims');

checkBtn.addEventListener('click', () => checkVideo());
checkTextBtn.addEventListener('click', () => checkText());

async function checkVideo() {
    const url = urlInput.value.trim();
    const language = document.querySelector('input[name="language"]:checked').value;
    
    if (!url) {
        showError('Please enter YouTube URL');
        return;
    }
    
    await performCheck('video', url, language);
}

async function checkText() {
    const text = textInput.value.trim();
    const language = document.querySelector('input[name="text-language"]:checked').value;
    
    if (!text || text.length < 50) {
        showError('Please enter at least 50 characters');
        return;
    }
    
    await performCheck('text', text, language);
}

async function performCheck(type, input, language) {
    hideError();
    results.classList.add('hidden');
    loading.classList.remove('hidden');
    checkBtn.disabled = true;
    checkTextBtn.disabled = true;
    
    try {
        let transcript;
        
        if (type === 'video') {
            loadingText.textContent = 'Getting captions...';
            const response = await fetch('/api/transcribe', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url: input, language })
            });
            const data = await handleResponse(response);
            transcript = data.transcript;
        } else {
            transcript = input;
        }
        
        transcriptDiv.textContent = transcript;
        
        loadingText.textContent = 'Extracting claims...';
        const claimsResponse = await fetch('/api/extract-claims', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ transcript, language })
        });
        const claimsData = await handleResponse(claimsResponse);
        
        claimsDiv.innerHTML = '';
        
        for (let i = 0; i < claimsData.claims.length; i++) {
            const claim = claimsData.claims[i];
            loadingText.textContent = `Checking ${i + 1}/${claimsData.claims.length}...`;
            
            const evidenceResponse = await fetch('/api/search-evidence', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ claim, language })
            });
            const evidenceData = await handleResponse(evidenceResponse);
            
            const verifyResponse = await fetch('/api/verify-claim', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ claim, evidence: evidenceData.evidence, language })
            });
            const verifyData = await handleResponse(verifyResponse);
            
            displayClaim(claim, verifyData.result);
            await new Promise(resolve => setTimeout(resolve, 1000));
        }
        
        loading.classList.add('hidden');
        results.classList.remove('hidden');
        
    } catch (error) {
        showError(error.message);
        loading.classList.add('hidden');
    } finally {
        checkBtn.disabled = false;
        checkTextBtn.disabled = false;
    }
}

async function handleResponse(response) {
    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || 'Request failed');
    }
    return response.json();
}

function displayClaim(claim, verification) {
    const card = document.createElement('div');
    card.className = 'claim-card';
    card.innerHTML = `
        <div class="claim-text">${claim}</div>
        <div class="verdict verdict-${verification.verdict}">${verification.verdict}</div>
        <div class="explanation">${verification.explanation}</div>
    `;
    claimsDiv.appendChild(card);
}

function showError(message) {
    errorDiv.textContent = `Error: ${message}`;
    errorDiv.classList.remove('hidden');
}

function hideError() {
    errorDiv.classList.add('hidden');
}

window.showTab = showTab;