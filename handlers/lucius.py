import os
import json
import boto3
from datetime import datetime
from collections import Counter
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def extract_sub_directory(path):
    if isinstance(path, str):
        path_parts = path.split('/')
        if len(path_parts) > 2 and (path_parts[0] == 'apps' or path_parts[0] == 'libs'):
            return '/'.join(path_parts[:3])
    return 'other'

def trim_alert(alert):
    try:
        details = alert.get('most_recent_instance', {})
        description = alert['rule']['description']
        rule_id = alert['rule']['id']
        dismissed_by = alert.get('dismissed_by')
        dismissed_reason = alert.get('dismissed_reason')
        first_seen = alert['created_at']
        number = alert['number']
        severity = alert['rule'].get('severity')
        state = alert['state']
        repository = 'monorepo'

        path = details.get('location', {}).get('path', 'unknown_path')
        severity_level = alert['rule'].get('security_severity_level', "N/A")

        alert_age = (datetime.now().date() - datetime.strptime(first_seen, '%Y-%m-%dT%H:%M:%SZ').date()).days
        age = next((i for i in [2, 7, 30, 60, 90] if alert_age <= i), 100)

        directory = extract_sub_directory(path)

        alert_trimmed = {
            'age': str(age),
            'details': details,
            'description': description,
            'rule_id': rule_id,
            'dismissed_by': dismissed_by,
            'dismissed_reason': dismissed_reason,
            'number': number,
            'path': path,
            'repository': repository,
            'security_severity_level': severity_level,
            'severity': severity,
            'state': state,
            'directory': directory
        }
        return alert_trimmed
    except Exception as e:
        logger.error(f"Error processing alert {alert}: {e}")
        return None

def generate_stats(alerts):
    total_alerts = len(alerts)
    severity_counts = Counter(alert['severity'] for alert in alerts if 'severity' in alert)
    state_counts = Counter(alert['state'] for alert in alerts if 'state' in alert)
    age_distribution = Counter(alert['age'] for alert in alerts if 'age' in alert)
    directory_counts = Counter(alert['directory'] for alert in alerts if 'directory' in alert)
    type_counts = Counter(alert['rule_id'] for alert in alerts if 'rule_id' in alert)

    return {
        'total_alerts': total_alerts,
        'severity_counts': dict(severity_counts),
        'state_counts': dict(state_counts),
        'age_distribution': dict(age_distribution),
        'directory_counts': dict(directory_counts),
        'type_counts': dict(type_counts)
    }

def main():
    sarif_directory = os.getenv('SARIF_DIRECTORY', './sarif-files')
    all_alerts = []

    for file_name in os.listdir(sarif_directory):
        if file_name.endswith(".sarif"):
            with open(os.path.join(sarif_directory, file_name), 'r') as file:
                sarif_data = json.load(file)
                for run in sarif_data["runs"]:
                    for result in run["results"]:
                        alert = trim_alert(result)
                        if alert:
                            all_alerts.append(alert)

    # Generate stats
    stats = generate_stats(all_alerts)
    logger.info("Statistics: %s", json.dumps(stats, indent=4))

    # Combine alerts and stats into one JSON object
    combined_data = {
        'stats': stats,
        'alerts': all_alerts
    }

    combined_json = json.dumps(combined_data, indent=4)

    # Save to S3
    s3_bucket = os.getenv('DATA_BUCKET', 'my-default-bucket')
    s3_client = boto3.client('s3')
    try:
        s3_client.put_object(Bucket=s3_bucket, Key="ghas/ghas.json", Body=combined_json)
        logger.info("File 'ghas.json' uploaded to S3 bucket '%s'", s3_bucket)
    except Exception as e:
        logger.error(f"Failed to upload ghas.json to S3: {e}")

def handler(event, context):
    main()

if __name__ == '__main__':
    main()
