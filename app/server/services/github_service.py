import os
import boto3
import requests
import json
import logging
from datetime import datetime
from collections import Counter

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class GitHubService:
    def __init__(self, repo, token):
        self.repo = repo
        self.token = token
        self.base_url = f"https://api.github.com/repos/{self.repo}"
        self.headers = {
            'Authorization': f'Bearer {self.token}',
            'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28'
        }

    def _make_github_request(self, url, method='GET', data=None):
        try:
            if method == 'GET':
                response = requests.get(url, headers=self.headers)
            elif method == 'POST':
                response = requests.post(url, headers=self.headers, json=data)
            elif method == 'PATCH':
                response = requests.patch(url, headers=self.headers, json=data)
            elif method == 'PUT':
                response = requests.put(url, headers=self.headers, json=data)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"GitHub API request failed: {e}")
            raise

    # GitHub Pull Requests, Issues, and Comments Handling
    def fetch_pr_details(self, pr_number):
        url = f"{self.base_url}/pulls/{pr_number}/files"
        return self._make_github_request(url)

    def create_github_issue(self, title, body):
        url = f"{self.base_url}/issues"
        data = {'title': title, 'body': body}
        return self._make_github_request(url, method='POST', data=data)

    def create_pull_request(self, branch_name, title, body, files):
        self._create_branch(branch_name)
        self._create_files_in_branch(branch_name, files)
        url = f"{self.base_url}/pulls"
        data = {"title": title, "body": body, "head": branch_name, "base": "main"}
        return self._make_github_request(url, method='POST', data=data)

    def fetch_pr_comments(self, pr_number):
        url = f"{self.base_url}/issues/{pr_number}/comments"
        return self._make_github_request(url)

    def create_issue_for_unresolved_comments(self, pr_number):
        comments = self.fetch_pr_comments(pr_number)
        for comment in comments:
            if 'resolved' not in comment['body'].lower():
                self.create_github_issue(
                    title=f"Unresolved comment on PR #{pr_number}",
                    body=comment['body']
                )

    # Helper Functions for PR Creation
    def _create_branch(self, branch_name):
        url = f"{self.base_url}/git/refs"
        base_sha = self._make_github_request(f"{self.base_url}/git/refs/heads/main")['object']['sha']
        data = {"ref": f"refs/heads/{branch_name}", "sha": base_sha}
        return self._make_github_request(url, method='POST', data=data)

    def _create_files_in_branch(self, branch_name, files):
        for file_path, content in files.items():
            url = f"{self.base_url}/contents/{file_path}"
            data = {
                "message": f"Add {file_path}",
                "content": content,
                "branch": branch_name
            }
            self._make_github_request(url, method='PUT', data=data)

    # GitHub Advanced Security (GHAS) - Alerts Handling
    def fetch_security_alerts(self, alert_type='code-scanning'):
        url = f"{self.base_url}/{alert_type}/alerts"
        return self._make_github_request(url)

    def _trim_alert(self, alert, alert_type):
        try:
            first_seen = alert['created_at']
            number = alert['number']
            repository = self.repo
            state = alert['state']
            alert_age = (datetime.now().date() - datetime.strptime(first_seen, '%Y-%m-%dT%H:%M:%SZ').date()).days
            age = next((i for i in [2, 7, 30, 60, 90] if alert_age <= i), 100)

            if alert_type == 'code-scanning':
                description = alert['rule']['description']
                severity = alert['rule'].get('severity', 'N/A')
                path = alert.get('most_recent_instance', {}).get('location', {}).get('path', 'unknown_path')
                return {
                    'age': str(age),
                    'number': number,
                    'repository': repository,
                    'state': state,
                    'description': description,
                    'severity': severity,
                    'path': path
                }
            elif alert_type == 'secret-scanning':
                secret_type = alert['secret_type_display_name']
                return {
                    'age': str(age),
                    'number': number,
                    'repository': repository,
                    'state': state,
                    'secret_type': secret_type
                }
            elif alert_type == 'dependabot':
                description = alert['security_advisory']['description']
                severity = alert['security_advisory'].get('severity', 'N/A')
                path = alert['dependency']['package']
                return {
                    'age': str(age),
                    'number': number,
                    'repository': repository,
                    'state': state,
                    'description': description,
                    'severity': severity,
                    'path': path
                }
        except KeyError as e:
            logger.error(f"Error processing {alert_type} alert {alert['number']}: {e}")
            return None

    def fetch_and_trim_alerts(self, alert_type):
        alerts = self.fetch_security_alerts(alert_type)
        trimmed_alerts = [self._trim_alert(alert, alert_type) for alert in alerts if self._trim_alert(alert, alert_type)]
        return trimmed_alerts

    def generate_alert_stats(self, alerts):
        total_alerts = len(alerts)
        severity_counts = Counter(alert['severity'] for alert in alerts if 'severity' in alert)
        state_counts = Counter(alert['state'] for alert in alerts if 'state' in alert)
        age_distribution = Counter(alert['age'] for alert in alerts if 'age' in alert)

        return {
            'total_alerts': total_alerts,
            'severity_counts': dict(severity_counts),
            'state_counts': dict(state_counts),
            'age_distribution': dict(age_distribution)
        }

    def process_alerts(self):
        try:
            # Fetch and trim alerts for all types
            code_scanning_alerts = self.fetch_and_trim_alerts('code-scanning')
            secret_scanning_alerts = self.fetch_and_trim_alerts('secret-scanning')
            dependabot_alerts = self.fetch_and_trim_alerts('dependabot')

            all_alerts = code_scanning_alerts + secret_scanning_alerts + dependabot_alerts
            alert_stats = self.generate_alert_stats(all_alerts)

            logger.info(f"Combined Alert Stats: {json.dumps(alert_stats, indent=4)}")

            return {
                'alerts': all_alerts,
                'stats': alert_stats
            }
        except Exception as e:
            logger.error(f"Error processing alerts: {e}")
            raise

    def upload_alerts_to_s3(self, s3_bucket, combined_data):
        s3_client = boto3.client('s3')
        combined_json = json.dumps(combined_data, indent=4)
        try:
            s3_client.put_object(Bucket=s3_bucket, Key="ghas/ghas.json", Body=combined_json)
            logger.info(f"File 'ghas.json' uploaded to S3 bucket '{s3_bucket}'")
        except Exception as e:
            logger.error(f"Failed to upload ghas.json to S3: {e}")
            raise
