// Phase B §4.2: legacy pagination redirects for the WordPress static archives; everything else is a static asset.
// Runs only for run_worker_first paths (/candidates/*, /parties/*). Master copy: olddroplet migration work/build/worker.js.

async function exists(env, url, path) {
  const r = await env.ASSETS.fetch(new URL(path, url));
  return r.status === 200;
}

function moved(url, path) {
  return Response.redirect(new URL(path, url).toString(), 301);
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    // 1. ?page=N / ?pagenum=N -> …/page/N/ (N <= 1 -> the bare path); every other query parameter is dropped
    const q = url.searchParams.get('page') ?? url.searchParams.get('pagenum');
    if (q !== null && /^\d+$/.test(q)) {
      const n = parseInt(q, 10);
      let base = url.pathname.replace(/page\/\d+\/?$/, '');
      if (!base.endsWith('/')) base += '/';
      const target = n <= 1 ? base : `${base}page/${n}/`;
      if (await exists(env, url, target)) return moved(url, target);
      if (target !== base && await exists(env, url, base)) return moved(url, base);
    }

    // 2. /candidates/<slug>/<N>/ (WordPress's own paged form) -> …/page/N/, unless an asset lives there
    const m = url.pathname.match(/^\/candidates\/([^/]+)\/(\d+)\/?$/);
    if (m && !(await exists(env, url, url.pathname))) {
      const n = parseInt(m[2], 10);
      const target = n <= 1 ? `/candidates/${m[1]}/` : `/candidates/${m[1]}/page/${n}/`;
      if (await exists(env, url, target)) return moved(url, target);
    }

    // 3. everything else
    return env.ASSETS.fetch(request);
  },
};
