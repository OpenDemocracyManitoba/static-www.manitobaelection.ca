"""Phase B §6.1 step 2 (R4): mirror the visual external dependencies of a static-<host> repo into site/_ext/.
Usage: python3 -I mirror_deps.py <host> [--apply]   (from the repo root; dry run by default)
Each dependency is fetched once into work/ext-cache/ (keyed by URL), copied to site/_ext/<host>/<path>, and the
pages' links are rewritten to the root-relative copy. The dns-prefetch hints for the mirrored hosts are removed.
Refuses to apply unless the per-pattern file counts match EXPECT and no reference to a mirrored host is left.
Works on bytes: some pages hold truncated UTF-8."""
import collections, hashlib, os, re, sys, urllib.parse, urllib.request

host = sys.argv[1]; APPLY = '--apply' in sys.argv[2:]
CACHE = '/home/stungeye/migration/work/ext-cache'
# Google Fonts serves woff2 with unicode-range subsets to current browsers; ask as one.
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36'
FA = 'https://use.fontawesome.com/releases/v5.1.1/css/all.css'
GF = 'https://fonts.googleapis.com/css?family=Libre+Franklin%3A400%2C700'
TW = 'https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css'
BS = 'https://stackpath.bootstrapcdn.com/bootstrap/4.4.1/css/bootstrap.min.css'
LOCAL = {FA: '/_ext/use.fontawesome.com/releases/v5.1.1/css/all.css',
         GF: '/_ext/fonts.googleapis.com/css/libre-franklin-400-700.css',
         TW: '/_ext/cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css',
         BS: '/_ext/stackpath.bootstrapcdn.com/bootstrap/4.4.1/css/bootstrap.min.css'}
VER = rb'(?:(?:\?|&#038;|&amp;|&)ver=[0-9.]+)?'
LINKS = {   # dependency -> the href forms the pages use (cache-buster versions vary per site)
    FA: re.compile(re.escape(FA.encode()) + VER),
    GF: re.compile(re.escape(GF.encode()) + VER),
    TW: re.compile(re.escape(TW.encode())),
    BS: re.compile(re.escape(BS.encode())),
}
PREFETCH = re.compile(rb"[ \t]*<link rel='dns-prefetch' href='//(?:fonts\.googleapis\.com|use\.fontawesome\.com)' />\r?\n")
OURS = re.compile(rb'/_ext/[^"\'\s)<>]*')   # links to the copies themselves
MIRRORED = re.compile(rb'use\.fontawesome\.com|fonts\.googleapis\.com|fonts\.gstatic\.com|tailwindcss@2\.2\.19|bootstrap/4\.4\.1')
WP4 = {FA: 0, GF: 0, 'prefetch': 0}
EXPECT = {   # HTML files per pattern (plan §2.2 / §3 D7 page counts; 2018's we2018address/ loads the Google Fonts CSS only)
    '2018.winnipegelection.ca': {FA: 507, GF: 508, 'prefetch': 507},
    '2019.manitobaelection.ca': {FA: 779, GF: 779, 'prefetch': 779},
    '2022.winnipegelection.ca': {FA: 641, GF: 641, 'prefetch': 641},
    'www.manitobaelection.ca': {FA: 794, GF: 794, 'prefetch': 794},
    'www.opendemocracymanitoba.ca': {TW: 4, BS: 1},
}[host]


def fetch(url):
    """Bytes of url, from the cache when present (cache file name = sha256 of the URL)."""
    os.makedirs(CACHE, exist_ok=True)
    p = os.path.join(CACHE, hashlib.sha256(url.encode()).hexdigest())
    if not os.path.exists(p):
        with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': UA}), timeout=60) as r:
            assert r.status == 200, (url, r.status)
            body = r.read()
        open(p + '.tmp', 'wb').write(body); os.replace(p + '.tmp', p)
        with open(os.path.join(CACHE, 'INDEX'), 'a') as f:
            f.write(f'{os.path.basename(p)} {url}\n')
    return open(p, 'rb').read()


def ext_path(url):
    u = urllib.parse.urlsplit(url)
    return '/_ext/' + u.netloc + u.path


def bundle(dep):
    """{site-relative path: bytes} for a dependency and everything its CSS loads."""
    css = fetch(dep)
    out = {}
    refs = sorted(set(m.decode() for m in re.findall(rb'url\(\s*["\']?([^"\')]+)["\']?\s*\)', css)))
    if dep == GF:   # absolute fonts.gstatic.com URLs: copy each font and point the CSS at the copy
        for r in refs:
            assert r.startswith('https://fonts.gstatic.com/'), r
            out[ext_path(r)] = fetch(r)
            css = css.replace(r.encode(), ext_path(r).encode())
    else:           # relative URLs (Font Awesome's ../webfonts/…): mirror the tree as is, CSS untouched
        for r in refs:
            if r.startswith('data:'):
                continue
            target = urllib.parse.urljoin(dep, r.split('#')[0].split('?')[0])
            assert target.startswith(dep.rsplit('/', 3)[0]), (dep, r)
            out[ext_path(target)] = fetch(target)
    out[LOCAL[dep]] = css
    return {k.lstrip('/'): v for k, v in out.items()}


