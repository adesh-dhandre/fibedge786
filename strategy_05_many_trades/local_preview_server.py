import json
import subprocess
import sys
import threading
import time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, unquote

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "netlify_site"

HOST = "127.0.0.1"
PORT = 8765

LOCK = threading.Lock()
JOBS = {}

SCAN_COMMANDS = {
    "CLASSIC": [
        [sys.executable, "fib_price_refresh_v2.py"],
        [sys.executable, "fibedge_quality_live_merge.py"],
        [sys.executable, "fibedge_opportunity_rank_v3.py"],
    ],
    "CLEAN": [
        [sys.executable, "fib_price_refresh_v2.py"],
        [sys.executable, "fibedge_quality_live_merge.py"],
        [sys.executable, "fibedge_opportunity_rank_v3.py"],
    ],
    "PREMIUM": [
        [sys.executable, "fib_price_refresh_v2.py"],
        [sys.executable, "fibedge_quality_live_merge.py"],
        [sys.executable, "fibedge_opportunity_rank_v3.py"],
    ],
    "PREMIUMPLUS": [
        [sys.executable, "archive/premium_v1/premium_plus_scanner.py"],
    ],
    "STRATEGY05": [
        [sys.executable, "strategy_05_live/strategy_05_scanner.py"],
    ],
}

SCAN_COMMANDS["ALL"] = (
    SCAN_COMMANDS["CLASSIC"]
    + SCAN_COMMANDS["PREMIUMPLUS"]
    + SCAN_COMMANDS["STRATEGY05"]
)


def local_index():
    path = SITE / "index.html"
    text = path.read_text(encoding="utf-8")

    # Local preview must read local worktree data, not GitHub/master feeds.
    text = text.replace(
        "const BASE='https://raw.githubusercontent.com/adesh-dhandre/fibedge786/master/';",
        "const BASE='/repo/';",
    )
    text = text.replace(
        "map:'./STOCK_UNIVERSE_MAPPING.csv'",
        "map:'/repo/STOCK_UNIVERSE_MAPPING.csv'",
    )
    text = text.replace(
        "premiumPlus:BASE+'archive/premium_v1/data/premium_plus_candidates.json'",
        "premiumPlus:'/repo/archive/premium_v1/data/premium_plus_candidates.json'",
    )
    text = text.replace(
        "strategy05:'https://raw.githubusercontent.com/adesh-dhandre/fibedge786/strategy-05-many-trades/strategy_05_live/data/strategy_05_candidates.json'",
        "strategy05:'/repo/strategy_05_live/data/strategy_05_candidates.json'",
    )

    # Local mode bypasses the production auth/GitHub-dispatch layer and runs
    # the scanner scripts directly inside this worktree.
    local_override = r"""
<script>
window.requestScan = async function(strategy, button) {
  const original = button ? button.textContent : 'Scan Now';

  if (button) {
    button.disabled = true;
    button.classList.add('busy');
    button.textContent = 'Starting local scan…';
  }

  try {
    const r = await fetch('/local-scan', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({strategy})
    });
    const data = await r.json();

    if (!r.ok) throw new Error(data.error || 'Could not start local scan.');

    if (button) button.textContent = 'Scanning locally…';

    const poll = async () => {
      const sr = await fetch('/local-status?strategy=' + encodeURIComponent(strategy), {
        cache: 'no-store'
      });
      const status = await sr.json();

      if (status.state === 'running') {
        if (button) {
          button.textContent = status.step
            ? 'Scanning · ' + status.step
            : 'Scanning locally…';
        }
        setTimeout(poll, 3000);
        return;
      }

      if (status.state === 'done') {
        if (button) {
          button.classList.remove('busy');
          button.classList.add('done');
          button.textContent = 'Scan Complete ✓';
        }
        await loadAll(true);
        setTimeout(() => {
          if (button) {
            button.disabled = false;
            button.classList.remove('done');
            button.textContent = original;
          }
        }, 3500);
        return;
      }

      if (status.state === 'failed') {
        throw new Error(status.error || 'Local scan failed.');
      }

      setTimeout(poll, 3000);
    };

    setTimeout(poll, 1000);
  } catch (e) {
    if (button) {
      button.disabled = false;
      button.classList.remove('busy','done');
      button.textContent = original;
    }
    alert(e.message || String(e));
  }
};
</script>
"""

    text = text.replace("</body>", local_override + "\n</body>")
    return text.encode("utf-8")


def safe_repo_path(url_path):
    rel = unquote(url_path[len("/repo/"):]).lstrip("/")
    target = (ROOT / rel).resolve()
    root = ROOT.resolve()

    if target != root and root not in target.parents:
        return None

    return target


