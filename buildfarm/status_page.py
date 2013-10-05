#!/usr/bin/env python

from __future__ import print_function

import csv
import re
import time
from StringIO import StringIO

import numpy as np

from buildfarm.ros_distro import debianize_package_name

version_rx = re.compile(r'[0-9.-]+[0-9]')


def get_da_strs(distro_arches):
    distros = set()
    output = []
    for d, a in distro_arches:
        if d not in distros:
            output.append(d + '_source')
            distros.add(d)
        output.append(get_dist_arch_str(d, a))
    return output


def get_distro_arches(arches, rosdistro):
    if rosdistro == 'fuerte':
        from buildfarm.ros_distro_fuerte import get_target_distros
    else:
        from buildfarm.ros_distro import get_target_distros

    distros = get_target_distros(rosdistro)
    return [(d, a) for d in distros for a in arches]


def make_versions_table(rd_data, apt_data,
                        da_strs, repo_names, rosdistro):
    '''
    Returns an in-memory table with all the information that will be displayed:
    ros package names and versions followed by debian versions for each
    distro/arch.
    '''
    left_columns = [('name', object), ('version', object), ('wet', object)]
    right_columns = [(da_str, object) for da_str in da_strs]
    columns = left_columns + right_columns

    distro_debian_names = [debianize_package_name(rosdistro, pkg.name) for pkg in  rd_data.packages.values()]

    # prefixes of other ros distros
    prefixes = ['ros-electric-', 'ros-fuerte-', 'ros-unstable-']
    for distribution in rd_data.rosdistro_index.distributions:
        prefixes.append('ros-%s-' % distribution)
    rosdistro_prefix = 'ros-%s-' % rosdistro
    if rosdistro_prefix in prefixes:
        prefixes.remove(rosdistro_prefix)

    non_distro_debian_names = []
    for debian_name in apt_data.debian_packages:
        skip = False
        # skip packages from other ros distros
        for prefix in prefixes:
            if debian_name.startswith(prefix):
                skip = True
        if skip:
            continue
        # skip packages which are in the rosdistro
        if debian_name in distro_debian_names:
            continue
        # skip packages without prefix of this ros distro
        if not debian_name.startswith(rosdistro_prefix):
            continue
        non_distro_debian_names.append(debian_name)

    table = np.empty(len(rd_data.packages) + len(non_distro_debian_names),
                     dtype=columns)

    # add all packages coming from the distro (wet, dry, variant)
    for i, pkg_data in enumerate(rd_data.packages.values()):
        table['name'][i] = pkg_data.name
        table['version'][i] = pkg_data.version
        table['wet'][i] = pkg_data.type
        for da_str in da_strs:
            debian_name = debianize_package_name(rosdistro, pkg_data.name)
            versions = get_versions(apt_data, debian_name,
                                    repo_names, da_str)
            table[da_str][i] = add_version_cell(versions)

    i = len(rd_data.packages)
    for debian_name in non_distro_debian_names:
        #undebianized_pkg_name = undebianize_package_name(rosdistro, pkg_name)
        pkg_name = debian_name
        if pkg_name.startswith(rosdistro_prefix):
            pkg_name = pkg_name[len(rosdistro_prefix):]
        table['name'][i] = pkg_name
        table['version'][i] = ''
        table['wet'][i] = 'unknown'
        all_versions = []
        for da_str in da_strs:
            versions = get_versions(apt_data, debian_name,
                                    repo_names, da_str)
            table[da_str][i] = add_version_cell(versions)
            all_versions.extend(versions)
        # if all version values are the same (or None) lets assume that is the expected version
        unique_versions = set([v for v in all_versions if v != 'None'])
        if len(unique_versions) == 1:
            table['version'][i] = unique_versions.pop()
        i += 1

    return table


def get_versions(apt_data, pkg_name, repo_names, da_str):
    versions = []
    for repo_name in repo_names:
        v = apt_data.get_version(pkg_name, repo_name, da_str)
        v = str(v)
        v = strip_version_suffix(v)
        versions.append(v)
    return versions


def add_version_cell(versions):
    return '|'.join(versions)


