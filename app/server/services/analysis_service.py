import os
import json
import logging
from app.utils.file_utils import load_json_file, should_analyze_file, is_excluded
from marvin.app.server.services.openai_service import OpenAIService
from app.server.services.github_service import GitHubService
from app.utils.code_utils import PRReviewer

logger = logging.getLogger(__name__)

class AnalysisService:
    def __init__(self, repo, token):
        self.project_data = self._load_project_data()
        self.openai_service = OpenAIService()
        self.github_service = GitHubService(repo, token)

    def _load_project_data(self):
        try:
            return load_json_file('.github/config/project.json')
        except Exception as error:
            logger.error(f'Error loading project data: {error}')
            raise

    def analyze_pull_request(self, event_path):
        try:
            with open(event_path, 'r') as file:
                event = json.load(file)

            reviewer = PRReviewer(event, self.project_data)
            reviewer.comment_on_pr()

            pr_number = event.get('pull_request', {}).get('number')
            logger.info(f"Analyzing PR #{pr_number}")

            pr_details = self.github_service.fetch_pr_details(pr_number)
            self._analyze_pr_files(pr_details)

            return {"status": "success"}
        except Exception as error:
            logger.error(f"Failed to analyze PR: {error}")
            return {"status": "error", "message": str(error)}

    def _analyze_pr_files(self, pr_details):
        try:
            for file in pr_details:
                file_path = file.get('filename', 'unknown')
                patch = file.get('patch', '')
                if patch:
                    prompt = f"Analyze the following code changes and suggest improvements: {patch}"
                    analysis = self.openai_service.call_openai_api(prompt)
                    logger.info(f"PR file analysis for {file_path}: {json.dumps(analysis, indent=2)}")
        except Exception as error:
            logger.error(f"Failed to analyze PR files: {error}")
            raise

    def analyze_repository(self):
        try:
            self._analyze_repository_structure()
            self._analyze_repository_files()
            return {"status": "success"}
        except Exception as error:
            logger.error(f"Failed to analyze repository: {error}")
            return {"status": "error", "message": str(error)}

    def _analyze_repository_structure(self):
        try:
            project_description = self.project_data['projects'][0]['description']
            prompt = f"Analyze the structure of this project: {project_description}. What improvements can be made?"
            analysis = self.openai_service.call_openai_api(prompt)
            logger.info(f"Project structure analysis: {json.dumps(analysis, indent=2)}")
            return analysis
        except Exception as error:
            logger.error(f"Failed to analyze repository structure: {error}")
            raise

    def _analyze_repository_files(self):
        try:
            exclude_patterns = self.project_data['exclude_patterns']
            file_size_limit = self.project_data['file_size_limit']

            for root, _, files in os.walk('.'):
                for file in files:
                    file_path = os.path.join(root, file)
                    if not is_excluded(file_path, exclude_patterns) and should_analyze_file(file_path, file_size_limit):
                        self._analyze_file(file_path)
        except Exception as error:
            logger.error(f"Failed to analyze repository files: {error}")
            raise

    def _analyze_file(self, file_path):
        try:
            with open(file_path, 'r') as f:
                file_content = f.read()

            prompt = f"Analyze the following file and suggest improvements: {file_content}"
            analysis = self.openai_service.call_openai_api(prompt)
            logger.info(f"File analysis for {file_path}: {json.dumps(analysis, indent=2)}")
        except Exception as error:
            logger.error(f"Failed to analyze file {file_path}: {error}")
            raise

    def analyze_github_alerts(self):
        try:
            logger.info("Starting GitHub Advanced Security alerts analysis")
            alerts_data = self.github_service.process_alerts()
            self.github_service.upload_alerts_to_s3(os.environ.get('S3_BUCKET'), alerts_data)
            return {"status": "success"}
        except Exception as error:
            logger.error(f"Failed to analyze GitHub alerts: {error}")
            return {"status": "error", "message": str(error)}
