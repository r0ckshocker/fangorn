import click
import logging
import os
import sys
from scripts import (
    bulk_users,
    credential_stuffing,
    privilege_escalation,
    data_exfiltration,
    scoper,
    consolidator,
    recon,
    data_mining,
    pdf_step_extractor,
    ai_abuse,
    codeql_commands,
    sarif_analyzer,
    goodbye
)
from scripts.tempo_client import TempoClient
from scripts.utils import setup_environment, create_http_session
from scripts.red import simulate_attack, credential_stuffing_attack, impossible_travel_detection

# Initialize the environment and Datadog using utils.py
setup_environment()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# CLI group
@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    """Lucius CLI - A tool for running security scripts."""
    if ctx.invoked_subcommand is None:
        interactive()

# Add existing commands
cli.add_command(credential_stuffing.credential_stuffing_cmd)
cli.add_command(bulk_users.bulk_users_cmd)
cli.add_command(privilege_escalation.privilege_escalation_cmd)
cli.add_command(data_exfiltration.data_exfiltration_cmd)
cli.add_command(consolidator.consolidator_cmd)
cli.add_command(recon.recon_cmd)
cli.add_command(data_mining.data_mining_cmd)
cli.add_command(pdf_step_extractor.pdf_step_extractor)
cli.add_command(ai_abuse.ai_abuse_cmd)
cli.add_command(codeql_commands.codeql)
cli.add_command(goodbye.cli)

@cli.command()
@click.option('--generate-attacks', is_flag=True, help='Flag to generate attack plans for scoped routes')
@click.option('--output', default='scoped_routes.json', help='Output file for scoping results (JSON)')
@click.option('--csv-output', default='routes_breakdown.csv', help='Output file for routes breakdown (CSV)')
@click.option('--max-workers', default=5, help='Maximum number of concurrent workers')
@click.option('--chunk-size', default=5, help='Number of routes to process in each chunk')
@click.option('--validation-loops', default=3, help='Number of validation loops to perform')
def scoper_cmd(generate_attacks, output, csv_output, max_workers, chunk_size, validation_loops):
    """Run the enhanced scoper script to analyze routes and generate a comprehensive security analysis."""
    scoper.run_scoper(generate_attacks, output, csv_output, max_workers, chunk_size, validation_loops)

# Group for Tempo Client commands
@cli.group()
def tempo():
    """Tempo Client CLI"""
    pass

@tempo.command()
@click.option('--public-api', default="https://ose-dev.public-api.apprentice.io", help='Public API URL')
def authenticate(public_api):
    """Authenticate and obtain an access token."""
    client = TempoClient(public_api=public_api)
    try:
        client.authenticate()
        click.echo(click.style('Authentication successful', fg='green'))
    except Exception as e:
        click.echo(click.style(f"Authentication failed: {e}", fg='red'))

@tempo.command()
@click.argument('endpoint', type=click.Choice(['users', 'user', 'samples', 'sample', 'locations', 'kits', 'kit', 'exceptions', 'exception', 'procedure_templates', 'procedure_template', 'procedure_runs', 'procedure_run', 'material_sublots', 'material_sublot', 'material_lots', 'material_lot', 'material_definitions', 'material_definition', 'equipment', 'single_equipment', 'batch_runs', 'batch_run', 'batch_templates', 'batch_template']))
@click.option('--id', default=None, help='ID of the specific resource')
@click.option('--public-api', default="https://ose-dev.public-api.apprentice.io", help='Public API URL')
def get_data(endpoint, id, public_api):
    """Fetch data from various Tempo API endpoints."""
    client = TempoClient(public_api=public_api)
    try:
        client.authenticate()
    except Exception as e:
        click.echo(click.style(f"Authentication failed: {e}", fg='red'))
        return

    try:
        if endpoint == 'users':
            data = client.user.get_all()
        elif endpoint == 'user':
            if not id:
                raise click.UsageError("The 'user' endpoint requires an --id option.")
            data = client.user.get(id)
        else:
            raise click.UsageError(f"Endpoint '{endpoint}' not implemented.")

        click.echo(click.style(f"Data for {endpoint}:", fg="green", bold=True))
        click.echo(click.style(json.dumps(data, indent=2), fg="blue"))
    except Exception as e:
        click.echo(click.style(f"Error fetching data: {str(e)}", fg="red", bold=True))

cli.add_command(tempo)

