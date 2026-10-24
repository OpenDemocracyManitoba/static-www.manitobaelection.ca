# www.manitobaelection.ca (static archive)

Static HTML copy of **www.manitobaelection.ca**, Open Democracy Manitoba's guide to the 2023 Manitoba provincial election. It ran on WordPress 5.9.7, with the ElectionData-V2 theme supplied by the Inform-Your-Vote-Wordpress-Plugin. It was crawled from olddroplet (`odm-nginx-ruby-php-2018`, 159.203.24.194) on 2026-10-24, before the server was retired. The apex `manitobaelection.ca` 301'd to this host.

* `site/` holds the crawl: 1,799 files, after the transform commit described below.
* `transform.py` is the script that made the second commit.
* `crawl.log.gz` holds the wget log.

The WordPress source (web root `/var/www/manitobaelection.ca/2023`), the DB dump (`2023_manitobaelection_ca`) and the nginx vhost are in the private repo `OpenDemocracyManitoba/archive-www.manitobaelection.ca`.

## How it was crawled

The crawl ran from a workstation against the origin directly (an `/etc/hosts` entry, bypassing Cloudflare). wp-cron was disabled and the site was frozen first.

```
wget --mirror --page-requisites --adjust-extension --restrict-file-names=windows \
     --no-host-directories --directory-prefix=site \
     -e robots=off --wait=0.1 --user-agent='ODM-archiver/1.0' \
     --reject-regex='(/wp-json|[?&]rest_route=|xmlrpc\.php|wp-login\.php|/wp-admin|[?&]replytocom=|/feed/?$|/trackback/?$|[?&]s=|/candidates/[^/]+/[0-9]+/|[?&]p=[0-9]+)' \
     -o crawl.log https://www.manitobaelection.ca/
```

* It ran on 2026-10-24, 12:28–12:37 CDT, and saved 1,835 files. wget exited 8 because some URLs returned 404.
* The last two reject patterns skip a crawler trap and WordPress `/?p=N` shortlinks:
  * `/candidates/<slug>/<N>/` is WordPress's path form of a paged candidate page. See the 2016 archive for the details. This site's pager uses its own `pagenum` parameter, so nothing links to that form here.
  * `/?p=N` shortlinks are duplicates of pages saved at their real paths, so they aren't archived (owner decision, 2026-10-24).
* There is no `--convert-links`, so the saved HTML keeps its original absolute `https://www.manitobaelection.ca/…` hrefs. The pagers use root-relative ones.
* The site-verification files (`google193ca….html`, `BingSiteAuth.xml`), `.htpasswd` and `wp-content/debug.log` are not linked from anywhere and are not in the crawl.

Three files are referenced only where wget doesn't look, so they were copied in from the source tree:

* `wp-content/uploads/2023/07/cropped-cropped-mb_icon-270x270.jpg` (icon `<meta>` tags);
* `wp-includes/js/wp-emoji-release.min.js` (inline JS);
* `wp-content/themes/ElectionData/ElectionData-V2/js/html5.js` (an IE conditional comment).

On the server, `wp-content/themes/ElectionData` is a symlink to `wp-content/plugins/Inform-Your-Vote-Wordpress-Plugin/theme/`, so `html5.js` was taken from there.

## Changes made on the live site before the crawl

The DB wasn't modified. The private archive repo has the untouched source and dump.

* **wp-cron disabled** (`DISABLE_WP_CRON`, and nginx returns 403 for `/wp-cron.php`). This stopped the news scraper.
* **`WP_HOME` / `WP_SITEURL` set to `https://www.manitobaelection.ca`** in `wp-config.php`. The DB's `home` was `http://www.manitobaelection.ca`.

No paging fix was needed: this site's news pager uses its own `pagenum` query variable, which WordPress doesn't redirect. There was no page cache, and no news cutoff was needed: the newest article is from October 2023, the month of the election (2023-10-03).

## Completeness

