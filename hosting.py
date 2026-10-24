"""Phase B §4.1 / R9 / R11: write the Cloudflare Workers hosting files for a static-<host> repo.
Usage: python3 -I hosting.py <host> <stage>   (from the repo root)
  stage preview: workers.dev only, no routes        (before cutover)
  stage routed:  <host>/* route + workers.dev       (cutover, §7.1)
  stage final:   <host>/* route, workers_dev false  (after cutover, R11)
Writes wrangler.jsonc, .gitignore, worker.js (WordPress sites; copied from this script's directory),
site/404.html (R9; not on 2014, which has its own) and the README "## Hosting" section.
It refuses to overwrite a site/404.html that it didn't write."""
import os, re, shutil, sys

host, stage = sys.argv[1], sys.argv[2]
assert stage in ('preview', 'routed', 'final'), stage
DATE = '2026-10-24'   # compatibility_date: the day this was first deployed
WP = {'2016.manitobaelection.ca', '2018.winnipegelection.ca', '2019.manitobaelection.ca', '2022.winnipegelection.ca', 'www.manitobaelection.ca'}
OWN_404 = {'2014.winnipegelection.ca'}
APEX = {'www.manitobaelection.ca', 'www.winnipegelection.ca', 'www.opendemocracymanitoba.ca'}   # R7: zone has an apex -> www rule
zone = '.'.join(host.split('.')[-2:])
name = 'static-' + host.replace('.', '-')
wp = host in WP
MARK = b'<!-- written by hosting.py (Phase B R9) -->'

routes = '' if stage == 'preview' else f',\n  "routes": [{{ "pattern": "{host}/*", "zone_name": "{zone}" }}]'
main = '  "main": "worker.js",\n' if wp else ''
extra = '    "binding": "ASSETS",\n' if wp else ''
rwf = ',\n    "run_worker_first": ["/candidates/*", "/parties/*"]' if wp else ''
open('wrangler.jsonc', 'w').write(f'''// Cloudflare Workers static assets for {host}. Written by hosting.py; see README "Hosting".
{{
  "name": "{name}",
{main}  "compatibility_date": "{DATE}",
  "workers_dev": {"false" if stage == "final" else "true"},
  "preview_urls": false,
  "assets": {{
    "directory": "./site",
{extra}    "html_handling": "auto-trailing-slash",
    "not_found_handling": "404-page"{rwf}
  }}{routes}
}}
''')
open('.gitignore', 'w').write('.wrangler/\nnode_modules/\n')
if wp:
    src = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'worker.js')
    if os.path.abspath(src) != os.path.abspath('worker.js'):   # run from work/build: copy the master; run in the repo: keep its copy
        shutil.copyfile(src, 'worker.js')

if host not in OWN_404:
    p = 'site/404.html'
    if os.path.exists(p) and MARK not in open(p, 'rb').read():
        sys.exit(f'refusing to overwrite {p}')
    open(p, 'wb').write(f'''<!DOCTYPE html>
<html lang="en">
{MARK.decode()}
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Page not found | {host}</title>
<style>body{{font-family:system-ui,sans-serif;max-width:36rem;margin:4rem auto;padding:0 1rem;line-height:1.5;color:#222}}a{{color:#0645ad}}</style>
</head>
<body>
<h1>This page isn't in the archive</h1>
<p>{host} is an archived copy of the original site, kept by Open Democracy Manitoba. The page you asked for isn't part of it.</p>
<p><a href="/">Go to the {host} home page</a></p>
</body>
</html>
'''.encode())

wd = f'https://{name}.stungeye.workers.dev'
lines = [
    '## Hosting',
    '',
    f'Served from **Cloudflare Workers static assets** (Phase B of the olddroplet migration). `wrangler.jsonc`{", `worker.js`" if wp else ""}, `.gitignore`'
    f'{"" if host in OWN_404 else ", `site/404.html`"} and this section are written by `hosting.py` (`python3 -I hosting.py {host} <preview|routed|final>`).',
    '',
    f'* **Worker:** `{name}`, account `Stungeye@gmail.com\'s Account`.',
    '* **Deploy:** `npx wrangler@4.148.0 deploy` from the repo root. Only `site/` is uploaded.',
    f'* **Routes:** {"none yet (preview only)" if stage == "preview" else f"`{host}/*` on zone `{zone}`, over the existing proxied DNS record"}.',
    f'* **workers.dev:** {"off (R11)" if stage == "final" else wd}. Per-version preview URLs are off (`preview_urls: false`).',
    '* **Serving:** `html_handling: auto-trailing-slash` (`/foo` serves `foo.html`, `/foo/` serves `foo/index.html`; the other forms 307 to those) and '
    f'`not_found_handling: 404-page` ({"the site\'s own `404.html`" if host in OWN_404 else "`site/404.html`, a minimal page added in Phase B"}).',
]
if wp:
    lines += [
        '* **Worker script** (`worker.js`, runs only for `/candidates/*` and `/parties/*`): `?page=N` / `?pagenum=N` 301 to `…/page/N/` (`N` ≤ 1 → the bare path; '
        'other query parameters are dropped; a page past the end → the bare path), and `/candidates/<slug>/<N>/` 301s to `…/page/N/`. Everything else falls through to the assets.',
    ]
lines += [
    '* **http → https:** the zone setting "Always Use HTTPS" (301 at Cloudflare\'s edge).',
    f'* **Redirect rules:** {(f"the `{zone}` zone has a Single Redirect rule: `http.host eq \"{zone}\"` → `concat(\"https://{host}\", http.request.uri.path)`, query string kept, 301" + (" (created in the dashboard at cutover)." if stage == "preview" else ".")) if host in APEX else "none."}',
    '* **Rollback:** while the old origin is up, remove `routes` from `wrangler.jsonc` and deploy (or delete the route in the dashboard); the origin serves again at once. '
    'A bad version can be rolled back with `npx wrangler@4.148.0 rollback`.',
    '',
]
section = '\n'.join(lines)
r = open('README.md').read()
if '\n## Hosting\n' in r:
    r = re.sub(r'\n## Hosting\n.*?(?=\n## |\Z)', '\n' + section.rstrip('\n') + '\n', r, flags=re.S)
else:
    i = r.find('\n## Secret scan')
    r = r[:i + 1] + section + '\n' + r[i + 1:] if i >= 0 else r.rstrip('\n') + '\n\n' + section
open('README.md', 'w').write(r)
print(f'{host}: stage {stage}; wrote wrangler.jsonc, .gitignore{", worker.js" if wp else ""}{"" if host in OWN_404 else ", site/404.html"}, README Hosting')
