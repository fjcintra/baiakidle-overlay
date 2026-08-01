import re

with open('content.js', 'r') as f:
    js = f.read()

# Pattern to find the injected block
pattern = r"""\s*const now = Date\.now\(\);\s*if \(now - lastGraphUpdate >= 5000\) \{\s*xphHistory\.push\(\{ t: now, val: xph \}\);\s*goldhHistory\.push\(\{ t: now, val: goldh \}\);\s*const cutoff = now - 60 \* 60 \* 1000;\s*xphHistory = xphHistory\.filter\(h => h\.t >= cutoff\);\s*goldhHistory = goldhHistory\.filter\(h => h\.t >= cutoff\);\s*lastGraphUpdate = now;\s*\}\s*try \{\s*drawGraph\('bxph-canvas-xp', xphHistory, 107, 255, 176\); // #6bffb0\s*drawGraph\('bxph-canvas-gold', goldhHistory, 255, 215, 106\); // #ffd76a\s*\} catch \(e\) \{\s*console\.error\('Error drawing canvas', e\);\s*\}\s*renderLevelOverlay\(\);"""

# Replace ALL occurrences with just "renderLevelOverlay();"
js = re.sub(pattern, "\n      renderLevelOverlay();\n", js)

# Now inject it ONLY inside render()
render_pattern = r"(function render\(\) \{.*?)(\n\s*renderLevelOverlay\(\);\n\s*\})"
replacement = r"\1\n\n    const now = Date.now();\n    if (now - lastGraphUpdate >= 5000) {\n      xphHistory.push({ t: now, val: xph });\n      goldhHistory.push({ t: now, val: goldh });\n      \n      const cutoff = now - 60 * 60 * 1000;\n      xphHistory = xphHistory.filter(h => h.t >= cutoff);\n      goldhHistory = goldhHistory.filter(h => h.t >= cutoff);\n\n      lastGraphUpdate = now;\n    }\n    \n    try {\n      drawGraph('bxph-canvas-xp', xphHistory, 107, 255, 176); // #6bffb0\n      drawGraph('bxph-canvas-gold', goldhHistory, 255, 215, 106); // #ffd76a\n    } catch (e) {\n      console.error('Error drawing canvas', e);\n    }\n\2"

js = re.sub(render_pattern, replacement, js, flags=re.DOTALL)

with open('content.js', 'w') as f:
    f.write(js)
