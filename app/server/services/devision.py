from datetime import datetime
import os
from app.server.models import Entmoot
from app.server.services.helper.actions import LambdaService, S3Service
import logging
from collections import defaultdict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Devision(Entmoot):
    def __init__(self, chat):
        super().__init__(
            blob_filename="devision/devision.json",
            tasks=[],
            chat=chat
        )
        self.data = {"apps": {}, "stats": {}, "updated": None}
        self.lambda_function = os.getenv("DEVISION_LAMBDA")
        logger.info(f"Devision Lambda function: {self.lambda_function}")
        self.lambda_service = LambdaService()
        self.dashboard_context = (
            "User is on the Devision page. Devision Entmoot displays device data from Kandji MDM, "
            "showing device status, OS versions, blueprints, and MDM enrollment status "
            "for iPads and other managed devices."
        )
        self.initialize_data()

    def calculate_stats(self, devices):
        """Calculate statistics from device array"""
        stats = {
            "total_devices": len(devices),
            "os_versions": defaultdict(int),
            "models": defaultdict(int),
            "blueprints": defaultdict(int),
            "mdm_status": {
                "enabled": 0,
                "disabled": 0
            },
            "agent_status": {
                "installed": 0,
                "missing": 0
            },
            "last_seen": {
                "today": 0,
                "week": 0,
                "month": 0,
                "older": 0
            }
        }

        now = datetime.utcnow()

        for device in devices:
            # Count OS versions
            if os_version := device.get("os_version"):
                stats["os_versions"][os_version] += 1

            # Count models
            if model := device.get("model_kandji"):
                stats["models"][model] += 1

            # Count blueprints
            if blueprint := device.get("blueprint"):
                stats["blueprints"][blueprint] += 1

            # Count MDM status
            if device.get("mdm_status") == "enabled":
                stats["mdm_status"]["enabled"] += 1
            else:
                stats["mdm_status"]["disabled"] += 1

            # Count agent status
            if device.get("agent_status") == "installed":
                stats["agent_status"]["installed"] += 1
            else:
                stats["agent_status"]["missing"] += 1

            # Calculate last seen buckets
            try:
                if last_seen_str := device.get("last_seen_kandji"):
                    last_seen = datetime.strptime(last_seen_str, "%Y-%m-%dT%H:%M:%S.%fZ")
                    delta = now - last_seen
                    
                    if delta.days == 0:
                        stats["last_seen"]["today"] += 1
                    elif delta.days <= 7:
                        stats["last_seen"]["week"] += 1
                    elif delta.days <= 30:
                        stats["last_seen"]["month"] += 1
                    else:
                        stats["last_seen"]["older"] += 1
            except Exception as e:
                logger.error(f"Error parsing last_seen date for device {device.get('serial')}: {e}")
                stats["last_seen"]["older"] += 1

        # Convert defaultdicts to regular dicts
        stats["os_versions"] = dict(stats["os_versions"])
        stats["models"] = dict(stats["models"])
        stats["blueprints"] = dict(stats["blueprints"])

        return stats

    def initialize_data(self):
        """Initialize data from array format"""
        logger.info("Initializing Devision data")
        devices = self.get_blob_data()
        
        if not isinstance(devices, list):
            logger.error("Failed to fetch device data or invalid format")
            self.data = {"error": "Failed to fetch device data"}
            return

        # Transform array to dictionary using serial as key
        self.data["apps"] = {device["serial"]: device for device in devices if device.get("serial")}
        
        # Calculate statistics
        self.data["stats"] = self.calculate_stats(devices)
        
        # Set updated timestamp
        self.data["updated"] = datetime.utcnow().isoformat()
        
        logger.info(f"Initialized with {len(self.data['apps'])} devices")

    def get_dashboard(self):
        """Get dashboard data with current statistics"""
        logger.info("Getting Devision dashboard data.")
        current_time = datetime.now()
        if self.last_updated is None or (current_time - self.last_updated) > self.update_interval:
            self.initialize_data()
            self.last_updated = current_time
        return self.data

    def refresh_dashboard(self):
        """Refresh dashboard by invoking lambda and reinitializing data"""
        logger.info(f"Refreshing Devision dashboard data. Invoking lambda {self.lambda_function}.")
        try:
            result = self.lambda_service.invoke_function(self.lambda_function, {})
            logger.info(f"Lambda function invoked successfully. Result: {result}")
            self.initialize_data()
            self.last_updated = datetime.now()
        except Exception as e:
            logger.error(f"Error invoking lambda {self.lambda_function}: {e}")
            return {"error": str(e)}
        
        return {
            "status": "updated",
            "updated": self.data["updated"],
            "total_devices": len(self.data["apps"])
        }

    def get_dashboard_summary(self):
        """Get dashboard summary statistics"""
        return {
            "total_devices": len(self.data.get("apps", {})),
            "os_versions": self.data.get("stats", {}).get("os_versions", {}),
            "mdm_status": self.data.get("stats", {}).get("mdm_status", {"enabled": 0, "disabled": 0}),
            "agent_status": self.data.get("stats", {}).get("agent_status", {"installed": 0, "missing": 0}),
            "activity": self.data.get("stats", {}).get("last_seen", {
                "today": 0,
                "week": 0,
                "month": 0,
                "older": 0
            }),
            "models": self.data.get("stats", {}).get("models", {}),
            "blueprints": self.data.get("stats", {}).get("blueprints", {}),
            "last_updated": self.data.get("updated")
        }