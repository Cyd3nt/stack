import os
import platform
import subprocess
import inquirer
import json

# --- Helper Functions ---

def load_tools():
    """Loads tool configuration from tools.json."""
    try:
        with open('tools.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print("❌ Error: tools.json not found. Please make sure the file exists.")
        return None
    except json.JSONDecodeError:
        print("❌ Error: Could not decode tools.json. Please check for syntax errors.")
        return None

def is_windows():
    """Check if the operating system is Windows."""
    return platform.system() == "Windows"

def get_clone_directory():
    """Prompts the user for a directory to clone git repos into."""
    questions = [
        inquirer.Text('path', message="Enter the full path for the 'git clone' directory", default=os.getcwd())
    ]
    answers = inquirer.prompt(questions)
    clone_path = answers['path']
    
    if not os.path.exists(clone_path):
        if inquirer.confirm(f"Directory '{clone_path}' does not exist. Create it?", default=True):
            try:
                os.makedirs(clone_path)
                print(f"✅ Directory '{clone_path}' created.")
            except OSError as e:
                print(f"❌ Error creating directory: {e}")
                return os.getcwd() # Fallback to current dir
        else:
            return os.getcwd() # Fallback to current dir
            
    return clone_path

def handle_file_creation(file_op, clone_dir):
    """Handles creation of files specified in post_install."""
    if not clone_dir:
        print("❌ Cannot create file without a clone directory specified.")
        return

    # Use the clone_dir for file operations
    file_path = os.path.join(clone_dir, file_op['name'])
    content = file_op['content']

    if os.path.exists(file_path):
        if not inquirer.confirm(f"File '{file_path}' already exists. Overwrite?", default=False):
            print(f"ℹ️ Skipping file creation for '{file_path}'.")
            return
    
    print(f"📝 Creating file: {file_path}")
    try:
        with open(file_path, 'w') as f:
            f.write(content)
        print(f"✅ Successfully created '{file_path}'.")
    except IOError as e:
        print(f"❌ Error creating file: {e}")


def add_new_tool(tool_config):
    questions = [
        inquirer.List(
            'tool_type',
            message="What type of tool do you want to add?",
            choices=["GitHub Repository", "Docker Image"],
        ),
    ]
    answers = inquirer.prompt(questions)
    tool_type = answers['tool_type']

    tool_name_q = [
        inquirer.Text('name', message="Enter a display name for the tool"),
    ]
    tool_name = inquirer.prompt(tool_name_q)['name']

    new_tool_entry = {}
    if tool_type == "GitHub Repository":
        repo_url_q = [
            inquirer.Text('url', message="Enter the GitHub repository URL (e.g., https://github.com/user/repo)"),
        ]
        repo_url = inquirer.prompt(repo_url_q)['url']
        new_tool_entry = {
            "type": "git",
            "command": f"git clone {repo_url}"
        }
        category = "GitHub Repositories"
    elif tool_type == "Docker Image":
        docker_image_q = [
            inquirer.Text('image', message="Enter the Docker image name (e.g., ubuntu:latest or myuser/myimage)"),
        ]
        docker_image = inquirer.prompt(docker_image_q)['image']
        new_tool_entry = {
            "type": "docker",
            "command": f"docker run -d {docker_image}" # Basic run command
        }
        category = "Docker Containers"

    if category not in tool_config:
        tool_config[category] = {}
    tool_config[category][tool_name] = new_tool_entry

    try:
        with open('tools.json', 'w') as f:
            json.dump(tool_config, f, indent=2)
        print(f"✅ Successfully added {tool_name} to {category}.")
    except IOError as e:
        print(f"❌ Error writing to tools.json: {e}")


def get_platform():
    """Detects the current operating system."""
    system = platform.system().lower()
    if system == "windows":
        return "windows"
    elif system == "darwin":
        return "macos"
    elif system == "linux":
        # This could be expanded to check for apt, yum, etc.
        return "linux"
    return "unknown"

def get_package_manager(platform):
    """Returns the appropriate package manager for the OS."""
    if platform == "windows":
        return "winget"
    elif platform == "macos":
        return "brew"
    elif platform == "linux":
        # This could be expanded to check for apt, yum, etc.
        return "apt"
    return None

def get_command_for_platform(tool_info, os_platform):
    """Gets the appropriate command for the current platform."""
    command_obj = tool_info.get("command", {})
    if isinstance(command_obj, str):
        return command_obj # Backwards compatibility
    
    # First, try the specific platform (e.g., 'windows', 'macos')
    if os_platform in command_obj:
        return command_obj[os_platform]
    
    # If not found, try the tool type (e.g., 'pip', 'git')
    tool_type = tool_info.get("type")
    if tool_type in command_obj:
        return command_obj[tool_type]
        
    return None


def run_command(tool_name, tool_info, os_platform, clone_dir=None):
    """Runs a command in the shell and prints output, including post-install."""
    command = get_command_for_platform(tool_info, os_platform)
    if not command:
        print(f"- Skipping {tool_name}: No command found for platform '{os_platform}'.")
        return

    tool_type = tool_info.get("type")
    
    # --- Main Installation ---
    if tool_type == "docker":
        if not is_docker_running():
            print(f"❌ Error: Docker is not running. Please start Docker Desktop and try again.")
            return
        # For Windows, replace $(pwd) with absolute path for Docker volumes
        if os_platform == "windows" and "$(pwd)" in command:
            current_working_dir = os.getcwd()
            docker_friendly_path = current_working_dir.replace('\\', '/') # Convert backslashes to forward slashes
            command = command.replace("$(pwd)", docker_friendly_path)

    print(f"\nExecuting: {command}")
    try:
        # Determine execution directory
        exec_dir = os.getcwd()
        if tool_type == "git":
            repo_name = tool_name.replace(' ', '-')
            final_clone_path = os.path.join(clone_dir, repo_name)
            if os.path.exists(final_clone_path):
                print(f"ℹ️ Directory '{final_clone_path}' already exists. Skipping clone.")
                exec_dir = final_clone_path # Set exec_dir for post-install even if clone is skipped
            else:
                clone_command = f"{command} \"{final_clone_path}\"";
                subprocess.run(clone_command, check=True, shell=True, text=True)
                print(f"✅ Successfully cloned {tool_name}.")
                exec_dir = final_clone_path
        else:
            subprocess.run(command, check=True, shell=True, text=True, cwd=exec_dir)
            print(f"✅ Successfully installed/executed {tool_name}.")

        # --- Post-Installation Steps ---
        if 'post_install' in tool_info:
            print(f"\n--- Running Post-Installation Steps for {tool_name} ---")
            for step in tool_info['post_install']:
                step_command = get_command_for_platform(step, os_platform)
                if not step_command:
                    print(f"- Skipping post-install step: No command for '{os_platform}'.")
                    continue

                if step['type'] == 'command':
                    print(f"\nExecuting post-install command: {step_command}")
                    subprocess.run(step_command, check=True, shell=True, text=True, cwd=exec_dir)
                    print("✅ Command executed successfully.")
                elif step['type'] == 'file':
                    handle_file_creation(step, exec_dir)
                elif step['type'] == 'note':
                    print(f"\n🔔 NOTE for {tool_name}: {step['content']}")

    except subprocess.CalledProcessError as e:
        print(f"❌ Error with {tool_name}: {e}")
        print("Please check the output above for details.")
        if tool_type == "docker":
            print("💡 Hint: For Docker tools, ensure Docker Desktop is running and fully initialized.")
    except FileNotFoundError:
        print(f"❌ Error: Command not found. Is the required package manager installed and in your PATH?")

def is_docker_running():
    """Checks if the Docker daemon is running."""
    try:
        subprocess.run(["docker", "info"], check=True, capture_output=True, text=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def get_installed_packages_pip():
    """Get a set of installed pip packages."""
    try:
        result = subprocess.run(['pip', 'freeze'], capture_output=True, text=True, check=True)
        return set(line.split('==')[0].lower() for line in result.stdout.strip().split('\n'))
    except (subprocess.CalledProcessError, FileNotFoundError):
        return set()

def is_installed_pip(package_name, installed_set):
    """Check if a pip package is installed."""
    return package_name.lower() in installed_set

def is_installed_winget(tool_info):
    """Check if a winget package is installed by its ID."""
    command = get_command_for_platform(tool_info, "windows")
    if not command or "--id" not in command:
        return False
    try:
        package_id = command.split("--id ")[1].split(" ")[0]
        result = subprocess.run(['winget', 'list', '--id', package_id], capture_output=True, text=True, check=True)
        return "No installed package found" not in result.stdout
    except (subprocess.CalledProcessError, FileNotFoundError, IndexError):
        return False # Assume not installed if winget fails or command is malformed

def is_installed_brew(tool_info):
    """Check if a brew package is installed."""
    command = get_command_for_platform(tool_info, "macos")
    if not command:
        return False
    try:
        # Assumes command is e.g., "brew install cask formula_name" or "brew install formula_name"
        parts = command.split()
        package_name = parts[-1]
        result = subprocess.run(['brew', 'list', '--formula'], capture_output=True, text=True, check=True)
        if package_name in result.stdout.split():
            return True
        result = subprocess.run(['brew', 'list', '--cask'], capture_output=True, text=True, check=True)
        return package_name in result.stdout.split()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def is_installed(tool_name, tool_info, os_platform, installed_pip_packages, clone_dir=None):
    """Check if a tool is installed based on its type and platform."""
    tool_type = tool_info.get("type")
    if tool_type == "pip":
        package_name = tool_name.split(' ')[0]
        return is_installed_pip(package_name, installed_pip_packages)
    elif tool_type == "package_manager":
        if os_platform == "windows":
            return is_installed_winget(tool_info)
        elif os_platform == "macos":
            return is_installed_brew(tool_info)
        # Add linux check here if needed
        return False
    elif tool_type == "git":
        repo_name = tool_name.replace(' ', '-')
        check_dir = clone_dir if clone_dir else os.getcwd()
        return os.path.exists(os.path.join(check_dir, repo_name))
    return False

# --- Main Logic ---

def select_and_install(category_name, tools, os_platform, installed_pip_packages, clone_dir=None):
    """Presents a checklist for a category and installs selected tools."""
    # If we are in a git-related category, we might need the clone dir for the is_installed check
    is_git_category = any(tool.get("type") == "git" for tool in tools.values())
    if is_git_category and clone_dir is None:
        clone_dir = get_clone_directory()

    while True: # Loop for category menu
        choices = []
        for name, info in tools.items():
            if get_command_for_platform(info, os_platform):
                installed_str = "(installed)" if is_installed(name, info, os_platform, installed_pip_packages, clone_dir) else ""
                choices.append((f"{name} {installed_str}", name))
            elif info.get("type") == "note":
                choices.append((f"{name} (Note)", name))
            

        questions = [
            inquirer.Checkbox(
                'selected',
                message=f"Select {category_name} to install (Space to select, Enter to confirm)",
                choices=choices + ["---", "Back to Main Menu"],
            )
        ]
        
        answers = inquirer.prompt(questions)
        if not answers or "Back to Main Menu" in answers.get('selected', []) or not answers.get('selected'):
            return clone_dir # Go back to main menu

        selected_tools = answers.get('selected', [])

        # Check again if we need the clone dir, in case the user selected a git tool from a mixed category
        git_tools_selected = any(tools[name].get("type") == "git" for name in selected_tools)
        if git_tools_selected and clone_dir is None:
            clone_dir = get_clone_directory()

        for tool_name in selected_tools:
            if tool_name == "Back to Main Menu": continue
            tool_info = tools[tool_name]
            print(f"\n--- Installing {tool_name} ---")
            run_command(tool_name, tool_info, os_platform, clone_dir=clone_dir)
        
        # After installation, ask if they want to install more from the same category
        if not inquirer.confirm("Install more from this category?", default=True):
            return clone_dir


def main():
    """Main function to run the CLI application."""
    os_platform = get_platform()
    if os_platform == "unknown":
        print("❌ Error: Unsupported operating system.")
        return

    tool_config = load_tools()
    if not tool_config:
        return

    print(f"--- Cyd3nt Stack: AI & LLM Development Environment Setup on {os_platform.capitalize()} ---")
    print("This script will help you install the necessary tools.")
    if os_platform == "linux" or os_platform == "macos":
        print("You may be prompted for your password to install system packages.")
    elif os_platform == "windows":
        print("Please run this script with administrator privileges for best results.\n")


    installed_pip_packages = get_installed_packages_pip()
    clone_dir = None # Initialize clone_dir to be used across sessions

    while True:
        questions = [
            inquirer.List(
                'category',
                message="Choose a category to install tools from (Enter to select)",
                choices=list(tool_config.keys()) + ["Add New Tool", "Install All", "Exit"],
            ),
        ]
        category_choice = inquirer.prompt(questions).get('category')

        if category_choice == "Exit":
            print("Exiting Cyd3nt Stack. Happy coding!")
            break

        if category_choice == "Add New Tool":
            add_new_tool(tool_config)
            # Reload tool_config after adding a new tool
            tool_config = load_tools()
            continue

        if category_choice == "Install All":
            if inquirer.confirm("Are you sure you want to attempt to install all tools from all categories? This may take a while.", default=False):
                # Check if any tool in any category is a git repo
                if any(t.get("type") == "git" for c in tool_config.values() for t in c.values()):
                    if clone_dir is None:
                        clone_dir = get_clone_directory()
                
                for category, tools in tool_config.items():
                    print(f"\n--- Installing All {category} ---")
                    for tool_name, tool_info in tools.items():
                        print(f"\n--- Installing {tool_name} ---")
                        run_command(tool_name, tool_info, os_platform, clone_dir=clone_dir)
            continue

        if category_choice in tool_config:
            clone_dir = select_and_install(category_choice, tool_config[category_choice], os_platform, installed_pip_packages, clone_dir)

if __name__ == "__main__":
    main()
