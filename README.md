# SimpleMessageQueue

The SimpleMessageQueue is a lightweight Message Queue for sending messages between different applications and processes.

There is a server component which acts as a dispatch for messages and a client component to send and receive messages.

Multiple clients can connect to a server

## Install on an Ubuntu Linux System
Update the packages in the package manager before installing
```
sudo apt-get update
sudo apt-get install python3-pip
```

Clone the project into your home directory
```
cd ~
git clone https://github.com/Snackman8/SimpleMessageQueue
```

Install the SimpleMessageQueue packge
```
cd ~/SimpleMessageQueue
sudo pip3 install .
```

Install the included systemd service to run the SimpleMessageQueue
```
sudo ./install_systemd_service.sh
```

To check the status of the service, stop, or start use the commands below
```
sudo systemctl status SimpleMessageQueue
sudo systemctl stop SimpleMessageQueue
sudo systemctl start SimpleMessageQueue
```

To view the logs for the service
```
sudo journalctl -u SimpleMessageQueue
```
