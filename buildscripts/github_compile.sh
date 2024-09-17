#!/bin/bash

build=`pwd`

pluginsDir=$build/helix_blender_plugin
if [ -d $pluginsDir ]; then
    rm -rf $pluginsDir
fi
mkdir -p $pluginsDir
mkdir -p $pluginsDir/site_packages

cd src/helix_blender_plugin/dam_app

if [ -d "venv" ]; then
    rm -rf "venv"
fi

mkdir -m 777 venv

python3 -m venv venv
source venv/bin/activate

python3 -m pip install --upgrade pip
python3 -m pip install pyinstaller
python3 -m pip install -r requirements-mac.txt
cp icon/plugin_402x.ico icon/plugin_402x.icns

pyinstaller PSWebView.py --name="HelixBlenderPlugin" \
                         --icon="icon/plugin_402x.icns" \
                         --add-data="icon/*:icon" \
                         --add-data="logs/config.xml:logs" \
                         --onefile

chmod +x dist/HelixBlenderPlugin

cp -f -r venv/lib/python3*/site-packages/psutil* $pluginsDir/site_packages
cp -f -r dist/HelixBlenderPlugin $pluginsDir/
cp -f -r logs $pluginsDir/
cp -f -r icon $pluginsDir/
cp -f -r ../*.py $pluginsDir/

rm -rf venv build dist

deactivate

cd $build

zip -rq helix_blender_plugin.zip helix_blender_plugin

rm -rf helix_blender_plugin