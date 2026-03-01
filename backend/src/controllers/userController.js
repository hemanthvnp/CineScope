const crypto = require("crypto")
const bcrypt = require("bcryptjs")
const jwt = require("jsonwebtoken")
const User = require("../models/User")
const PendingRegistration = require("../models/PendingRegistration")
const { sendOtpEmail } = require("../services/emailService")

const OTP_EXPIRY_MS = 10 * 60 * 1000

const hashOtp = (otpCode) => {
	const otpSecret = process.env.OTP_SECRET || "cinescope-otp-secret"

	return crypto
		.createHash("sha256")
		.update(`${otpCode}:${otpSecret}`)
		.digest("hex")
}

const generateOtpCode = () => {
	return String(Math.floor(100000 + Math.random() * 900000))
}

const createAuthPayload = (user) => {
	const jwtSecret = process.env.JWT_SECRET || "cinescope-jwt-secret"
	const token = jwt.sign(
		{ userId: user._id.toString(), email: user.email },
		jwtSecret,
		{ expiresIn: "7d" }
	)

	return {
		token,
		user: {
			id: user._id,
			name: user.name,
			screenName: user.screenName,
			email: user.email,
			favoriteGenre: user.favoriteGenre,
			favoriteEra: user.favoriteEra,
			signatureLine: user.signatureLine,
			emailVerified: user.emailVerified
		}
	}
}

const initiateRegistration = async (req, res) => {
	try {
		const {
			name,
			screenName = "",
			email,
			password,
			favoriteGenre = "",
			favoriteEra = "",
			signatureLine = ""
		} = req.body

		if (!name || !email || !password) {
			return res.status(400).json({ message: "Name, email, and password are required." })
		}

		if (password.length < 6) {
			return res.status(400).json({ message: "Password must be at least 6 characters." })
		}

		const normalizedEmail = email.toLowerCase().trim()
		const existingUser = await User.findOne({ email: normalizedEmail })

		if (existingUser) {
			return res.status(409).json({ message: "Email is already registered." })
		}

		const otpCode = generateOtpCode()
		const otpHash = hashOtp(otpCode)
		const otpExpiresAt = new Date(Date.now() + OTP_EXPIRY_MS)
		const passwordHash = await bcrypt.hash(password, 10)

		await PendingRegistration.findOneAndUpdate(
			{ email: normalizedEmail },
			{
				name: name.trim(),
				screenName: screenName.trim(),
				email: normalizedEmail,
				passwordHash,
				favoriteGenre,
				favoriteEra,
				signatureLine,
				otpHash,
				otpExpiresAt,
				createdAt: new Date()
			},
			{ upsert: true, new: true, setDefaultsOnInsert: true }
		)

		const emailResult = await sendOtpEmail({
			toEmail: normalizedEmail,
			otpCode,
			fullName: name.trim()
		})

		return res.status(200).json({
			message: emailResult.fallback
				? "OTP sent using test SMTP. Check backend logs for preview URL."
				: "OTP sent to your email.",
			requiresOtp: true,
			smtpFallback: emailResult.fallback,
			previewUrl: emailResult.previewUrl || undefined
		})
	} catch (error) {
		return res.status(500).json({ message: "Failed to initiate registration." })
	}
}

const verifyRegistrationOtp = async (req, res) => {
	try {
		const { email, otp } = req.body

		if (!email || !otp) {
			return res.status(400).json({ message: "Email and OTP are required." })
		}

		const normalizedEmail = email.toLowerCase().trim()
		const pending = await PendingRegistration.findOne({ email: normalizedEmail })

		if (!pending) {
			return res.status(404).json({ message: "No pending registration found for this email." })
		}

		if (pending.otpExpiresAt.getTime() < Date.now()) {
			await PendingRegistration.deleteOne({ _id: pending._id })
			return res.status(400).json({ message: "OTP expired. Please register again." })
		}

		const providedOtpHash = hashOtp(otp.trim())

		if (providedOtpHash !== pending.otpHash) {
			return res.status(400).json({ message: "Invalid OTP." })
		}

		const existingUser = await User.findOne({ email: normalizedEmail })

		if (existingUser) {
			await PendingRegistration.deleteOne({ _id: pending._id })
			return res.status(409).json({ message: "Email is already registered." })
		}

		const user = await User.create({
			name: pending.name,
			screenName: pending.screenName,
			email: pending.email,
			password: pending.passwordHash,
			favoriteGenre: pending.favoriteGenre,
			favoriteEra: pending.favoriteEra,
			signatureLine: pending.signatureLine,
			emailVerified: true
		})

		await PendingRegistration.deleteOne({ _id: pending._id })
		const authPayload = createAuthPayload(user)

		return res.status(201).json({
			message: "Email verified and account created successfully.",
			...authPayload
		})
	} catch (error) {
		return res.status(500).json({ message: "Failed to verify OTP." })
	}
}

const loginUser = async (req, res) => {
	try {
		const { email, password } = req.body

		if (!email || !password) {
			return res.status(400).json({ message: "Email and password are required." })
		}

		const normalizedEmail = email.toLowerCase().trim()
		const user = await User.findOne({ email: normalizedEmail })

		if (!user) {
			return res.status(401).json({ message: "Invalid email or password." })
		}

		const passwordMatches = await bcrypt.compare(password, user.password)

		if (!passwordMatches) {
			return res.status(401).json({ message: "Invalid email or password." })
		}

		if (!user.emailVerified) {
			return res.status(403).json({ message: "Email is not verified yet." })
		}

		return res.status(200).json({
			message: "Login successful.",
			...createAuthPayload(user)
		})
	} catch (error) {
		return res.status(500).json({ message: "Login failed." })
	}
}

const getProfile = async (req, res) => {
	try {
		const user = await User.findById(req.auth.userId).select("-password")

		if (!user) {
			return res.status(404).json({ message: "User not found." })
		}

		return res.status(200).json({ user })
	} catch (error) {
		return res.status(500).json({ message: "Failed to fetch profile." })
	}
}

module.exports = {
	initiateRegistration,
	verifyRegistrationOtp,
	loginUser,
	getProfile
}
