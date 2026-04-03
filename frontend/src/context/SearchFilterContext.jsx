import { createContext, useContext, useState } from "react"

const SearchFilterContext = createContext()

export function SearchFilterProvider({ children }) {
  const [search, setSearch] = useState("")
  const [year, setYear] = useState("")
  const [genre, setGenre] = useState("")

  const setFilters = ({ year, genre }) => {
    setYear(year)
    setGenre(genre)
  }

  const clearSearch = () => {
    setSearch("")
    setYear("")
    setGenre("")
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
        setFilters,
        clearSearch,
      }}
    >
      {children}
    </SearchFilterContext.Provider>
  )
}

export function useSearchFilter() {
  return useContext(SearchFilterContext)
}