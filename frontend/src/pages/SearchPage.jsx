import { useState, useEffect } from "react"
import { useSearchParams } from "react-router-dom"
import { useSearchFilter } from "../context/SearchFilterContext"
import api from "../api/axios"
import MovieRow from "../components/MovieRow"
import SkeletonRow from "../components/SkeletonRow"
import "./SearchPage.css"

const SearchPage = () => {
  const [searchParams] = useSearchParams()
  const { search, year, genre } = useSearchFilter()
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [totalResults, setTotalResults] = useState(0)

  const query = searchParams.get("q") || search
  const yearFilter = searchParams.get("year") || year
  const genreFilter = searchParams.get("genre") || genre

  useEffect(() => {
    const fetchSearchResults = async () => {
      if (!query.trim()) {
        setResults([])
        setLoading(false)
        return
      }

      setLoading(true)
      setError("")

      try {
        const params = {
          query: query,
          page: 1
        }

        if (yearFilter) {
          params.year = yearFilter
        }

        if (genreFilter) {
          // Convert genre name to TMDB genre ID if needed
          params.with_genres = genreFilter
        }

        const response = await api.get("/movies/search", { params })
        
        setResults(response.data.results || [])
        setTotalResults(response.data.total_results || 0)
      } catch (error) {
        console.error("Search failed:", error)
        setError("Failed to search movies. Please try again.")
        setResults([])
      } finally {
        setLoading(false)
      }
    }

    fetchSearchResults()
  }, [query, yearFilter, genreFilter])

  const getSearchDescription = () => {
    const parts = []
    if (query) parts.push(`"${query}"`)
    if (yearFilter) parts.push(`from ${yearFilter}`)
    if (genreFilter) parts.push(`in ${genreFilter}`)
    
    if (parts.length === 0) return "All movies"
    if (parts.length === 1) return parts[0]
    
    return parts.slice(0, -1).join(", ") + " " + parts.slice(-1).join("and ")
  }

  if (loading) {
    return (
      <div className="search-page">
        <div className="search-header">
          <h1>Searching...</h1>
        </div>
        <SkeletonRow />
      </div>
    )
  }

  if (error) {
    return (
      <div className="search-page">
        <div className="search-header">
          <h1>Search Error</h1>
          <p className="error-message">{error}</p>
        </div>
      </div>
    )
  }

  if (!query.trim()) {
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
          {totalResults} results found for {getSearchDescription()}
        </p>
      </div>
      
      <MovieRow 
        movies={results} 
        title={`${results.length} Results`}
        loading={false}
        emptyMessage="No movies found matching your search criteria."
      />
    </div>
  )
}

export default SearchPage
