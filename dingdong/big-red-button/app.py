#!/usr/bin/env python3
import os
import sys
import time
import pathlib
import math
import struct
import wave
import subprocess
import threading
from flask import Flask, request, jsonify, make_response

app = Flask(__name__)

# --- Configuration ---
# Path to your sound script. Change this if you want.
DING_SCRIPT = os.environ.get("DING_SCRIPT", "./dingdong.py")
# Minimum seconds between presses (prevents rapid double-clicks)
COOLDOWN_SEC = float(os.environ.get("COOLDOWN_SEC", "1.5"))
# Command timeout in seconds (avoid hanging)
CMD_TIMEOUT = float(os.environ.get("CMD_TIMEOUT", "10"))

_lock = threading.Lock()
_audio_lock = threading.Lock()
_last_press = 0.0

INDEX_HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
  <title>Big Red Button</title>
  <style>
    :root { --bg:#0b0b0b; --red:#e11; --red-dark:#a00; }
    html, body { height:100%; margin:0; background:var(--bg); color:#fff; }
    body { display:flex; align-items:center; justify-content:center; font-family:system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, Cantarell, "Helvetica Neue", Arial, "Noto Sans", "Apple Color Emoji", "Segoe UI Emoji"; }
    .wrap { width:100vw; height:100vh; display:flex; align-items:center; justify-content:center; }
    #btn { width:min(80vw, 480px); height:min(80vw, 480px); border-radius:50%; border:none; outline:none; cursor:pointer; background:var(--red); color:#fff; font-weight:800; letter-spacing:0.04em; font-size:clamp(28px, 9vw, 56px); box-shadow:0 12px 0 var(--red-dark), 0 24px 48px rgba(0,0,0,.6); transition: transform .06s ease, box-shadow .06s ease, filter .15s ease; }
    #btn:active { transform: translateY(4px); box-shadow:0 8px 0 var(--red-dark), 0 16px 32px rgba(0,0,0,.55); }
    #btn:disabled { filter: grayscale(0.2) brightness(0.85); cursor:not-allowed; }
    .status { position:fixed; bottom:16px; left:0; right:0; text-align:center; opacity:0.9; font-size:clamp(12px, 2.5vw, 16px); }
  </style>
</head>
<body>
  <div class="wrap">
    <button id="btn" aria-label="Ring the bell">DING DONG</button>
  </div>
  <div class="status" id="status">Ready</div>
  <script>
    const btn = document.getElementById('btn');
    const statusEl = document.getElementById('status');
    async function ring() {
      btn.disabled = true;
      statusEl.textContent = 'Ringing…';
      try {
        const res = await fetch('/ding', { method: 'POST' });
        const data = await res.json().catch(() => ({}));
        if (res.ok && data.ok) {
          statusEl.textContent = 'Dinged!';
        } else {
          statusEl.textContent = 'Error — ' + (data.error || res.statusText);
        }
      } catch (e) {
        statusEl.textContent = 'Network error';
      } finally {
        setTimeout(() => { statusEl.textContent = 'Ready'; btn.disabled = false; }, 800);
      }
    }
    btn.addEventListener('click', ring);
    document.addEventListener('keydown', (e) => { if (e.code === 'Space' || e.code === 'Enter') ring(); });
  </script>
</body>
</html>
"""

@app.get("/")
def index():
    resp = make_response(INDEX_HTML)
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    return resp

@app.post("/ding")
def ding():
    global _last_press
    with _lock:
        now = time.monotonic()
        if now - _last_press < COOLDOWN_SEC:
            return jsonify(ok=False, error=f"cooldown {COOLDOWN_SEC:.1f}s"), 429
        _last_press = now

    script_path = pathlib.Path(DING_SCRIPT)
    if not script_path.exists():
        return jsonify(ok=False, error=f"Script not found: {script_path}"), 500

    try:
        if script_path.suffix == ".py":
            cmd = [sys.executable, str(script_path)]
        else:
            cmd = [str(script_path)]
        
        with _audio_lock:
            subprocess.run(cmd, cwd=str(script_path.parent), check=True, timeout=CMD_TIMEOUT)
        
        return jsonify(ok=True)
    except subprocess.TimeoutExpired:
        return jsonify(ok=False, error=f"Script timed out after {CMD_TIMEOUT}s"), 504
    except subprocess.CalledProcessError as e:
        return jsonify(ok=False, error=f"Script exited with {e.returncode}"), 500
    except Exception as e:
        return jsonify(ok=False, error=str(e)), 500

def generate_keepalive_wav(filename="keepalive.wav"):
    """Generates a 1-second, 20Hz sine wave at low amplitude."""
    sample_rate = 44100
    duration = 1.0
    frequency = 20.0
    amplitude = 4000  # Low amplitude (16-bit range is -32768 to 32767)
    
    n_samples = int(sample_rate * duration)
    
    with wave.open(filename, 'w') as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 2 bytes per sample (16-bit)
        wav_file.setframerate(sample_rate)
        
        for i in range(n_samples):
            value = int(amplitude * math.sin(2 * math.pi * frequency * i / sample_rate))
            data = struct.pack('<h', value)
            wav_file.writeframesraw(data)

def start_keepalive_loop():
    """Plays the keepalive sound every 8 minutes in a background thread."""
    def loop():
        wav_path = os.path.join(str(pathlib.Path(__file__).parent.absolute()), "keepalive.wav")
        # Ensure the file exists
        if not os.path.exists(wav_path):
            try:
                generate_keepalive_wav(wav_path)
                print(f"Generated keepalive sound at {wav_path}")
            except Exception as e:
                print(f"Failed to generate keepalive wav: {e}")
                return
        sleepTime = 10
        countdown = 3
        while True:
            time.sleep(sleepTime-countdown)
            for i in range(countdown):
                time.sleep(1)
                print("Keepalive sound playing in", countdown-i, "seconds")
            try:
                # Use aplay (ALSA player) which is standard on Raspberry Pi
                with _audio_lock:
                    subprocess.run(["aplay", wav_path], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                print("Keepalive sound played")
            except Exception as e:
                print(f"Error playing keepalive sound: {e}")

    thread = threading.Thread(target=loop, daemon=True)
    thread.start()

if __name__ == "__main__":
    start_keepalive_loop()
    app.run(host="0.0.0.0", port=8000)
