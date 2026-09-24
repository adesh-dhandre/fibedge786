const ALLOWED = new Set([
  "FIBEDGE_LATEST_SIGNALS.csv",
  "FIBEDGE_BEST_OPPORTUNITIES_V3.csv",
  "archive/premium_v1/data/premium_plus_candidates.json",
  "strategy_05_live/data/strategy_05_candidates.json"
]);

function reply(statusCode, body, contentType = "application/json; charset=utf-8") {
  return {
    statusCode,
    headers: {
      "Content-Type": contentType,
      "Cache-Control": "no-store, max-age=0",
      "X-Content-Type-Options": "nosniff"
    },
    body
  };
}

exports.handler = async (event) => {
  if (event.httpMethod !== "GET") {
    return reply(405, JSON.stringify({ ok: false, error: "GET required" }));
  }

  const path = String(event.queryStringParameters?.path || "");
  if (!ALLOWED.has(path)) {
    return reply(400, JSON.stringify({ ok: false, error: "Unknown data file" }));
  }

  const url = `https://raw.githubusercontent.com/adesh-dhandre/fibedge786/master/${path}?v=${Date.now()}`;

  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 12000);
    const response = await fetch(url, {
      signal: controller.signal,
      headers: {
        "User-Agent": "FibEdge-Netlify-Data",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache"
      }
    });
    clearTimeout(timer);

    if (!response.ok) {
      return reply(
        502,
        JSON.stringify({ ok: false, error: "GitHub data fetch failed", status: response.status })
      );
    }

    const body = await response.text();
    const contentType = path.endsWith(".json")
      ? "application/json; charset=utf-8"
      : "text/csv; charset=utf-8";

    return reply(200, body, contentType);
  } catch (error) {
    const message = error?.name === "AbortError" ? "GitHub data fetch timed out" : "GitHub data fetch failed";
    return reply(502, JSON.stringify({ ok: false, error: message }));
  }
};
