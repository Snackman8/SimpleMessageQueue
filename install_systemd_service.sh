#!/bin/sh

sudo useradd -r -s /bin/false SimpleMessageQueue

sudo cp ./SimpleMessageQueue.service /etc/systemd/system/
sudo chown root:root /etc/systemd/system/SimpleMessageQueue.service
sudo chmod 644 /etc/systemd/system/SimpleMessageQueue.service

sudo systemctl daemon-reload

sudo systemctl enable SimpleMessageQueue
sudo systemctl restart SimpleMessageQueue
