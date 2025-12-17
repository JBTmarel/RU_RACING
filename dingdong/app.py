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
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, make_response, render_template, send_from_directory
from flask import abort, Response, redirect, url_for, session
from markupsafe import escape

app = Flask(__name__)

TEST_SOUND_FILE = os.path.join(os.path.dirname(__file__), "test_sound.mp3")

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

INDEX_HTML = open("templates/index.html").read()

# Needed for sessions (password login)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "123")

# Password required on allowed IPs
LOG_PASSWORD = os.environ.get("LOG_PASSWORD", "123")

# In-memory IP block list: ip -> datetime (UTC) until which it’s blocked
BLOCKED_IPS = {}


@app.route("/apple-touch-icon.png")
@app.route("/apple-touch-icon-precomposed.png")
def apple_touch_icon():
    return send_from_directory("static/icons", "apple-touch-icon.png")

@app.route("/favicon.ico")
def favicon():
    return send_from_directory("static/icons", "icon-192.png")


@app.get("/")
def index():
    # resp = make_response(INDEX_HTML)
    # resp.headers["Cache-Control"] = "no-store"
    # resp.headers["X-Content-Type-Options"] = "nosniff"
    # return resp
    return render_template("index.html")

def client_ip():
    return request.remote_addr or "unknown"

@app.route("/admin/logs", methods=["GET", "POST"])
@app.route("/admin/logs", methods=["GET", "POST"])
@app.route("/admin/logs", methods=["GET", "POST"])
@app.route("/admin/logs", methods=["GET", "POST"])
def admin_logs():
    ip = client_ip()
    message = ""

    # 1) Password gate using session
    if not session.get("logs_authenticated"):
        if request.method == "POST" and request.form.get("password"):
            if request.form["password"] == LOG_PASSWORD:
                session["logs_authenticated"] = True
                return redirect(url_for("admin_logs"))
            else:
                message = "Wrong password."

        # show login form
        return f"""
        <html><body>
          <h1>Admin Login</h1>
          <p>Your IP: {escape(ip)}</p>
          <p style="color:red;">{escape(message)}</p>
          <form method="post">
            <input type="password" name="password" placeholder="Password">
            <button type="submit">Login</button>
          </form>
        </body></html>
        """

    # 2) Already authenticated: handle actions (block IP, test sound)
    if request.method == "POST":
        action = request.form.get("action", "")
        if action == "block":
            target_ip = (request.form.get("ip") or "").strip()
            try:
                minutes = int(request.form.get("minutes") or "0")
            except ValueError:
                minutes = 0

            if target_ip and minutes > 0:
                BLOCKED_IPS[target_ip] = datetime.utcnow() + timedelta(minutes=minutes)
                message = f"Blocked {target_ip} for {minutes} minute(s)."
            else:
                message = "Invalid IP or minutes."

        elif action == "test_sound":
        # Play a test sound with mpg321 to check the speaker
            if os.path.exists(TEST_SOUND_FILE):
                try:
                    # -q = quiet console output
                    # & at the end so Flask isn't blocked while playing
                    os.system(f"mpg321 -q '{TEST_SOUND_FILE}' &")
                    message = "Test sound triggered."
                except Exception as e:
                    message = f"Error playing test sound: {e}"
            else:
                message = "Test sound file not found on the Pi."


    # 3) Read log file
    try:
        with open("app.log", "r") as f:
            data = f.read()
    except FileNotFoundError:
        data = "No log file yet."

    max_chars = 8000
    if len(data) > max_chars:
        data = "...(truncated)...\n" + data[-max_chars:]

    # 4) Build HTML for current blocks
    now = datetime.utcnow()
    blocked_list_items = []
    for bip, until in list(BLOCKED_IPS.items()):
        if now >= until:
            # expired: clean up
            del BLOCKED_IPS[bip]
            continue
        mins_left = int((until - now).total_seconds() // 60) + 1
        blocked_list_items.append(f"<li>{escape(bip)} - {mins_left} min left</li>")

    blocked_html = "<ul>" + "".join(blocked_list_items) + "</ul>" if blocked_list_items else "<p>None.</p>"

    page = f"""
    <html><body>
      <h1>Admin Logs</h1>
      <p>Your IP: {escape(ip)}</p>
      <p style="color: green;">{escape(message)}</p>

      <h2>Speaker test</h2>
      <form method="post">
        <input type="hidden" name="action" value="test_sound">
        <button type="submit">Play test sound</button>
      </form>

      <hr>

      <h2>Block IP from using the button</h2>
      <form method="post">
        <input type="hidden" name="action" value="block">
        <label>IP:
          <input name="ip" placeholder="10.100.8.123">
        </label>
        <label>Minutes:
          <input name="minutes" type="number" min="1" max="1440" value="5">
        </label>
        <button type="submit">Block</button>
      </form>

      <h3>Currently blocked IPs</h3>
      {blocked_html}

      <h2>Log output</h2>
      <pre>{escape(data)}</pre>
    </body></html>
    """
    return Response(page, mimetype="text/html")


@app.post("/ding")
def ding():

    ip = client_ip()
    now = datetime.utcnow()

    until = BLOCKED_IPS.get(ip)
    if until and now < until:
        remaining_sec = (until - now).total_seconds()
        remaining_min = int(remaining_sec // 60) + 1
        return f"Your IP is blocked from using this button for {remaining_min} more minute(s).", 403

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
    print("Got into keepalive")
    def loop():
        print("Got into loop")
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
            print("Got into while loop")
            time.sleep(sleepTime)#-countdown)
#            for i in range(countdown):
#                time.sleep(1)
#                print("Keepalive sound playing in", countdown-i, "seconds")
            try:
                # Use aplay (ALSA player) which is standard on Raspberry Pi
                print("Got into try")
                with _audio_lock:
                    subprocess.run(["aplay", wav_path], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    now = datetime.now()
                    now_f = now.strftime("[%H:%M:%S]")
                    print(now_f, "Keepalive sound played")
            except Exception as e:
                print(f"Error playing keepalive sound: {e}")

    thread = threading.Thread(target=loop, daemon=True)
    thread.start()

if __name__ == "__main__":
    start_keepalive_loop()
    app.run(host="0.0.0.0", port=8000)
