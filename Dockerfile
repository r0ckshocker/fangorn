FROM debian:bookworm-slim

# Install Node, Python, git, and other necessary packages
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    nodejs python3 git \
    ghostscript build-essential ffmpeg libsm6 libxext6 python3.11-venv \
    npm

# Create and activate Python virtual environment
RUN mkdir -p /usr/src/venv
RUN python3 -m venv /usr/src/venv
RUN /usr/src/venv/bin/pip install gunicorn

# Copy and install Python dependencies
COPY requirements.txt /usr/src/requirements.txt
RUN /usr/src/venv/bin/pip install -r /usr/src/requirements.txt

# Copy and install npm dependencies
RUN mkdir -p /usr/src/app/client
COPY app/client/package.json /usr/src/app/client/package.json
COPY app/client/package-lock.json /usr/src/app/client/package-lock.json
WORKDIR /usr/src/app/client
RUN npm install --legacy-peer-deps

# Copy the rest of the client and build it
COPY app/client /usr/src/app/client
RUN npm run build

# Copy the Flask server code
WORKDIR /usr/src/app/server
COPY app/server /usr/src/app/server

# Copy the run script and the main Python script
WORKDIR /usr/src
COPY run.py /usr/src/run.py
COPY run.sh /usr/src/run.sh
RUN chmod +x /usr/src/run.sh

# Expose the port
EXPOSE 8080

# Start the application
CMD ["/usr/src/run.sh"]
