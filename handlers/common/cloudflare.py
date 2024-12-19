import logging
from dotenv import load_dotenv
import json
from .helper import get_or_throw
import requests
import os

class CloudFlareClient():
    def __init__(self):
        load_dotenv()
        self.CLOUDFLARE_KEY = os.getenv("CLOUDFLARE_API_KEY")
        self.base_url = "https://api.cloudflare.com/client/v4/"

    def device_list(self):
        per_page = 100
        count = 2
        page = 1
        devices = []

        url = self.base_url + "accounts/5636156c5055d0024d9b63c50e1b2d61/devices"
        headers = {
            "Authorization": "Bearer " + self.CLOUDFLARE_KEY,
            "Content-Type": "application/json"
        }

        while len(devices) < count:
            response = requests.get(url + f"?per_page={per_page}&page={page}", headers=headers)
            if response.status_code == 200:
                result = response.json()
                data = [x for x in result["result"] if x["device_type"] != "ios"]
                page = result["result_info"]["page"]
                count = result["result_info"]["count"]
                for item in data:
                    item["serial"] = item["serial_number"]
                    item["last_seen_cf"] = item.get("last_seen")
                    item["model_cf"] = item.get('model')
                    item["user_cf"] = item["user"]["name"]
                    item.pop('key', None)
                devices.extend(data)
            else:
                raise Exception("Failed to retreive device list.")
        json.dump(devices, open("device_list.json", "w"))
        return devices
