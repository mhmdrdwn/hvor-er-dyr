// Cache the whole app, including every sound, so it works offline (on a plane, Wi-Fi off).
// Bump VERSION whenever you change a file so devices pick up the update.
const VERSION = "dyrene-v5";
const CORE = ["./", "index.html", "content.json", "manifest.webmanifest", "icon.svg", "icon-512.png"];

// Same file naming as tools/build_audio.py and index.html.
function audioFiles(c) {
  const files = [
    ...c.praise.map((_, i) => `voice/praise_${i}.m4a`),
    ...c.end.map((_, i) => `voice/end_${i}.m4a`),
  ];
  for (const s of c.scenes) {
    files.push(`voice/intro_${s.id}.m4a`);
    for (const a of s.animals) {
      files.push(`sounds/${a.id}.m4a`, `voice/ask_${a.id}.m4a`, `voice/is_${a.id}.m4a`, `voice/line_${a.id}.m4a`);
    }
  }
  return files;
}

self.addEventListener("install", (e) => {
  e.waitUntil((async () => {
    const cache = await caches.open(VERSION);
    await cache.addAll(CORE);
    const content = await (await cache.match("content.json")).json();
    // Cache sounds one by one, so one missing file never blocks the update.
    await Promise.all(audioFiles(content).map((f) => cache.add(f).catch(() => {})));
    await self.skipWaiting();
  })());
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== VERSION).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

// The page and content.json: network first, so updates show up at once; cache when offline.
// Sounds and icons: cache first (they rarely change), and remember anything new.
self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin) return;
  const fresh = e.request.mode === "navigate" || url.pathname.endsWith(".html") || url.pathname.endsWith("content.json");
  e.respondWith(fresh ? networkFirst(e.request) : cacheFirst(e.request));
});

async function networkFirst(req) {
  const cache = await caches.open(VERSION);
  try {
    const res = await fetch(req, { cache: "no-store" });
    if (res.ok) cache.put(req, res.clone());
    return res;
  } catch {
    return (await cache.match(req, { ignoreSearch: true })) || cache.match("index.html");
  }
}

async function cacheFirst(req) {
  const hit = await caches.match(req, { ignoreSearch: true });
  if (hit) return hit;
  const res = await fetch(req);
  if (res.ok) (await caches.open(VERSION)).put(req, res.clone());
  return res;
}
