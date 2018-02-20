#!/bin/env python3

import json
import jsondiff
import sys
import subprocess
import operator
from pprint import pprint

resource=""
namespace=""
name=""
ignoreEnvVars = []
ignoreAnnotations = ["deployment.kubernetes.io/revision", "kubectl.kubernetes.io/last-applied-configuration"]

def getContexts():
    completed = subprocess.run(['oc', 'config', 'view', '-o', 'json'],
            stdout=subprocess.PIPE,
    )
    if completed.returncode != 0:
        print("Unable to run oc `config view`")
        os.exit(1)
    config = json.loads(completed.stdout.decode('utf-8'))
    contexts = config["contexts"]
    out = []
    for context in contexts:
        cluster = context["context"]["cluster"]
        namespace = context["context"]["namespace"]
        if namespace != "default":
            continue
        if "starter" not in cluster and "free" not in cluster:
            continue
        out.append(context["name"])
    out.sort()
    return out

def getDefaultsFromTemplate(dc):
    global resource
    global namespace
    global name
    resource = dc["kind"]
    namespace = dc["metadata"]["namespace"]
    name = dc["metadata"]["name"]

    global ignoreEnvVars
    for containers in dc["spec"]["template"]["spec"]["containers"]:
        if "env" not in containers:
            continue
        env = containers["env"]
        for val in env:
            if val["value"] == "IGNORED":
                ignoreEnvVars.append(val["name"])

    global ignoreAnnotations
    if "annotations" in dc["metadata"]:
        annotations = dc["metadata"]["annotations"]
        for key,value in annotations.items():
            if value == "IGNORED":
                ignoreAnnotations.append(key)

def cleanENV(dc, ignoreEnvVars):
    for c in dc["spec"]["template"]["spec"]["containers"]:
        if "env" not in c:
            continue
        env = c["env"]

        # Sorting could cause problems if we have the same thing twice
        # but we should see that in the jsondiff
        env.sort(key=operator.itemgetter('name'))

        out = []
        for val in env:
            if val['name'] in ignoreEnvVars:
                v = {'name': val['name'], 'value': 'IGNORED'}
                out.append(v)
            else:
                out.append(val)
        c["env"] = out

def cleanMeta(dc):
    meta = dc["metadata"]
    for key in [ 'creationTimestamp', 'generation', 'resourceVersion', 'selfLink', 'uid' ]:
        meta.pop(key)
    dc["metadata"] = meta
    if "annotations" in dc["metadata"]:
        annotations = dc["metadata"]["annotations"]
        for ignore in ignoreAnnotations:
            annotations.pop(ignore, None)

def cleanStatus(dc):
    dc.pop('status')

with open(sys.argv[1]) as json_data:
    template = json.load(json_data)
    json_data.close()

getDefaultsFromTemplate(template)
cleanENV(template, ignoreEnvVars)
cleanMeta(template)
cleanStatus(template)

contexts = getContexts()
for context in contexts:
    completed = subprocess.run(
        ['oc', 'get', '-o', 'json', ("--namespace=%s" % namespace), ("--context=%s" % context), resource, name],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode != 0:
        print("Error: oc get -o json --namespace=%s --context=%s %s %s:" % (namespace, context, resource, name))
        print(completed.stderr.decode('utf-8'))
        sys.exit(1)
    dc = json.loads(completed.stdout.decode('utf-8'))
    cleanMeta(dc)
    cleanENV(dc, ignoreEnvVars)
    cleanStatus(dc)
    print("Results for: ", context)
    pprint(jsondiff.diff(template, dc, syntax='symmetric'))
