import re

with open('overlay.css', 'r') as f:
    css = f.read()

# Add main char gold styling if not already there
main_style = """
/* Highlight Main Character (Gold) */
.bxph-level-main .bxph-level-name,
.bxph-level-main .bxph-level-eta {
  color: #ffd76a;
}
.bxph-level-main .bxph-level-progress-fill {
  background: #ffd76a;
}
"""
if "Highlight Main Character" not in css:
    css += main_style

# Remove .bxph-config-row and its children completely
css = re.sub(r"\.bxph-config-row \{.*?(?=\/\* Level Up Compact UI \*\/)", "", css, flags=re.DOTALL)

with open('overlay.css', 'w') as f:
    f.write(css)
