const mongoose = require("mongoose")

/**
 * UserWatchlist Schema
 * Tracks movies that users have added to their watchlist or have rated
 * Used to exclude already-seen/rated movies from recommendations
 *
 * Note: user_id references users from the main backend service
 */
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
    enum: ["watchlist", "watched", "rated", "liked"],
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

// Compound unique index: one entry per user per movie
userWatchlistSchema.index({ user_id: 1, movie_id: 1 }, { unique: true })

module.exports = mongoose.model("UserWatchlist", userWatchlistSchema)
