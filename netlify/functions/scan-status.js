const crypto = require("crypto");

function json(statusCode, body) {
  return {
    statusCode,
    headers: {"Content-Type":"application/json","Cache-Control":"no-store"},
    body: JSON.stringify(body)
  };
}

function parseCookies(header) {
  const out = {};
  String(header || "").split(";").forEach((part) => {
    const i = part.indexOf("=");
    if (i > 0) out[part.slice(0, i).trim()] = part.slice(i + 1).trim();
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
  if (!Number.isFinite(expires) || expires < Math.floor(Date.now() / 1000)) return false;
  const expected = crypto.createHmac("sha256", secret).update(String(expires)).digest("hex");
  try {
    return crypto.timingSafeEqual(Buffer.from(sig, "hex"), Buffer.from(expected, "hex"));
  } catch {
    return false;
  }
}

exports.handler = async (event) => {
  if (event.httpMethod !== "GET") return json(405, {ok:false,error:"GET required"});
  if (!validSession(event)) return json(401, {ok:false,error:"Scan authorization required"});

  const requestId = String((event.queryStringParameters || {}).request_id || "");
  if (!/^[a-f0-9]{24}$/.test(requestId)) {
    return json(400, {ok:false,error:"Invalid scan tracking ID"});
  }

  const token = process.env.GITHUB_ACTIONS_TOKEN;
  if (!token) {
    return json(503, {ok:false,error:"GitHub Actions status is not configured on the server."});
  }

  const response = await fetch(
    "https://api.github.com/repos/adesh-dhandre/fibedge786/actions/workflows/fibedge_website_scan.yml/runs?branch=master&event=workflow_dispatch&per_page=30",
    {
      headers: {
        Accept: "application/vnd.github+json",
        Authorization: "Bearer " + token,
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "FibEdge-Netlify-Scan"
      }
    }
  );

  if (!response.ok) {
    const detail = await response.text();
    return json(502, {
      ok:false,
      error:"Could not read GitHub scan status",
      status:response.status,
      detail:detail.slice(0,500)
    });
  }

  const body = await response.json();
  const run = (body.workflow_runs || []).find((r) =>
    String(r.display_title || "").includes(requestId)
  );

  if (!run) {
    return json(200, {ok:true,status:"waiting",request_id:requestId});
  }

  let duration = null;
  if (run.run_started_at) {
    const started = new Date(run.run_started_at).getTime();
    const ended = run.status === "completed" && run.updated_at
      ? new Date(run.updated_at).getTime()
      : Date.now();
    if (Number.isFinite(started) && Number.isFinite(ended)) {
      duration = Math.max(0, Math.round((ended - started) / 1000));
    }
  }

  return json(200, {
    ok:true,
    request_id:requestId,
    run_id:run.id,
    status:run.status,
    conclusion:run.conclusion,
    duration_seconds:duration,
    created_at:run.created_at,
    run_started_at:run.run_started_at,
    updated_at:run.updated_at
  });
};
