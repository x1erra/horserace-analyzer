#!/bin/bash
set -e

echo "Installing nvm (Node Version Manager)..."
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash

export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"  # This loads nvm
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"  # This loads nvm bash_completion

echo "Installing Node.js 20..."
nvm install 20
nvm use 20
nvm alias default 20

echo "Verifying Node version..."
node -v

echo "----------------------------------------------------------------"
echo "Node.js 20 installed successfully!"
echo "Please restart your terminal or run 'source ~/.bashrc' to use the new version."
echo "Then navigate to the project folder and run 'npm run dev' again."
echo "----------------------------------------------------------------"
