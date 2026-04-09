"""
ui.py  —  Yacht IQ Input Bot web UI

Run:  python ui.py
Opens http://localhost:5000 automatically.

Steps performed on submit:
  1. Save the uploaded PDF to samples/
  2. Run src/main.py --input <pdf>          (parse → output/result.json)
  3. Run src/input_YIQ.py --id <id> --input output/result.json --no-review
     (fill YachtIQ form; --no-equipment added if toggle is off)
Output from both steps is streamed live to the browser.
"""

import atexit
import os
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

from flask import Flask, Response, render_template_string, request

# ---------------------------------------------------------------------------
BASE_DIR    = Path(__file__).resolve().parent
SAMPLES_DIR = BASE_DIR / "samples"
OUTPUT_FILE = BASE_DIR / "output" / "result.json"
PYTHON      = str(Path(sys.executable))

SAMPLES_DIR.mkdir(exist_ok=True)
(BASE_DIR / "output").mkdir(exist_ok=True)

def _cleanup_pdfs():
    for p in SAMPLES_DIR.glob("*.pdf"):
        p.unlink(missing_ok=True)

atexit.register(_cleanup_pdfs)

# ---------------------------------------------------------------------------
# Heartbeat watchdog — shuts down the process when the browser tab closes
# ---------------------------------------------------------------------------
_last_ping   = None          # None = page not yet loaded
_PING_TIMEOUT = 8            # seconds without a ping → shut down

def _watchdog():
    while True:
        time.sleep(2)
        if _last_ping is not None and (time.time() - _last_ping) > _PING_TIMEOUT:
            print("\n[UI] Browser tab closed - shutting down.")
            _cleanup_pdfs()
            os._exit(0)

_wd = threading.Thread(target=_watchdog, daemon=True)
_wd.start()

app = Flask(__name__)

