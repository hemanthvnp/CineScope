const mongoose = require("mongoose")

/**
 * Genre Schema
 * Stores genre information (aligned with TMDB genre IDs)
 */
const genreSchema = new mongoose.Schema({
  genre_id: {
    type: Number,
    required: true,
    unique: true,
    index: true
  },
  genre_name: {
    type: String,
    required: true,
    trim: true
  }
}, { timestamps: true })

module.exports = mongoose.model("Genre", genreSchema)
