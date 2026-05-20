const mongoose = require("mongoose")


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
