# Update-headers-script
A script that identifies differences between commit hashes in a Git repository, focusing on the SRC folder. It tracks modifications, deletions, and renames of files, appending headers for modified files and organizing changes in a structured JSON document. Key inputs are the oldest and latest commit hashes and the specific source folder for updates

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
