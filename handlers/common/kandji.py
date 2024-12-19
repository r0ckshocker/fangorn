import logging
from dotenv import load_dotenv
import json
from .helper import get_or_throw
import requests
import os

class KandjiClient():
    def __init__(self):
        load_dotenv()
        self.KANDJI_API_KEY = os.getenv("KANDJI_API_KEY")
        self.KANDJI_SUBDOMAIN = os.getenv("KANDJI_SUBDOMAIN")
        self.base_url = f"https://{self.KANDJI_SUBDOMAIN}.api.kandji.io/api/v1"

    def device_list(self):
        """Fetch all devices from Kandji with pagination"""
        devices = []
        offset = 0
        limit = 300
        
        url = f"{self.base_url}/devices"
        headers = {'Authorization': f'Bearer {self.KANDJI_API_KEY}'}

        while True:
            response = requests.get(
                url,
                headers=headers,
                params={'limit': limit, 'offset': offset}
            )
            
            if response.status_code == 200:
                data = response.json()
                if not data:
                    break
                    
                devices.extend(data)
                
                if len(data) < limit:
                    break
                    
                offset += limit
            else:
                raise Exception(f"Failed to retrieve device list: {response.status_code}")
                
        return devices