import api from "./axios"

export const aiQuery = async ({ q, locale = "US", maxResults = 10, includeProviders = true, includeSynthesis = false }) => {
  const response = await api.post("/query", {
    q,
    locale,
    options: {
      max_results: maxResults,
      include_providers: includeProviders,
      include_synthesis: includeSynthesis,
    },
  })
  return response.data
}
