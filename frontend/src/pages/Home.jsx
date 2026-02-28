import HeroBanner from "../components/HeroBanner"
import MovieRow from "../components/MovieRow"

function Home() {
  return (
    <div>
      <HeroBanner />
      <MovieRow title="🎯 Personalized Recommendations" />
      <MovieRow title="🧠 Because You Like Sci-Fi" />
      <MovieRow title="📊 Trending Insights" />
      <MovieRow title="🎭 Deep Genre Exploration" />
    </div>
  )
}

export default Home