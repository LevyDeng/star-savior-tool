(function () {
  if (location.protocol !== 'https:' || location.hostname !== 'ss.espr.gg') return null;
  let stream = '';
  for (const script of document.scripts) {
    const text = script.textContent.trim();
    if (!text.startsWith('self.__next_f.push(')) continue;
    try {
      const chunk = JSON.parse(text.slice(text.indexOf('(') + 1, text.lastIndexOf(')')));
      if (chunk[0] === 1 && typeof chunk[1] === 'string') stream += chunk[1];
    } catch (_) { /* Incomplete streaming chunks are retried on the next poll. */ }
  }
  const start = stream.indexOf('{"events":');
  if (start < 0) return null;
  let depth = 0, quoted = false, escaped = false;
  for (let i = start; i < stream.length; i++) {
    const c = stream[i];
    if (quoted) {
      if (escaped) escaped = false;
      else if (c === '\\') escaped = true;
      else if (c === '"') quoted = false;
    } else if (c === '"') quoted = true;
    else if (c === '{' || c === '[') depth++;
    else if (c === '}' || c === ']') {
      if (--depth === 0) {
        const data = JSON.parse(stream.slice(start, i + 1));
        if (!Array.isArray(data.events) || !data.events.length || !Array.isArray(data.tiers)) return null;
        return JSON.stringify(data, (key, value) => key === 'search' ? undefined : value === '$undefined' ? null : value);
      }
    }
  }
  return null;
})()