def strip_version_suffix(version):
    """
    Removes trailing junk from the version number.

    >>> strip_version_suffix('')
    ''
    >>> strip_version_suffix('None')
    'None'
    >>> strip_version_suffix('1.9.9-0quantal-20121115-0529-+0000')
    '1.9.9-0'
    >>> strip_version_suffix('1.9.9-foo')
    '1.9.9'
    """
    match = version_rx.search(version)
    return match.group(0) if match else version


def detect_source_version(source_name, source_records):
    """
    Detect if the source package is available on the server and return
    the version, else None
    """
    source_records.restart()
    source_lookup = source_records.lookup(source_name)
    if not source_lookup:
        #print("Missed %s" % source_name)
        return None
    else:
        src_version = strip_version_suffix(source_records.version)
        #print("Source %s %s" % (source_name, src_version))
        return src_version


def get_dist_arch_str(d, a):
    return "%s_%s" % (d, a)


def render_csv(rd_data, apt_data, outfile, rosdistro,
               distro_arches, ros_repos):
    distros = {}

    for (d, a) in distro_arches:
        if not d in distros:
            distros[d] = []
        distros[d].append(a)
    das = []
    for d in distros:
        for a in distros[d]:
            das.append((d, a))
    da_strs = get_da_strs(das)

    # Make an in-memory table showing the latest deb version for each package.
    t = make_versions_table(rd_data,
                            apt_data,
                            da_strs,
                            ros_repos.keys(),
                            rosdistro)

    with open(outfile, 'w') as fh:
        # Output CSV from the in-memory table
        w = csv.writer(fh)
        w.writerow(t.dtype.names)
        for row in t:
            w.writerow(row)


def transform_csv_to_html(data_source, metadata_builder,
                          rosdistro, start_time, resource_path, cached_release=None):
    reader = csv.reader(data_source, delimiter=',', quotechar='"')
    rows = [row for row in reader]

    header = rows[0]
    rows = rows[1:]

    html_head = make_html_head(rosdistro, start_time, resource_path, cached_release is not None)

    metadata_columns = [None] * 3 + [metadata_builder(c) for c in header[3:]]
    header = [format_header_cell(header[i],
                                 metadata_columns[i]) \
                  for i in range(len(header))]

    # count non-None rows per (sub-)column
    counts = [[]] * 3 + [[0] * 3 for _ in range(3, len(header))]
    for row in rows:
        for i in range(3, len(counts)):
            versions = get_cell_versions(row[i])
            for j in range(0, len(versions)):
                if versions[j] != 'None':
                    counts[i][j] += 1

    def get_package_name_from_row(row):
        return row[0]
    rows = sorted(rows, key=get_package_name_from_row)
    rows = [format_row(r, metadata_columns) for r in rows]
    if cached_release:
        inject_status_and_maintainer(cached_release, header, counts, rows)

    # div-wrap the first two cells for layout reasons.
    for row in rows:
        row[0] = "<div>%s</div>" % row[0]
        row[1] = "<div>%s</div>" % row[1]
        
    body = make_html_legend()
    body += make_html_table(header, counts, rows)
    return make_html_doc(html_head, body)


def inject_status_and_maintainer(cached_release, header, counts, rows):
    from catkin_pkg.package import InvalidPackage, parse_package_string
    header[3:3] = ['Status', 'Maintainer']
    counts[3:3] = [[], []]
    for row in rows:
        status_cell = ''
        maintainer_cell = ''
        if row[2] == 'wet':
            pkg_name = row[0].split(' ')[0]
            pkg = cached_release.packages[pkg_name]
            repo = cached_release.repositories[pkg.repository_name]
            status = 'unknown'
            if pkg.status is not None:
                status = pkg.status
            elif repo.status is not None:
                status = repo.status
            status_description = ''
            if pkg.status_description is not None:
                status_description = pkg.status_description
            elif repo.status_description is not None:
                status_description = repo.status_description
            status_cell = '<div class="%s"%s>%s</div>' % (status, ' title="%s"' % status_description if status_description else '', status)
            pkg_xml = cached_release.get_package_xml(pkg_name)
            if pkg_xml is not None:
                try:
                    pkg = parse_package_string(pkg_xml)
                    maintainer_cell = ''.join(['<a href="mailto:%s">%s</a>' % (m.email, m.name) for m in pkg.maintainers])
                except InvalidPackage as e:
                    maintainer_cell = 'invalid package.xml'
            else:
                maintainer_cell = '?'
        else:
            status_cell = '<div class="unknown">--</div>'
        row[3:3] = [status_cell, maintainer_cell]


