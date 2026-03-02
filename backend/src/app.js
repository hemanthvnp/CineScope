const express = require("express")
const cors = require("cors")

const watchlistRoutes = require("./routes/watchlistRoutes")


const movieRoutes = require("./routes/movieRoutes")
const userRoutes = require("./routes/userRoutes")

const app = express()

app.use(cors())
app.use(express.json())

app.use("/watchlist", watchlistRoutes)

app.use("/api/movies", movieRoutes)
app.use("/api/users", userRoutes)

module.exports = app