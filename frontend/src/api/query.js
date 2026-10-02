import api from "./axios"

// filters (all optional, any combination): { genres: [name|id], language, year, yearFrom, yearTo,
//   era, minRating, platforms: [name], country }. `q` may be empty when filters are given.
export const aiQuery = async ({ q = "", filters, locale = "US", maxResults = 10, includeProviders = true, includeSynthesis = false, timeout }) => {
  const body = {
    q,
    locale,
    options: {
      max_results: maxResults,
      include_providers: includeProviders,
      include_synthesis: includeSynthesis,
    },
  }

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

  const response = await api.post("/query", body, timeout ? { timeout } : undefined)
  return response.data
}
