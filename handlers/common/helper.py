import os
import sys
import json
import logging
from datetime import datetime, timezone
from cryptography.fernet import Fernet
import errno

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def get_or_throw(key_name):
    res = os.getenv(key_name, None)
    if res is None:
        logger.error(f"Environment variable '{key_name}' is required.")
        sys.exit(1)
    return res

def get_today():
    return datetime.now(timezone.utc).date()

def hours_since_timestamp(timestamp):
    timestamp_dt = datetime.strptime(timestamp, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    difference = now - timestamp_dt
    return difference.total_seconds() / 3600

def get_keys(filter_key, src):
    return list({item.get(filter_key) for item in src})

def groups_filter(src, field, query):
    return [item for item in src if item.get(field) == query]

def search_list(src, match):
    if match in src:
        logger.info(f'Match found for {match}')
        results = src[match]
        if isinstance(results, list):
            return ", ".join(results)
        return results
    return None

def write_file(data, filename):
    path = f"/tmp/{filename}"
    try:
        with open(path, "w") as file:
            json.dump(data, file, indent=4)
            logger.info(f"File '{filename}' written successfully.")
    except Exception as e:
        logger.error(f"Failed to write file {filename}: {e}")
        raise
    return path


def decrypt_file(path):
    try:
        with open(path, "r") as file:
            cipher_text = file.read().encode()
            key = Fernet.generate_key()  # This should be stored securely and not hard-coded
            cipher_suite = Fernet(key)
            data = cipher_suite.decrypt(cipher_text).decode()
            logger.info(f"File '{path}' decrypted successfully.")
            return json.loads(data)
    except Exception as e:
        logger.error(f"Failed to decrypt file {path}: {e}")
        raise

def dedupe(src):
    dupes = {}
    for item in src:
        key = item.title
        logger.info(f"De-duplicating findings named {key}")
        if key in dupes:
            find = dupes[key]
            find.endpoints.extend(item.endpoints)
            logger.info(f"{find.title} found in {len(find.endpoints)} locations")
        else:
            dupes[key] = item
    return list(dupes.values())

def cereal(objects):
    return json.loads(json.dumps([obj.__dict__ for obj in objects]))

def create_dir(path):
    if not os.path.exists(path):
        try:
            logger.info(f"Attempting to create directory {path}.")
            os.makedirs(path)
        except OSError as exc:
            if exc.errno != errno.EEXIST:
                raise

def get_timestamp():
    return datetime.utcnow().strftime("%Y/%m/%d %H:%M:%S UTC")
