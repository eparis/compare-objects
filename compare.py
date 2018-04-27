#!/bin/env python3

import json
import jsondiff
import sys
import subprocess
import operator
import argparse
from pprint import pprint

resource=""
namespace=""
name=""
ignoreEnvVars = []
ignoreAnnotations = []
ignoreTemplateAnnotations = []

def getContexts(clusterCSV):
    clusters = clusterCSV.split(",")
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
        name = context["name"]
        context = context["context"]
        if "cluster" not in context or "namespace" not in context:
            continue
        cluster = context["cluster"]
        namespace = context["namespace"]
        if namespace != "default":
            continue
        found = False
        for c in clusters:
            if c in cluster:
                found = True
                break
        if found:
            out.append(name)
    out.sort()
    return out

def getDefaultsFromTemplate(dc):
    global resource
    global namespace
    global name
    resource = dc["kind"]
    namespace = "default"
    if "namespace" in dc["metadata"]:
        namespace = dc["metadata"]["namespace"]
    name = dc["metadata"]["name"]

    global ignoreEnvVars
    if "spec" in dc and "template" in dc["spec"] and "spec" in dc["spec"]["template"] and "containers" in dc["spec"]["template"]["spec"]:
        for containers in dc["spec"]["template"]["spec"]["containers"]:
            if "env" not in containers:
                continue
            env = containers["env"]
            for val in env:
                if "value" in val and val["value"] == "IGNORED":
                    ignoreEnvVars.append(val["name"])

    global ignoreAnnotations
    if "annotations" in dc["metadata"]:
        annotations = dc["metadata"]["annotations"]
        for key,value in annotations.items():
            if value == "IGNORED":
                ignoreAnnotations.append(key)

    global ignoreTemplateAnnotations
    if "spec" in dc and "template" in dc["spec"] and "metadata" in dc["spec"]["template"] and "annotations" in dc["spec"]["template"]["metadata"]:
        annotations = dc["spec"]["template"]["metadata"]["annotations"]
        for key,value in annotations.items():
            if value == "IGNORED":
                ignoreTemplateAnnotations.append(key)

def cleanENV(dc):
    if "spec" not in dc or "template" not in dc["spec"] or "spec" not in dc["spec"]["template"] or "containers" not in dc["spec"]["template"]["spec"]:
        return
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
        meta.pop(key, None)
    dc["metadata"] = meta
    if "annotations" in dc["metadata"]:
        annotations = dc["metadata"]["annotations"]
        for ignore in ignoreAnnotations:
            annotations.pop(ignore, None)

def cleanTemplateMeta(dc):
    if "spec" not in dc or "template" not in dc["spec"] or "metadata" not in dc["spec"]["template"]:
        return
    meta = dc["spec"]["template"]["metadata"]
    if "annotations" in dc["spec"]["template"]["metadata"]:
        annotations = dc["spec"]["template"]["metadata"]["annotations"]
        for ignore in ignoreTemplateAnnotations:
            annotations.pop(ignore, None)

def cleanSpec(dc):
    if "sepc" in dc:
        spec = dc["spec"]
        for key in [ 'templateGeneration' ]:
            spec.pop(key, None)

def cleanStatus(dc):
    dc.pop('status', None)

def cleanFields(template):
    cleanSpec(template)
    cleanStatus(template)
    cleanENV(template)
    cleanMeta(template)
    cleanTemplateMeta(template)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("templateFile", help="File To Use As A Template")
    parser.add_argument("--clusters", help="strings to look for in cluster names (CSV)", default="starter,free")
    args = parser.parse_args()

    with open(args.templateFile) as json_data:
        template = json.load(json_data)
        json_data.close()

    getDefaultsFromTemplate(template)
    cleanFields(template)

    contexts = getContexts(args.clusters)
    for context in contexts:
        completed = subprocess.run(
            ['oc', 'get', '-o', 'json', ("--namespace=%s" % namespace), ("--context=%s" % context), resource, name],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if completed.returncode != 0:
            print("Error: oc get -o json --namespace=%s --context=%s %s %s:" % (namespace, context, resource, name))
            print(completed.stderr.decode('utf-8'))
            continue
        dc = json.loads(completed.stdout.decode('utf-8'))
        cleanFields(dc)
        print("Results for: ", context)
        pprint(jsondiff.diff(template, dc, syntax='symmetric'))
        print("************************************************************")
        print("")

if __name__== "__main__":
  main()
