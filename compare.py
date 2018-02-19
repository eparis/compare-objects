#!/bin/env python3

import json
import jsondiff
import sys
import subprocess
from pprint import pprint

with open('template.json') as json_data:
    template = json.load(json_data)
    json_data.close()
    #template = set(d.items())

contexts = sys.argv[1:]
dcs = dict()
for context in contexts:
    contextFlag = ("--context=%s" % context)
    completed = subprocess.run(
        ['oc', 'get', '-o', 'json', '--namespace=default', contextFlag, 'deploymentconfig', 'router'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode != 0:
        print("Error getting router dc on", context)
        print(completed.stderr.decode('utf-8'))
        sys.exit(1)
    dc = completed.stdout.decode('utf-8')
    jdc = json.loads(dc)
    meta = jdc["metadata"]
    for key in [ 'creationTimestamp', 'generation', 'resourceVersion', 'selfLink', 'uid' ]:
        meta.pop(key)
    jdc["metadata"] = meta
    jdc.pop('status')
    dcs[context] = jdc

for cluster,router in dcs.items():
    jsondiff.diff(template, router)
