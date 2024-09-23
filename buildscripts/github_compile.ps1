$build = (Get-Location).Path

$pluginsDir = "$build\helix_blender_plugin"

if (Test-Path $pluginsDir) {
    Remove-Item -Recurse -Force $pluginsDir
}

New-Item -ItemType Directory -Path $pluginsDir
New-Item -ItemType Directory -Path "$pluginsDir\site_packages"

Set-Location "$build\src\helix_blender_plugin\dam_app"

if (Test-Path "venv") {
    Remove-Item -Recurse -Force "venv"
}

New-Item -ItemType Directory -Path "venv"

# Try to run the script using 'py'
$pythonCommand = "py"
if (-not (Get-Command $pythonCommand -ErrorAction SilentlyContinue)) {
    # Fallback to 'python' if 'py' is not available
    $pythonCommand = "python"
}

& $pythonCommand -m venv venv
& "$build\src\helix_blender_plugin\dam_app\venv\Scripts\Activate.ps1"

python.exe -m pip install --upgrade pip
python.exe -m pip install pyinstaller
python.exe -m pip install -r requirements-win.txt

pyinstaller PSWebView.py --name="HelixBlenderPlugin.exe" `
                         --icon="icon/plugin_402x.ico" `
                         --add-data="icon/*:icon" `
                         --add-data="logs/config.xml:logs" `
                         --onefile

# The chmod command isn't relevant on Windows, as executable permissions work differently

Copy-Item -Recurse -Force "venv\Lib\site-packages\psutil*" "$pluginsDir\site_packages"
Copy-Item -Recurse -Force "dist\HelixBlenderPlugin.exe" $pluginsDir
Copy-Item -Recurse -Force "logs" $pluginsDir
Copy-Item -Recurse -Force "icon" $pluginsDir
Copy-Item -Recurse -Force "..\*.py" $pluginsDir

Remove-Item -Recurse -Force "venv", "build", "dist"

deactivate

Set-Location $build

Compress-Archive -Path "$pluginsDir" -DestinationPath "helix_blender_plugin.zip" -Force

Remove-Item -Recurse -Force $pluginsDir