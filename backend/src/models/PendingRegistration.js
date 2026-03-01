const mongoose = require("mongoose")

const pendingRegistrationSchema = new mongoose.Schema({
  name: { type: String, required: true, trim: true },
  screenName: { type: String, trim: true, default: "" },
  email: { type: String, required: true, unique: true, lowercase: true, trim: true },
  passwordHash: { type: String, required: true },
  favoriteGenre: { type: String, default: "" },
  favoriteEra: { type: String, default: "" },
  signatureLine: { type: String, default: "" },
  otpHash: { type: String, required: true },
  otpExpiresAt: { type: Date, required: true },
  createdAt: { type: Date, default: Date.now, expires: 900 }
})

module.exports = mongoose.model("PendingRegistration", pendingRegistrationSchema)
