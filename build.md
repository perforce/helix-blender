
# Helix-Blender Plugin for DAM - Build Instructions

To build the Helix-Blender plugin for DAM, follow these steps:

1. Download the source code from the GitHub repository and unzip the source code archive.

2. Open a terminal (macOS) or PowerShell (Windows), and navigate to the directory where the source code was unzipped by running the following command:
   ```bash
   cd /path/to/unzipped/source
   ```

3. Run the build command based on your operating system:
   - For **macOS**, run:
     ```bash
     sh ./buildscripts/github_compile.sh
     ```
   - For **Windows**, run the following command in PowerShell as Administrator:
     ```powershell
     powershell -ExecutionPolicy Bypass -File .\buildscripts\github_compile.ps1
     ```

4. After the build succeeds, the final output will be generated in the same directory with the name `helix_blender_plugin.zip`.

This zip file contains the built plugin and is ready for use.
