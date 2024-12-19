import os
import json
import logging
from datetime import datetime
from app.server.services.helper.actions import LambdaService, S3Service
from app.server.models import Entmoot

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Lucius(Entmoot):
    def __init__(self, chat):
        super().__init__(
            blob_filename="lucius/lucius.json",
            chat=chat
        )
        self.lambda_function = os.getenv("LUCIUS_JSON_LAMBDA")
        self.data = {
            "apps": {},
            "stats": {}
        }
        self.lambda_service = LambdaService()
        self.dashboard_context = (
            "User is on the Lucius page; Lucius Entmoot displays GitHub Advanced Security alerts "
            "organized by rule and application."
        )
        self.initialize_data()

    def get_app_name(self, path):
        """Extract app or lib name from path"""
        if not path:
            return "unknown"
        
        parts = path.split('/')
        if not parts:
            return "unknown"
            
        if parts[0] == "apps" and len(parts) > 1:
            return f"apps/{parts[1]}"
        elif parts[0] == "libs" and len(parts) > 1:
            return f"libs/{parts[1]}"
        return parts[0]

    get_relevant_alerts(self,)

    def initialize_data(self):
        logger.info("Initializing Lucius data")
        alert_data = self.get_blob_data()
        if not alert_data or 'error' in alert_data:
            logger.error("No alert data found in the blob.")
            return

        # Process alerts
        formatted_alerts = {}
        rule_stats = {}
        app_stats = {}
        
        raw_alerts = alert_data.get("alerts", {})
        
        for alert_id, alert in raw_alerts.items():
            if not isinstance(alert, dict):
                continue

            # Determine rule ID
            rule_id = None
            if alert.get("type") == "code_scanning":
                rule_id = alert.get("rule", "unknown_rule")
            elif alert.get("type") == "secret_scanning":
                rule_id = "secret_scanning_alerts"
            elif alert.get("type") == "dependabot":
                rule_id = "dependency_alerts"

            # Get app/lib name
            app_name = self.get_app_name(alert.get("path"))

            # Format alert
            formatted_alert = {
                "type": alert.get("type", "unknown"),
                "id": alert.get("id", ""),
                "rule": rule_id,
                "severity": alert.get("severity", ""),
                "security_level": alert.get("security_level", ""),
                "state": alert.get("state", ""),
                "path": alert.get("path", ""),
                "directory": alert.get("directory", ""),
                "description": alert.get("description", ""),
                "age_days": alert.get("age_days", 0),
                "age_bucket": alert.get("age_bucket", ""),
                "created": alert.get("created", ""),
                "updated": alert.get("updated", ""),
                "app_name": app_name,
                "dismissed_by": json.dumps(alert.get("dismissed_by", {})),
                "dismissed_reason": alert.get("dismissed_reason", "")
            }
            formatted_alerts[alert_id] = formatted_alert

            # Update rule statistics
            if rule_id not in rule_stats:
                rule_stats[rule_id] = {
                    "count": 0,
                    "severity_counts": {},
                    "state_counts": {},
                    "type": alert.get("type"),
                    "apps": {}
                }
            
            rule_stats[rule_id]["count"] += 1
            severity = alert.get("severity", "unknown").lower()
            state = alert.get("state", "unknown").lower()
            
            # Update rule severity and state counts
            rule_stats[rule_id]["severity_counts"][severity] = \
                rule_stats[rule_id]["severity_counts"].get(severity, 0) + 1
            rule_stats[rule_id]["state_counts"][state] = \
                rule_stats[rule_id]["state_counts"].get(state, 0) + 1

            # Update rule->app statistics
            if app_name not in rule_stats[rule_id]["apps"]:
                rule_stats[rule_id]["apps"][app_name] = {
                    "count": 0,
                    "alerts": [],
                    "severity_counts": {},
                    "state_counts": {}
                }
            
            app_stats = rule_stats[rule_id]["apps"][app_name]
            app_stats["count"] += 1
            app_stats["alerts"].append(alert_id)
            app_stats["severity_counts"][severity] = \
                app_stats["severity_counts"].get(severity, 0) + 1
            app_stats["state_counts"][state] = \
                app_stats["state_counts"].get(state, 0) + 1

        # Store processed data
        self.data = {
            "apps": {
                "alerts": formatted_alerts,
                "rule_stats": rule_stats
            },
            "stats": alert_data.get("stats", {}),
            "updated": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        }
        logger.info(f"Lucius data initialized with {len(formatted_alerts)} alerts")

    def get_dashboard_summary(self):
        """Enhanced dashboard summary with rule and app-based statistics"""
        rule_stats = self.data["apps"].get("rule_stats", {})
        alerts = self.data["apps"].get("alerts", {})

        # Get total alerts by type
        type_counts = {
            "code_scanning": sum(1 for alert in alerts.values() if alert["type"] == "code_scanning"),
            "secret_scanning": sum(1 for alert in alerts.values() if alert["type"] == "secret_scanning"),
            "dependabot": sum(1 for alert in alerts.values() if alert["type"] == "dependabot")
        }

        # Get top rules by alert count
        top_rules = sorted(
            [(rule, data["count"]) for rule, data in rule_stats.items()],
            key=lambda x: x[1],
            reverse=True
        )[:5]

        # Get unique apps/libs
        apps = {alert["app_name"] for alert in alerts.values()}

        summary = {
            "total_alerts": len(alerts),
            "type_counts": type_counts,
            "rules_summary": {
                "total_rules": len(rule_stats),
                "top_rules": top_rules
            },
            "total_apps": len(apps),
            "severity_distribution": self.data["stats"].get("severity_counts", {}),
            "state_distribution": self.data["stats"].get("state_counts", {}),
            "last_updated": self.data.get("updated", "Unknown")
        }
        
        logger.info(f"Lucius dashboard summary: {summary}")
        return summary

    def get_dashboard(self):
        logger.info("Getting Lucius dashboard data.")
        current_time = datetime.now()
        if self.last_updated is None or (current_time - self.last_updated) > self.update_interval:
            self.initialize_data()
            self.last_updated = current_time
        return self.data

    def refresh_dashboard(self):
        logger.info(f"Refreshing Lucius dashboard data. Invoking lambda {self.lambda_function}.")
        try:
            self.lambda_service.invoke_function(self.lambda_function, {})
            logger.info("Lambda function invoked successfully.")
            self.initialize_data()
            self.last_updated = datetime.now()
        except Exception as e:
            logger.error(f"Error invoking lambda {self.lambda_function}: {e}")
            return {"error": str(e)}
        
        total_alerts = len(self.data["apps"]["alerts"])
        status = {
            "status": "updated",
            "updated": self.data["updated"],
            "message": f"{total_alerts} alerts processed."
        }
        logger.info("Lucius dashboard refreshed.")
        return status