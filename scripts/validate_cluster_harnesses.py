"""Offline manifest validation; no kubectl calls or configuration changes."""
import argparse
import json
from pathlib import Path
from hanni.compute.harnesses import manifests, network_policy, resource_quota, validate_deployment


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--deployment',type=Path,required=True)
    parser.add_argument('--task',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    deployment=validate_deployment(json.loads(args.deployment.read_text()))
    preview=manifests(deployment,json.loads(args.task.read_text()))
    preview['network_policy']=network_policy(deployment)
    preview['resource_quota']=resource_quota(deployment)
    preview['live_infrastructure']='NOT VERIFIED'
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x') as stream:json.dump(preview,stream,indent=2)
    print('Offline manifests valid; binding '+preview['binding']+'; no resources applied.')


if __name__=='__main__':main()