|Check|Result|
|-|-|
|Candidate pages|189 of 189 published `ed_candidates`|
|Paginated candidates|35, with 314 extra news pages. None missing, none identical to page 1.|
|Paginated parties|4 (Green, Liberal, NDP, PC), with 211 extra news pages. None missing, none duplicated.|
|News|2,047 of the 2,060 distinct approved news URLs appear on some page (details below)|
|Questionnaire answers|11 of 11 question/answer pairs, on 11 candidate pages. The DB has 13 non-empty `ed_answers` out of 203; the other 2 are the PC Party's answers, shown on `parties/pc/`.|
|Uploads|Every referenced `wp-content/uploads/` file on this host is in the crawl. The crawl holds 989 of the 1,164 files in the source uploads tree; the rest aren't linked from any page.|
|Asset CDNs|no `i0.wp.com` / `c0.wp.com` references|

**News.** There is no paginated news archive on this site: `news_articles/` shows the latest 90 items, and older news is reachable through the candidate and party pages.

The plugin moderates news, and only `approved` articles were ever shown. Of the 2,879 published articles, 2,062 are approved (2,060 distinct URLs) and 817 are `rejected`.

2,047 of them appear in the crawl. The other 13 couldn't be reached on the live site either. The cause is in the theme's `display_news_summaries()`, and **it's archived as is** (owner decision, 2026-10-24): the pager computes `total = round(count / 10)`, so a candidate's last page is never linked when it would hold fewer than 5 articles. For example, Kevin Klein has 142 articles but 14 pages, and Scott Johnston has 33 but 3. The same function skips an article that has no summary for that candidate, so some pages can show fewer than 10 items.

The candidate pages carry the theme's notice "Showing news articles published after June 1st 2023". That's only text: `get_news()` has no date filter.

**404s:** only `wp-content/themes/ElectionData/ElectionData-V2/ipad4/arrow.gif` and `arrowl.gif`, which are referenced by the theme CSS and missing on the live site too.

## Links to other hosts

* **This site over plain http.** 3 files link to `http://www.manitobaelection.ca/…`: `about-manitobaelection-ca/` links to `/press-mentions/` and `/press-releases/`, and `frequently-asked-questions/` (and its slashless copy) to `/about-manitobaelection-ca/` and `/frequently-asked-questions/`. All four pages are in the archive; only the scheme is old.
* `about-manitobaelection-ca/` also links to `http://2023.manitobaelection.ca/wp-admin/frequently-asked-questions`, a broken link in the page content (that host was never served from here, and `/wp-admin` is blocked), and to `http://winnipegelection.ca`.
* `press-releases/` (and its slashless copy) links to 6 files on `2016.manitobaelection.ca`: older press-release PDFs and images. All of them are in the 2016 static archive.

There were no references to `upcoming.manitobaelection.ca` or `159.203.24.194`.

## wget quirk, left as is

`frequently-asked-questions.html`, `press-mentions.html` and `press-releases.html` at the root are wget's saves of slashless links (e.g. `/press-releases`). The server 301'd each one to the slash form, and wget saved the redirect target under the slashless name. Static hosting with `auto-trailing-slash` serves `/press-releases` from `press-releases.html`.

## Commits and URL mapping

The repo has two commits:

1. **Raw crawl.** `--restrict-file-names=windows` saved each URL's `?` as `@`.
2. **Path-based URLs** (owner decision, 2026-10-24), made by `python3 -I transform.py www.manitobaelection.ca --apply`:

|Old URL (live site)|Crawl file (commit 1)|Now|
|-|-|-|
|`/candidates/<slug>/?pagenum=N#news`|`candidates/<slug>/index.html@pagenum=N.html`|`candidates/<slug>/page/N/index.html` (314 files; 35 candidates)|
|`/parties/<slug>/?pagenum=N#news`|`parties/<slug>/index.html@pagenum=N.html`|`parties/<slug>/page/N/index.html` (211 files; 4 parties)|
|`…/?pagenum=1#news`|`…/index.html@pagenum=1.html` (39 files)|dropped: identical to `…/index.html`, apart from cache comments|
|`<file>?ver=X`|`<file>@ver=X`, `<file>@ver=X.css`|`<file>` (9 files; no plain copy existed)|

