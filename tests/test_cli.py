import subprocess
import sys
import os

def get_python_command():
    venv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "venv")
    if os.path.exists(venv_path):
        if sys.platform == "win32":
            return os.path.join(venv_path, "Scripts", "python.exe")
        return os.path.join(venv_path, "bin", "python")
    return "python3"

def run_command(command):
    print(f"Running command: {command}")
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Command failed with error: {result.stderr}")
        return False
    print("Command succeeded")
    return True

def main():
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # Change to project root directory
    python_cmd = get_python_command()

    commands = [
        f"{python_cmd} lucius.py --help",
        f"{python_cmd} lucius.py tempo authenticate",
        f"{python_cmd} lucius.py tempo get-data users",
        # f"{python_cmd} lucius.py red-team-simulations",  # This command is not yet implemented
    ]

    failed_commands = []

    for command in commands:
        if not run_command(command):
            failed_commands.append(command)

    if failed_commands:
        print("\nThe following commands failed:")
        for cmd in failed_commands:
            print(f"- {cmd}")
        sys.exit(1)
    else:
        print("\nAll commands executed successfully!")

if __name__ == "__main__":
    main()