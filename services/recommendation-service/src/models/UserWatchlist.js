const mongoose = require("mongoose")


const userWatchlistSchema = new mongoose.Schema({
  user_id: {
    type: mongoose.Schema.Types.ObjectId,
    required: true,
    index: true
  },
  movie_id: {
    type: Number,
    required: true,
    index: true
  },
  status: {
    type: String,
    enum: ["watchlist", "watched", "rated", "liked", "disliked"],
    default: "watchlist"
  },
  rating: {
    type: Number,
    min: 0,
    max: 10,
    default: null
  },
  added_at: {
    type: Date,
    default: Date.now
  }
}, { timestamps: true })

userWatchlistSchema.index({ user_id: 1, movie_id: 1 }, { unique: true })

module.exports = mongoose.model("UserWatchlist", userWatchlistSchema)