def content_type(path):
    ext = path.suffix.lower()
    return {
        ".html": "text/html; charset=utf-8",
        ".csv": "text/csv; charset=utf-8",
        ".json": "application/json; charset=utf-8",
        ".js": "application/javascript; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".txt": "text/plain; charset=utf-8",
    }.get(ext, "application/octet-stream")


def run_scan(strategy):
    commands = SCAN_COMMANDS[strategy]

    with LOCK:
        JOBS[strategy] = {
            "state": "running",
            "started_at": time.time(),
            "finished_at": None,
            "step": "starting",
            "error": None,
            "log": [],
        }

    try:
        for i, cmd in enumerate(commands, 1):
            label = Path(cmd[-1]).name

            with LOCK:
                JOBS[strategy]["step"] = f"{i}/{len(commands)} {label}"

            proc = subprocess.Popen(
                cmd,
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            lines = []
            assert proc.stdout is not None
            for line in proc.stdout:
                clean = line.rstrip()
                print(f"[{strategy}] {clean}", flush=True)
                lines.append(clean)
                if len(lines) > 120:
                    lines = lines[-120:]

                with LOCK:
                    JOBS[strategy]["log"] = lines[-120:]

            rc = proc.wait()
            if rc != 0:
                raise RuntimeError(
                    f"{label} exited with code {rc}. Check Terminal output."
                )

        with LOCK:
            JOBS[strategy].update(
                state="done",
                step="complete",
                finished_at=time.time(),
            )

    except Exception as exc:
        print(f"[{strategy}] ERROR: {exc}", flush=True)
        with LOCK:
            JOBS[strategy].update(
                state="failed",
                error=str(exc),
                step="failed",
                finished_at=time.time(),
            )


class Handler(BaseHTTPRequestHandler):
    server_version = "FibEdgeLocal/1.0"

    def send_bytes(self, status, data, ctype):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, status, payload):
        self.send_bytes(
            status,
            json.dumps(payload).encode("utf-8"),
            "application/json; charset=utf-8",
        )

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path in ("/", "/index.html"):
            self.send_bytes(200, local_index(), "text/html; charset=utf-8")
            return

        if parsed.path.startswith("/repo/"):
            target = safe_repo_path(parsed.path)
            if target is None or not target.is_file():
                self.send_json(404, {"error": "Local file not found"})
                return

            try:
                data = target.read_bytes()
            except Exception as exc:
                self.send_json(500, {"error": str(exc)})
                return

            self.send_bytes(200, data, content_type(target))
            return

        if parsed.path == "/local-status":
            from urllib.parse import parse_qs
            q = parse_qs(parsed.query)
            strategy = str((q.get("strategy") or [""])[0]).upper()

            with LOCK:
                job = dict(JOBS.get(strategy, {"state": "idle"}))

            self.send_json(200, job)
            return

        self.send_json(404, {"error": "Not found"})

    def do_POST(self):
        parsed = urlparse(self.path)

        if parsed.path != "/local-scan":
            self.send_json(404, {"error": "Not found"})
            return

        try:
            size = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(size) or b"{}")
        except Exception:
            self.send_json(400, {"error": "Invalid JSON"})
            return

        strategy = str(payload.get("strategy", "")).upper()
        if strategy not in SCAN_COMMANDS:
            self.send_json(400, {"error": f"Unknown strategy: {strategy}"})
            return

        with LOCK:
            running = [
                k for k, v in JOBS.items()
                if v.get("state") == "running"
            ]

        if running:
            self.send_json(
                409,
                {
                    "error": "Another local scan is already running: "
                    + ", ".join(running)
                },
            )
            return

        thread = threading.Thread(
            target=run_scan,
            args=(strategy,),
            daemon=True,
        )
        thread.start()

        self.send_json(
            202,
            {
                "ok": True,
                "strategy": strategy,
                "message": "Local scan started",
            },
        )

    def log_message(self, fmt, *args):
        # Keep terminal readable; scanner output is more useful than every
        # browser request.
        if "/local-" in self.path:
            super().log_message(fmt, *args)


def main():
    print("=" * 72)
    print("FibEdge LOCAL website preview")
    print("=" * 72)
    print(f"Repo: {ROOT}")
    print(f"Open: http://{HOST}:{PORT}")
    print()
    print("Direct website scan buttons run LOCAL scripts only.")
    print("No GitHub push, Netlify deploy, or master update happens here.")
    print("Press Ctrl+C to stop the preview server.")
    print("=" * 72)

    server = ThreadingHTTPServer((HOST, PORT), Handler)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nLocal preview stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
