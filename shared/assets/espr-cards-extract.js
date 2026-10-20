(function () {
  if (location.protocol !== 'https:' || location.hostname !== 'ss.espr.gg') return null;
  if (document.readyState !== 'complete') return null;
  const cards = new Map();
  for (const link of document.querySelectorAll('a[href*="/database/arcanas/"]')) {
    const image = link.querySelector('img');
    if (!image || !image.alt.trim()) continue;
    const source = new URL(image.getAttribute('src') || '', location.origin);
    let url;
    try { url = new URL(source.pathname === '/_next/image' ? source.searchParams.get('url') : source.href); }
    catch (_) { continue; }
    if (url.protocol !== 'https:' || url.hostname !== 'ss.esprcdn.dev') continue;
    const found = /^\/images\/arcanas\/illustration\/(\d+)\.webp$/.exec(url.pathname);
    if (!found || url.search || url.hash) continue;
    const id = Number(found[1]);
    if (!Number.isSafeInteger(id) || id <= 0) continue;
    cards.set(id, {id, name: image.alt.trim(), image_url: url.href});
  }
  return cards.size ? JSON.stringify({cards: Array.from(cards.values())}) : null;
})()
