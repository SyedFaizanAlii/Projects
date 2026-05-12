// ============================================================
// CDSS Clinical Query Handler
// ============================================================

const form          = document.getElementById('queryForm');
const queryInput    = document.getElementById('queryInput');
const charCountEl   = document.getElementById('charCount');
const submitBtn     = document.getElementById('submitBtn');
const clearBtn      = document.getElementById('clearBtn');
const resultsSection = document.getElementById('results');
const errorBox      = document.getElementById('errorBox');
const errorMsg      = document.getElementById('errorMsg');

// ---------- Character counter ----------
queryInput.addEventListener('input', () => {
    const len = queryInput.value.length;
    charCountEl.textContent = len;
    charCountEl.style.color = len > 480 ? '#ef4444' : len > 400 ? '#f59e0b' : '#94a3b8';
    if (len > 500) queryInput.value = queryInput.value.slice(0, 500);
});

// ---------- Example chips ----------
document.querySelectorAll('.example-chip').forEach(chip => {
    chip.addEventListener('click', () => {
        queryInput.value = chip.dataset.q;
        charCountEl.textContent = chip.dataset.q.length;
        queryInput.focus();
        queryInput.scrollIntoView({ behavior: 'smooth', block: 'center' });
    });
});

// ---------- Clear ----------
clearBtn.addEventListener('click', () => {
    queryInput.value = '';
    charCountEl.textContent = '0';
    resultsSection.style.display = 'none';
    errorBox.style.display = 'none';
    queryInput.focus();
});

// ---------- Submit ----------
form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const queryText = queryInput.value.trim();
    if (!queryText) { showError('Please enter a clinical question before submitting.'); return; }

    setLoading(true);
    errorBox.style.display = 'none';
    resultsSection.style.display = 'none';

    try {
        const res = await fetch('/api/queries/submit_query/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
            },
            body: JSON.stringify({ query_text: queryText }),
        });

        const data = await res.json();
        if (!res.ok) throw new Error(data?.error || data?.detail || `Server error (${res.status})`);
        displayResults(data);

    } catch (err) {
        showError(err.message || 'Failed to connect to the clinical engine. Is the server running?');
    } finally {
        setLoading(false);
    }
});

// ============================================================
// DISPLAY RESULTS
// ============================================================
function displayResults(queryData) {
    const resp = queryData.response || {};

    // ---- Answer ----
    const answerText = resp.response_text || 'No clinical recommendation generated.';
    document.getElementById('answerBox').textContent = answerText;

    // ---- Confidence ----
    const confRaw = typeof resp.confidence_score === 'number' ? resp.confidence_score : 0;
    const confPct = Math.round(confRaw * 100);
    document.getElementById('confidenceScore').textContent = `${confPct}%`;

    // Confidence meter animation
    const meter = document.getElementById('confidenceMeter');
    meter.style.width = '0%';
    setTimeout(() => { meter.style.width = `${confPct}%`; }, 120);

    // Confidence badge color
    const badge = document.getElementById('confidenceBadge');
    const hintEl = document.getElementById('confidenceHint');
    if (confPct >= 75) {
        badge.className = 'confidence-badge conf-high';
        hintEl.textContent = 'Strong semantic match with indexed evidence';
    } else if (confPct >= 45) {
        badge.className = 'confidence-badge conf-medium';
        hintEl.textContent = 'Moderate match — review sources for full context';
    } else {
        badge.className = 'confidence-badge conf-low';
        hintEl.textContent = 'Low match — consider rephrasing your query';
    }

    // Meter fill color
    meter.className = 'meter-fill ' + (confPct >= 75 ? 'meter-high' : confPct >= 45 ? 'meter-medium' : 'meter-low');

    // ---- Sources ----
    let sources = resp.sources;
    if (typeof sources === 'string') {
        try { sources = JSON.parse(sources); } catch { sources = []; }
    }
    if (!Array.isArray(sources)) sources = [];

    // Filter to document-type only and deduplicate by pmid
    const docSources = [];
    const seenPmids = new Set();
    for (const s of sources) {
        const pmid = s.pmid || s.reference || '';
        if (pmid && seenPmids.has(pmid)) continue;
        if (pmid) seenPmids.add(pmid);
        docSources.push(s);
    }

    const countEl = document.getElementById('sourcesCount');
    const listEl  = document.getElementById('sourcesList');

    if (docSources.length === 0) {
        countEl.textContent = '';
        listEl.innerHTML = '<p class="no-sources">No reference sources were found for this query. The answer above is based on general knowledge graph relationships.</p>';
    } else {
        countEl.textContent = `${docSources.length} source${docSources.length > 1 ? 's' : ''}`;
        listEl.innerHTML = docSources.map(buildSourceCard).join('');
    }

    resultsSection.style.display = 'block';
    setTimeout(() => resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' }), 80);
}

function buildSourceCard(src) {
    const specialty   = src.specialty  || '';
    const title       = src.title      || 'Untitled Publication';
    const pmid        = src.pmid       || '';
    const doi         = src.doi        || '';
    const pubDate     = src.publication_date || '';
    const snippet     = (src.snippet   || '').trim().replace(/</g, '&lt;').replace(/>/g, '&gt;');
    const pubmedUrl   = src.pubmed_url || (pmid ? `https://pubmed.ncbi.nlm.nih.gov/${pmid}/` : '');

    const specialtyBadge = specialty
        ? `<span class="source-specialty-badge">${specialty}</span>` : '';

    const pubDateStr = pubDate ? `<span class="source-date"><i class="fas fa-calendar-alt"></i> ${pubDate}</span>` : '';

    const linkGroup = [];
    if (pubmedUrl) linkGroup.push(`<a href="${pubmedUrl}" target="_blank" rel="noopener" class="source-link pubmed-link"><i class="fas fa-external-link-alt"></i> PubMed${pmid ? ` #${pmid}` : ''}</a>`);
    if (doi) linkGroup.push(`<a href="https://doi.org/${doi}" target="_blank" rel="noopener" class="source-link doi-link"><i class="fas fa-link"></i> DOI</a>`);

    return `
    <div class="source-card">
        <div class="source-card-header">
            ${specialtyBadge}
            ${pubDateStr}
        </div>
        <h4 class="source-title">${title || 'Clinical Research Publication'}</h4>
        ${snippet ? `<p class="source-snippet">${snippet}</p>` : ''}
        ${linkGroup.length ? `<div class="source-links">${linkGroup.join('')}</div>` : ''}
    </div>`;
}

// ============================================================
// HELPERS
// ============================================================
function setLoading(on) {
    submitBtn.disabled = on;
    submitBtn.querySelector('.btn-text').style.display  = on ? 'none' : 'flex';
    submitBtn.querySelector('.btn-loading').style.display = on ? 'flex' : 'none';
}

function showError(msg) {
    errorMsg.textContent = msg;
    errorBox.style.display = 'flex';
    errorBox.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}
