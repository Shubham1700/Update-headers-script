"""
This script generates the differences between commit hashes in a Git repository,
focusing specifically on the SRC folder. It tracks modifications, deletions, and
renames of files, appending headers for the modified files in the commits and
managing these changes in a structured JSON document.

Input Parameters:
Oldest Commit Hash - The older commit hash/tag from the branch history
Latest Commit Hash - The latest commit hash/HEAD from the branch history
Folder to analyse - The source folder containing safe files only for which header updates are required

Script usage:
python update_headers.py <commit1> <commit2> <folder to analyse in root repo>
Example: python update_headers.py 1.1.0.03 HEAD <src>

"""
import os
import json
import re
import subprocess
from datetime import datetime
import argparse
import sys
import rbc_common

# Constants
local_base_path = os.path.dirname(os.path.abspath(__file__))  # Current folder (ci folder)
diff_path = os.path.join(local_base_path, "diff.txt")
# Path to the comments dictionary JSON
HISTORY_FILE_PATH = 'history.json'
# Path to store the output
missing_authors_path = os.path.join(local_base_path, 'missing_authors.json')  
path_filters = [".ada", ".adb", ".ads"]
header_regex = re.compile(r'--\s\d{2}/\d{2}/\d{4}\s+([A-Z.]+\s+[A-Z]+)?\s+atvcm\d+\s+:\s+\[.*?\]')

def commits_are_valid(sha1_1, sha1_2):
    """Function to check if commits exist in the Git repository."""
    try:
        subprocess.check_output(['git', 'cat-file', '-e', sha1_1])
        subprocess.check_output(['git', 'cat-file', '-e', sha1_2])
        return True
    except subprocess.CalledProcessError:
        return False

def generate_git_diff_command(commit1, commit2, output_path, folder):
    """Function to generate Git diff command to get the changes between two commits from source folder."""
    git_command = f"git diff {commit1}..{commit2} --name-status -- {folder} > \"{output_path}\""
    return git_command

def process_diff_file(diff_file_path):
    """Function to process the diff.txt file and extract modified, renamed, and deleted files."""
    modified_and_new_files = []
    renamed_files = []
    deleted_files = []
    renamed_and_modified_files = []

    with open(diff_file_path, 'r', encoding='utf-8') as f:
        for line in f:
            status, *file_paths = line.split()
            if status == 'M' and any(file_paths[0].endswith(ext) for ext in path_filters):
                modified_and_new_files.append(file_paths[0])
            elif status.startswith('R') and len(file_paths) == 2:
                old_name, new_name = file_paths
                if any(new_name.endswith(ext) for ext in path_filters):
                    renamed_files.append((old_name, new_name))
                    # Check if content was modified (Rxx < 100 indicates modification)
                    if status != 'R100':
                        renamed_and_modified_files.append((old_name, new_name))
            elif status == 'D' and any(file_paths[0].endswith(ext) for ext in path_filters):
                deleted_files.append(file_paths[0])
            elif status == 'A' and any(file_paths[0].endswith(ext) for ext in path_filters):
                modified_and_new_files.append(file_paths[0])

    return modified_and_new_files, renamed_files, deleted_files, renamed_and_modified_files

def remove_older_duplicate(file_path, commit_header, comments_dict):
    """Function to remove duplicate headers, keeping the latest one at the end"""
    comments = comments_dict.get(file_path, [])
    comments_dict[file_path] = [c for c in comments if commit_header not in c]

def append_commit_message_to_files(modified_and_new_files, renamed_and_modified_files, commit_message, commit_date, author_name, comments_dict):
    """Function to append commit message to modified and renamed-modified files in comments_dict."""
    # Extract commit header from the second set of square brackets
    try:
        commit_header = commit_message.split("[")[2].split("]")[0]
        commit_header = commit_header.strip()
        clean_message = commit_message.split("]")[-1].strip()
    except IndexError:
        print("Invalid header found with commit message:" + commit_message)  # In case no valid header is found
        return 1
    # Clean the commit message by removing anything after "See merge request"
    if "\n\nSee merge request" in commit_message:
        clean_message = clean_message.split("\n\nSee merge request")[0]
 
    # Consolidate into a single clean line
    clean_message = ' '.join(clean_message.splitlines()).strip()
 
    # Process modified files and new files
    for file_path in modified_and_new_files:
        comments_dict.setdefault(file_path, [])
        # Remove any older comments with the same commit header
        remove_older_duplicate(file_path, commit_header, comments_dict)
        # Append the new commit message at the end
        comments_dict[file_path].append(f"-- {commit_date} {author_name}    {commit_header} : {clean_message}")

    # Process renamed and modified files
    for old_path, new_path in renamed_and_modified_files:

        if old_path in comments_dict:
            comments_dict[new_path] = comments_dict.pop(old_path)
            print(f"Renamed: {old_path} -> {new_path}")
            remove_older_duplicate(new_path, commit_header, comments_dict)
            comments_dict[new_path].append(f"-- {commit_date} {author_name}    {commit_header} : {clean_message}")

    return 0

