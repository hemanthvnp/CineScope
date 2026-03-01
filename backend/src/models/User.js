const mongoose = require("mongoose")

const userSchema = new mongoose.Schema({
  name: { type: String, required: true, trim: true },
  screenName: { type: String, trim: true, default: "" },
  email: { type: String, required: true, unique: true, lowercase: true, trim: true },
  password: { type: String, required: true },
  favoriteGenre: { type: String, default: "" },
  favoriteEra: { type: String, default: "" },
  signatureLine: { type: String, default: "" },
  emailVerified: { type: Boolean, default: false }
}, { timestamps: true })

module.exports = mongoose.model("User", userSchema)