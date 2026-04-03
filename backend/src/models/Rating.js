const mongoose = require("mongoose")

const ratingSchema = new mongoose.Schema({
  userId: {
    type: mongoose.Schema.Types.ObjectId,
    ref: "User",
    required: true,
    index: true
  },
  movieId: {
    type: Number,
    required: true,
    index: true
  },
  rating: {
    type: Number,
    required: true,
    min: 1,
    max: 10
  },
  review: {
    type: String,
    default: "",
    maxlength: 1000
  }
}, { timestamps: true })

// One rating per user per movie
ratingSchema.index({ userId: 1, movieId: 1 }, { unique: true })

module.exports = mongoose.model("Rating", ratingSchema)
