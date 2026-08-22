/** Parte URIs pegadas en una línea o unidas por coma, sin romper query strings. */
const URI_SPLIT = /[\s,]+(?=https?:\/\/)/i

export function parseRedirectUris(text: string): string[] {
  const seen = new Set<string>()
  const result: string[] = []
  for (const part of text.split(URI_SPLIT)) {
    const cleaned = part.trim().replace(/^,+|,+$/g, "").trim()
    if (!cleaned || seen.has(cleaned)) continue
    seen.add(cleaned)
    result.push(cleaned)
  }
  return result
}

export function urisToText(uris: unknown): string {
  const raw = Array.isArray(uris)
    ? uris.filter((u): u is string => typeof u === "string").join("\n")
    : typeof uris === "string"
      ? uris
      : ""
  return parseRedirectUris(raw).join("\n")
}
