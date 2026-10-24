"""Phase B §6.1 step 3 (D7): remove Google Tag Manager / Google Analytics from a static-<host> repo.
Usage: python3 -I strip_analytics.py <host> [--apply]   (from the repo root; dry run by default)
Removes the gtag.js loader + its adjacent inline <script> block, or the analytics.js inline loader,
plus the HTML comment directly above (and ExactMetrics' END comment directly below). An inline block is
only removed if every statement in it is GTM/GA; anything else is reported and the run refuses to apply.
Works on bytes: some pages hold truncated UTF-8."""
import collections, os, re, sys

host = sys.argv[1]; APPLY = '--apply' in sys.argv[2:]
WS = rb'[ \t\r\n]*'
COMMENT = rb'(?:<!--(?:(?!-->).){0,200}?(?:gtag|Google|ExactMetrics|Event snippet)(?:(?!-->).){0,200}?-->(?:<br ?/?>)?' + WS + rb')?'
GTAG = re.compile(COMMENT + rb'<script\s+async\s+src=["\']https://www\.googletagmanager\.com/gtag/js\?id=([A-Z]+-[0-9A-Z-]+)["\']' + WS + rb'>' + WS +
                  rb'</script>' + WS + rb'<script>((?:(?!</script>).)*)</script>', re.S)
GAJS = re.compile(COMMENT + rb'<script>((?:(?!</script>).)*(?:google-analytics\.com/analytics\.js|gtag\()(?:(?!</script>).)*)</script>'
                  rb'(?:' + WS + rb'<!-- END ExactMetrics Universal Analytics -->)?', re.S)
OK_STMTS = [   # every statement an inline block may contain (order matters: the bare '}' goes last)
    rb'window\.dataLayer\s*=\s*window\.dataLayer\s*\|\|\s*\[\]\s*;',
    rb'function\s+gtag\s*\(\s*\)\s*\{\s*dataLayer\.push\(\s*arguments\s*\)\s*;?\s*\}',
    rb'gtag\(\s*["\']js["\']\s*,\s*new Date\(\)\s*\)\s*;',
    rb'gtag\(\s*["\']config["\']\s*,\s*["\'][A-Z]+-[0-9A-Z-]+["\']\s*\)\s*;',
    rb"\(function\(i,s,o,g,r,a,m\)\{i\['GoogleAnalyticsObject'\]=r;i\[r\]=i\[r\]\|\|function\(\)\{\s*\(i\[r\]\.q=i\[r\]\.q\|\|\[\]\)\.push\(arguments\)\},"
    rb"i\[r\]\.l=1\*new Date\(\);a=s\.createElement\(o\),\s*m=s\.getElementsByTagName\(o\)\[0\];a\.async=1;a\.src=g;m\.parentNode\.insertBefore\(a,m\)\s*"
    rb"\}\)\(window,document,'script','https://www\.google-analytics\.com/analytics\.js','ga'\);",
    rb"ga\('create',\s*'UA-[0-9-]+',\s*'auto'\);", rb"ga\('send',\s*'pageview'\);",
    rb'var conversioned\s*=\s*true\s*;',
    rb"gtag\(\s*'event'\s*,\s*'conversion'\s*,\s*\{\s*'send_to'\s*:\s*'AW-[0-9]+/[0-9A-Za-z_-]+'\s*\}\s*\)\s*;",
    rb'if\s*\(\s*typeof conversioned\s*===\s*"undefined"\s*\)\s*\{', rb'\}',
]
LEFT = re.compile(rb'googletagmanager\.com|google-analytics\.com|gtag\(|dataLayer|ga\(\'create\'')
ID = re.compile(rb'\b(?:UA|G|AW)-[0-9A-Z-]+')


def pure_ga(body):
    rest = body
    for s in OK_STMTS:
        rest = re.sub(s, b'', rest)
    return not rest.strip()


def widen(d, s, e):
    """Take the whole line(s) when the snippet sits alone on them."""
    ls = d.rfind(b'\n', 0, s) + 1
    if not d[ls:s].strip():
        s = ls
    le = d.find(b'\n', e)
    le = len(d) if le < 0 else le + 1
    if not d[e:le].strip() and s == ls:
        e = le
    return s, e


shapes, shape_ex, ids, per_ext, bad, left = collections.Counter(), {}, collections.Counter(), collections.Counter(), [], []
changed, writes = 0, {}
for root, _, fs in os.walk('site'):
    for f in sorted(fs):
        p = os.path.join(root, f)
        if os.path.islink(p):
            continue
        d = open(p, 'rb').read()
        if not LEFT.search(d):
            continue
        out, pos, n = [], 0, 0
        for m in sorted(list(GTAG.finditer(d)) + list(GAJS.finditer(d)), key=lambda m: m.start()):
            if m.start() < pos:
                continue
            body = m.group(m.lastindex)
            if not pure_ga(body):
                bad.append(p); continue
            s, e = widen(d, m.start(), m.end())
            out.append(d[pos:s]); pos = e; n += 1
            norm = re.sub(rb'\s+', b' ', ID.sub(b'<ID>', m.group(0))).strip()
            shapes[norm] += 1; shape_ex.setdefault(norm, p)
            ids.update(i.decode() for i in ID.findall(m.group(0)))
        new = b''.join(out) + d[pos:]
        if LEFT.search(new):
            left.append(p)
        if n:
            changed += 1
            per_ext['.html' if f.endswith('.html') else f] += 1
            writes[p] = new

print(f'{host}: {"APPLIED" if APPLY else "dry run"}; files changed: {changed} {dict(per_ext)}')
print('IDs (occurrences):', dict(ids))
for k, v in shapes.most_common():
    print(f'--- shape x{v}, e.g. {shape_ex[k]}\n{k.decode("utf-8", "replace")}')
if bad:
    print(f'REFUSED: {len(bad)} block(s) mix other code:', bad[:10])
if left:
    print(f'LEFTOVER GTM/GA references in {len(left)} file(s):', left[:10])
if bad or left:
    sys.exit('stop and report' + ('; nothing written' if APPLY else ''))
if APPLY and writes:
    for p, new in writes.items():
        open(p, 'wb').write(new)
    exts = ', '.join(f'{n:,} `{e}`' if e != '.html' else f'{n:,} HTML file' + ('s' if n != 1 else '') for e, n in per_ext.items())
    lines = ['## Analytics removed', '',
             'Google Tag Manager / Google Analytics (and the Google Ads tag that rides on `gtag.js`) were removed in Phase B of the olddroplet '
             f'migration (owner decision D7, 2026-10-24) by `python3 -I strip_analytics.py {host} --apply`. Files changed: {exts}. '
             f'IDs: {", ".join(f"`{i}`" for i in sorted(ids))}. Each loader went together with its inline block and the comment around it. '
             'Other third-party scripts (fonts, embeds, Jetpack stats) were left as they were.', '', 'Snippet shapes removed (IDs and whitespace normalised):', '']
    for k, v in shapes.most_common():
        lines += [f'* {v:,} ×', '', '  ```html', '  ' + k.decode('utf-8', 'replace'), '  ```', '']
    section = '\n'.join(lines)
    r = open('README.md').read()
    i = min([j for j in (r.find('\n## Hosting\n'), r.find('\n## Secret scan')) if j >= 0] or [len(r)])
    open('README.md', 'w').write(r[:i + 1] + section + '\n' + r[i + 1:] if i < len(r) else r.rstrip('\n') + '\n\n' + section)
