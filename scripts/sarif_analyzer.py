import json
import logging
import csv
from typing import List, Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SarifAnalyzer:
    def __init__(self, sarif_file: str):
        self.sarif_file = sarif_file
        self.sarif_data = self._load_sarif_file()

    def _load_sarif_file(self) -> Dict[str, Any]:
        try:
            with open(self.sarif_file, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing SARIF file: {e}")
            return {}
        except FileNotFoundError:
            logger.error(f"SARIF file not found: {self.sarif_file}")
            return {}

    def get_results(self) -> List[Dict[str, Any]]:
        return self.sarif_data.get('runs', [{}])[0].get('results', [])

    def get_high_severity_issues(self) -> List[Dict[str, Any]]:
        return [result for result in self.get_results() if result.get('level') == 'error']

    def get_affected_files(self) -> List[str]:
        files = set()
        for result in self.get_results():
            for location in result.get('locations', []):
                file_path = location.get('physicalLocation', {}).get('artifactLocation', {}).get('uri')
                if file_path:
                    files.add(file_path)
        return list(files)

    def get_issue_types(self) -> Dict[str, int]:
        issue_types = {}
        for result in self.get_results():
            rule_id = result.get('ruleId')
            if rule_id:
                issue_types[rule_id] = issue_types.get(rule_id, 0) + 1
        return issue_types

    def get_summary(self) -> Dict[str, Any]:
        return {
            "total_issues": len(self.get_results()),
            "high_severity_issues": len(self.get_high_severity_issues()),
            "affected_files": len(self.get_affected_files()),
            "issue_types": len(self.get_issue_types())
        }

    def generate_report(self) -> Dict[str, Any]:
        return {
            "summary": self.get_summary(),
            "high_severity_issues": self.get_high_severity_issues(),
            "affected_files": self.get_affected_files(),
            "issue_types": self.get_issue_types()
        }

    def export_to_csv(self, csv_file: str):
        """Exports SARIF results to CSV."""
        results = self.get_results()
        if not results:
            logger.info("No results found to export.")
            return
        
        fieldnames = ['ruleId', 'message', 'severity', 'fileLocation']
        with open(csv_file, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for result in results:
                rule_id = result.get('ruleId', 'N/A')
                message = result.get('message', {}).get('text', 'No message')
                severity = result.get('level', 'unknown')
                file_location = (
                    result.get('locations', [{}])[0]
                    .get('physicalLocation', {})
                    .get('artifactLocation', {})
                    .get('uri', 'unknown')
                )

                writer.writerow({
                    'ruleId': rule_id,
                    'message': message,
                    'severity': severity,
                    'fileLocation': file_location
                })

def analyze_sarif(sarif_file: str, csv_file: str = None) -> Dict[str, Any]:
    analyzer = SarifAnalyzer(sarif_file)
    report = analyzer.generate_report()

    # If a CSV file is provided, export the report to CSV
    if csv_file:
        analyzer.export_to_csv(csv_file)
        logger.info(f"Results exported to {csv_file}")

    return report

if __name__ == "__main__":
    import sys
    if len(sys.argv) not in [2, 3]:
        print("Usage: python sarif_analyzer.py <path_to_sarif_file> [<path_to_csv_file>]")
        sys.exit(1)
    
    sarif_file = sys.argv[1]
    csv_file = sys.argv[2] if len(sys.argv) == 3 else None

    report = analyze_sarif(sarif_file, csv_file)
    print(json.dumps(report, indent=2))