files = sorted(os.path.join(r, f) for r, _, fs in os.walk('site') for f in fs if f.endswith('.html') and not r.startswith('site/_ext'))
per = collections.Counter(); refs = collections.Counter(); writes = {}
for p in files:
    b = new = open(p, 'rb').read()
    for dep, rx in LINKS.items():
        new, n = rx.subn(LOCAL[dep].encode(), new)
        if n:
            per[dep] += 1; refs[dep] += n
    new, n = PREFETCH.subn(b'', new)
    if n:
        per['prefetch'] += 1; refs['prefetch'] += n
    if new != b:
        writes[p] = new
left = [p for p in files if MIRRORED.search(OURS.sub(b'', writes.get(p, b'')))] + \
       [os.path.join(r, f) for r, _, fs in os.walk('site') for f in fs if not r.startswith('site/_ext') and not f.endswith('.html')
        and f.endswith(('.css', '.js', '.json', '.xml')) and MIRRORED.search(open(os.path.join(r, f), 'rb').read())]
left += [p for p in files if p not in writes and MIRRORED.search(open(p, 'rb').read())]
deps = [d for d in LINKS if per[d]]
add = {}
for d in deps:
    add.update(bundle(d))
clash = [k for k in add if os.path.exists(os.path.join('site', k)) and open(os.path.join('site', k), 'rb').read() != add[k]]

print(f'{host}: {len(files)} HTML files, {len(writes)} to change')
for k in list(LINKS) + ['prefetch']:
    if per[k] or k in EXPECT:
        print(f'  {LOCAL.get(k, "dns-prefetch hint removed")}: {per[k]} files ({refs[k]} refs), expected {EXPECT.get(k, 0)}')
print(f'  site/_ext/: {len(add)} files, {sum(map(len, add.values())):,} bytes')
for k in sorted(add):
    print(f'    {k} ({len(add[k]):,} B)')
mismatch = {k: (per[k], v) for k, v in EXPECT.items() if per[k] != v} | {k: (per[k], 0) for k in per if k not in EXPECT}
if mismatch:
    print('COUNT MISMATCH:', mismatch)
if left:
    print(f'LEFTOVER references to mirrored hosts in {len(left)} file(s):', left[:10])
if clash:
    print('site/_ext/ files already present with other bytes:', clash)
if mismatch or left or clash:
    sys.exit('stop and report' + ('; nothing written' if APPLY else ''))
if APPLY:
    for k, v in add.items():
        os.makedirs(os.path.dirname(os.path.join('site', k)), exist_ok=True)
        open(os.path.join('site', k), 'wb').write(v)
    for p, new in writes.items():
        open(p, 'wb').write(new)
    lines = ['## External dependencies mirrored', '',
             'In Phase B of the olddroplet migration (R4, 2026-10-24), the stylesheets every page needs to render were copied into '
             f'`site/_ext/` by `python3 -I mirror_deps.py {host} --apply`, and the pages now load the copies (root-relative links):', '']
    for d in deps:
        lines.append(f'* `{d}` → `{LOCAL[d]}` ({per[d]:,} HTML files)' + (', with its webfonts, byte-identical' if d == FA else
                     ', with its `woff2` files; the CSS (fetched as a current Chrome) points at the copies under `/_ext/fonts.gstatic.com/`' if d == GF else ''))
    if per['prefetch']:
        lines.append(f'* the `dns-prefetch` hints for `fonts.googleapis.com` and `use.fontawesome.com` were removed ({per["prefetch"]:,} HTML files)')
    lines += ['', 'Font Awesome Free is under the Font Awesome Free License (fonts SIL OFL 1.1, CSS MIT); Libre Franklin is under the SIL OFL 1.1. '
              'Other third-party scripts and embeds were left as they were.' if deps != [TW, BS] and FA in deps else
              'Tailwind CSS and Bootstrap are under the MIT License. Other third-party resources were left as they were.', '']
    section = '\n'.join(lines)
    r = open('README.md').read()
    i = min([j for j in (r.find('\n## Analytics removed\n'), r.find('\n## Hosting\n'), r.find('\n## Secret scan')) if j >= 0] or [len(r)])
    open('README.md', 'w').write(r[:i + 1] + section + '\n' + r[i + 1:] if i < len(r) else r.rstrip('\n') + '\n\n' + section)
    print('written')
