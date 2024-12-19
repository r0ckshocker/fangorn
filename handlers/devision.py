from common.kandji import KandjiClient
# from common.crowdstrike import CrowdStrikeClient
# from common.cloudflare import CloudFlareClient
from common.helper import get_or_throw
import boto3
import json
from io import BytesIO
import os
from dotenv import load_dotenv
import logging

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

def get_kandji_devices():
    """Fetch Kandji devices"""
    logger.info("Fetching Kandji devices")
    try:
        client = KandjiClient()
        devices = client.device_list()
        logger.info(f"Retrieved {len(devices)} devices from Kandji")
        return devices
    except Exception as e:
        logger.error(f"Error fetching Kandji devices: {e}")
        return []

def trim_device_data(devices):
    """Transform raw Kandji data into trimmed format"""
    trimmed_devices = []
    
    for device in devices:
        trimmed_device = {
            "serial": device.get("serial_number", ""),
            "last_seen_kandji": device.get("last_check_in", ""),
            "model_kandji": device.get("model", ""),
            "user_kandji": device.get("user", {}).get("name", "") if isinstance(device.get("user"), dict) else "",
            "api_url": device.get("asset_tag", ""),
            "device_name": device.get("device_name", ""),
            "os_version": device.get("os_version", ""),
            "blueprint": device.get("blueprint_name", ""),
            "email": device.get("user", {}).get("email", "") if isinstance(device.get("user"), dict) else "",
            "mdm_status": "enabled" if device.get("mdm_enabled") else "disabled",
            "agent_status": "installed" if device.get("agent_installed") else "missing"
        }
        trimmed_devices.append(trimmed_device)
    
    return trimmed_devices

# Commented out template for future agent status checks
"""
def get_cs_status(serial_number):
    try:
        client = CrowdStrikeClient()
        response = client.find_by_serial_number(serial_number)
        if response and response.get("body", {}).get("resources"):
            return "installed"
        return "not_found"
    except Exception as e:
        logger.error(f"Error checking CS status for {serial_number}: {e}")
        return "error"

def get_warp_status(serial_number):
    try:
        client = CloudFlareClient()
        devices = client.device_list()
        for device in devices:
            if device.get("serial_number") == serial_number:
                return "installed"
        return "not_found"
    except Exception as e:
        logger.error(f"Error checking Warp status for {serial_number}: {e}")
        return "error"

def enrich_device_data(devices):
    enriched_devices = []
    for device in devices:
        serial = device.get("serial")
        if serial:
            device["falcon_status"] = get_cs_status(serial)
            device["warp_status"] = get_warp_status(serial)
        enriched_devices.append(device)
    return enriched_devices
"""

def handler(event, context):
    logger.info("Handler started")
    load_dotenv()
    DATA_BUCKET = os.getenv('DATA_BUCKET')
    
    try:
        # Get raw device data
        raw_devices = get_kandji_devices()
        
        # Create trimmed version
        trimmed_devices = trim_device_data(raw_devices)
        
        # Option to enrich data with agent status checks
        # trimmed_devices = enrich_device_data(trimmed_devices)
        
        # Prepare files for S3
        raw_file = BytesIO(json.dumps(raw_devices).encode('utf-8'))
        trimmed_file = BytesIO(json.dumps(trimmed_devices).encode('utf-8'))
        
        # Upload both files to S3 in the devision directory
        s3 = boto3.client('s3')
        s3.put_object(Bucket=DATA_BUCKET, Key='devision/kandji_devices.json', Body=raw_file)
        s3.put_object(Bucket=DATA_BUCKET, Key='devision/devision.json', Body=trimmed_file)
        
        logger.info("Handler completed successfully")
        
    except Exception as e:
        logger.error(f"Failed to process devices: {e}")
        raise

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    handler(None, None)