def format_header_cell(cell, metadata):
    if metadata and 'column_label' in metadata:
        cell = metadata['column_label']
    else:
        cell = cell[0].upper() + cell[1:]
    return cell


def format_row(row, metadata_columns):
    public_changing_on_sync = [False] * 3 + \
        [is_public_changing_on_sync(c) for c in row[3:]]
    # Flag if this is dry or a variant so as not to show sourcedebs as red
    no_source = row[2] in ['variant', 'dry']
    # ignore source columns for dry/variant when deciding of columns are homogeneous
    diff_columns = [c for i, c in enumerate(row) if i > 2 and (not no_source or i % 3)]
    has_diff_between_rosdistros = len(set(diff_columns)) > 1

    # urls for each building repository column
    metadata = [None] * 3 + [md for md in metadata_columns[3:]]
    if row[2] == 'dry':
        # disable links for dry source columns
        metadata = [(c if i < 3 or i % 3 else None) for i, c in enumerate(metadata)]
    elif row[2] in ['unknown', 'variant']:
        # disable all links for unknown and variant rows
        metadata = [None for _ in range(len(metadata))]
    job_urls = [md['job_url'].format(pkg=row[0].replace('_', '-')) \
                    if md else None for md in metadata]
    # for unknown packages the latest version number is only a guess so don't mark missing cells
    latest_version = row[1] if row[2] != 'unknown' else None
    # only pass no_source if this is a sourcedeb entry
    row = row[:3] + [format_versions_cell(row[i],
                                          latest_version,
                                          job_urls[i],
                                          public_changing_on_sync[i],
                                          no_source and i % 3 == 0) \
                         for i in range(3, len(row))]

    if has_diff_between_rosdistros:
        row[0] += ' <span class="ht">diff</span>'

    type_texts = {
       'wet': 'wet',
       'dry': 'dry',
       'unknown': '?',
       'variant': "var"
    }
    row[2] = type_texts[row[2]]
    return row


def is_public_changing_on_sync(cell):
    versions = get_cell_versions(cell)
    return versions[1] != versions[2]


def get_cell_versions(cell):
    return cell.split('|')


def format_versions_cell(cell, latest_version, url=None,
                         public_changing_on_sync=False,
                         no_source=False):
    versions = get_cell_versions(cell)
    repos = ['building', 'shadow-fixed', 'ros/public']
    search_suffixes = ['1', '2', '3']
    # set the latest_version to None if no package expected
    if no_source:
        latest_version = None
    cell = ''.join([format_version(v,
                                   latest_version,
                                   r,
                                   s,
                                   versions[-1],
                                   url if r == 'building' else None)\
                        for v, r, s in zip(versions, repos, search_suffixes)])

    if public_changing_on_sync:
        cell += '<span class="ht">sync</span>'

    return cell


def format_version(version, latest, repo, search_suffix,
                   public_version, url=None):
    label = '%s: %s' % (repo, version)
    if latest:
        color = {'None': 'm',
                 latest: ''}.get(version, 'o')
        # use reasonable names (even if invisible) to be searchable
        order_value = {'None': '5&nbsp;red',
                       latest: '1&nbsp;green'}.get(version, '3&nbsp;blue')
    else:
        color = {'None': 'i'}.get(version, 'obs')
        # use reasonable names (even if invisible) to be searchable
        order_value = {'None': '2&nbsp;gray'}.get(version, '4&nbsp;yellow')
    order_value += search_suffix
    if repo != 'ros/public' and is_regression(version, public_version):
        order_value += '&nbsp;regression' + search_suffix
    if url:
        order_value = '<a href="%s"></a>' % (url) #, order_value)
    else:
        order_value = ''
    return make_square_div(label, color, order_value)


