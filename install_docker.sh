#!/bin/bash
set -e

echo "Detected Linux Mint (based on Ubuntu Noble)"
echo "Installing Docker dependencies..."

# Update package list
sudo apt-get update

# Install prerequisites
sudo apt-get install -y ca-certificates curl gnupg

# Add Docker's official GPG key
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Add the repository to Apt sources
echo \
  "deb [arch=\"$(dpkg --print-architecture)\" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  noble stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update

# Install Docker packages
echo "Installing docker-ce, docker-ce-cli, containerd.io, docker-buildx-plugin, docker-compose-plugin..."
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Add user to docker group
echo "Adding user $USER to the docker group..."
sudo usermod -aG docker $USER

echo "----------------------------------------------------------------"
echo "Installation complete!"
echo "IMPORTANT: You need to log out and log back in for the group changes to take effect."
echo "Alternatively, run 'newgrp docker' in your current terminal session."
echo "----------------------------------------------------------------"
echo "Verify installation with: docker compose version"
