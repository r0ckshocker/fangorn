import json
import re
import time
from collections import defaultdict, Counter
import click
import logging
from scripts.utils import logger
from scripts.alfred import ask_alfred

# Configure logging
LOG_FILE = 'consolidator.log'
logging.basicConfig(level=logging.INFO, filename=LOG_FILE, filemode='w')
logger = logging.getLogger(__name__)

def load_routes(file_path):
    """Load routes from a JSON file and count deprecated routes."""
    try:
        with open(file_path, 'r') as file:
            data = json.load(file)
        filtered_data = {route: details for route, details in data.items() if not details.get('isDeprecated', False)}
        deprecated_count = len(data) - len(filtered_data)
        return filtered_data, deprecated_count
    except FileNotFoundError:
        logger.error(f"File not found: {file_path}")
        return {}, 0
    except json.JSONDecodeError:
        logger.error(f"Error decoding JSON from file: {file_path}")
        return {}, 0

def extract_base_path(path):
    """Extract the base path from a route."""
    path = re.sub(r'/v[0-9]+', '', path)
    segments = path.strip('/').split('/')
    return '/' + segments[0] if segments else '/'

def consolidate_routes(data):
    """Consolidate routes into a structured format."""
    consolidated = defaultdict(lambda: {
        "consolidated_route_count": 0,
        "unique_middleware_count": 0,
        "unique_parameters_count": 0,
        "methods": defaultdict(lambda: {
            "parameters": [],
            "middleware": [],
            "handlers": [],
            "original_routes": []
        })
    })
    metrics = Counter()
    old_routes = set(data.keys())

    for route, details in data.items():
        method, path = route.split(' ', 1)
        base_path = extract_base_path(path)
        parameters = details.get('params', [])
        middleware = details.get('middleware', [])
        handler = details.get('handler', 'No handler specified')

        consolidated[base_path]['consolidated_route_count'] += 1
        consolidated[base_path]['methods'][method]['parameters'] = list(set(consolidated[base_path]['methods'][method]['parameters'] + parameters))
        consolidated[base_path]['methods'][method]['middleware'] = list(set(consolidated[base_path]['methods'][method]['middleware'] + middleware))
        consolidated[base_path]['methods'][method]['handlers'].append(handler)
        consolidated[base_path]['methods'][method]['original_routes'].append(route)

    for base_path, info in consolidated.items():
        unique_middleware = set()
        unique_parameters = set()
        for method_info in info['methods'].values():
            unique_middleware.update(method_info['middleware'])
            unique_parameters.update(method_info['parameters'])
        consolidated[base_path]['unique_middleware_count'] = len(unique_middleware)
        consolidated[base_path]['unique_parameters_count'] = len(unique_parameters)

    metrics['unique_middleware'] = sum(info['unique_middleware_count'] for info in consolidated.values())
    metrics['unique_parameters'] = sum(info['unique_parameters_count'] for info in consolidated.values())
    metrics['old_routes'] = len(old_routes)
    metrics['new_routes'] = len(consolidated)
    metrics['new_actions'] = sum(len(base['methods']) for base in consolidated.values())

    return consolidated, metrics

def write_outputs(consolidated_data, metrics, deprecated_count, file_name_prefix=""):
    """Write outputs to JSON and print summaries."""
    json_file_name = f'{file_name_prefix}consolidated_routes.json'

    with open(json_file_name, 'w') as file:
        json.dump(consolidated_data, file, indent=4)

    for base_path, info in consolidated_data.items():
        logger.info(f"Base Path: {base_path}, Summary: {info}")
    logger.info(f"Consolidation complete. Metrics: {metrics}")
    logger.info(f"Deprecated routes count: {deprecated_count}")

def validate_consolidated_route(consolidated_data):
    """Validate each method within a consolidated base path."""
    validation_results = {}

    for base_path, details in consolidated_data.items():
        for method, method_details in details['methods'].items():
            full_consolidated_structure = {
                "base_path": base_path,
                "method": method,
                "method_details": method_details
            }
            message = f"Does the method {method} on the consolidated base path {base_path} support all of the following original routes? {json.dumps(method_details['original_routes'], indent=4)} Respond only with JSON: {{\"included\": true/false, \"reasoning\": \"reasoning here\"}}"
            logger.info(f"Asking Alfred about method {method} on base path {base_path}")
            response = ask_alfred(message)
            logger.info(f"Response: {response}")
            validation_results[f"{base_path} {method}"] = response

    with open('validation_results.json', 'w') as file:
        json.dump(validation_results, file, indent=4)

    return validation_results

def update_consolidated_route(consolidated_data, base_path, method, reasoning):
    """Update a single consolidated route based on the reasoning provided."""
    message = f"Update the method {method} on the consolidated route {base_path} based on the following reasoning: {reasoning} {json.dumps(consolidated_data[base_path], indent=4)} Respond only with JSON: {{\"updated_base_path\": {{\"base_path_object\": \"updated base path object here\"}}}}"
    logger.info(f"Asking Alfred to update method {method} on base path {base_path}")
    response = ask_alfred(message)
    logger.info(f"Response: {response}")
    if isinstance(response, dict) and "updated_base_path" in response:
        updated_base_path = response["updated_base_path"]
        consolidated_data[base_path] = updated_base_path
        logger.info(f"Updated method {method} on base path {base_path} with new details.")
        return updated_base_path
    else:
        logger.warning(f"Failed to update method {method} on base path {base_path}. Response: {response}")
    return consolidated_data[base_path]

