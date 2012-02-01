#!/usr/bin/env python

from __future__ import print_function
import os
import sys
import argparse
import yaml
import urllib2
import create_debjobs
import dependency_walker
import tempfile
import shutil

#import pprint # for debugging only, remove 

URL_PROTOTYPE="https://raw.github.com/willowgarage/rosdistro/master/%s.yaml"

def parse_options():
    parser = argparse.ArgumentParser(
             description='Create a set of jenkins jobs '
             'for source debs and binary debs for a catkin package.')
    parser.add_argument('--fqdn', dest='fqdn',
           help='The source repo to push to, fully qualified something...',
           default='50.28.27.175')
    parser.add_argument(dest='rosdistro',
           help='The ros distro. electric, fuerte, galapagos')
    parser.add_argument('--distros', nargs='+',
           help='A list of debian distros. Default: %(default)s',
           default=['lucid', 'oneiric'])
    parser.add_argument('--commit', dest='commit',
           help='Really?', action='store_true')
    parser.add_argument('--repo-workspace', dest='repos', action='store', 
           help='A directory into which all the repositories will be checked out into.')
    parser.add_argument('--username',dest='username')
    parser.add_argument('--password',dest='password')
    args = parser.parse_args()
    if args.commit and ( not args.username or not args.password ):
        print('If you are going to commit, you need a username and pass.',file=sys.stderr)
        sys.exit(1)
    return parser.parse_args()

def doit(repo_map, package_names_by_url, distros, fqdn, jobs_graph, commit = False, username = None, password=None):

    for r in repo_map:
        url = r['url']
        #TODO add distros parsing 
        if 'target' in r:
            if r['target'] == 'all':
                #TODO HACK Load from targets.yaml on github/rosdistro
                target_distros = ['lucid', 'oneiric']
            else:
                target_distros = r['target']
        else:
            target_distros = distros

        print ("Configuring %s for %s"%(r['url'], target_distros))
        
        create_debjobs.doit(url, package_names_by_url[url], target_distros, fqdn, jobs_graph, commit, username, password)

    return

if __name__ == "__main__":
    args = parse_options()
    repo = "http://"+args.fqdn+"/repos/building"

    repo_map = yaml.load(urllib2.urlopen(URL_PROTOTYPE%args.rosdistro))

    workspace = args.repos
    try:
        if not args.repos:
            workspace = tempfile.mkdtemp()
            
        (dependencies, package_names_by_url) = dependency_walker.get_dependencies(workspace, repo_map)

    finally:
        if not args.repos:
            shutil.rmtree(workspace)

    doit(repo_map, package_names_by_url, args.distros, args.fqdn, dependencies, args.commit, args.username, args.password)
