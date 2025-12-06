# Big Red Button (Flask) for Raspberry Pi

A tiny web app that shows a full-screen **big red button** (mobile + desktop). When pressed, it runs **your Python script** that plays a “ding-dong” on a speaker (e.g., via GPIO PWM).

## Quick start (on the Pi)

```bash
unzip big-red-button.zip
cd big-red-button

# Create venv + install deps
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Put your sound script at /home/pi/dingdong.py or edit DING_SCRIPT env var
# (An example dingdong.py is included; it uses GPIO18 PWM to chirp.)

# Test (dev server)
python app.py
# or production server
.venv/bin/gunicorn -b 0.0.0.0:8000 app:app
```

Open: `http://<PI-IP>:8000` (find IP with `hostname -I`).

## Start on boot (systemd)

```bash
# Copy service unit
sudo cp systemd/big-red-button.service /etc/systemd/system/big-red-button.service
sudo systemctl daemon-reload
sudo systemctl enable --now big-red-button.service
sudo systemctl status big-red-button.service --no-pager
# Logs
journalctl -u big-red-button -f
```

## Configure

- **DING_SCRIPT**: path to your script (default `/home/pi/dingdong.py`).
- **COOLDOWN_SEC**: min seconds between presses (default `1.5`).
- **CMD_TIMEOUT**: max seconds to let your script run (default `10`).

If your script needs root (GPIO), you can change `User=pi` to `User=root` in the service, or set up permissions/capabilities to access GPIO as `pi`.

## Wiring for the example `dingdong.py`

- GPIO 18 (PWM) → 330Ω resistor → speaker +; speaker − → GND.
- Start quietly! Tiny speakers only.

> Security note: This is intended for LAN use. If exposing outside your network, add auth/reverse proxy and firewall appropriately.
