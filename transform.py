"""Path-based pagination, ?ver= normalisation and shortlink-tag removal for a crawled WordPress
static archive (Phase A plan §7.1, owner decisions 2026-10-24).

Usage, from the repo root:  python3 -I transform.py <host> [--apply]
Without --apply it only prints what it would do. With --apply it rewrites site/ in place.

1. Files. wget --restrict-file-names=windows saved `?` as `@`:
   * <dir>/index.html@page=N.html, @pagenum=N  ->  <dir>/page/N/index.html  (N=1 -> <dir>/index.html,
     or dropped if that already exists with the same content)
   * <file>@ver=X (and <file>.css@ver=X.css, where --adjust-extension added `.css`)  ->  <file>.
     Bare-number cache-busters on CSS/JS (<file>.css@3.css, <file>.js@17, from hand-written `?3` / `?17`) are treated the same.
     If <file> already exists: identical -> the @ copy is dropped; different -> both are left and flagged.
   * anything else with `@` (other query strings) is left as it is and listed.
   It refuses to overwrite: if any target exists (and isn't an identical copy, as above), or two
   files map to the same target, nothing is changed.
2. Links, in every HTML and CSS file (byte-level: some pages contain truncated UTF-8 from the live site):
   * https://<host>/<dir>/?page=N#frag (or ?pagenum=N, or root-relative /<dir>/?page=N)  ->  .../<dir>/page/N/#frag;
     N=1 -> .../<dir>/#frag. Only when the query is that one parameter and the target file exists.
   * <link rel="canonical" href=".../candidates/<slug>/<N>/">  ->  .../candidates/<slug>/page/N/  (WP's path form
     of a paged candidate page; the /N/ copies were a crawler trap and aren't in the archive).
   * ?ver=X (and a bare ?N on .css/.js) is stripped from URLs on <host> (also JSON-escaped https:\\/\\/<host>\\/...),
     and from relative href/src URLs (resolved against the page's directory), when the plain file exists.
   * every <link rel='shortlink' ...> tag is removed (the /?p=N shortlink pages aren't archived).
   Links are only rewritten when the new target is in site/, so nothing is pointed at a missing file.
3. Forminator (owner decision 2026-10-24, 2019): a page's Forminator feedback form is replaced by a note that
   feedback closed after the election, keeping the form's own HTML text field minus its "Please use this form"
   line; the form's <link>/<script> tags are removed, and wp-content/{plugins,uploads}/forminator/ is deleted.
4. Party pages (owner decision 2026-10-24, 2019): on parties/* pages, news pager blocks that link ?page=N are
   removed (the party template reads `paged`, so ?page=N always showed page 1). The @page=N copies are still
   moved as in 1. Pagers that link the path form (/page/N/, 2016) are left alone.
"""
import collections, os, re, sys

host = sys.argv[1]
apply = '--apply' in sys.argv[2:]
SITE = 'site'
if not os.path.isdir(SITE):
    raise SystemExit('run from the repo root (no site/ here)')
H = re.escape(host.encode())

PAGE_FILE = re.compile(r'^index\.html@(page|pagenum)=(\d+)\.html$')
VER_FILE = re.compile(r'^(.+?)@ver=([^&@]+)$')
BUST_FILE = re.compile(r'^(.+\.(?:css|js))@(\d+(?:\.css)?)$')   # hand-written ?N cache-buster
CACHE_COMMENT = re.compile(rb'<!-- (Dynamic page generated|Cached page generated|super cache|Compression = )[^>]*-->\s*')


def norm(data):   # page content minus WP-Super-Cache's per-request comments
    return CACHE_COMMENT.sub(b'', data)


def same(a, b, html):
    da, db = open(a, 'rb').read(), open(b, 'rb').read()
    return norm(da) == norm(db) if html else da == db


# ---- 1. plan the file moves -------------------------------------------------------------------
FORMINATOR_DIRS = tuple(os.path.join(SITE, 'wp-content', d, 'forminator') + os.sep for d in ('plugins', 'uploads'))
removes = sorted(os.path.join(r, f) for r, _, fs in os.walk(SITE) for f in fs
                 if os.path.join(r, f).startswith(FORMINATOR_DIRS))
moves, drops, flagged, unmapped = [], [], [], []
for root, dirs, files in os.walk(SITE):
    for f in files:
        if '@' not in f:
            continue
        src = os.path.join(root, f)
        if src.startswith(FORMINATOR_DIRS):
            continue
        m = PAGE_FILE.match(f)
        if m:
            n = int(m.group(2))
            dst = os.path.join(root, 'index.html') if n == 1 else os.path.join(root, 'page', str(n), 'index.html')
            if n == 1 and os.path.exists(dst):
                (drops if same(src, dst, True) else flagged).append((src, dst))
            else:
                moves.append((src, dst))
            continue
        m = VER_FILE.match(f) or BUST_FILE.match(f)
        if m:
            base, ver = m.groups()
            for ext in ('.css', '.html'):   # suffix added by --adjust-extension
                if ver.endswith(ext) and base.endswith(ext):
                    ver = ver[:-len(ext)]
            if ver.endswith(('.css', '.html')):
                unmapped.append((src, 'adjust-extension suffix does not match the file name'))
                continue
            dst = os.path.join(root, base)
            if os.path.exists(dst):
                (drops if same(src, dst, False) else flagged).append((src, dst))
            else:
                moves.append((src, dst))
            continue
        unmapped.append((src, 'query string not handled'))

