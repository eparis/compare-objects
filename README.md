A tool to compare kube objects across clusters.

Log into each cluster:
```
for cluster in $(ssh devaccess@use-tower1.ops.rhcloud.com ohi --list-clusters -o yaml | grep -E 'free|starter'); do oc login -u <YOUR_access.redhat.com_USERNAME> https://api.${cluster}.openshift.com:443; done
```

Run the comparator:
```
./compare.py logging-curator.json 
```

The output might not be easy to read, but think of it as a diff from the template to the version of the object running on that cluster.
