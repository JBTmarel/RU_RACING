#!/usr/bin/env python3
# import time
# import RPi.GPIO as GPIO

# PIN = 18  # PWM pin
# FREQ1 = 784  # G5
# FREQ2 = 659  # E5

# GPIO.setmode(GPIO.BCM)
# GPIO.setup(PIN, GPIO.OUT)
# p = GPIO.PWM(PIN, FREQ1)
# try:
#     p.start(50)         # 50% duty
#     p.ChangeFrequency(FREQ1); time.sleep(0.2)
#     p.ChangeFrequency(FREQ2); time.sleep(0.3)
# finally:
#     p.stop()
#     GPIO.cleanup()

import subprocess
import os
import sys

# Get the directory of the current script
script_dir = os.path.dirname(os.path.abspath(__file__))
wav_path = os.path.join(script_dir, "dingdong.wav")

# Try using paplay (PulseAudio) which handles more formats (like ADPCM) than aplay
# If paplay is missing, you might need to convert the wav to PCM:
# ffmpeg -i dingdong.wav -acodec pcm_s16le dingdong_fixed.wav
try:
    subprocess.run(["paplay", wav_path], check=True)
except FileNotFoundError:
    # Fallback or error if paplay is not installed
    print("Error: 'paplay' not found. Try installing PulseAudio or converting the WAV to PCM.")
    # Fallback to aplay just in case
    subprocess.run(["aplay", wav_path])