# ---------------------------------------------------------------------------
# HTML template
# ---------------------------------------------------------------------------
PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Yacht IQ Input Bot</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #ffffff;
    color: #333333;
    display: flex;
    justify-content: center;
    align-items: flex-start;
    min-height: 100vh;
    padding: 48px 16px;
  }
  .card {
    background: #fff;
    border-radius: 12px;
    box-shadow: 0 2px 20px rgba(0,0,0,.08);
    padding: 40px;
    width: 100%;
    max-width: 520px;
  }
  h1 {
    font-size: 1.5rem;
    font-weight: 700;
    margin-bottom: 28px;
    color: #333333;
  }
  h1 span { color: #785f47; }

  label {
    display: block;
    font-size: .85rem;
    font-weight: 500;
    color: #333333;
    margin-bottom: 6px;
  }
  input[type="text"] {
    width: 100%; padding: 10px 12px; border: 1px solid #ddd;
    border-radius: 7px; font-size: .95rem; outline: none; color: #333;
    transition: border-color .2s;
  }
  input[type="text"]:focus { border-color: #785f47; }
  .field { margin-bottom: 20px; }

  /* Upload */
  .upload-area {
    border: 2px dashed #ddd; border-radius: 7px; padding: 24px;
    text-align: center; cursor: pointer;
    transition: border-color .2s, background .2s;
    position: relative;
  }
  .upload-area:hover { border-color: #785f47; background: #faf7f5; }
  .upload-area input[type="file"] {
    position: absolute; inset: 0; opacity: 0; cursor: pointer; width: 100%; height: 100%;
  }
  .upload-text { font-size: .9rem; color: #888; pointer-events: none; }

  /* Filename pill — sits BELOW the upload area, outside the form */
  .filename-pill {
    display: none;
    align-items: center;
    gap: 8px;
    margin-top: 10px;
    padding: 7px 12px;
    background: #f5f0ec;
    border-radius: 6px;
    font-size: .85rem;
    color: #785f47;
    font-weight: 500;
  }
  .filename-pill.visible { display: flex; }
  .filename-pill-text { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .delete-pdf-btn {
    flex-shrink: 0;
    background: none;
    border: none;
    cursor: pointer;
    font-size: 1rem;
    line-height: 1;
    color: #a08060;
    padding: 2px 4px;
    border-radius: 4px;
  }
  .delete-pdf-btn:hover { background: #e8d8cc; color: #9b2335; }

  /* Toggle */
  .toggle-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 24px;
    padding: 14px 16px;
    border: 1px solid #eee;
    border-radius: 8px;
    background: #fafafa;
  }
  .toggle-label { font-size: .9rem; font-weight: 500; color: #333; }
  .toggle-wrap { display: flex; align-items: center; gap: 10px; }
  .toggle-state { font-size: .82rem; font-weight: 600; color: #999; min-width: 24px; text-align: right; }
  .toggle-state.on { color: #785f47; }
  .switch { position: relative; display: inline-block; width: 44px; height: 24px; }
  .switch input { opacity: 0; width: 0; height: 0; }
  .slider {
    position: absolute; cursor: pointer; inset: 0;
    background: #ccc; border-radius: 24px; transition: .2s;
  }
  .slider:before {
    content: ""; position: absolute;
    width: 18px; height: 18px; left: 3px; bottom: 3px;
    background: white; border-radius: 50%; transition: .2s;
  }
  input:checked + .slider { background: #785f47; }
  input:checked + .slider:before { transform: translateX(20px); }

  /* Button */
  button[type="submit"] {
    width: 100%; padding: 12px; background: #785f47; color: #fff;
    border: none; border-radius: 7px; font-size: 1rem; font-weight: 600;
    cursor: pointer; transition: background .2s; margin-top: 4px;
  }
  button[type="submit"]:hover { background: #6a5240; }
  button[type="submit"]:disabled { background: #bbb; cursor: not-allowed; }

  /* Log */
  #log-wrap { margin-top: 28px; display: none; }
  #log-wrap h2 { font-size: .95rem; font-weight: 600; margin-bottom: 8px; color: #333; }
  #log {
    background: #1a1a2e; color: #e0e0e0; border-radius: 7px;
    padding: 14px 16px;
    font-family: "Cascadia Code", "Consolas", monospace;
    font-size: .78rem; line-height: 1.55; max-height: 400px; overflow-y: auto;
    white-space: pre-wrap; word-break: break-all;
  }
  #log .ok   { color: #6fcf97; }
  #log .err  { color: #eb5757; }
  #log .info { color: #c9a882; }
  .done-msg {
    margin-top: 12px; padding: 10px 14px; border-radius: 7px;
    font-size: .9rem; font-weight: 500; display: none;
  }
  .done-msg.success { background: #f5f0ec; color: #785f47; }
  .done-msg.error   { background: #fdecea; color: #9b2335; }
</style>
</head>
<body>
<div class="card">
  <h1><span>Yacht IQ</span> Input Bot</h1>

  <!-- Filename pill lives OUTSIDE the form so nothing interferes with it -->
  <div class="filename-pill" id="filename-pill">
    <span class="filename-pill-text" id="filename-text"></span>
    <button type="button" class="delete-pdf-btn" id="delete-pdf-btn" title="Remove PDF">&#x2715;</button>
  </div>

  <form id="run-form" enctype="multipart/form-data">
    <div class="field">
      <label>PDF Specification</label>
      <div class="upload-area">
        <input type="file" name="pdf" id="pdf-input" accept=".pdf">
        <div class="upload-text">Click to browse or drag &amp; drop a PDF</div>
      </div>
    </div>

    <div class="field">
      <label for="yacht-id">YachtIQ ID</label>
      <input type="text" id="yacht-id" name="yacht_id"
             placeholder="e.g. 447250" required autocomplete="off">
    </div>

    <div class="toggle-row">
      <span class="toggle-label">Include Equipment?</span>
      <div class="toggle-wrap">
        <span class="toggle-state" id="toggle-state">Off</span>
        <label class="switch">
          <input type="checkbox" name="include_equipment" id="equip-toggle">
          <span class="slider"></span>
        </label>
      </div>
    </div>

    <button type="submit" id="run-btn">Run</button>
  </form>

  <div id="log-wrap">
    <h2>Output</h2>
    <div id="log"></div>
    <div class="done-msg" id="done-msg"></div>
  </div>
</div>

<script>
// ── Heartbeat: keep server alive; stopping pings signals tab-close ──────────
setInterval(() => fetch('/ping', { method: 'POST', keepalive: true }), 2000);

// ── Filename pill helpers ─────────────────────────────────────────────────
// _serverPdf  = name of PDF currently saved in samples/ (null if none)
// _localFile  = File object the user just selected (null if none)
let _serverPdf = null;
let _localFile = null;

function _updatePill() {
  const pill = document.getElementById('filename-pill');
  const text = document.getElementById('filename-text');
  const name = _localFile ? _localFile.name : _serverPdf;
  if (name) {
    text.textContent = name;
    pill.classList.add('visible');
  } else {
    text.textContent = '';
    pill.classList.remove('visible');
  }
}

// On load: check for PDF already in samples/
fetch('/current-pdf').then(r => r.json()).then(d => {
  _serverPdf = d.name || null;
  _updatePill();
});

// New file selected
document.getElementById('pdf-input').addEventListener('change', function() {
  _localFile = this.files[0] || null;
  _updatePill();
});

// Delete / clear
document.getElementById('delete-pdf-btn').addEventListener('click', function() {
  if (_serverPdf) {
    fetch('/delete-pdf', { method: 'POST' }).then(r => {
      if (r.ok) {
        _serverPdf = null;
        _localFile = null;
        document.getElementById('pdf-input').value = '';
        _updatePill();
      }
    });
  } else {
    _localFile = null;
    document.getElementById('pdf-input').value = '';
    _updatePill();
  }
});

// ── Toggle label ─────────────────────────────────────────────────────────
const equipToggle = document.getElementById('equip-toggle');
const toggleState = document.getElementById('toggle-state');
equipToggle.addEventListener('change', function() {
  toggleState.textContent = this.checked ? 'On' : 'Off';
  toggleState.className = 'toggle-state' + (this.checked ? ' on' : '');
});

// ── Form submit → stream output ──────────────────────────────────────────
document.getElementById('run-form').addEventListener('submit', async function(e) {
  e.preventDefault();

  // Must have either a freshly-selected file or a server-side PDF
  if (!_localFile && !_serverPdf) {
    alert('Please select a PDF first.');
    return;
  }

  const btn     = document.getElementById('run-btn');
  const logWrap = document.getElementById('log-wrap');
  const logEl   = document.getElementById('log');
  const doneMsg = document.getElementById('done-msg');

  logEl.textContent = '';
  doneMsg.style.display = 'none';
  doneMsg.className = 'done-msg';
  logWrap.style.display = 'block';
  btn.disabled = true;
  btn.textContent = 'Running\u2026';

  const formData = new FormData(this);
  // If no new file was chosen but a server PDF exists, tell the server to reuse it
  if (!_localFile && _serverPdf) {
    formData.set('reuse_pdf', _serverPdf);
  }

  try {
    const resp = await fetch('/run', { method: 'POST', body: formData });
    if (!resp.ok) {
      logEl.textContent = await resp.text();
      showDone(false);
      return;
    }

    const reader  = resp.body.getReader();
    const decoder = new TextDecoder();
    let hadError  = false;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      decoder.decode(value, { stream: true }).split('\\n').forEach(line => {
        if (!line) { logEl.appendChild(document.createTextNode('\\n')); return; }
        const span  = document.createElement('span');
        const lower = line.toLowerCase();
        if (lower.includes('[ok]') || lower.startsWith('done') || lower.includes('log complete'))
          span.className = 'ok';
        else if (lower.includes('[error]') || lower.includes('traceback') ||
                 (lower.includes('error') && !lower.includes('[ok]'))) {
          span.className = 'err'; hadError = true;
        } else if (lower.includes('[miss]') || lower.includes('warning'))
          span.className = 'err';
        else if (lower.startsWith('===') || lower.startsWith('filling') ||
                 lower.startsWith('navigating') || lower.startsWith('---'))
          span.className = 'info';
        span.textContent = line + '\\n';
        logEl.appendChild(span);
        logEl.scrollTop = logEl.scrollHeight;
      });
    }

    // After a successful run, the PDF is still on the server — update state
    if (!hadError && _localFile) {
      _serverPdf = _localFile.name;
      _localFile = null;
      document.getElementById('pdf-input').value = '';
      _updatePill();
    }

    showDone(!hadError);
  } catch (err) {
    const span = document.createElement('span');
    span.className = 'err';
    span.textContent = 'Network error: ' + err.message + '\\n';
    logEl.appendChild(span);
    showDone(false);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Run';
  }

  function showDone(ok) {
    doneMsg.style.display = 'block';
    doneMsg.className = 'done-msg ' + (ok ? 'success' : 'error');
    doneMsg.textContent = ok
      ? 'Pipeline complete. Review the YachtIQ page, save, then close it.'
      : 'Pipeline finished with errors \u2014 check the log above.';
  }
});
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template_string(PAGE)


@app.route("/ping", methods=["POST"])
def ping():
    global _last_ping
    _last_ping = time.time()
    return Response("", status=204)


@app.route("/run", methods=["POST"])
def run():
    pdf_file   = request.files.get("pdf")
    reuse_name = request.form.get("reuse_pdf", "").strip()
    yacht_id   = request.form.get("yacht_id", "").strip()
    include_equipment = request.form.get("include_equipment") == "on"

    if not yacht_id:
        return Response("No YachtIQ ID provided.", status=400)

    # Determine which PDF to use
    if pdf_file and pdf_file.filename:
        safe_name = Path(pdf_file.filename).name
        pdf_path  = SAMPLES_DIR / safe_name
        # Remove any previously stored PDFs before saving the new one
        for old in SAMPLES_DIR.glob("*.pdf"):
            if old.name != safe_name:
                old.unlink(missing_ok=True)
        pdf_file.save(str(pdf_path))
    elif reuse_name:
        pdf_path = SAMPLES_DIR / Path(reuse_name).name
        if not pdf_path.exists():
            return Response("Stored PDF not found. Please re-upload.", status=400)
    else:
        return Response("No PDF provided.", status=400)

    def generate():
        # Step 1 — PDF parser
        yield "=== Step 1: Parsing PDF ===\n"
        proc1 = subprocess.Popen(
            [PYTHON, str(BASE_DIR / "src" / "main.py"), "--input", str(pdf_path)],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, cwd=str(BASE_DIR), stdin=subprocess.DEVNULL,
        )
        for line in proc1.stdout:
            yield line
        proc1.wait()
        if proc1.returncode != 0:
            yield f"\n[ERROR] Parser exited with code {proc1.returncode}\n"
            return

        # Step 2 — YachtIQ filler
        yield "\n=== Step 2: Filling YachtIQ ===\n"
        cmd2 = [
            PYTHON, str(BASE_DIR / "src" / "input_YIQ.py"),
            "--id",    yacht_id,
            "--input", str(OUTPUT_FILE),
            "--no-review",
        ]
        if not include_equipment:
            cmd2.append("--no-equipment")

        proc2 = subprocess.Popen(
            cmd2, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, cwd=str(BASE_DIR), stdin=subprocess.DEVNULL,
        )
        for line in proc2.stdout:
            yield line
            if "=== BROWSER OPEN" in line:
                yield "\nLog complete. Review the YachtIQ page, save, then close it.\n"
                return

        proc2.wait()
        if proc2.returncode != 0:
            yield f"\n[ERROR] YachtIQ filler exited with code {proc2.returncode}\n"
            return

        yield "\nDone.\n"

    return Response(generate(), mimetype="text/plain")


@app.route("/current-pdf")
def current_pdf():
    pdfs = sorted(
        [p for p in SAMPLES_DIR.iterdir() if p.is_file() and p.suffix.lower() == ".pdf"],
        key=lambda p: p.stat().st_mtime, reverse=True,
    )
    return {"name": pdfs[0].name if pdfs else None}


@app.route("/delete-pdf", methods=["POST"])
def delete_pdf():
    for p in SAMPLES_DIR.glob("*.pdf"):
        p.unlink(missing_ok=True)
    return Response("", status=204)


# ---------------------------------------------------------------------------
# Launch
# ---------------------------------------------------------------------------

def _open_browser():
    webbrowser.open("http://localhost:5000")


if __name__ == "__main__":
    t = threading.Timer(1.2, _open_browser)
    t.daemon = True
    t.start()
    print("Yacht IQ Input Bot -> http://localhost:5000")
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)
