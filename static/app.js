const storageKey = 'sql-to-mysql-history';

function renderHistory(entries) {
  const historyList = document.getElementById('history-list');
  if (!historyList) {
    return;
  }

  if (!entries.length) {
    historyList.innerHTML = '<li>No recent queries yet.</li>';
    return;
  }

  historyList.innerHTML = entries
    .map((entry) => `<li data-query="${entry.query.replace(/"/g, '&quot;')}">${entry.query.slice(0, 80)}${entry.query.length > 80 ? '...' : ''}</li>`)
    .join('');

  historyList.querySelectorAll('li').forEach((item) => {
    item.addEventListener('click', () => {
      document.getElementById('input-query').value = item.dataset.query;
    });
  });
}

function loadHistory() {
  const saved = localStorage.getItem(storageKey);
  if (!saved) {
    renderHistory([]);
    return;
  }

  try {
    const parsed = JSON.parse(saved);
    renderHistory(parsed);
  } catch (error) {
    renderHistory([]);
  }
}

function saveHistory(query, converted) {
  const history = JSON.parse(localStorage.getItem(storageKey) || '[]');
  history.unshift({ query, converted });
  const trimmed = history.slice(0, 5);
  localStorage.setItem(storageKey, JSON.stringify(trimmed));
  renderHistory(trimmed);
}

async function convertQuery() {
  const input = document.getElementById('input-query').value;
  const output = document.getElementById('output-query');
  const warnings = document.getElementById('warnings');

  if (!input.trim()) {
    warnings.innerHTML = 'Please enter a query before converting.';
    output.value = '';
    return;
  }

  warnings.innerHTML = 'Converting...';

  const response = await fetch('/convert', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query: input })
  });

  const data = await response.json();
  output.value = data.converted || '';
  warnings.innerHTML = data.warnings.map((item) => `<div>${item}</div>`).join('');

  if (data.converted) {
    saveHistory(input, data.converted);
  }
}

function copyOutput() {
  const output = document.getElementById('output-query');
  if (!output.value) {
    return;
  }

  navigator.clipboard.writeText(output.value).then(() => {
    const warnings = document.getElementById('warnings');
    warnings.innerHTML = 'Copied to clipboard.';
  });
}

function handleFileUpload(event) {
  const file = event.target.files[0];
  if (!file) {
    return;
  }

  const reader = new FileReader();
  reader.onload = (event) => {
    document.getElementById('input-query').value = event.target.result;
  };
  reader.readAsText(file);
}

document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('convert-btn').addEventListener('click', convertQuery);
  document.getElementById('copy-btn').addEventListener('click', copyOutput);
  document.getElementById('sql-file').addEventListener('change', handleFileUpload);
  loadHistory();
});
