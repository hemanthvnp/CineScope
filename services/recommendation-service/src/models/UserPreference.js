const mongoose = require("mongoose")

/**
 * UserPreference Schema
 * Stores user's preference scores for each genre
 * Score indicates how much the user prefers a particular genre
 * Higher scores = stronger preference
 *
 * Note: user_id references users from the main backend service
 */
const userPreferenceSchema = new mongoose.Schema({
  user_id: {
    type: mongoose.Schema.Types.ObjectId,
    required: true,
    index: true
  },
  genre_id: {
    type: Number,
    required: true,
    index: true
  },
  score: {
    type: Number,
    required: true,
    default: 1.0,
    min: 0,
    max: 10
  }
}, { timestamps: true })

// Compound unique index: one preference per user per genre
userPreferenceSchema.index({ user_id: 1, genre_id: 1 }, { unique: true })

module.exports = mongoose.model("UserPreference", userPreferenceSchema)
