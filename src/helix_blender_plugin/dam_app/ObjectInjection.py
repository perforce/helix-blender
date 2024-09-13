from PyQt5.QtWebEngineWidgets import QWebEngineScript
from PyQt5.QtCore import QFile, QIODevice
import logging

def get_webchannel_source():
    file = QFile(":/qtwebchannel/qwebchannel.js")
    if not file.open(QIODevice.ReadOnly):
        return ""
    return bytes(file.readAll()).decode('utf-8')

objectInjectionSourceCode = '''
"use strict";


var P4VObjectInjection = (function(){
    var injectedObjectsPromise = new Promise((resolve) => {
        // We use setTimeout() because depending on the order that QT injects
        // qwebchannel.js into the page, it may not be loaded yet so before
        // attempting to use it, we wait one iteration through the event-loop.
        // The result is that this only runs after the browser has parsed through
        // all the injected scripts.
        setTimeout(() => {
            new QWebChannel(qt.webChannelTransport, function(channel) {
                resolve(channel.objects);
            });
        },0)
    });
    
    
    return {
        injectedObject: async function(name) {
            let injectedObjects = await injectedObjectsPromise;
            console.log(injectedObjects[name])
            return injectedObjects[name];
        }
    };
}());
'''

def objectInjectionScripts(scripts = []):
    logging.debug("In objectInjectionScripts Function...")
    if len(scripts) == 0:
        allSourceCode = {}
        allSourceCode["qwebchannel.js"] = get_webchannel_source()
        allSourceCode["p4objectinjection.js"] = objectInjectionSourceCode
        for name, val in allSourceCode.items():
            script = QWebEngineScript()
            script.setName(name)
            script.setSourceCode(val)
            script.setInjectionPoint(QWebEngineScript.DocumentCreation)
            script.setWorldId(QWebEngineScript.MainWorld)
            scripts.append(script)
    return scripts