def generate_threat_model_comment(base_path, method, details):
    """Generate a threat model comment for a single consolidated endpoint."""
    message = f"Please provide a threat model comment for the following consolidated endpoint {base_path} {method}: {json.dumps(details, indent=4)} Respond only with JSON: {{\"threat_model_comment\": \"comment here\"}}"
    logger.info(f"Asking Alfred for a threat model comment for base path {base_path} {method}")
    response = ask_alfred(message)
    logger.info(f"Response: {response}")
    if isinstance(response, dict) and "threat_model_comment" in response:
        threat_model_comment = response["threat_model_comment"]
        details['threat_model_comment'] = threat_model_comment
        return threat_model_comment
    else:
        details['threat_model_comment'] = "token limit exceeded"
        return "token limit exceeded"

def review_route(consolidated_data):
    """Review the entire consolidated structure."""
    message = f"Review the entire consolidated structure and provide notes about the security perspective, potential further consolidation, and any possible breakages: {json.dumps(consolidated_data, indent=4)}"
    logger.info("Asking Alfred to review the entire consolidated structure")
    response = ask_alfred(message)
    logger.info(f"Response: {response}")

    with open('review_summary.json', 'w') as file:
        json.dump({"review": response}, file, indent=4)

    return response

def review_route(consolidated_data):
    """Review the entire consolidated structure."""
    message = f"Review the entire consolidated structure and provide notes about the security perspective, potential further consolidation, and any possible breakages: {json.dumps(consolidated_data, indent=4)}"
    logger.info("Asking Alfred to review the entire consolidated structure")
    response = ask_alfred(message)
    logger.info(f"Response: {response}")

    with open('review_summary.json', 'w') as file:
        json.dump({"review": response}, file, indent=4)

    return response

def generate_run_summary(consolidated_data, metrics, deprecated_count, review_notes):
    """Generate a summary of the run using metrics and logs."""
    summary = {
        "metrics": metrics,
        "total_base_paths": len(consolidated_data),
        "complete_and_correct_base_paths": sum(1 for info in consolidated_data.values() if info.get('is_complete_and_correct', False)),
        "deprecated_base_paths": deprecated_count,
        "threat_model_comments": {base_path: info.get('threat_model_comment', '') for base_path, info in consolidated_data.items()},
        "review_notes": review_notes
    }

    before_after_diff = {
        "before": load_routes('routes.json')[0],
        "after": consolidated_data
    }

    with open('run_summary.json', 'w') as file:
        json.dump(summary, file, indent=4)
    with open('before_after_diff.json', 'w') as file:
        json.dump(before_after_diff, file, indent=4)

@click.command()
@click.option('--use-alfred', is_flag=True, help='Use Alfred to summarize and suggest next steps')
@click.option('--local', is_flag=True, help='Run against a local Alfred instance')
def consolidator_cmd(use_alfred, local):
    """Run the consolidator script."""
    logging.info("Starting consolidator script...")
    original_data, deprecated_count = load_routes('routes.json')

    if not original_data:
        logging.error("No data loaded. Exiting script.")
        return

    consolidated_data, metrics = consolidate_routes(original_data)
    write_outputs(consolidated_data, metrics, deprecated_count)

    # Check for existing validation_results.json file
    try:
        with open('validation_results.json', 'r') as file:
            validation_results_raw = json.load(file)
        logging.info("Existing validation results found. Using them to update routes.")
        use_existing_validation_results = True
    except FileNotFoundError:
        validation_results_raw = None
        use_existing_validation_results = False

    validation_results = {}
    if validation_results_raw:
        for route, result_str in validation_results_raw.items():
            result_str = result_str.replace('\n', ' ')
            validation_results[route] = json.loads(result_str)

    if use_alfred:
        if not use_existing_validation_results:
            logging.info("Starting validation process with Alfred...")
            # Initial validation
            validation_results = validate_consolidated_route(consolidated_data)
            with open('validation_results.json', 'w') as file:
                json.dump(validation_results, file, indent=4)
        else:
            logging.info("Skipping initial validation as existing results are found.")

        # Update routes based on validation results
        for original_route, result in validation_results.items():
            logging.info(f"Processing validation result for route: {original_route}")
            base_path, method = original_route.rsplit(' ', 1)
            if isinstance(result, dict) and result.get("included") is False:
                reasoning = result.get("reasoning", "No reasoning provided")
                logging.info(f"Updating consolidated route: {base_path} {method} with reasoning: {reasoning}")
                update_consolidated_route(consolidated_data, base_path, method, reasoning)
            else:
                logging.info(f"Skipping route {original_route} based on validation result: {result}")

        # Perform threat modeling on every route after ensuring all validations are successful
        for base_path, details in consolidated_data.items():
            for method in details['methods']:
                generate_threat_model_comment(base_path, method, details['methods'][method])

        review_notes = review_route(consolidated_data)
    else:
        review_notes = ""

    write_outputs(consolidated_data, metrics, deprecated_count, file_name_prefix="updated_")

    generate_run_summary(consolidated_data, metrics, deprecated_count, review_notes)

if __name__ == "__main__":
    consolidator_cmd()