# several @ver copies of one file: identical ones collapse to one move, different ones are flagged
by_dst = collections.defaultdict(list)
for s, d in moves:
    by_dst[d].append(s)
moves = []
for d, ss in sorted(by_dst.items()):
    ss.sort()
    if len(ss) == 1:
        moves.append((ss[0], d))
    elif all(same(ss[0], s, False) for s in ss[1:]) and not PAGE_FILE.match(os.path.basename(ss[0])):
        moves.append((ss[0], d))
        drops += [(s, d) for s in ss[1:]]
    else:
        flagged += [(s, d) for s in ss]

conflicts = [(s, d) for s, d in moves if os.path.exists(d)]
if conflicts:
    for s, d in conflicts:
        print('CONFLICT: target exists:', d, '<-', s)
    raise SystemExit('refusing to overwrite; nothing changed')
flag_dst = {d for _, d in flagged}   # hrefs to these keep their ?ver=

# ---- 2. link rewriting --------------------------------------------------------------------------
after = {d for _, d in moves} | {os.path.join(r, f) for r, _, fs in os.walk(SITE) for f in fs}
after -= {s for s, _ in moves} | {s for s, _ in drops} | set(removes)


def exists(path):   # path is a URL path, bytes
    return os.path.join(SITE, path.decode('utf-8', 'replace').lstrip('/')) in after


PAGE_URL = re.compile(rb'(?P<pre>["\'(=])(?P<origin>https?://' + H + rb')?(?P<path>/[^"\'\s<>?#]*)?'
                      rb'\?(?:page|pagenum)=(?P<n>\d+)(?P<frag>#[^"\'\s<>]*)?(?=["\'\s<>)])')
CANON = re.compile(rb'(<link rel=["\']canonical["\'] href=["\'](?:https?://' + H + rb')?/candidates/[^/"\']+/)(\d+)/(["\'])')
VER_URL = re.compile(rb'(?P<url>(?:https?:(?:\\?/){2}' + H + rb')?(?P<path>(?:\\?/)[^"\'\s<>?#()]*))'
                     rb'\?(?P<q>ver=[A-Za-z0-9._-]+|\d+)(?=["\'\s<>)#\\])')
REL_URL = re.compile(rb'(?P<pre>(?:href|src)=["\'])(?P<path>(?![A-Za-z][A-Za-z0-9+.-]*:|/|#)[^"\'\s<>?#]+)'
                     rb'\?(?P<q>ver=[A-Za-z0-9._-]+|\d+)(?=["\'])')
SHORT_LINE = re.compile(rb'(?m)^[ \t]*<link rel=["\']shortlink["\'][^>]*>[ \t]*\r?\n')
SHORT_TAG = re.compile(rb'<link rel=["\']shortlink["\'][^>]*>')
FM_FORM = re.compile(rb'<form\s+id="forminator-module-\d+".*?</form>', re.S)
FM_TEXT = re.compile(rb'<div class="forminator-field forminator-merge-tags"><label class="forminator-label">[^<]*</label>'
                     rb'(.*?)</div></div></div>(?=<div class="forminator-row">|</form>)', re.S)
FM_ASK = re.compile(rb'<div>(?:(?!</div>).)*Please use this form(?:(?!</div>).)*</div>\s*', re.S)
FM_SPACERS = re.compile(rb'^(?:\s*<div>(?:\s|&nbsp;|\xc2\xa0)*</div>)+\s*')
FM_JUNK = re.compile(rb'<div class="forminator-ui forminator-custom-form[^"]*"[^>]*data-form="forminator-module-\d+"><br/></div>'
                     rb'|<link rel=\'stylesheet\' id=\'forminator-[^\']*\'[^>]*/>[ \t]*\r?\n?'
                     rb'|<script\b[^>]*\bid=\'forminator-[^\']*\'[^>]*>.*?</script>[ \t]*\r?\n?'
                     rb'|<script type="text/javascript">(?:(?!</script>).)*[Ff]orminator(?:(?!</script>).)*</script>[ \t]*\r?\n?', re.S)
YEAR = re.match(r'(\d{4})\.', host)
FM_NOTE = (b'<div class="odm-archive-note"><p><strong>Feedback for this site closed after the '
           + (YEAR.group(1).encode() + b' ' if YEAR else b'') + b'election.</strong></p>')
PAGER = re.compile(rb'(?:<(span|a)\b[^>]*class="[^"]*\bpage-numbers\b[^"]*"[^>]*>.*?</\1>\s*)+(?:<br><br>)?', re.S)
stats = collections.Counter()


def forminator_sub(m):
    t = FM_TEXT.search(m.group(0))
    text = FM_SPACERS.sub(b'', FM_ASK.sub(b'', t.group(1))) if t else b''
    stats['forminator forms replaced by a note'] += 1
    return FM_NOTE + text + b'</div>'


