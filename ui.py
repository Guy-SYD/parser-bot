"""
ui.py  —  Parser Bot web UI

Run:  python ui.py
Opens http://localhost:5000 automatically.

Steps performed on submit:
  1. Save the uploaded PDF to samples/
  2. Run src/main.py --input <pdf>          (parse → output/result.json)
  3. Run src/input_YIQ.py --id <id> --input output/result.json --no-review
     (fill YachtIQ form)
Output from both steps is streamed live to the browser.
"""

import os
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path

from flask import Flask, Response, redirect, render_template_string, request, url_for

# ---------------------------------------------------------------------------
BASE_DIR    = Path(__file__).resolve().parent
SAMPLES_DIR = BASE_DIR / "samples"
OUTPUT_FILE = BASE_DIR / "output" / "result.json"
PYTHON      = str(Path(sys.executable))          # same venv python

SAMPLES_DIR.mkdir(exist_ok=True)
(BASE_DIR / "output").mkdir(exist_ok=True)

app = Flask(__name__)

# ---------------------------------------------------------------------------
# HTML template (inline — no templates/ folder needed)
# ---------------------------------------------------------------------------
PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Parser Bot</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #f5f5f5;
    display: flex;
    justify-content: center;
    align-items: flex-start;
    min-height: 100vh;
    padding: 48px 16px;
  }
  .card {
    background: #fff;
    border-radius: 12px;
    box-shadow: 0 2px 16px rgba(0,0,0,.1);
    padding: 40px;
    width: 100%;
    max-width: 520px;
  }
  h1 { font-size: 1.4rem; font-weight: 600; margin-bottom: 28px; color: #111; }
  label { display: block; font-size: .85rem; font-weight: 500; color: #444; margin-bottom: 6px; }
  input[type="text"], input[type="number"] {
    width: 100%; padding: 10px 12px; border: 1px solid #ddd;
    border-radius: 7px; font-size: .95rem; outline: none;
    transition: border-color .2s;
  }
  input[type="text"]:focus, input[type="number"]:focus { border-color: #4f8ef7; }
  .field { margin-bottom: 20px; }
  .upload-area {
    border: 2px dashed #ddd; border-radius: 7px; padding: 24px;
    text-align: center; cursor: pointer; transition: border-color .2s, background .2s;
    position: relative;
  }
  .upload-area:hover { border-color: #4f8ef7; background: #f0f6ff; }
  .upload-area input[type="file"] {
    position: absolute; inset: 0; opacity: 0; cursor: pointer; width: 100%; height: 100%;
  }
  .upload-text { font-size: .9rem; color: #888; pointer-events: none; }
  .filename {
    margin-top: 8px; font-size: .85rem; color: #4f8ef7; font-weight: 500;
    min-height: 1.2em;
  }
  button[type="submit"] {
    width: 100%; padding: 12px; background: #4f8ef7; color: #fff;
    border: none; border-radius: 7px; font-size: 1rem; font-weight: 600;
    cursor: pointer; transition: background .2s; margin-top: 8px;
  }
  button[type="submit"]:hover { background: #3a7de0; }
  button[type="submit"]:disabled { background: #aaa; cursor: not-allowed; }

  /* Output log */
  #log-wrap {
    margin-top: 28px; display: none;
  }
  #log-wrap h2 { font-size: .95rem; font-weight: 600; margin-bottom: 8px; color: #333; }
  #log {
    background: #1a1a2e; color: #e0e0e0; border-radius: 7px;
    padding: 14px 16px; font-family: "Cascadia Code", "Consolas", monospace;
    font-size: .78rem; line-height: 1.55; max-height: 400px; overflow-y: auto;
    white-space: pre-wrap; word-break: break-all;
  }
  #log .ok   { color: #6fcf97; }
  #log .err  { color: #eb5757; }
  #log .info { color: #56ccf2; }
  .done-msg {
    margin-top: 12px; padding: 10px 14px; border-radius: 7px;
    font-size: .9rem; font-weight: 500; display: none;
  }
  .done-msg.success { background: #e6f9ee; color: #1a7a40; }
  .done-msg.error   { background: #fdecea; color: #9b2335; }
</style>
</head>
<body>
<div class="card">
  <h1>Parser Bot</h1>
  <form id="run-form" enctype="multipart/form-data">
    <div class="field">
      <label>PDF Specification</label>
      <div class="upload-area" id="drop-zone">
        <input type="file" name="pdf" id="pdf-input" accept=".pdf" required>
        <div class="upload-text">Click to browse or drag & drop a PDF</div>
      </div>
      <div class="filename" id="filename-display"></div>
    </div>
    <div class="field">
      <label for="yacht-id">YachtIQ ID</label>
      <input type="text" id="yacht-id" name="yacht_id"
             placeholder="e.g. 447250" required autocomplete="off">
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
// Show filename after selection
document.getElementById('pdf-input').addEventListener('change', function() {
  const name = this.files[0] ? this.files[0].name : '';
  document.getElementById('filename-display').textContent = name;
});

// Form submit → stream output
document.getElementById('run-form').addEventListener('submit', async function(e) {
  e.preventDefault();

  const btn = document.getElementById('run-btn');
  const logWrap = document.getElementById('log-wrap');
  const logEl = document.getElementById('log');
  const doneMsg = document.getElementById('done-msg');

  // Reset
  logEl.textContent = '';
  doneMsg.style.display = 'none';
  doneMsg.className = 'done-msg';
  logWrap.style.display = 'block';
  btn.disabled = true;
  btn.textContent = 'Running…';

  const formData = new FormData(this);

  try {
    const resp = await fetch('/run', { method: 'POST', body: formData });
    if (!resp.ok) {
      const text = await resp.text();
      logEl.textContent = text;
      showDone(false);
      return;
    }

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let hadError = false;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      const chunk = decoder.decode(value, { stream: true });
      // Append text, colour-code lines
      chunk.split('\\n').forEach(line => {
        if (!line) { logEl.appendChild(document.createTextNode('\\n')); return; }
        const span = document.createElement('span');
        const lower = line.toLowerCase();
        if (lower.includes('[ok]') || lower.startsWith('done')) span.className = 'ok';
        else if (lower.includes('[error]') || lower.includes('error') || lower.includes('traceback')) {
          span.className = 'err';
          hadError = true;
        }
        else if (lower.includes('[miss]') || lower.includes('warning')) span.className = 'err';
        else if (lower.startsWith('==') || lower.startsWith('filling') || lower.startsWith('navigating')) span.className = 'info';
        span.textContent = line + '\\n';
        logEl.appendChild(span);
        logEl.scrollTop = logEl.scrollHeight;
      });
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

  function showDone(success) {
    doneMsg.style.display = 'block';
    if (success) {
      doneMsg.className = 'done-msg success';
      doneMsg.textContent = 'Pipeline completed successfully.';
    } else {
      doneMsg.className = 'done-msg error';
      doneMsg.textContent = 'Pipeline finished with errors — check the log above.';
    }
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


@app.route("/run", methods=["POST"])
def run():
    pdf_file  = request.files.get("pdf")
    yacht_id  = request.form.get("yacht_id", "").strip()

    if not pdf_file or not pdf_file.filename:
        return Response("No PDF uploaded.", status=400)
    if not yacht_id:
        return Response("No YachtIQ ID provided.", status=400)

    # Save PDF to samples/
    safe_name = Path(pdf_file.filename).name
    pdf_path  = SAMPLES_DIR / safe_name
    pdf_file.save(str(pdf_path))

    def generate():
        # ── Step 1: PDF parser ──────────────────────────────────────────────
        yield "=== Step 1: Parsing PDF ===\n"
        cmd1 = [PYTHON, str(BASE_DIR / "src" / "main.py"), "--input", str(pdf_path)]
        proc1 = subprocess.Popen(
            cmd1, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, cwd=str(BASE_DIR),
            stdin=subprocess.DEVNULL,
        )
        for line in proc1.stdout:
            yield line
        proc1.wait()
        if proc1.returncode != 0:
            yield f"\n[ERROR] Parser exited with code {proc1.returncode}\n"
            return

        yield "\n=== Step 2: Filling YachtIQ ===\n"
        # ── Step 2: YachtIQ filler ──────────────────────────────────────────
        cmd2 = [
            PYTHON, str(BASE_DIR / "src" / "input_YIQ.py"),
            "--id",    yacht_id,
            "--input", str(OUTPUT_FILE),
            "--no-review",
        ]
        proc2 = subprocess.Popen(
            cmd2, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, cwd=str(BASE_DIR),
            stdin=subprocess.DEVNULL,
        )
        for line in proc2.stdout:
            yield line
            # Sentinel printed by input_YIQ.py once the summary is done.
            # The browser is now open and waiting for the user — end the stream
            # here so the UI shows the log without hanging.
            if "=== BROWSER OPEN" in line:
                yield "\nLog complete. Review the YachtIQ page, save, then close it.\n"
                return

        # Only reached if sentinel never appeared (error path)
        proc2.wait()
        if proc2.returncode != 0:
            yield f"\n[ERROR] YachtIQ filler exited with code {proc2.returncode}\n"
            return

        yield "\nDone.\n"

    return Response(generate(), mimetype="text/plain")


# ---------------------------------------------------------------------------
# Launch
# ---------------------------------------------------------------------------

def _open_browser():
    webbrowser.open("http://localhost:5000")


if __name__ == "__main__":
    # Open browser after a short delay so Flask is ready
    t = threading.Timer(1.2, _open_browser)
    t.daemon = True
    t.start()

    print("Parser Bot UI → http://localhost:5000")
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)