def is_regression(version, public_version):
    # public has a package and specific repo doesn't
    return public_version != 'None' and version == 'None'


def make_square_div(label, color, order_value):
    #order_value = '<a></a>'
    if color == '': 
        return '<a title="%s" />' % label
    else:
        return '<a class="%s" title="%s" />' % (color, label)

def make_html_head(rosdistro, start_time, resource_path, has_status_and_maintainer=False):
    rosdistro = rosdistro[0].upper() + rosdistro[1:]
    output = StringIO();

    output.write('<title>ROS %s - build status page - %s</title>\n' % (rosdistro, time.strftime('%Y-%m-%d %H:%M:%S %Z', start_time)))
    output.write('''
<meta http-equiv="Content-Type" content="text/html;charset=utf-8"/>

<script type="text/javascript" src="jquery/jquery-1.8.3.min.js"></script>
<script type="text/javascript" src="jquery/jquery.dataTables.min.js"></script>
<script type="text/javascript" src="jquery/jquery.dataTables.columnFilter.js"></script>
<script type="text/javascript" src="jquery/FixedHeader.min.js"></script>
<script type="text/javascript" src="jquery/TableTools.min.js"></script>

<link rel="stylesheet" href="css/status_page.css" />
''')

    # '{ type: "select",  values: ["--", "developed", "maintained", "unmaintained", "end-of-life", "unknown"] }, { type: "text" },' if has_status_and_maintainer else '')

    return output.getvalue()

def make_html_legend():
    definitions = [
        ('wet', '<a href="http://ros.org/wiki/catkin">catkin</a>'),
        ('dry', '<a href="http://ros.org/wiki/rosbuild">rosbuild</a>'),
        ('<span class="square">1</span>&nbsp;<span class="square">2</span>&nbsp;<span class="square">3</span>', 'The apt repos (1) building, (2) shadow-fixed, (3) ros/public'),
        ('<span class="square pkgLatest">&nbsp;</span>', 'same version'),
        ('<span class="square pkgOutdated">&nbsp;</span>', 'different version'),
        ('<span class="square pkgMissing">&nbsp;</span>', 'missing'),
        ('<span class="square pkgObsolete">&nbsp;</span>', 'obsolete'),
        ('<span class="square pkgIgnore">&nbsp;</span>', 'intentionally missing')
    ]
    definitions = ['<li><b>%s:</b>&nbsp;%s</li>' % (k, v) for (k, v) in definitions]
    return '''\
<ul>
    %s
</ul>
''' % ('\n'.join(definitions))


def make_html_table(columns, counts, rows):
    '''
    Returns a string containing an HTML-formatted table, given a header and some
    rows.

    >>> make_html_table(header=['a'], rows=[[1], [2]])
    '<table>\\n<tr><th>a</th></tr>\\n<tr><td>1</td></tr>\\n<tr><td>2</td></tr>\\n</table>\\n'

    '''
    headers = []
    for i in range(len(columns)):
        headers.append('%s<br/>%s' % (columns[i], ''.join(['<span class="sum repo%s">%d</span>' % (i + 1, v) for i, v in enumerate(counts[i])])))
    header_str = '<tr>' + ''.join('<th>%s</th>' % c for c in headers) + '</tr>'
    rows_str = '\n'.join('<tr>' + ''.join('<td>%s</td>' % c for c in r) + '</tr>' for r in rows)
    footer_str = '<tr>' + ''.join('<th>%s</th>' % (c if i != 2 else '') for i, c in enumerate(columns)) + '</tr>'
    return '''\
<table class="display" id="csv_table">
    <thead>
        %s
    </thead>
    <tfoot>
        %s
    </tfoot>
    <tbody>
        %s
    </tbody>
</table>
''' % (header_str, footer_str, rows_str)


def make_html_doc(head, body):
    '''
    Returns the contents of an HTML page, given a title and body.
    '''
    output = StringIO()
    output.write('<!DOCTYPE html>\n')
    output.write('<html>\n<head>\n')
    output.write(head)
    output.write('</head>\n<body>\n')
    output.write(body)
    output.write('</body>\n</html>\n')
    return output.getvalue()
