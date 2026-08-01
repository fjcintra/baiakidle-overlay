import re

with open('content.js', 'r') as f:
    js = f.read()

# Config
js = re.sub(
    r'const MAX_HISTORY_MS =.*?;',
    'const MAX_HISTORY_MS = 60 * 60 * 1000;',
    js
)
js = re.sub(
    r'const WINDOWS = \[.*?\];',
    "const WINDOWS = [\n    { key: '1h', label: '1h', ms: 60 * 60 * 1000 },\n  ];",
    js, flags=re.DOTALL
)

# State
js = re.sub(
    r"let selectedWindow = '5m';",
    "let selectedWindow = '1h';",
    js
)

js = re.sub(
    r'let goldFound = false;',
    'let goldFound = false;\n\n  // Canvas history\n  let xphHistory = [];\n  let goldhHistory = [];\n  let lastGraphUpdate = 0;',
    js
)

# Overlay Build
overlay_html = """
    overlayEl.innerHTML = `
      <div id="bxph-header">
        <span>Performance</span>
        <span class="bxph-header-icons">
          <span class="bxph-toggle" title="Minimizar/expandir">▾</span>
        </span>
      </div>
      <div class="bxph-body">
        <div class="bxph-row">
          <span class="bxph-label">XP/h</span>
          <span class="bxph-value" id="bxph-real-xph">–</span>
        </div>
        <canvas id="bxph-canvas-xp" class="bxph-canvas"></canvas>
        <div class="bxph-row">
          <span class="bxph-label">Gold/h</span>
          <span class="bxph-value" id="bxph-gold-h">–</span>
        </div>
        <canvas id="bxph-canvas-gold" class="bxph-canvas"></canvas>
        <div class="bxph-windows" id="bxph-windows"></div>
        <button id="bxph-reset-btn" class="bxph-reset-btn">Resetar</button>
        <div id="bxph-status"></div>
      </div>
    `;
"""
js = re.sub(
    r'overlayEl\.innerHTML = `.*?`;',
    overlay_html,
    js, flags=re.DOTALL, count=1
)

# Remove docking from overlay toggle
js = re.sub(
    r"overlayEl\.querySelector\('\.bxph-dock-toggle'\)\.addEventListener\('click', \(\) => {.*?}\);",
    "",
    js, flags=re.DOTALL
)

# Level overlay remove appendChild
js = re.sub(
    r"document\.body\.appendChild\(levelOverlayEl\);",
    "// document.body.appendChild(levelOverlayEl);",
    js
)

# Reset Button modification
js = re.sub(
    r"overlayEl\.querySelector\('#bxph-reset-btn'\)\.addEventListener\('click', \(\) => {",
    "overlayEl.querySelector('#bxph-reset-btn').addEventListener('click', () => {\n      xphHistory = [];\n      goldhHistory = [];",
    js
)

# Render function modification
render_func = """
  function drawGraph(canvasId, history, r, g, b) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    
    const rect = canvas.getBoundingClientRect();
    if (rect.width === 0) return; // not visible
    canvas.width = rect.width;
    canvas.height = 70; // fixed

    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    if (history.length < 2) return;

    // EMA Smoothing
    const smoothed = [];
    let ema = history[0].val;
    const alpha = 0.2; 
    for (let i = 0; i < history.length; i++) {
      ema = alpha * history[i].val + (1 - alpha) * ema;
      smoothed.push({ t: history[i].t, val: ema });
    }

    const now = Date.now();
    const maxTime = now;
    const minTime = now - 60 * 60 * 1000;

    let minVal = Math.min(...smoothed.map(h => h.val));
    let maxVal = Math.max(...smoothed.map(h => h.val));
    if (minVal > 0) minVal = 0; 
    if (maxVal === minVal) maxVal = minVal + 1;
    
    // add 10% headroom to max
    const range = maxVal - minVal;
    maxVal += range * 0.1;

    const getX = (t) => ((t - minTime) / (maxTime - minTime)) * canvas.width;
    const getY = (v) => canvas.height - ((v - minVal) / (maxVal - minVal)) * canvas.height;

    ctx.beginPath();
    ctx.strokeStyle = `rgb(${r}, ${g}, ${b})`;
    ctx.lineWidth = 2;
    ctx.lineJoin = 'round';
    ctx.lineCap = 'round';

    for (let i = 0; i < smoothed.length; i++) {
      const x = getX(smoothed[i].t);
      const y = getY(smoothed[i].val);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();
    
    ctx.lineTo(getX(smoothed[smoothed.length - 1].t), canvas.height);
    ctx.lineTo(getX(smoothed[0].t), canvas.height);
    ctx.closePath();
    
    const grad = ctx.createLinearGradient(0, 0, 0, canvas.height);
    grad.addColorStop(0, `rgba(${r}, ${g}, ${b}, 0.4)`);
    grad.addColorStop(1, `rgba(${r}, ${g}, ${b}, 0)`);
    ctx.fillStyle = grad;
    ctx.fill();
  }

  function render() {
"""
js = re.sub(
    r'function render\(\) {',
    render_func,
    js
)

# Inside render()
js = re.sub(
    r"overlayEl\.querySelector\('#bxph-elapsed'\)\.textContent = formatElapsed\(elapsedSec\);",
    "",
    js
)
js = re.sub(
    r"const gameXph = findGameXphValue\(\);\s*overlayEl\.querySelector\('#bxph-game-xph'\)\.textContent =\s*gameXph !== null \? formatNumber\(gameXph\) : '–';",
    "",
    js
)

# Graph updating logic inside render
graph_update = """
    const now = Date.now();
    if (now - lastGraphUpdate >= 5000) {
      xphHistory.push({ t: now, val: xph });
      goldhHistory.push({ t: now, val: goldh });
      
      const cutoff = now - 60 * 60 * 1000;
      xphHistory = xphHistory.filter(h => h.t >= cutoff);
      goldhHistory = goldhHistory.filter(h => h.t >= cutoff);

      lastGraphUpdate = now;
    }
    
    try {
      drawGraph('bxph-canvas-xp', xphHistory, 107, 255, 176); // #6bffb0
      drawGraph('bxph-canvas-gold', goldhHistory, 255, 215, 106); // #ffd76a
    } catch (e) {
      console.error('Error drawing canvas', e);
    }

    renderLevelOverlay();
"""
js = re.sub(
    r'renderLevelOverlay\(\);',
    graph_update,
    js
)

# Reset Request
js = re.sub(
    r"if \(area === 'local' && changes\.bxph_reset_request\) {",
    "if (area === 'local' && changes.bxph_reset_request) {\n      xphHistory = [];\n      goldhHistory = [];",
    js
)

# Resize Observer
js = re.sub(
    r'setInterval\(tick, TICK_MS\);',
    """setInterval(tick, TICK_MS);
    const ro = new ResizeObserver(() => {
      try {
        drawGraph('bxph-canvas-xp', xphHistory, 107, 255, 176);
        drawGraph('bxph-canvas-gold', goldhHistory, 255, 215, 106);
      } catch(e) {}
    });
    if (overlayEl) ro.observe(overlayEl);""",
    js
)

with open('content.js', 'w') as f:
    f.write(js)
