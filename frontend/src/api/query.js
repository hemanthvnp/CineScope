import api from "./axios"

// filters (all optional, any combination): { genres: [name|id], language, year, yearFrom, yearTo,
//   era, minRating, platforms: [name], country }. `q` may be empty when filters are given.
// conversation: the `conversation` of the previous response, to ask a follow-up to it.
const buildBody = ({ q = "", filters, conversation, locale = "US", maxResults = 10, includeProviders = true, includeSynthesis = false }) => {
  const body = {
    q,
    locale,
    options: {
      max_results: maxResults,
      include_providers: includeProviders,
      include_synthesis: includeSynthesis,
    },
  }

  if (conversation) body.conversation = conversation

  if (filters) {
    const { genres, genre, language, year, yearFrom, yearTo, era, minRating, platforms, country } = filters
    const genreList = genres ?? (genre ? [genre] : [])
    body.filters = {
      genres: genreList.map(String),
      language: language || null,
      year: year ? Number(year) : null,
      year_from: yearFrom ? Number(yearFrom) : null,
      year_to: yearTo ? Number(yearTo) : null,
      era: era || null,
      min_rating: minRating != null && minRating !== "" ? Number(minRating) : null,
      platforms: platforms || [],
      country: country || null,
    }
  }
  return body
}

export const aiQuery = async ({ timeout, ...params }) => {
  const response = await api.post("/query", buildBody(params), timeout ? { timeout } : undefined)
  return response.data
}

const errorMessage = (data) => {
  const detail = data?.detail
  if (Array.isArray(detail)) return detail.map((d) => d.msg).join("; ")
  return data?.error || data?.message || detail
}

// Streamed query: onEvent(name, data) is called for each Server-Sent Event as it arrives —
// "intent", "preview" (results before providers), "results", "synthesis", "done", "error".
// Resolves with the final response (the "done" payload). Abort with `signal`.
export const streamQuery = async ({ signal, onEvent, ...params }) => {
  const token = localStorage.getItem("cinescope-token")
  const response = await fetch(`${api.defaults.baseURL}/query/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token && { Authorization: `Bearer ${token}` }),
    },
    body: JSON.stringify(buildBody(params)),
    signal,
  })

  if (response.status === 404) {
    // Gateway without the streaming route (e.g. mid-deploy): answer in one piece instead
    const data = await aiQuery(params)
    onEvent("done", data)
    return data
  }
  if (!response.ok) {
    const data = await response.json().catch(() => null)
    throw new Error(errorMessage(data) || `Query failed (${response.status})`)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ""
  let final = null

  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    let boundary
    while ((boundary = buffer.indexOf("\n\n")) !== -1) {
      const block = buffer.slice(0, boundary)
      buffer = buffer.slice(boundary + 2)

      let event = "message"
      let data = ""
      for (const line of block.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim()
        else if (line.startsWith("data:")) data += line.slice(5).trim()
      }
      if (!data) continue

      const payload = JSON.parse(data)
      if (event === "error") throw new Error(payload.error || "Query failed")
      if (event === "done") final = payload
      onEvent(event, payload)
    }
  }

  if (!final) throw new Error("The query stream ended early")
  return final
}
