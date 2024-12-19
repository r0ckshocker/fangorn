import json
import csv
import click
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from functools import lru_cache
import re
from collections import defaultdict, Counter
import os
import time
import random
from scripts.utils import logger, create_http_session, get_bearer_token
from scripts.alfred import ask_alfred
import backoff
from ratelimit import limits, sleep_and_retry

# Configure logging
LOG_FILE = 'local_data/scoper.log'
logging.basicConfig(level=logging.INFO, filename=LOG_FILE, filemode='w')
logger = logging.getLogger(__name__)

# Constants
MAX_WORKERS = 5
CHUNK_SIZE = 5
MAX_RETRIES = 3
CALLS_PER_MINUTE = 50  # Adjust based on your API limit

# Define MITRE ATT&CK tactics we're interested in
MITRE_TACTICS = [
    "Reconnaissance",
    "Initial Access",
    "Execution",
    "Persistence",
    "Privilege Escalation",
    "Defense Evasion",
    "Credential Access",
    "Discovery",
    "Lateral Movement",
    "Collection",
    "Command and Control",
    "Exfiltration",
    "Impact"
]

# Global system prompt
SYSTEM_PROMPT = f"""
You are Lucius, an expert security analyst for the Apprentice.io Security team. Your task is to analyze API routes from their CLI, considering that Tempo is a monorepo TypeScript application running in Amazon ECS with Cloudflare WAF in a passive configuration.

Think from an attacker's perspective, considering the unique attack surface and threat model of a cloud-based manufacturing system for large pharma companies.

When analyzing potential attacks, categorize them according to the MITRE ATT&CK framework, focusing on the following tactics:
{', '.join(MITRE_TACTICS)}

Provide your analysis in a structured JSON format as specified in the user prompts.
"""

def load_routes(file_path):
    """Load routes from a JSON file."""
    try:
        with open(file_path, 'r') as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error(f"Error loading routes: {e}")
        return {}

def chunk_routes(routes, chunk_size):
    """Split routes into chunks for processing."""
    return [
        {k: routes[k] for k in list(routes.keys())[i:i+chunk_size]}
        for i in range(0, len(routes), chunk_size)
    ]
