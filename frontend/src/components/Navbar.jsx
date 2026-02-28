import { Link } from "react-router-dom"

function Navbar() {
  return (
    <nav style={styles.nav}>
      <h2 style={styles.logo}>CineScope</h2>
      <div style={styles.links}>
        <Link to="/" style={styles.link}>Home</Link>
        <Link to="/watchlist" style={styles.link}>Watchlist</Link>
        <Link to="/profile" style={styles.link}>Profile</Link>
        <Link to="/login" style={styles.link}>Login</Link>
      </div>
    </nav>
  )
}

const styles = {
  nav: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "1rem 2rem",
    backgroundColor: "#141414"
  },
  logo: {
    color: "#e50914"
  },
  links: {
    display: "flex",
    gap: "1.5rem"
  },
  link: {
    color: "white",
    textDecoration: "none"
  }
}

export default Navbar