def handle_file_renaming(old_name, new_name, comments_dict):
    """Function to handle file renaming in comments_dict"""
    if old_name in comments_dict:
        comments_dict[new_name] = comments_dict.pop(old_name)
        print(f"Renamed: {old_name} -> {new_name}")

def handle_file_deletion(deleted_file, comments_dict):
    """Function to handle file deletion in comments_dict"""
    if deleted_file in comments_dict:
        del comments_dict[deleted_file]
        print(f"Deleted: {deleted_file}")

def get_commit_details(commit):
    """Optimized function to get commit details using git log command."""
    git_log_output = subprocess.check_output(
        ['git', 'log', '-1', '--pretty=%B||%ci||%an', commit]
    ).decode('utf-8').strip()
    commit_message, commit_date_str, author_name = git_log_output.split("||")
    commit_date = datetime.strptime(commit_date_str, '%Y-%m-%d %H:%M:%S %z').strftime('%d/%m/%Y')
    return commit_message, commit_date, author_name

def find_missing_authors(comments_dict):
    """Function to find lines with missing authors in the comments_dict."""
    missing_authors = {}
    for file_path, comments in comments_dict.items():
        missing_lines = []
        for comment in comments:
            if re.match(header_regex, comment):
                if re.match(r'--\s\d{2}/\d{2}/\d{4}\s{5,}', comment):
                    missing_lines.append(comment)
        if missing_lines:
            missing_authors[file_path] = missing_lines
    return missing_authors


def main():
    """Main function to process git commits and update history.json"""
    parser = argparse.ArgumentParser(description="Process git commits and update history.json.")
    parser.add_argument('commit1', nargs='?', type=str, default = rbc_common.get_previous_internal_version(), help="Oldest commit hash of the baseline.")
    parser.add_argument('commit2', nargs='?', type=str, default = "HEAD", help="Latest commit hash.")
    parser.add_argument('folder', nargs='?', type=str, default = "src", help="Folder for safe files to analyse")
    args = parser.parse_args()

    commit1 = args.commit1
    commit2 = args.commit2
    folder = args.folder
    # Validate the commits
    if not commits_are_valid(commit1, commit2):
        print(f"Error: One or both of the commits ({commit1}, {commit2}) are invalid.")
        sys.exit(1)  # Exit the script immediately

    print(f"Commits {commit1} and {commit2} exist.")

    #Move to repository base directory
    base_directory  = rbc_common.Get_Base_Directory()
    os.chdir(base_directory)

    # Load the existing comments_dict if it exists, otherwise start with an empty dictionary
    comments_dict = {}
    if os.path.exists(HISTORY_FILE_PATH):
        with open(HISTORY_FILE_PATH, 'r', encoding='utf-8') as f:
            comments_dict = json.load(f)

    commits_list = []
    commits_list = subprocess.check_output(
        ['git', 'rev-list', '--topo-order', '--reverse', f'{commit1}..{commit2}','--', f'{folder}']
    ).decode('utf-8').split()
    
    for commit in commits_list:
        print("next_commit" + commit)

        # Generate the git diff between current_commit and next_commit
        git_diff_command = generate_git_diff_command((commit + "~"), commit, diff_path, folder)
        result = subprocess.run(git_diff_command, shell=True, check=True)
        if result.returncode != 0:
            print(f"Error: Git diff failed for commit {commit}")
            sys.exit(1)

        # Process the diff file to get modified, renamed, and deleted files
        modified_and_new_files, renamed_files, deleted_files, renamed_and_modified_files = process_diff_file(diff_path)
        
        print(f"Modified files: {modified_and_new_files}")
        print(f"Renamed files: {renamed_files}")
        print(f"Deleted files: {deleted_files}")
        print(f"Renamed and Modified files: {renamed_and_modified_files}")

        commit_message, commit_date, author_name = get_commit_details(commit)
        print (commit_message, commit_date, author_name)

        return_value = append_commit_message_to_files(modified_and_new_files,renamed_and_modified_files, commit_message, commit_date, author_name, comments_dict)

        if return_value == 0:
            # Handle file renaming in comments_dict
            for old_name, new_name in renamed_files:
                handle_file_renaming(old_name, new_name, comments_dict)
            
            # Handle renamed and modified files
            for old_name, new_name in renamed_and_modified_files:
                handle_file_renaming(old_name, new_name, comments_dict)
        
            # Handle file deletions in comments_dict
            for deleted_file in deleted_files:
                handle_file_deletion(deleted_file, comments_dict)

    # Save the updated comments_dict to the JSON file
    with open(HISTORY_FILE_PATH, 'w', encoding='utf-8') as f:
        json.dump(comments_dict, f, indent=4)
    print(f"Comments have been written to {HISTORY_FILE_PATH}")

    # Find missing authors
    missing_authors = find_missing_authors(comments_dict)
    # Check if missing authors are found
    if missing_authors:
        with open(missing_authors_path, 'w', encoding='utf-8') as f:
            json.dump(missing_authors, f, indent=4)
        print(f"Missing authors' comments have been saved to {missing_authors_path}")
    else:
        print("No missing author headers found.")

    #clean up diff file
    os.remove(diff_path)

# Run the main function
if __name__ == "__main__":
    main()
