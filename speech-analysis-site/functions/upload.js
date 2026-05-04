function formatKSTTimestamp() {

	const now = new Date()
	const kst = new Date(now.getTime() + (9 * 60 * 60 * 1000))

	const months = [
		"JAN","FEB","MAR","APR","MAY","JUN",
		"JUL","AUG","SEP","OCT","NOV","DEC"
	]

	const month = months[kst.getMonth()]
	const day = String(kst.getDate()).padStart(2,"0")
	const year = kst.getFullYear()

	const hours = String(kst.getHours()).padStart(2,"0")
	const minutes = String(kst.getMinutes()).padStart(2,"0")

	return `${month}${day}-${year}-${hours}${minutes}`
}

export async function onRequest(context) {

	const { request, env } = context

	if (request.method !== "POST") {
		return new Response("Method not allowed", { status: 405 })
	}

	const form = await request.formData()

	const email = form.get("email")
	const name = form.get("name")
	const student = form.get("student")
	const text = form.get("text")
	const audio = form.get("audio")

	if (!audio) {
		return new Response("Missing field: audio", { status: 400 })
	}

	if (!audio.type || !audio.type.startsWith("audio/")) {
		return new Response("Uploaded file must be an audio file", { status: 400 })
	}

	if (!email) {
		return new Response("Missing field: email", { status: 400 })
	}

	if (!name) {
		return new Response("Missing field: name", { status: 400 })
	}

	if (!student) {
		return new Response("Missing field: student number", { status: 400 })
	}

	if (!text) {
		return new Response("Missing field: document text", { status: 400 })
	}

	// 50 MB file limit
	if (audio.size > 50 * 1024 * 1024) {
		return new Response("File too large (max 50MB)", { status: 400 })
	}

	const timestampReadable = formatKSTTimestamp()

	const submissionId =
		`${student}_${timestampReadable}_${crypto.randomUUID().slice(0,4)}`

	const audioPath = `submissions/${submissionId}/audio.webm`
	const metaPath = `submissions/${submissionId}/metadata.json`

	// 🔹 Cloudflare automatic geo detection
	const country = request.cf?.country || "UNKNOWN"

	let region = "other"
	if (country === "KR") region = "korea"
	else if (country === "JP") region = "japan"
	else if (country === "CN") region = "china"

	await env.AUDIO_BUCKET.put(audioPath, audio.stream())

	const metadata = {
		submission_id: submissionId,
		email,
		name,
		student,
		text,
		country,
		region,
		original_filename: audio.name,
		timestamp_kst: timestampReadable,
		timestamp_iso: new Date().toISOString()
	}

	await env.AUDIO_BUCKET.put(
		metaPath,
		JSON.stringify(metadata, null, 2),
		{ httpMetadata: { contentType: "application/json" } }
	)

	return new Response(
		JSON.stringify({ success: true, id: submissionId }),
		{
			headers: { "content-type": "application/json" }
		}
	)
}