@cli.command()
def red_team_simulations():
    """Run red team attack simulations."""
    click.echo("Simulating a probe attack...")
    simulate_attack()

    click.echo("Simulating a credential stuffing attack...")
    email = click.prompt("Enter email for credential stuffing", type=str)
    password = click.prompt("Enter password", type=str, hide_input=True)
    credential_stuffing_attack(email, password)

    click.echo("Simulating impossible travel detection...")
    impossible_travel_detection(email)

def interactive():
    """Interactive mode to choose which script to run."""
    while True:
        click.echo("\nChoose an option:")
        click.echo("1: Credential Stuffing")
        click.echo("2: Bulk User Creation")
        click.echo("3: Privilege Escalation")
        click.echo("4: Data Exfiltration")
        click.echo("5: Scoper")
        click.echo("6: Consolidator")
        click.echo("7: Recon Scan")
        click.echo("8: Data Mining")
        click.echo("9: PDF Step Extractor")
        click.echo("10: AI Abuse Scenario")
        click.echo("11: CodeQL Database Creation")
        click.echo("12: CodeQL Database Analysis")
        click.echo("13: Compare CodeQL Results")
        click.echo("14: Find Express.js Endpoints")
        click.echo("15: SARIF Analysis and Scoping")
        click.echo("16: Red Team Attack Simulations")
        click.echo("17: Goodbye (Remove User(s) from All Databases)")
        click.echo("18: Exit")
        
        choice = click.prompt("Enter the number of your choice", type=int)

        if choice == 1:
            credential_stuffing.perform_brute_force()
        elif choice == 2:
            url = click.prompt("URL to use", type=str)
            bulk_users.bulk_users_cmd.callback(url=url)
        elif choice == 3:
            url = click.prompt("Base URL of the environment (e.g., ose-dev or ose-val)", type=str)
            email = click.prompt("Operator email for authentication", type=str)
            password = click.prompt("Operator password for authentication", hide_input=True, type=str)
            attempts = click.prompt("Number of access attempts per page", type=int, default=10)
            privilege_escalation.privilege_escalation_cmd.callback(url=url, email=email, password=password, attempts=attempts)
        elif choice == 4:
            url = click.prompt("Base URL of the environment (e.g., ose-dev or ose-val)", type=str)
            summarize = click.confirm("Summarize findings with Alfred?")
            data_exfiltration.data_exfiltration_cmd.callback(url=url, summarize=summarize)
        elif choice == 5:
            generate_attacks = click.confirm("Generate attack plans for scoped routes?")
            output = click.prompt("JSON output file name", type=str, default="scoped_routes.json")
            csv_output = click.prompt("CSV output directory name", type=str, default="csv_output")
            max_workers = click.prompt("Maximum number of concurrent workers", type=int, default=5)
            chunk_size = click.prompt("Number of routes to process in each chunk", type=int, default=5)
            validation_loops = click.prompt("Number of validation loops to perform", type=int, default=3)
            scoper.run_scoper(generate_attacks, output, csv_output, max_workers, chunk_size, validation_loops)
            click.echo("Scoping complete. Check the 'local_data' directory for JSON and CSV outputs.")
        elif choice == 6:
            use_alfred = click.confirm("Use Alfred to summarize the output?")
            local = click.confirm("Run against a local Alfred instance?")
            consolidator.consolidator_cmd.callback(use_alfred=use_alfred, local=local)
        elif choice == 7:
            target = click.prompt("Target URL", type=str)
            wordlist = click.prompt("Path to wordlist (press Enter for default)", type=str, default="/usr/share/wordlists/dirbuster/directory-list-2.3-medium.txt")
            run_all = click.confirm("Run all scans?", default=False)
            crawl = run_all or click.confirm("Run site crawling?", default=False)
            brute_force = run_all or click.confirm("Run directory brute-forcing?", default=False)
            headers = run_all or click.confirm("Analyze HTTP headers?", default=False)
            zap = run_all or click.confirm("Run OWASP ZAP scan?", default=False)
            nmap = run_all or click.confirm("Run Nmap port scan?", default=False)
            scapy = run_all or click.confirm("Run Scapy network packet analysis?", default=False)
            recon.recon_cmd.callback(target=target, wordlist=wordlist, run_all=run_all, crawl=crawl, brute_force=brute_force, headers=headers, zap=zap, nmap=nmap, scapy=scapy)
        elif choice == 8:
            input_file = click.prompt("Input CSV file path", default="scripts/input_data.csv")
            output_file = click.prompt("Output CSV file path", default="scripts/evaluated_data.csv")
            data_mining.data_mining_cmd.callback(input_file=input_file, output_file=output_file)
        elif choice == 9:
            pdf_path = click.prompt("Path to the input PDF file", type=str)
            output_path = click.prompt("Path for saving the output JSON file", type=str)
            pdf_step_extractor.pdf_step_extractor.callback(pdf_path=pdf_path, output_path=output_path)
        elif choice == 10:
            url = "cobalt-dev"  # Set the URL to cobalt-dev
            email, password = ai_abuse.load_admin_credentials()
            if not email or not password:
                click.echo("Failed to load admin credentials. Aborting AI abuse test.")
                continue
            attempts = click.prompt("Number of abusive prompts per procedure", type=int, default=5)
            mode = click.prompt("Choose mode (basic/owasp/destroy)", type=click.Choice(['basic', 'owasp', 'destroy']), default='basic')
            procedure_id = None
            num_steps = 10
            num_procedures = 5
            owasp_mode = "single"
            if mode == 'owasp':
                num_procedures = click.prompt("Number of procedures to test", type=int, default=5)
                owasp_mode = click.prompt("Choose OWASP mode (single/chain)", type=click.Choice(['single', 'chain']), default='single')
            elif mode == 'destroy':
                procedure_id = click.prompt("ID of the procedure to manipulate", type=str)
                num_steps = click.prompt("Number of steps to manipulate", type=int, default=10)
            ai_abuse.ai_abuse_cmd.callback(url=url, email=email, password=password, attempts=attempts, mode=mode, procedure_id=procedure_id, num_steps=num_steps, num_procedures=num_procedures, owasp_mode=owasp_mode)
        elif choice == 11:
            language = click.prompt("Programming language to analyze", type=str, default="javascript")
            source_root = click.prompt("Path to the source code root", type=str, default="../../monorepo/")
            database_name = click.prompt("Name for the CodeQL database", type=str)
            codeql_commands.create_database.callback(language=language, source_root=source_root, database_name=database_name)
        elif choice == 12:
            database = click.prompt("Name of the CodeQL database", type=str)
            queries = click.prompt("Path to the queries directory or QL pack", type=str, default="codeql")
            output = click.prompt("Output file for analysis results", type=str)
            format = click.prompt("Output format", type=str, default="sarif-latest")
            codeql_commands.analyze_database.callback(database=database, queries=queries, output=output, format=format)
        elif choice == 13:
            file1 = click.prompt("Name of first CodeQL results file", type=str)
            file2 = click.prompt("Name of second CodeQL results file", type=str)
            output = click.prompt("Output file for diff results", type=str)
            codeql_commands.compare_results.callback(file1=file1, file2=file2, output=output)
        elif choice == 14:
            database = click.prompt("Name of the CodeQL database", type=str)
            output = click.prompt("Output file for analysis results", type=str)
            codeql_commands.find_express_endpoints.callback(database=database, output=output)
        elif choice == 15:
            sarif_file = click.prompt("Path to the SARIF file for analysis", type=str)
            generate_attacks = click.confirm("Generate attack plans for scoped routes?")
            url = click.prompt("Base URL for API", type=str) if generate_attacks else None
            email = click.prompt("Email for authentication", type=str) if generate_attacks else None
            password = click.prompt("Password for authentication", hide_input=True, type=str) if generate_attacks else None
            api_url = click.prompt("API URL", type=str, default="https://alfred.apprenticefs.net/api/chat")
            sarif_analyzer.sarif_scope(sarif_file=sarif_file, generate_attacks=generate_attacks, url=url, email=email, password=password, api_url=api_url)
        elif choice == 16:
            red_team_simulations()
        elif choice == 17:
            email_file = click.prompt("Enter the path to the text file with email addresses", type=click.Path(exists=True))
            log_file = click.prompt("Enter the path for the log file (optional)", default=None)
            aws_profile = click.prompt("Enter the AWS CLI SSO profile to use", default='default')
            
            # Generate plan
            plan_output = click.prompt("Enter the path to save the plan JSON file", default='removal_plan.json')
            goodbye.plan.callback(
                email_file=email_file, 
                output=plan_output, 
                log_file=log_file
            )
            
            if click.confirm("Do you want to apply the generated plan?"):
                goodbye.apply.callback(plan_file=plan_output, log_file=log_file, aws_profile=aws_profile)
        elif choice == 18:
            click.echo("Exiting...")
            break
        else:
            click.echo("Invalid choice. Please try again.")

if __name__ == "__main__":
    cli()