"""Phase B §6.1 step 1 (R3): rewrite links to a site's old host so they point at the archive's own host.
Usage: python3 -I rewrite_links.py <host> [--apply]   (from the repo root; dry run by default)
Only links whose target is in site/ are rewritten (/x/ -> x/index.html, /x -> x, x.html or x/index.html); the rest are
listed and left alone. Text files only (HTML, JS, CSS, JSON, XML): PDFs and other binaries are listed, not edited.
Refuses to apply unless the counts match EXPECT. Works on bytes: some pages hold truncated UTF-8."""
import collections, os, re, sys, urllib.parse

host = sys.argv[1]; APPLY = '--apply' in sys.argv[2:]
RULES = {   # host -> (old prefix, new prefix, expected (text files changed, links rewritten))
    '2022.winnipegelection.ca': (b'https://www.winnipegelection.ca', b'https://2022.winnipegelection.ca', (6, 42)),
    '2016.manitobaelection.ca': (b'http://www.manitobaelection.ca', b'https://2016.manitobaelection.ca', None),
    'www.manitobaelection.ca': (b'http://www.manitobaelection.ca', b'https://www.manitobaelection.ca', (3, 6)),
}
OLD, NEW, EXPECT = RULES[host]
LINK = re.compile(re.escape(OLD) + rb'(?![\w.-])(/[^"\'\s<>)\\]*)?')
TEXT = ('.html', '.js', '.css', '.json', '.xml', '.txt')


def exists(path):
    p = urllib.parse.unquote(path.split('#')[0].split('?')[0]).lstrip('/')
    cands = ['index.html'] if p == '' else [p + 'index.html'] if p.endswith('/') else [p, p + '.html', p + '/index.html']
    return any(os.path.isfile(os.path.join('site', c)) for c in cands)


writes, kept, binary = {}, collections.Counter(), collections.Counter()
paths = collections.Counter()
for r, _, fs in os.walk('site'):
    for f in fs:
        p = os.path.join(r, f)
        b = open(p, 'rb').read()
        if OLD not in b:
            continue
        if not f.endswith(TEXT):
            binary[p] = len(LINK.findall(b))
            continue

        def sub(m):
            path = (m.group(1) or b'').decode('utf-8', 'replace')
            if exists(path):
                paths[path] += 1
                return NEW + (m.group(1) or b'')
            kept[path] += 1
            return m.group(0)
        new = LINK.sub(sub, b)
        if new != b:
            writes[p] = new
n = sum(paths.values())
print(f'{host}: {OLD.decode()} -> {NEW.decode()}: {n} links in {len(writes)} text files, expected {EXPECT}')
for k, v in paths.most_common():
    print(f'  {v:5} {k or "(bare host)"}')
if kept:
    print(f'left alone (target not in site/): {sum(kept.values())}', dict(kept))
if binary:
    print('left alone (binary files):', dict(binary))
if (len(writes), n) != EXPECT:
    sys.exit('COUNT MISMATCH: stop and report' + ('; nothing written' if APPLY else ''))
if APPLY:
    for p, new in writes.items():
        open(p, 'wb').write(new)
    lines = ['## Old-host links rewritten', '',
             f'In Phase B of the olddroplet migration (R3, 2026-10-24), `python3 -I rewrite_links.py {host} --apply` rewrote {n:,} links '
             f'in {len(writes):,} files from `{OLD.decode()}/…` to `{NEW.decode()}/…`. Only links whose target is in `site/` were changed:', '']
    lines += [f'* `{k or "/"}` ({v:,})' for k, v in sorted(paths.items())]
    if kept or binary:
        lines += ['', 'Left as they were: ' + '; '.join([f'`{k}` ({v}, not in the archive)' for k, v in sorted(kept.items())] +
                                                       [f'{v} in `{p[5:]}` (binary file)' for p, v in sorted(binary.items())]) + '.']
    lines.append('')
    section = '\n'.join(lines)
    r = open('README.md').read()
    i = min([j for j in (r.find('\n## External dependencies mirrored\n'), r.find('\n## Analytics removed\n'), r.find('\n## Hosting\n'),
                         r.find('\n## Secret scan')) if j >= 0] or [len(r)])
    open('README.md', 'w').write(r[:i + 1] + section + '\n' + r[i + 1:] if i < len(r) else r.rstrip('\n') + '\n\n' + section)
    print('written')
