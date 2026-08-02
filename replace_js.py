import re

with open('content.js', 'r') as f:
    js = f.read()

# 1. Windows array
js = re.sub(
    r"const WINDOWS = \[\s*\{ key: '1h', label: '1h', ms: 60 \* 60 \* 1000 \},\s*\];",
    "const WINDOWS = [\n    { key: '15m', label: '15m', ms: 15 * 60 * 1000 },\n    { key: '30m', label: '30m', ms: 30 * 60 * 1000 },\n    { key: '1h', label: '1h', ms: 60 * 60 * 1000 },\n  ];",
    js
)

# 2. renderLevelOverlay WINDOWS index
js = re.sub(
    r"const winDef = WINDOWS\.find\(\(w\) => w\.key === selectedWindow\) \|\| WINDOWS\[0\];",
    "const winDef = WINDOWS.find((w) => w.key === selectedWindow) || WINDOWS[2];",
    js
)

# 3. render() update
render_find = r"try \{\s*drawGraph\('bxph-canvas-xp', xphHistory, 107, 255, 176\); // #6bffb0\s*drawGraph\('bxph-canvas-gold', goldhHistory, 255, 215, 106\); // #ffd76a\s*\} catch \(e\) \{"
render_repl = """const winDef = WINDOWS.find((w) => w.key === selectedWindow) || WINDOWS[2];
    try {
      drawGraph('bxph-canvas-xp', xphHistory, 107, 255, 176, winDef); 
      drawGraph('bxph-canvas-gold', goldhHistory, 255, 215, 106, winDef); 
    } catch (e) {"""
js = re.sub(render_find, render_repl, js)

# 4. init() update
init_find = r"try \{\s*drawGraph\('bxph-canvas-xp', xphHistory, 107, 255, 176\);\s*drawGraph\('bxph-canvas-gold', goldhHistory, 255, 215, 106\);\s*\} catch\(e\) \{\}"
init_repl = """try {
        const winDef = WINDOWS.find((w) => w.key === selectedWindow) || WINDOWS[2];
        drawGraph('bxph-canvas-xp', xphHistory, 107, 255, 176, winDef);
        drawGraph('bxph-canvas-gold', goldhHistory, 255, 215, 106, winDef);
      } catch(e) {}"""
js = re.sub(init_find, init_repl, js)

# 5. drawGraph update
draw_find = r"function drawGraph\(canvasId, history, r, g, b\) \{.*?(?=function render\(\) \{)"
draw_repl = """function drawGraph(canvasId, history, r, g, b, winDef) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    
    const rect = canvas.getBoundingClientRect();
    if (rect.width === 0) return; // not visible
    canvas.width = rect.width;
    canvas.height = 85; // fixed

    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    if (history.length < 2) return;

    // EMA Smoothing over the full history up to 1h
    const smoothed = [];
    let ema = history[0].val;
    const alpha = 0.6; // Sensitivity value to micro-variations
    for (let i = 0; i < history.length; i++) {
      ema = alpha * history[i].val + (1 - alpha) * ema;
      smoothed.push({ t: history[i].t, val: ema });
    }

    const now = Date.now();
    const maxTime = now;
    const minTime = now - winDef.ms;

    // Filter visible points only for scaling and drawing
    const visibleSmoothed = smoothed.filter(h => h.t >= minTime);
    if (visibleSmoothed.length < 2) return;

    const rawMin = Math.min(...visibleSmoothed.map(h => h.val));
    const rawMax = Math.max(...visibleSmoothed.map(h => h.val));
    
    let range = rawMax - rawMin;
    if (range === 0) range = 1;
    
    // Dynamic scale highlighting micro-variations
    let maxVal = rawMax + range * 0.35; // 35% top padding for max text
    let minVal = rawMin - range * 0.35; // 35% bottom padding for min text

    const getX = (t) => ((t - minTime) / (maxTime - minTime)) * canvas.width;
    const getY = (v) => canvas.height - ((v - minVal) / (maxVal - minVal)) * canvas.height;

    ctx.beginPath();
    ctx.strokeStyle = `rgb(${r}, ${g}, ${b})`;
    ctx.lineWidth = 2;
    ctx.lineJoin = 'round';
    ctx.lineCap = 'round';

    for (let i = 0; i < visibleSmoothed.length; i++) {
      const x = getX(visibleSmoothed[i].t);
      const y = getY(visibleSmoothed[i].val);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();
    
    ctx.lineTo(getX(visibleSmoothed[visibleSmoothed.length - 1].t), canvas.height);
    ctx.lineTo(getX(visibleSmoothed[0].t), canvas.height);
    ctx.closePath();
    
    const grad = ctx.createLinearGradient(0, 0, 0, canvas.height);
    grad.addColorStop(0, `rgba(${r}, ${g}, ${b}, 0.4)`);
    grad.addColorStop(1, `rgba(${r}, ${g}, ${b}, 0)`);
    ctx.fillStyle = grad;
    ctx.fill();

    // Draw text overlays
    ctx.fillStyle = 'rgba(255, 255, 255, 0.6)';
    ctx.font = '9px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif';
    ctx.textAlign = 'left';
    ctx.fillText(`-${winDef.key}`, 2, canvas.height - 2);
    
    ctx.fillStyle = `rgb(${r}, ${g}, ${b})`;
    ctx.textAlign = 'right';
    // Use true max for the text
    ctx.fillText(`Máx: ${formatCompact(rawMax)}/h`, canvas.width - 2, 10);
    // Use true min for the text
    ctx.fillText(`Mín: ${formatCompact(rawMin)}/h`, canvas.width - 2, canvas.height - 2);
  }

  """
js = re.sub(draw_find, draw_repl, js, flags=re.DOTALL)

with open('content.js', 'w') as f:
    f.write(js)