def generate_basic_csvs(results, output_dir):
    """Generate basic CSV files from the scoping results."""
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate in_scope_routes.csv
    with open(os.path.join(output_dir, 'in_scope_routes.csv'), 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Route', 'Risk Level', 'Reason'])
        for route in results['in_scope_routes']:
            writer.writerow([route['route'], route['risk_level'], route['reason']])
    
    # Generate out_of_scope_routes.csv
    with open(os.path.join(output_dir, 'out_of_scope_routes.csv'), 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Route', 'Reason'])
        for route in results['out_of_scope_routes']:
            writer.writerow([route['route'], route['reason']])
    
    # Generate attack_samples.csv
    with open(os.path.join(output_dir, 'attack_samples.csv'), 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Attack Type', 'Description', 'Impact', 'Suggested Mitigation'])
        for tactic in results['attack_scenarios']:
            for scenario in results['attack_scenarios'][tactic]:
                writer.writerow([scenario['name'], scenario['description'], scenario['potential_impact'], ''])  # No mitigation in current structure

def generate_formatted_routes_csv(results, output_file):
    """Generate a formatted CSV file for in-scope routes."""
    paths = []
    methods = []
    risks = []
    analyses = []

    for route in results['in_scope_routes']:
        full_route = route['route']
        method, path = full_route.split(' ', 1)
        paths.append(full_route)
        methods.append(method)
        risks.append(route['risk_level'])
        analyses.append(route['reason'])

    # Determine the maximum depth of the path segments
    max_depth = max(len(path.split('/')) for path in paths)

    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f)
        
        # Write header
        header = ['Full_Route', 'Method', 'Risk', 'Analysis'] + [f'Level_{i}' for i in range(1, max_depth)]
        writer.writerow(header)

        # Write data rows
        for i, full_route in enumerate(paths):
            method = methods[i]
            risk = risks[i]
            analysis = analyses[i]
            path = full_route.split(' ', 1)[1]
            segments = path.split('/')
            row = [full_route, method, risk, analysis] + segments + [''] * (max_depth - len(segments))
            writer.writerow(row)

@lru_cache(maxsize=1000)
@sleep_and_retry
@limits(calls=CALLS_PER_MINUTE, period=60)
@backoff.on_exception(backoff.expo, Exception, max_tries=MAX_RETRIES)
def analyze_routes_chunk(chunk, previous_results_json):
    """Analyze a chunk of routes with caching, rate limiting, and exponential backoff."""
    previous_results = json.loads(previous_results_json)
    
    user_prompt = f"""
    Analyze the following chunk of API routes:
    {chunk}

    Consider the previous analysis results:
    {json.dumps(previous_results, indent=2)}

    Provide your analysis in the following JSON format:
    {{
        "in_scope_routes": [
            {{
                "route": "route_name",
                "risk_level": "high/medium/low",
                "reason": "reason for risk level"
            }}
        ],
        "out_of_scope_routes": [
            {{
                "route": "route_name",
                "reason": "reason for being out of scope"
            }}
        ],
        "focus_areas": ["focus area 1", "focus area 2"],
        "attack_scenarios": {{
            "Reconnaissance": [
                {{
                    "name": "scenario name",
                    "description": "brief description of the attack scenario",
                    "affected_routes": ["route 1", "route 2"],
                    "potential_impact": "description of potential impact"
                }}
            ],
            "Initial Access": [],
            "Execution": [],
            "Persistence": [],
            "Privilege Escalation": [],
            "Defense Evasion": [],
            "Credential Access": [],
            "Discovery": [],
            "Lateral Movement": [],
            "Collection": [],
            "Command and Control": [],
            "Exfiltration": [],
            "Impact": []
        }}
    }}
    
    Ensure that each attack scenario is categorized under the most appropriate MITRE ATT&CK tactic.
    """
    
    response = ask_alfred(user_prompt, SYSTEM_PROMPT)
    result = json.loads(response)
    
    # Ensure all keys are present in the result
    for key in ["in_scope_routes", "out_of_scope_routes", "focus_areas", "attack_scenarios"]:
        if key not in result:
            result[key] = []
    for tactic in MITRE_TACTICS:
        if tactic not in result["attack_scenarios"]:
            result["attack_scenarios"][tactic] = []
    
    return result

def process_routes(routes, chunk_size, max_workers):
    """Process all routes in parallel chunks."""
    chunks = chunk_routes(routes, chunk_size)
    results = {
        "in_scope_routes": [],
        "out_of_scope_routes": [],
        "focus_areas": [],
        "attack_scenarios": {tactic: [] for tactic in MITRE_TACTICS}
    }

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_chunk = {
            executor.submit(analyze_routes_chunk, json.dumps(chunk), json.dumps(results)): chunk
            for chunk in chunks
        }

        for future in tqdm(as_completed(future_to_chunk), total=len(chunks), desc="Analyzing routes"):
            try:
                chunk_result = future.result()
                results["in_scope_routes"].extend(chunk_result.get("in_scope_routes", []))
                results["out_of_scope_routes"].extend(chunk_result.get("out_of_scope_routes", []))
                results["focus_areas"].extend(chunk_result.get("focus_areas", []))
                for tactic in MITRE_TACTICS:
                    results["attack_scenarios"][tactic].extend(chunk_result.get("attack_scenarios", {}).get(tactic, []))
            except Exception as e:
                logger.error(f"Error processing chunk: {e}")

    # Remove duplicates from focus_areas while preserving order
    results["focus_areas"] = list(dict.fromkeys(results["focus_areas"]))
    return results

@sleep_and_retry
@limits(calls=CALLS_PER_MINUTE, period=60)
@backoff.on_exception(backoff.expo, Exception, max_tries=MAX_RETRIES)
def validate_results(results):
    """Validate the analysis results with rate limiting and exponential backoff."""
    validation_prompt = f"""
    Review and validate the following analysis results:
    {json.dumps(results, indent=2)}

    Provide your validation in the following JSON format:
    {{
        "is_valid": true/false,
        "issues": [
            {{
                "type": "issue type (e.g., 'inconsistency', 'missing_data', 'incorrect_classification')",
                "description": "detailed description of the issue"
            }}
        ],
        "suggested_improvements": [
            "improvement suggestion 1",
            "improvement suggestion 2"
        ]
    }}
    """

    validation_response = ask_alfred(validation_prompt, SYSTEM_PROMPT)
    return json.loads(validation_response)

def generate_summary(results, validation):
    """Generate a summary of the analysis."""
    summary = {
        "summary": {
            "total_routes": len(results["in_scope_routes"]) + len(results["out_of_scope_routes"]),
            "in_scope_routes": len(results["in_scope_routes"]),
            "high_risk_routes": sum(1 for r in results["in_scope_routes"] if r["risk_level"] == "high"),
            "medium_risk_routes": sum(1 for r in results["in_scope_routes"] if r["risk_level"] == "medium"),
            "low_risk_routes": sum(1 for r in results["in_scope_routes"] if r["risk_level"] == "low")
        },
        "in_scope_routes": results["in_scope_routes"],
        "out_of_scope_routes": results["out_of_scope_routes"],
        "focus_areas": results["focus_areas"],
        "attack_scenarios": results["attack_scenarios"],
        "validation_result": validation,
        "testing_priorities": []
    }

    # Generate testing priorities
    priorities = []
    priorities.extend([f"Focus on {len([r for r in results['in_scope_routes'] if r['risk_level'] == 'high'])} high-risk routes"])
    priorities.extend([f"Address focus area: {area}" for area in results["focus_areas"][:3]])
    
    for tactic in MITRE_TACTICS:
        if results["attack_scenarios"][tactic]:
            priorities.append(f"Test against {tactic} scenarios: {len(results['attack_scenarios'][tactic])} identified")

    summary["testing_priorities"] = priorities[:10]  # Limit to top 10 priorities

    return summary

def generate_csv_output(routes, output_file):
    """Generate a CSV file with a granular breakdown of routes."""
    fieldnames = ['App', 'top-level', 'second-level', 'Method', 'Count']
    app_totals = defaultdict(int)

    with open(output_file, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for route, details in routes.items():
            method, path = route.split(' ', 1)
            parts = path.strip('/').split('/')
            app = f"/routes/{parts[0]}" if parts else "/routes/unknown"
            top_level = f"/{parts[1]}" if len(parts) > 1 else ""
            second_level = '/' + '/'.join(parts[2:]) if len(parts) > 2 else ""

            writer.writerow({
                'App': app,
                'top-level': top_level,
                'second-level': second_level,
                'Method': method,
                'Count': 1
            })

            app_totals[app] += 1

        for app, total in app_totals.items():
            writer.writerow({
                'App': f"{app} Total",
                'top-level': "",
                'second-level': "",
                'Method': "",
                'Count': total
            })

    logger.info(f"CSV output written to {output_file}")

def scoper_logic(generate_attacks, output, max_workers, csv_output, chunk_size, validation_loops):
    """Core logic for the scoper command."""
    logger.info("Starting enhanced scoper script...")
    routes_file = os.path.join('local_data', 'routes.json')
    routes = load_routes(routes_file)
    
    if not routes:
        logger.error("No routes loaded. Exiting script.")
        return

    results = process_routes(routes, chunk_size, max_workers)
    
    for i in range(validation_loops):
        logger.info(f"Starting validation loop {i+1}/{validation_loops}")
        validation = validate_results(results)
        if validation["is_valid"]:
            logger.info("Validation passed. Proceeding with summary generation.")
            break
        elif i < validation_loops - 1:
            logger.warning(f"Validation failed. Reprocessing routes. Attempt {i+2}/{validation_loops}")
            results = process_routes(routes, chunk_size, max_workers)
        else:
            logger.warning("Validation failed in all attempts. Proceeding with best effort results.")
    
    final_summary = generate_summary(results, validation)
    
    # Generate JSON output
    json_output_path = os.path.join('local_data', output)
    with open(json_output_path, 'w') as f:
        json.dump(final_summary, f, indent=2)
    
    logger.info(f"Enhanced scoping complete. JSON results written to {json_output_path}")
    print(f"Enhanced scoping complete. JSON results written to {json_output_path}")

    # Generate basic CSV files
    csv_output_dir = os.path.join('local_data', 'csv_output')
    generate_basic_csvs(final_summary, csv_output_dir)
    logger.info(f"Basic CSV files generated in {csv_output_dir}")
    print(f"Basic CSV files generated in {csv_output_dir}")

    # Generate formatted routes CSV
    formatted_csv_path = os.path.join('local_data', 'formatted_routes.csv')
    generate_formatted_routes_csv(final_summary, formatted_csv_path)
    logger.info(f"Formatted routes CSV generated: {formatted_csv_path}")
    print(f"Formatted routes CSV generated: {formatted_csv_path}")

    if not validation["is_valid"]:
        logger.warning("Validation failed. Please review the issues in the output file.")
        print("Validation failed. Please review the issues in the output file.")

@click.command()
@click.option('--generate-attacks', is_flag=True, help='Flag to generate attack plans for scoped routes')
@click.option('--output', default='scoped_routes.json', help='Output file for scoping results (JSON)')
@click.option('--csv-output', default='routes_breakdown.csv', help='Output file for routes breakdown (CSV)')
@click.option('--max-workers', default=MAX_WORKERS, help='Maximum number of concurrent workers')
@click.option('--chunk-size', default=CHUNK_SIZE, help='Number of routes to process in each chunk')
@click.option('--validation-loops', default=3, help='Number of validation loops to perform')
def scoper_cmd(generate_attacks, output, csv_output, max_workers, chunk_size, validation_loops):
    """Run the enhanced scoper script to analyze routes and generate a comprehensive security analysis."""
    scoper_logic(generate_attacks, output, max_workers, csv_output, chunk_size, validation_loops)

def run_scoper(generate_attacks=False, output='scoped_routes.json', csv_output='routes_breakdown.csv', max_workers=MAX_WORKERS, chunk_size=CHUNK_SIZE, validation_loops=3):
    scoper_logic(generate_attacks, output, max_workers, csv_output, chunk_size, validation_loops)

if __name__ == "__main__":
    scoper_cmd()