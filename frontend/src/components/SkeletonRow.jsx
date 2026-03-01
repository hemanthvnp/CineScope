function SkeletonRow() {
  return (
    <section className="movie-row">
      <div className="skeleton-title" />
      <div className="movie-strip">
        {[...Array(6)].map((_, i) => (
          <div key={i} className="skeleton-card" />
        ))}
      </div>
    </section>
  )
}

export default SkeletonRow