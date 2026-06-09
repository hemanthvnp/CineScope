const mongoose = require("mongoose")

const watchlistSchema = new mongoose.Schema(
  {
    movieId: {
      type: Number,
      required: true,
      unique: true
    },
    title: {
      type: String,
      required: true
    },
    year: {
      type: String
    },
    poster: {
      type: String
    }
  },
  { timestamps: true }
)

module.exports = mongoose.model("Watchlist", watchlistSchema)