def pager_sub(m):
    if b'?page=' not in m.group(0):
        return m.group(0)
    stats['party ?page= pager blocks removed'] += 1
    return b''


def page_sub(m):
    path, n = m.group('path') or b'/', int(m.group('n'))
    if not path.endswith(b'/'):
        stats['page links left (path is not a directory)'] += 1
        return m.group(0)
    new = path if n == 1 else path + b'page/%d/' % n
    if not exists(new + b'index.html'):
        stats['page links left (no saved page)'] += 1
        return m.group(0)
    stats['page links rewritten'] += 1
    return m.group('pre') + (m.group('origin') or b'') + new + (m.group('frag') or b'')


def canon_sub(m):
    rel = re.sub(rb'^.*?(/candidates/)', rb'\1', m.group(1))
    if not exists(rel + b'page/' + m.group(2) + b'/index.html'):
        stats['candidate /N/ canonicals left (no saved page)'] += 1
        return m.group(0)
    stats['candidate /N/ canonicals rewritten'] += 1
    return m.group(1) + b'page/' + m.group(2) + b'/' + m.group(3)


def bare_ok(m, path):   # a bare ?N only counts as a cache-buster on CSS/JS
    return m.group('q').startswith(b'ver=') or path.endswith((b'.css', b'.js'))


def ver_sub(m):
    path = m.group('path').replace(b'\\/', b'/')
    if not m.group('url').startswith((b'http', b'/', b'\\/')) or not bare_ok(m, path) or not exists(path) \
            or os.path.join(SITE, path.decode('utf-8', 'replace').lstrip('/')) in flag_dst:
        stats['?ver= left (no plain file, or flagged)'] += 1
        return m.group(0)
    stats['?ver= stripped'] += 1
    return m.group('url')


def rel_sub(page):
    def sub(m):
        path = m.group('path')
        tgt = os.path.normpath(os.path.join(os.path.dirname(page), path.decode('utf-8', 'replace')))
        if not bare_ok(m, path) or tgt not in after or tgt in flag_dst:
            stats['?ver= left (no plain file, or flagged)'] += 1
            return m.group(0)
        stats['?ver= stripped'] += 1
        return m.group('pre') + path
    return sub


def is_text_page(p):
    if p.endswith(('.html', '.css')):
        return True
    if os.path.splitext(p)[1] == '':   # e.g. wget's plain-file save of a 301'd directory URL
        head = open(p, 'rb').read(512).lower()
        return b'<html' in head or b'<!doctype html' in head
    return False


pages = sorted(p for p in after if is_text_page(p))
src_of = {d: s for s, d in moves}   # before --apply, read moved files from their old path
changed = {}
for p in pages:
    data = open(src_of.get(p, p), 'rb').read()
    new = data
    if FM_FORM.search(new):
        new = FM_JUNK.sub(b'', FM_FORM.sub(forminator_sub, new))
    if p.startswith(os.path.join(SITE, 'parties') + os.sep):
        new = PAGER.sub(pager_sub, new)
    new = PAGE_URL.sub(page_sub, new)
    new = CANON.sub(canon_sub, new)
    if b'?' in new:
        new = VER_URL.sub(ver_sub, new)
        new = REL_URL.sub(rel_sub(p), new)
    k = len(SHORT_TAG.findall(new))
    if k:
        stats['shortlink tags removed'] += k
        new = SHORT_TAG.sub(b'', SHORT_LINE.sub(b'', new))
    if new != data:
        changed[p] = new

# ---- 3. report, then apply ----------------------------------------------------------------------
kind = lambda s: re.sub(r'\d+', 'N', os.path.basename(s).split('@', 1)[1]) if '@' in s else s
print(f'{host}: {"APPLY" if apply else "dry run"}')
print(f'  file moves: {len(moves)}', dict(collections.Counter(kind(s) for s, _ in moves)))
print(f'  @ copies dropped (identical plain/page-1 file exists): {len(drops)}')
for s, d in drops:
    print('    ', s)
print(f'  flagged (left as they are, content differs): {len(flagged)}')
for s, d in flagged:
    print('    ', s, '!=', d)
print(f'  unmapped @ files (left as they are): {len(unmapped)}')
for s, why in sorted(unmapped):
    print('    ', s, f'({why})')
print(f'  forminator files deleted: {len(removes)}')
print(f'  pages rewritten: {len(changed)}')
for k, v in sorted(stats.items()):
    print(f'  {k}: {v}')

if apply:
    for s, d in moves:
        os.makedirs(os.path.dirname(d), exist_ok=True)
        if os.path.exists(d):
            raise SystemExit(f'target appeared: {d}')
        os.rename(s, d)
    for s, _ in drops:
        os.remove(s)
    for s in removes:
        os.remove(s)
    for d in FORMINATOR_DIRS:
        for r, _, _ in sorted(os.walk(d), reverse=True):   # deepest first; only empty dirs go
            os.rmdir(r)
    for p, data in changed.items():
        with open(p, 'wb') as fh:
            fh.write(data)
    print('  applied.')
