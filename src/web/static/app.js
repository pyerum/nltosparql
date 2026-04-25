const $ = (sel) => document.querySelector(sel);

let configData = {};

async function loadConfig() {
    const res = await fetch('/api/config');
    configData = await res.json();

    const providerSel = $('#provider');
    for (const name of Object.keys(configData.providers)) {
        const opt = document.createElement('option');
        opt.value = name;
        opt.textContent = name;
        providerSel.appendChild(opt);
    }
    providerSel.addEventListener('change', updateModels);
    updateModels();

    const endpointSel = $('#endpoint');
    for (const name of configData.endpoints) {
        const opt = document.createElement('option');
        opt.value = name;
        opt.textContent = name;
        endpointSel.appendChild(opt);
    }

    const ontologySel = $('#ontology');
    for (const name of configData.ontologies) {
        const opt = document.createElement('option');
        opt.value = name;
        opt.textContent = name;
        ontologySel.appendChild(opt);
    }
}

function updateModels() {
    const provider = $('#provider').value;
    const modelSel = $('#model');
    modelSel.innerHTML = '';
    const models = configData.providers[provider]?.models || [];
    for (const m of models) {
        const opt = document.createElement('option');
        opt.value = m;
        opt.textContent = m;
        modelSel.appendChild(opt);
    }
}

function setStatus(text, cls) {
    const el = $('#status');
    el.textContent = text;
    el.className = 'status-bar ' + (cls || '');
    $('#output').style.display = 'block';
}

function appendLog(type, html) {
    const container = $('#log-content');
    const entry = document.createElement('div');
    entry.className = 'log-entry ' + type;
    entry.innerHTML = html;
    container.appendChild(entry);
    container.scrollTop = container.scrollHeight;
}

function escapeHtml(str) {
    if (str == null) return '';
    return String(str)
        .replace(/&/g, '&')
        .replace(/</g, '<')
        .replace(/>/g, '>');
}

function renderResult(data) {
    const panel = $('#result-panel');
    const content = $('#result-content');
    panel.style.display = 'block';

    if (data.status === 'success') {
        const r = data.result || {};
        let html = '';
        if (r.sparql_query) {
            html += `<h3>SPARQL Query</h3><div class="sparql-query">${escapeHtml(r.sparql_query)}</div>`;
        }
        if (r.answer) {
            html += `<h3>Answer</h3><p>${escapeHtml(r.answer)}</p>`;
        }
        if (r.explanation) {
            html += `<h3>Explanation</h3><p>${escapeHtml(r.explanation)}</p>`;
        }
        content.innerHTML = html;
    } else if (data.status === 'cancelled') {
        const r = data.result || {};
        content.innerHTML = `<p><strong>Cancelled:</strong> ${escapeHtml(r.explanation || '')}</p>`;
    } else if (data.status === 'timeout') {
        let html = `<p><strong>Timeout:</strong> ${escapeHtml(data.error || '')}</p>`;
        if (data.best_sparql) {
            html += `<h3>Best Attempt</h3><div class="sparql-query">${escapeHtml(data.best_sparql)}</div>`;
        }
        if (data.best_answer) {
            html += `<p><strong>Answer:</strong> ${escapeHtml(data.best_answer)}</p>`;
        }
        content.innerHTML = html;
    } else {
        content.innerHTML = `<p class="error">Error: ${escapeHtml(data.error || 'Unknown error')}</p>`;
    }
}

function renderSummary(data) {
    const panel = $('#summary-panel');
    const content = $('#summary-content');
    panel.style.display = 'block';

    const iterations = data.iterations || 0;
    const calls = data.function_calls || [];
    const successCalls = calls.filter(c => c.success).length;
    const failedCalls = calls.filter(c => !c.success).length;

    const breakdown = {};
    for (const c of calls) {
        breakdown[c.function] = (breakdown[c.function] || 0) + 1;
    }

    let html = `<div class="summary-grid">
        <div class="summary-item"><div class="value">${iterations}</div><div class="label">Iterations</div></div>
        <div class="summary-item"><div class="value">${calls.length}</div><div class="label">Total Calls</div></div>
        <div class="summary-item"><div class="value">${successCalls}</div><div class="label">Successful</div></div>
        <div class="summary-item"><div class="value">${failedCalls}</div><div class="label">Failed</div></div>
    </div>`;

    if (Object.keys(breakdown).length > 0) {
        html += `<ul class="breakdown-list">`;
        for (const [func, count] of Object.entries(breakdown)) {
            html += `<li>${escapeHtml(func)}: ${count}</li>`;
        }
        html += `</ul>`;
    }

    content.innerHTML = html;
}

async function runQuery() {
    const btn = $('#submit');
    btn.disabled = true;
    $('#output').style.display = 'block';
    $('#result-panel').style.display = 'none';
    $('#summary-panel').style.display = 'none';
    $('#log-content').innerHTML = '';
    setStatus('Running...', 'running');

    const body = {
        question: $('#question').value,
        provider: $('#provider').value,
        model: $('#model').value,
        endpoint: $('#endpoint').value,
        ontology: $('#ontology').value || null,
    };

    const res = await fetch('/api/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    });

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split('\n');
        buffer = lines.pop(); // keep incomplete line

        for (let i = 0; i < lines.length; i++) {
            const line = lines[i];
            if (line.startsWith('event: ')) {
                const eventType = line.slice(7);
                const dataLine = lines[i + 1];
                if (dataLine && dataLine.startsWith('data: ')) {
                    const jsonStr = dataLine.slice(6);
                    let data;
                    try { data = JSON.parse(jsonStr); } catch { continue; }
                    handleEvent(eventType, data);
                    i++; // skip data line
                }
            }
        }
    }

    btn.disabled = false;
}

function handleEvent(type, data) {
    if (type === 'function_call') {
        const args = JSON.stringify(data.arguments, null, 2);
        appendLog('function-call', `
            <div class="meta">Iteration ${data.iteration} — Function call: ${escapeHtml(data.function)}</div>
            <pre>${escapeHtml(args)}</pre>
        `);
    } else if (type === 'function_result') {
        const typeClass = data.success ? 'function-result' : 'function-error';
        const payload = data.success
            ? JSON.stringify(data.result, null, 2)
            : data.error;
        appendLog(typeClass, `
            <div class="meta">Iteration ${data.iteration} — Result: ${escapeHtml(data.function)}</div>
            <pre>${escapeHtml(payload)}</pre>
        `);
    } else if (type === 'reasoning') {
        appendLog('reasoning', `
            <div class="meta">Iteration ${data.iteration} — Reasoning</div>
            <pre>${escapeHtml(data.content)}</pre>
        `);
    } else if (type === 'error') {
        setStatus('Error: ' + (data.message || ''), 'error');
    } else if (type === 'complete') {
        const statusMap = { success: 'Completed', cancelled: 'Cancelled', timeout: 'Timeout' };
        setStatus(statusMap[data.status] || data.status, data.status);
    } else if (type === 'final') {
        renderResult(data);
        renderSummary(data);
        const statusMap = { success: 'Completed', cancelled: 'Cancelled', timeout: 'Timeout', error: 'Error' };
        setStatus(statusMap[data.status] || data.status, data.status);
    }
}

$('#submit').addEventListener('click', runQuery);
loadConfig();
