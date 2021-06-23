#!/bin/sh

sudo cp ./SimpleMessageQueue.service /etc/systemd/system/
sudo chown root:root /etc/systemd/system/SimpleMessageQueue.service
sudo chmod 644 /etc/systemd/system/SimpleMessageQueue.service
