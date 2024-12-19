#!/bin/bash

# Ensure the script is run from the project root
if [ ! -f "setup.sh" ]; then
    echo "Please run this script from the project root directory."
    exit 1
fi

# Function to update .env file
update_env() {
    echo "Updating .env file..."

    # Check if .env file exists, create from template if it doesn't
    if [ ! -f .env ]; then
        echo "Creating new .env file from template..."
        cp .env.tpl .env
    fi

    # Prompt the user for new values or keep the current ones
    while IFS='=' read -r key value; do
        # Skip empty lines and comments
        if [[ ! -z "$key" && "$key" != \#* ]]; then
            current_value=$(grep "^$key=" .env | cut -d '=' -f2)
            echo -n "$key (current value: $current_value): "
            read -r new_value
            # If user input is empty, retain the current value
            if [ -z "$new_value" ]; then
                new_value=$current_value
            fi
            # Update the .env file with the new value or the existing one
            sed -i '' "s|$key=.*|$key=$new_value|" .env
        fi
    done < .env.tpl

    echo ".env file updated. Please review the file if necessary."
}

# Check if virtual environment exists, create if it doesn't
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

echo "Setting up environment..."

# Call the update_env function
update_env

# Handle users.json
if [ ! -f users.json ]; then
    cp users.json.tpl users.json
    echo "users.json file created. Please update it with your admin details."
    
    # Prompt for admin details
    read -p "Enter admin first name: " admin_first_name
    read -p "Enter admin last name: " admin_last_name
    read -p "Enter admin email: " admin_email
    read -s -p "Enter admin password: " admin_password
    echo

    # Update users.json with admin details
    sed -i '' "s/\"first_name\": \"Admin\"/\"first_name\": \"$admin_first_name\"/" users.json
    sed -i '' "s/\"last_name\": \"Apprentice\"/\"last_name\": \"$admin_last_name\"/" users.json
    sed -i '' "s/\"email\": \"admin@apprentice.io\"/\"email\": \"$admin_email\"/" users.json
    sed -i '' "s/\"password\": \"adminpassword\"/\"password\": \"$admin_password\"/" users.json

    echo "Admin details updated in users.json."
else
    echo "users.json already exists. Skipping creation."
fi

# Install Python dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Setup CodeQL
echo "Setting up CodeQL..."
make setup-codeql

echo "Setup complete."
echo "Next step: Run 'make run' to start the application or 'make run command=<command_name>' to run a specific command."

# Deactivate virtual environment
deactivate