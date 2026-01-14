// Gujarat AnyROR Scraper Frontend

let API_URL = localStorage.getItem('apiUrl') || '';
let gujaratData = null;
let jobId = null;
let pollInterval = null;

// Initialize
document.addEventListener('DOMContentLoaded', async () => {
    updateApiDisplay();
    await loadGujaratData();
});

function updateApiDisplay() {
    document.getElementById('apiUrl').textContent = API_URL || 'Not configured';
}

function configureApi() {
    const url = prompt('Enter VM API URL (e.g., http://35.200.100.50:8000):', API_URL);
    if (url !== null) {
        API_URL = url.replace(/\/$/, ''); // Remove trailing slash
        localStorage.setItem('apiUrl', API_URL);
        updateApiDisplay();
    }
}

async function loadGujaratData() {
    try {
        const response = await fetch('gujarat-anyror-complete.json');
        gujaratData = await response.json();
        populateDistricts();
    } catch (e) {
        console.error('Failed to load Gujarat data:', e);
        document.getElementById('district').innerHTML = '<option value="">Failed to load data</option>';
    }
}

function populateDistricts() {
    const select = document.getElementById('district');
    select.innerHTML = '<option value="">-- Select District --</option>';
    
    gujaratData.districts.forEach(d => {
        const opt = document.createElement('option');
        opt.value = d.value;
        opt.textContent = `${d.label} (${d.talukas.length} talukas)`;
        opt.dataset.talukas = JSON.stringify(d.talukas);
        select.appendChild(opt);
    });
    
    select.addEventListener('change', onDistrictChange);
}

function onDistrictChange() {
    const districtSelect = document.getElementById('district');
    const talukaSelect = document.getElementById('taluka');
    
    if (!districtSelect.value) {
        talukaSelect.innerHTML = '<option value="">Select district first</option>';
        talukaSelect.disabled = true;
        updateVillageCount();
        return;
    }
    
    const selectedOption = districtSelect.options[districtSelect.selectedIndex];
    const talukas = JSON.parse(selectedOption.dataset.talukas);
    
    talukaSelect.innerHTML = '<option value="">-- All Talukas --</option>';
    talukas.forEach(t => {
        const opt = document.createElement('option');
        opt.value = t.value;
        opt.textContent = `${t.label} (${t.villages.length} villages)`;
        opt.dataset.villages = t.villages.length;
        talukaSelect.appendChild(opt);
    });
    
    talukaSelect.disabled = false;
    talukaSelect.addEventListener('change', updateVillageCount);
    updateVillageCount();
}

function updateVillageCount() {
    const districtSelect = document.getElementById('district');
    const talukaSelect = document.getElementById('taluka');
    const countEl = document.getElementById('villageCount');
    
    if (!districtSelect.value) {
        countEl.textContent = '';
        return;
    }
    
    const district = gujaratData.districts.find(d => d.value === districtSelect.value);
    if (!district) return;
    
    let count = 0;
    if (talukaSelect.value) {
        const taluka = district.talukas.find(t => t.value === talukaSelect.value);
        count = taluka ? taluka.villages.length : 0;
    } else {
        count = district.talukas.reduce((sum, t) => sum + t.villages.length, 0);
    }
    
    countEl.textContent = `${count} villages`;
}

async function startScraping() {
    if (!API_URL) {
        alert('Please configure the API URL first');
        configureApi();
        return;
    }
    
    const district = document.getElementById('district').value;
    if (!district) {
        alert('Please select a district');
        return;
    }
    
    const taluka = document.getElementById('taluka').value;
    const surveyFilter = document.getElementById('surveyFilter').value;
    const numContexts = document.getElementById('numContexts').value;
    
    // Show status card
    document.getElementById('statusCard').style.display = 'block';
    document.getElementById('resultsCard').style.display = 'none';
    document.getElementById('startBtn').disabled = true;
    document.getElementById('stopBtn').style.display = 'inline-block';
    
    clearLog();
    addLog('Starting scraper...', 'info');
    
    try {
        const response = await fetch(`${API_URL}/start`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                district_code: district,
                taluka_code: taluka || null,
                survey_filter: surveyFilter || null,
                num_contexts: parseInt(numContexts)
            })
        });
        
        const data = await response.json();
        
        if (data.job_id) {
            jobId = data.job_id;
            addLog(`Job started: ${jobId}`, 'success');
            startPolling();
        } else {
            throw new Error(data.error || 'Failed to start job');
        }
    } catch (e) {
        addLog(`Error: ${e.message}`, 'error');
        resetUI();
    }
}

