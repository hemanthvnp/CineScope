const nodemailer = require("nodemailer")

let cachedTransport = null
let cachedMeta = null

const getTransport = async () => {
  const { SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_SECURE } = process.env
  const hasConfiguredSmtp = Boolean(SMTP_HOST && SMTP_PORT && SMTP_USER && SMTP_PASS)

  if (cachedTransport && cachedMeta?.fallback && hasConfiguredSmtp) {
    cachedTransport = null
    cachedMeta = null
  }

  if (cachedTransport) {
    return { transport: cachedTransport, meta: cachedMeta }
  }

  if (hasConfiguredSmtp) {
    cachedTransport = nodemailer.createTransport({
      host: SMTP_HOST,
      port: Number(SMTP_PORT),
      secure: SMTP_SECURE === "true",
      auth: {
        user: SMTP_USER,
        pass: SMTP_PASS
      }
    })

    cachedMeta = { fallback: false }
    return { transport: cachedTransport, meta: cachedMeta }
  }

  const testAccount = await nodemailer.createTestAccount()
  cachedTransport = nodemailer.createTransport({
    host: "smtp.ethereal.email",
    port: 587,
    secure: false,
    auth: {
      user: testAccount.user,
      pass: testAccount.pass
    }
  })

  cachedMeta = {
    fallback: true,
    account: {
      user: testAccount.user,
      pass: testAccount.pass
    }
  }

  return { transport: cachedTransport, meta: cachedMeta }
}

const sendOtpEmail = async ({ toEmail, otpCode, fullName }) => {
  const { transport, meta } = await getTransport()
  const info = await transport.sendMail({
    from: process.env.SMTP_FROM || process.env.SMTP_USER || "CineScope <no-reply@cinescope.dev>",
    to: toEmail,
    subject: "Your CineScope verification code",
    text: `Hi ${fullName}, your CineScope verification code is ${otpCode}. It expires in 10 minutes.`,
    html: `<p>Hi ${fullName},</p><p>Your CineScope verification code is:</p><h2 style="letter-spacing: 4px;">${otpCode}</h2><p>This code expires in 10 minutes.</p>`
  })

  const previewUrl = nodemailer.getTestMessageUrl(info) || null

  if (previewUrl) {
    console.log(`Ethereal preview URL: ${previewUrl}`)
  }

  return {
    delivered: true,
    fallback: Boolean(meta?.fallback),
    previewUrl,
    testAccount: meta?.account || null
  }
}

module.exports = {
  sendOtpEmail
}
