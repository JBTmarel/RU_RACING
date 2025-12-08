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

import os
os.system('mpg321 dingdong.mp3')