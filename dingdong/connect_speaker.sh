#!/bin/bash

bluetoothctl <<EOF
connect 2C:FD:B4:22:A8:CD

EOF

/home/arnarob23/RU_RACING/dingdong/big-red-button/venv/bin/python3 /home/arnarob23/RU_RACING/dingdong/big-red-button/app.py
