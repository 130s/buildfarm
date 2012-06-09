#!/usr/bin/env python

import apt
import os
import argparse
import tempfile
import shutil
import yaml
import urllib2

import buildfarm.apt_root #setup_apt_root
import buildfarm.rosdistro

URL_PROTOTYPE="https://raw.github.com/ros/rosdistro/master/releases/%s.yaml"

def parse_options():
    parser = argparse.ArgumentParser(description="List all packages available in the repos for each arch.  Filter on substring if provided")
    parser.add_argument("--rootdir", dest="rootdir", default = None,
                        help='The directory for apt to use as a rootdir')
    parser.add_argument("--rosdistro", dest='rosdistro', default = 'fuerte',
           help='The ros distro. electric, fuerte, galapagos')
    parser.add_argument("--substring", dest="substring", default="", 
                        help="substring to filter packages displayed default = 'ros-ROSDISTRO'")
    parser.add_argument("-u", "--update", dest="update", action='store_true', default=False, 
                        help="update the cache from the server")
    parser.add_argument('--repo', dest='repo_urls', action='append',metavar=['REPO_NAME@REPO_URL'],
           help='The name for the source and the url such as ros@http://50.28.27.175/repos/building')

    args = parser.parse_args()

    # default for now to use our devel server
    if not args.repo_urls:
        args.repo_urls =['ros@http://50.28.27.175/repos/building']
    for a in args.repo_urls:
        if not '@' in a:
            parser.error("Invalid repo definition: %s"%a)

    if not args.substring:
        args.substring = 'ros-%s'%args.rosdistro

    return args

class Package(object):
    def __init__(self, name, version):
        self.name = name
        self.version = version


def list_packages(rootdir, update, substring):
    c = apt.Cache(rootdir=rootdir)
    c.open()

    if update:
        c.update()

    c.open() # required to recall open after updating or you will query the old data

    packages = []
    for p in [k for k in c.keys() if args.substring in k]:
        v = c[p].versions[0]
        packages.append(Package(p, c[p].candidate.version))

    return packages



def render_vertical(packages):
    all_package_names_set = set()
    package_map = {}
    for v in packages.itervalues():
        all_package_names_set.update([p.name for p in v])

    all_package_names = list(all_package_names_set)
    all_package_names.sort()
    
    if len(all_package_names) == 0:
        print "no packages found matching substring" 
        return

    width = max([len(p) for p in all_package_names])
    pstr = "package"
    print pstr, " "*(width-len(pstr)), ":",
    arch_distro_list = sorted(packages.iterkeys())
    for k in arch_distro_list:
        print k+"|",
    print '' 

    

    for p in all_package_names:
        l = len(p)
        print p, " "*(width-l), ":",
        for k  in arch_distro_list:
            pkg_name_lookup = {}
            for pkg in packages[k]:
                pkg_name_lookup[pkg.name] = pkg
            if p in pkg_name_lookup:
                version_string = pkg_name_lookup[p].version
                print version_string[:len(k)]+' '*max(0, len(k) -len(version_string) )+('|' if len(version_string) < len(k) else '>'),
                #, 'x'*len(k),'|', 
            else:
                print ' '*len(k)+'|', 
        print ''
            

if __name__ == "__main__":
    args = parse_options()


    if args.rootdir:
        rootdir = args.rootdir
    else:  
        rootdir = tempfile.mkdtemp()
        

    arches = ['i386', 'amd64']
    #distros = ['lucid', 'oneiric']

    print("Fetching " + URL_PROTOTYPE%'targets')
    targets_map = yaml.load(urllib2.urlopen(URL_PROTOTYPE%'targets'))
    my_targets = [x for x in targets_map if args.rosdistro in x]
    if len(my_targets) != 1:
        print("Must have exactly one entry for rosdistro %s in targets.yaml"%(args.rosdistro))
        sys.exit(1)
    distros = my_targets[0][args.rosdistro]


    ros_repos = buildfarm.apt_root.parse_repo_args(args.repo_urls)

    packages = {}



    try:
        for d in distros:
            for a in arches:
                dist_arch = "%s_%s"%(d, a)
                specific_rootdir = os.path.join(rootdir, dist_arch)
                buildfarm.apt_root.setup_apt_rootdir(specific_rootdir, d, a, additional_repos = ros_repos)
                print "setup rootdir %s"%specific_rootdir
                
                packages[dist_arch] = list_packages(specific_rootdir, update=True, substring=args.substring)

                
    finally:
        if not args.rootdir: # don't delete if it's not a tempdir
            shutil.rmtree(rootdir)

    rd = buildfarm.rosdistro.Rosdistro(args.rosdistro)
    distro_packages = rd.get_package_list()


    packages[' '+ args.rosdistro] = [Package(buildfarm.rosdistro.debianize_package_name(args.rosdistro, p), rd.get_version(p)) for p in distro_packages]
    render_vertical(packages)
