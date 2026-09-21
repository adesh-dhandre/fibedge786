const crypto = require("crypto");

const ALLOWED = new Set([
  "ALL",
  "CLASSIC",
  "CLEAN",
  "PREMIUM",
  "PREMIUMPLUS",
  "STRATEGY05",
]);

function json(statusCode, body) {
  return {
    statusCode,
    headers: {
      "Content-Type": "application/json",
      "Cache-Control": "no-store",
    },
    body: JSON.stringify(body),
  };
}

function parseCookies(header) {
  const out = {};
  String(header || "")
    .split(";")
    .forEach((part) => {
      const i = part.indexOf("=");
      if (i > 0) {
        out[part.slice(0, i).trim()] = part.slice(i + 1).trim();
      }
    });
  return out;
}

function validSession(event) {
  const secret = process.env.SCAN_SESSION_SECRET;
  if (!secret) return false;

  const cookies = parseCookies(event.headers.cookie || event.headers.Cookie);
  const token = cookies.fibedge_scan_session;
  if (!token) return false;

  const parts = token.split(".");
  if (parts.length !== 2) return false;

  const expires = Number(parts[0]);
  const sig = parts[1];

  if (!Number.isFinite(expires) || expires < Math.floor(Date.now() / 1000)) {
    return false;
  }

  const expected = crypto
    .createHmac("sha256", secret)
    .update(String(expires))
    .digest("hex");

  try {
    return crypto.timingSafeEqual(
      Buffer.from(sig, "hex"),
      Buffer.from(expected, "hex")
    );
  } catch {
    return false;
  }
}

exports.handler = async (event) => {
  if (event.httpMethod !== "POST") {
    return json(405, { ok: false, error: "POST required" });
  }

  if (!validSession(event)) {
    return json(401, { ok: false, error: "Scan authorization required" });
  }

  let payload;
  try {
    payload = JSON.parse(event.body || "{}");
  } catch {
    return json(400, { ok: false, error: "Invalid JSON" });
  }

  const strategy = String(payload.strategy || "").toUpperCase();
  if (!ALLOWED.has(strategy)) {
    return json(400, { ok: false, error: "Unknown strategy" });
  }

  const token = process.env.GITHUB_ACTIONS_TOKEN;
  if (!token) {
    return json(503, {
      ok: false,
      error: "GitHub Actions trigger is not configured on the server.",
    });
  }

  const owner = "adesh-dhandre";
  const repo = "fibedge786";
  const workflow = "fibedge_website_scan.yml";
  const ref = process.env.SCAN_WORKFLOW_REF || "master";

  const response = await fetch(
    `https://api.github.com/repos/${owner}/${repo}/actions/workflows/${workflow}/dispatches`,
    {
      method: "POST",
      headers: {
        Accept: "application/vnd.github+json",
        Authorization: `Bearer ${token}`,
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "FibEdge-Netlify-Scan",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        ref,
        inputs: { strategy },
      }),
    }
  );

  if (!response.ok) {
    const detail = await response.text();
    return json(502, {
      ok: false,
      error: "Could not start GitHub scan workflow",
      status: response.status,
      detail: detail.slice(0, 500),
    });
  }

  return json(202, {
    ok: true,
    strategy,
    message: "Scan requested",
  });
};
