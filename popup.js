document.getElementById('reset-btn').addEventListener('click', () => {
  chrome.storage.local.set({ bxph_reset_request: Date.now() }, () => {
    const statusEl = document.getElementById('status');
    statusEl.textContent = 'Dados resetados!';
    setTimeout(() => (statusEl.textContent = ''), 1500);
  });
});
