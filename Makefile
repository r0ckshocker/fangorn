.PHONY: push pull tail build up down test logs clean login venv help setup run install-codeql setup-codeql create-local-data install-js-packs cli-test codeql-analyze codeql-compare codeql-find-endpoints archive upload update

# Virtual environment settings
VENV_NAME := venv
PYTHON := $(VENV_NAME)/bin/python
PIP := $(VENV_NAME)/bin/pip
CODEQL_VERSION := 2.12.6
CODEQL_DIR := $(HOME)/codeql
CODEQL_ZIP := codeql-bundle-osx64.zip
CODEQL_URL := https://github.com/github/codeql-cli-binaries/releases/download/v$(CODEQL_VERSION)/$(CODEQL_ZIP)
current_dir := $(shell pwd)

# Default target
all: setup setup-codeql

# Help documentation
help:  ## Print the help documentation
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

# Clean build artifacts
clean:
	rm -rf bin/ \
	rm -rf build/ \
	rm -rf tmp/ \
	rm -rf lambda.zip \
	rm -rf $(VENV_NAME) \
	find ./ -type d -name '__pycache__' -delete \
	find ./ -type f -name '*.pyc' -delete

# Setup the environment and update .env
setup: create-local-data
	@echo "Setting up environment..."
	python3 -m venv $(VENV_NAME)
	./setup.sh
	@echo "Installing Python dependencies..."
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

# Create local_data directory
create-local-data:
	@mkdir -p local_data	

# Install CodeQL
install-codeql:
	@echo "Installing CodeQL..."
	@if [ ! -d "$(CODEQL_DIR)" ]; then \
		mkdir -p $(CODEQL_DIR); \
		echo "Downloading CodeQL from $(CODEQL_URL)..."; \
		if curl -L $(CODEQL_URL) -o $(CODEQL_DIR)/$(CODEQL_ZIP); then \
			echo "Download completed. Verifying file..."; \
			if file $(CODEQL_DIR)/$(CODEQL_ZIP) | grep -q "Zip archive data"; then \
				echo "File verified as ZIP archive. Extracting..."; \
				cd $(CODEQL_DIR) && unzip -q $(CODEQL_ZIP); \
				rm $(CODEQL_DIR)/$(CODEQL_ZIP); \
				echo "export PATH=\"$(CODEQL_DIR)/codeql:$$PATH\"" >> $(HOME)/.zshrc; \
				echo "CodeQL installed successfully."; \
			else \
				echo "Error: Downloaded file is not a valid ZIP archive."; \
				echo "File type: $$(file $(CODEQL_DIR)/$(CODEQL_ZIP))"; \
				rm $(CODEQL_DIR)/$(CODEQL_ZIP); \
				exit 1; \
			fi; \
		else \
			echo "Error: Failed to download CodeQL."; \
			exit 1; \
		fi; \
	else \
		echo "CodeQL is already installed."; \
	fi

# Setup CodeQL in VSCode and venv
setup-codeql: install-codeql
	@echo "Setting up CodeQL in VSCode..."
	@if [ ! -f "$(HOME)/Library/Application Support/Code/User/settings.json" ]; then \
		mkdir -p "$(HOME)/Library/Application Support/Code/User"; \
		echo '{"codeQL.cli.executablePath": "$(CODEQL_DIR)/codeql/codeql"}' > "$(HOME)/Library/Application Support/Code/User/settings.json"; \
	else \
		sed -i '' 's|"codeQL.cli.executablePath":.*|"codeQL.cli.executablePath": "$(CODEQL_DIR)/codeql/codeql"|' "$(HOME)/Library/Application Support/Code/User/settings.json"; \
	fi
	@echo "CodeQL path set in VSCode settings."
	@echo "export PATH=\"$(CODEQL_DIR)/codeql:\$$PATH\"" >> $(VENV_NAME)/bin/activate
	@echo "CodeQL path added to venv activation script."

# Install JavaScript packs
install-js-packs:
	@echo "Installing JavaScript packs..."
	npm install -g @github/codeql-javascript

# Run a specific command or interactive mode
run:
	@if [ -z "$(command)" ]; then \
		$(PYTHON) grond.py; \
	else \
		$(PYTHON) grond.py $(command); \
	fi

# Login to AWS ECR
login:
	@echo "Logging into AWS ECR..."
	aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 016897515115.dkr.ecr.us-east-1.amazonaws.com

# Build Docker image
build:
	@echo "Building Docker image..."
	docker build --platform linux/amd64 -t fangorn:latest .

# Push Docker image to ECR
push: login build
	@echo "Pushing Docker image to ECR..."
	docker tag fangorn:latest 016897515115.dkr.ecr.us-east-1.amazonaws.com/fangorn:latest
	docker push 016897515115.dkr.ecr.us-east-1.amazonaws.com/fangorn:latest

# Pull Docker image from ECR
pull: clean login
	aws ecr get-login-password | docker login --username AWS --password-stdin 016897515115.dkr.ecr.us-east-1.amazonaws.com
	docker pull 016897515115.dkr.ecr.us-east-1.amazonaws.com/fangorn:latest

# Tail Docker logs
tail: up
	docker logs -f app

# Build Docker Compose
build-compose:
	docker-compose build

# Start Docker Compose
up:
	docker-compose --env-file .env up --build -d

# Stop Docker Compose
down:
	docker-compose down

# Create virtual environment
venv:
	@echo "Creating virtual environment..."
	python3 -m venv $(VENV_NAME)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.test.txt
	@echo "Virtual environment created and dependencies installed."

# Run tests
test: venv
	@echo "Running tests..."
	$(PYTHON) test_fangorn.py
	@echo "Tests complete. Details at logs.json and test.log"

# Display test logs
logs: test
	@echo "Displaying test logs..."

# Create the ZIP archive for AWS lambda
archive: build  ## Create the archive for AWS lambda
	docker run --platform linux/amd64 -v $(current_dir):/opt/mount --entrypoint /bin/sh --workdir /var/task fangorn:latest -c "zip -r9 /opt/mount/lambda.zip ."

# Upload the archive to S3
upload:  ## Upload the archive to S3
	aws s3 cp lambda.zip s3://afs-org-ose-fangorn-data/entmoot.zip --profile sec

# Update one of the lambda functions
update: upload  ## Update the lambda function
	aws lambda update-function-code --function-name afs-lambda-$(LAMBDA_NAME)-ose-us-east-2 --s3-bucket afs-org-ose-fangorn-data --s3-key entmoot.zip --profile sec

# Install required packages
install-packages:
	@echo "Installing required packages..."
	$(PIP) install -r requirements.txt

# Run CLI tests
cli-test: install-packages
	@echo "Running CLI tests..."
	$(PYTHON) tests/test_cli.py