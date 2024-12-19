#!/bin/bash

# Everything here happens at container-start time. That's important for building
# the react-app as it'll bake-in some ENV variables given to the container at
# that time

# Compile react
cd /usr/src/app/client
echo "Compiling react app"
react_build_log="build.log"
# something here is wrongly assuming dist/ and this shuts it up
mkdir -p ./dist/public/webviewer
npm run build > "$react_build_log" 2>&1

if [ $? -ne 0 ]; then
  cat "$react_build_log"
  echo "React failed to build: $?"
  exit 1
fi

# Ensure the built files are in the correct place
mkdir -p /usr/src/app/server/static/
cp -r dist/* /usr/src/app/server/static/

# Start the Flask app
cd /usr/src
/usr/src/venv/bin/python3 -u run.py
