const express = require("express")
const cors = require("cors")

const movieRoutes = require("./routes/movieRoutes")
const userRoutes = require("./routes/userRoutes")

const app = express()

app.use(cors())
app.use(express.json())

app.use("/api/movies", movieRoutes)
app.use("/api/users", userRoutes)

module.exports = app