No URL combines `pagenum` with another query parameter, so every pager link mapped cleanly. The `&pagenum=N` URLs in the server's access log weren't linked from any crawled page.

The transform also rewrote the links in the HTML:
* 6,144 pager links: `?pagenum=N` → `page/N/`, keeping `#news`, and `?pagenum=1` → the bare path.
* 6,474 cache-buster query strings stripped, including the JSON-escaped emoji-loader URL.
* 513 `<link rel='shortlink'>` tags removed.

Only the external Font Awesome stylesheet keeps a `?ver=`. The transform only rewrites a link when its new target is in `site/`, and it never overwrites a file.

**No `@` files are left.** An internal-link check finds **0 unresolved out of 133,587**. It covers every `https://www.manitobaelection.ca/…`, root-relative or `url()` reference, ignores the blocked `/wp-json` and `xmlrpc.php` links, and counts `/foo` → `foo.html` as resolved.

**For the hosting phase:** 301 `?pagenum=N` (alone or alongside other parameters) to `…/page/N/` (`N=1` → the bare path), and http → https. Query strings on assets need no rule.

## Old-host links rewritten

In Phase B of the olddroplet migration (R3, 2026-10-24), `python3 -I rewrite_links.py www.manitobaelection.ca --apply` rewrote 6 links in 3 files from `http://www.manitobaelection.ca/…` to `https://www.manitobaelection.ca/…`. Only links whose target is in `site/` were changed:

* `/about-manitobaelection-ca/` (2)
* `/frequently-asked-questions/` (2)
* `/press-mentions/` (1)
* `/press-releases/` (1)

## External dependencies mirrored

In Phase B of the olddroplet migration (R4, 2026-10-24), the stylesheets every page needs to render were copied into `site/_ext/` by `python3 -I mirror_deps.py www.manitobaelection.ca --apply`, and the pages now load the copies (root-relative links):

* `https://use.fontawesome.com/releases/v5.1.1/css/all.css` → `/_ext/use.fontawesome.com/releases/v5.1.1/css/all.css` (794 HTML files), with its webfonts, byte-identical
* `https://fonts.googleapis.com/css?family=Libre+Franklin%3A400%2C700` → `/_ext/fonts.googleapis.com/css/libre-franklin-400-700.css` (794 HTML files), with its `woff2` files; the CSS (fetched as a current Chrome) points at the copies under `/_ext/fonts.gstatic.com/`
* the `dns-prefetch` hints for `fonts.googleapis.com` and `use.fontawesome.com` were removed (794 HTML files)

Font Awesome Free is under the Font Awesome Free License (fonts SIL OFL 1.1, CSS MIT); Libre Franklin is under the SIL OFL 1.1. Other third-party scripts and embeds were left as they were.

## Analytics removed

Google Tag Manager / Google Analytics (and the Google Ads tag that rides on `gtag.js`) were removed in Phase B of the olddroplet migration (owner decision D7, 2026-10-24) by `python3 -I strip_analytics.py www.manitobaelection.ca --apply`. Files changed: 794 HTML files. IDs: `G-PGEKPCB44B`. Each loader went together with its inline block and the comment around it. Other third-party scripts (fonts, embeds, Jetpack stats) were left as they were.

Snippet shapes removed (IDs and whitespace normalised):

* 794 ×

  ```html
  <!-- Google tag (gtag.js) --> <script async src="https://www.googletagmanager.com/gtag/js?id=<ID>"></script> <script> window.dataLayer = window.dataLayer || []; function gtag(){dataLayer.push(arguments);} gtag('js', new Date()); gtag('config', '<ID>'); </script>
  ```

## Secret scan

The Phase A §7.2 scan was run over `site/` and found nothing. It checks for:

* no `.git`, `.env`, `.ftpconfig`, `.htpasswd`, `debug.log`, `*.php` or `*.sql*` files;
* no `DB_PASSWORD`, `AUTH_KEY`, `SECURE_AUTH`, private keys, `phpinfo()` or `mysql(i)_connect` in any text file;
* no `*.php.html` pages.
