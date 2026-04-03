import React, { createContext, useContext, useState, useEffect, useMemo } from "react"
import api from "../api/axios"

const SearchFilterContext = createContext()

export function SearchFilterProvider({ children }) {
  const [search, setSearch] = useState("")
  const [year, setYear] = useState("")
  const [genre, setGenre] = useState("")
  const [language, setLanguage] = useState("")

  const [genresList, setGenresList] = useState([])
  const [languagesList, setLanguagesList] = useState([])

  useEffect(() => {
    const fetchMetadata = async () => {
      try {
        const response = await api.get("/movies/filter/options")
        const { genres, languages } = response.data
        
        setGenresList(genres || [])
        
        const sortedLangs = (languages || []).sort((a, b) => 
          (a.name || "").localeCompare(b.name || "")
        )
        setLanguagesList(sortedLangs)
      } catch (error) {
        console.error("Failed to fetch search metadata:", error)
      }
    }
    fetchMetadata()
  }, [])

  const languageMap = useMemo(() => {
    return languagesList.reduce((acc, lang) => {
      acc[lang.code] = lang.name
      return acc
    }, {})
  }, [languagesList])

  const genreMap = useMemo(() => {
    return genresList.reduce((acc, g) => {
      acc[g.id] = g.name
      acc[g.name] = g.id // bidirectional for convenience
      return acc
    }, {})
  }, [genresList])

  const setFilters = ({ year, genre, language }) => {
    if (year !== undefined) setYear(year)
    if (genre !== undefined) setGenre(genre)
    if (language !== undefined) setLanguage(language)
  }

  const clearSearch = () => {
    setSearch("")
    setYear("")
    setGenre("")
    setLanguage("")
  }

  return (
    <SearchFilterContext.Provider
      value={{
        search,
        setSearch,
        year,
        setYear,
        genre,
        setGenre,
        language,
        setLanguage,
        genresList,
        languagesList,
        genreMap,
        languageMap,
        setFilters,
        clearSearch,
      }}
    >
      {children}
    </SearchFilterContext.Provider>
  )
}

export const useSearchFilter = () => {
  const context = useContext(SearchFilterContext)
  if (!context) {
    throw new Error("useSearchFilter must be used within a SearchFilterProvider")
  }
  return context
}