async function stopScraping() {
    if (!jobId) return;
    
    try {
        await fetch(`${API_URL}/stop/${jobId}`, { method: 'POST' });
        addLog('Stop requested...', 'info');
    } catch (e) {
        addLog(`Stop error: ${e.message}`, 'error');
    }
}

function startPolling() {
    pollInterval = setInterval(pollStatus, 2000);
}

function stopPolling() {
    if (pollInterval) {
        clearInterval(pollInterval);
        pollInterval = null;
    }
}

async function pollStatus() {
    if (!jobId) return;
    
    try {
        const response = await fetch(`${API_URL}/status/${jobId}`);
        const data = await response.json();
        
        updateStats(data);
        
        // Add new log entries
        if (data.recent_logs) {
            data.recent_logs.forEach(log => {
                addLog(log.message, log.type || 'info');
            });
        }
        
        // Check if done
        if (data.status === 'completed' || data.status === 'failed' || data.status === 'stopped') {
            stopPolling();
            onJobComplete(data);
        }
    } catch (e) {
        addLog(`Poll error: ${e.message}`, 'error');
    }
}

function updateStats(data) {
    document.getElementById('statTotal').textContent = data.total || 0;
    document.getElementById('statDone').textContent = data.done || 0;
    document.getElementById('statSuccess').textContent = data.success || 0;
    document.getElementById('statRate').textContent = `${(data.rate || 0).toFixed(1)}/s`;
    
    const progress = data.total > 0 ? (data.done / data.total * 100) : 0;
    document.getElementById('progressFill').style.width = `${progress}%`;
}

function onJobComplete(data) {
    addLog(`Job ${data.status}: ${data.success}/${data.total} successful`, 
           data.status === 'completed' ? 'success' : 'error');
    
    resetUI();
    showResults(data);
}

function showResults(data) {
    const card = document.getElementById('resultsCard');
    const content = document.getElementById('resultsContent');
    
    card.style.display = 'block';
    
    let html = `
        <div class="stats" style="margin-bottom:20px;">
            <div class="stat">
                <div class="value">${data.total || 0}</div>
                <div class="label">Total Villages</div>
            </div>
            <div class="stat">
                <div class="value" style="color:#00ff88;">${data.success || 0}</div>
                <div class="label">Successful</div>
            </div>
            <div class="stat">
                <div class="value" style="color:#ff4444;">${(data.total || 0) - (data.success || 0)}</div>
                <div class="label">Failed</div>
            </div>
            <div class="stat">
                <div class="value">${((data.success || 0) / (data.total || 1) * 100).toFixed(1)}%</div>
                <div class="label">Success Rate</div>
            </div>
        </div>
    `;
    
    if (data.download_url) {
        html += `<a href="${API_URL}${data.download_url}" class="btn btn-primary" download>📥 Download Results</a>`;
    }
    
    content.innerHTML = html;
}

function resetUI() {
    document.getElementById('startBtn').disabled = false;
    document.getElementById('stopBtn').style.display = 'none';
    jobId = null;
}

function addLog(message, type = 'info') {
    const log = document.getElementById('log');
    const entry = document.createElement('div');
    entry.className = `log-entry ${type}`;
    entry.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
    log.appendChild(entry);
    log.scrollTop = log.scrollHeight;
}

function clearLog() {
    document.getElementById('log').innerHTML = '';
}
