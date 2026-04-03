import { useState, useEffect } from "react"
import { useSearchParams } from "react-router-dom"
import { useSearchFilter } from "../context/SearchFilterContext"
import api from "../api/axios"
import MovieCard from "../components/MovieCard"
import SkeletonRow from "../components/SkeletonRow"
import "./SearchPage.css"

const SearchPage = () => {
  const [searchParams] = useSearchParams()
  const { 
    setSearch, setYear, setGenre, setLanguage, setFilters,
    search, year, genre, language, genreMap, languageMap 
  } = useSearchFilter()
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState("")
  const [totalResults, setTotalResults] = useState(0)
  const [page, setPage] = useState(1)

  const query = searchParams.get("q") || ""
  const yearFilter = searchParams.get("year") || ""
  const genreFilter = searchParams.get("genre") || ""
  const languageFilter = searchParams.get("language") || ""

  // Reset to page 1 when filters change
  useEffect(() => {
    setPage(1)
  }, [query, yearFilter, genreFilter, languageFilter])

  // Sync URL params to context
  useEffect(() => {
    setSearch(query)
    setYear(yearFilter)
    setGenre(genreFilter)
    setLanguage(languageFilter)
    setFilters({ year: yearFilter, genre: genreFilter, language: languageFilter })
  }, [query, yearFilter, genreFilter, languageFilter])

  useEffect(() => {
    const fetchSearchResults = async () => {
      // Allow fetching if we have a query OR filters (year/genre/language)
      if (!query.trim() && !yearFilter && !genreFilter && !languageFilter) {
        setResults([])
        setLoading(false)
        return
      }

      if (page === 1) setLoading(true)
      else setLoadingMore(true)
      
      setError("")

      try {
        const params = {
          query: query,
          page: page
        }

        if (yearFilter) params.year = yearFilter
        if (genreFilter) params.genre = genreFilter
        if (languageFilter) params.language = languageFilter

        const response = await api.get("/movies/search", { params })
        
        const mappedResults = (response.data.results || []).map(m => ({
          ...m,
          movie_id: m.id,
          explanation: { reason: `Match for your search`, type: "general" }
        }))
        
        if (page === 1) {
          setResults(mappedResults)
        } else {
          // Prevent duplicates if the effect re-runs
          setResults(prev => {
            const existingIds = new Set(prev.map(r => r.movie_id || r.id))
            const newResults = mappedResults.filter(r => !existingIds.has(r.movie_id || r.id))
            return [...prev, ...newResults]
          })
        }
        setTotalResults(response.data.total_results || 0)
      } catch (error) {
        console.error("Search failed:", error)
        setError("Failed to search movies. Please try again.")
      } finally {
        setLoading(false)
        setLoadingMore(false)
      }
    }

    fetchSearchResults()
  }, [query, yearFilter, genreFilter, languageFilter, page])

  const handleLoadMore = () => {
    setPage(prev => prev + 1)
  }

  const getSearchDescription = () => {
    const parts = []
    if (query) parts.push(`"${query}"`)
    if (yearFilter) parts.push(`from ${yearFilter}`)
    
    if (genreFilter) {
      const genreName = genreMap[genreFilter] || genreFilter
      parts.push(`matching genre ${genreName}`)
    }
    
    if (languageFilter) {
      const langName = languageMap[languageFilter] || languageFilter
      parts.push(`in ${langName}`)
    }
    
    if (parts.length === 0) return "All movies"
    if (parts.length === 1) return parts[0]
    
    return parts.slice(0, -1).join(", ") + (parts.length > 1 ? " and " : "") + parts.slice(-1).join("")
  }

  if (loading && page === 1) {
    return (
      <div className="search-page">
        <div className="search-header">
          <h1>Searching...</h1>
        </div>
        <SkeletonRow />
      </div>
    )
  }

  if (error && page === 1) {
    return (
      <div className="search-page">
        <div className="search-header">
          <h1>Search Error</h1>
          <p className="error-message">{error}</p>
        </div>
      </div>
    )
  }

  if (!query.trim() && !yearFilter && !genreFilter && !languageFilter) {
    return (
      <div className="search-page">
        <div className="search-header">
          <h1>Search Movies</h1>
          <p>Enter a movie title, actor, or director to start searching.</p>
        </div>
      </div>
    )
  }

  if (results.length === 0) {
    return (
      <div className="search-page">
        <div className="search-header">
          <h1>No Results Found</h1>
          <p>No movies found for {getSearchDescription()}.</p>
          <div className="search-suggestions">
            <h3>Try:</h3>
            <ul>
              <li>Checking the spelling</li>
              <li>Using more general terms</li>
              <li>Removing filters</li>
              <li>Searching for a different movie</li>
            </ul>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="search-page">
      <div className="search-header">
        <h1>Search Results</h1>
        <p className="search-description">
          Found {totalResults} movies {getSearchDescription()}
        </p>
      </div>

      <div className="search-results-section">
        <h2 className="rec-row-title">
          Showing {results.length} of {totalResults} results
        </h2>
        <div className="search-results-grid">
          {results.map((movie, index) => (
            <MovieCard
              key={`${movie.movie_id || movie.id}-${index}`}
              movie={movie}
              showExplanation={false}
            />
          ))}
        </div>

        {results.length < totalResults && (
          <div className="load-more-container">
            <button 
              className="load-more-btn" 
              onClick={handleLoadMore}
              disabled={loadingMore}
            >
              {loadingMore ? "Loading..." : "Load More"}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

export default SearchPage
