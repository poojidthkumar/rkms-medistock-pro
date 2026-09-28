"""Usage: python apply_upgrade.py your_page.html  ->  writes your_page_upgraded.html
Removes the login credential hint + prefilled username, and inlines rkms-upgrade-v2.js."""
import sys, re, os
src = sys.argv[1] if len(sys.argv) > 1 else 'index.html'
js = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rkms-upgrade-v2.js'), encoding='utf-8').read()
h = open(src, encoding='utf-8').read()
h = re.sub(r'\s*<div class="login-hint">.*?</div>', '', h, count=1, flags=re.S)
h = h.replace('id="lu" placeholder="Username" value="admin"', 'id="lu" placeholder="Username" autocomplete="off"')
i = h.rfind('</body>')
h = h[:i] + '<script>\n' + js + '\n</script>\n' + h[i:]
out = src.rsplit('.', 1)[0] + '_upgraded.html'
open(out, 'w', encoding='utf-8').write(h)
print('Written:', out, '| hint removed:', 'login-hint">' not in h)
