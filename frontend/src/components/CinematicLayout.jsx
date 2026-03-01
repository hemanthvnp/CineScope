import "./CinematicLayout.css"

function CinematicLayout({ children }) {
  return (
    <div className="cinema-wrapper particles">
      <div className="overlay"></div>
      <div className="grain"></div>
      <div className="cinema-card">
        {children}
      </div>
    </div>
  )
}

export default CinematicLayout