const crypto = require("crypto");

function json(statusCode, body, headers = {}) {
  return {
    statusCode,
    headers: {
      "Content-Type": "application/json",
      "Cache-Control": "no-store",
      ...headers,
    },
    body: JSON.stringify(body),
  };
}

function safeEqual(a, b) {
  const ah = crypto.createHash("sha256").update(String(a)).digest();
  const bh = crypto.createHash("sha256").update(String(b)).digest();
  return crypto.timingSafeEqual(ah, bh);
}

exports.handler = async (event) => {
  if (event.httpMethod !== "POST") {
    return json(405, { ok: false, error: "POST required" });
  }

  const expected = process.env.SCAN_PASSWORD;
  const secret = process.env.SCAN_SESSION_SECRET;

  if (!expected || !secret) {
    return json(503, {
      ok: false,
      error: "Scan authentication is not configured on the server.",
    });
  }

  let payload;
  try {
    payload = JSON.parse(event.body || "{}");
  } catch {
    return json(400, { ok: false, error: "Invalid JSON" });
  }

  if (!safeEqual(payload.password || "", expected)) {
    return json(401, { ok: false, error: "Incorrect scan password" });
  }

  const expires = Math.floor(Date.now() / 1000) + 12 * 60 * 60;
  const data = String(expires);
  const sig = crypto
    .createHmac("sha256", secret)
    .update(data)
    .digest("hex");
  const token = data + "." + sig;

  return json(
    200,
    { ok: true, expires_at: expires },
    {
      "Set-Cookie":
        "fibedge_scan_session=" +
        token +
        "; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=43200",
    }
  );
};
