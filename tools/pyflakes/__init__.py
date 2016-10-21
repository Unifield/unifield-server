#!/usr/bin/env python

from bzrlib import branch, errors
import subprocess

def pyflakes_check(local_branch, master_branch, old_revision_number, old_revision_id, future_revision_number, future_revision_id, tree_delta, future_tree):

#TreeDelta(added=[], removed=[], renamed=[], kind_changed=[], modified=[(u'bin/addons/purchase/purchase.py', 'svn2bzr-bba8342460a88e50a33859a3805ec275dbf9b5fd', 'file', True, False)], unchanged=[], unversioned=[])

    files_to_check = []
    for i in tree_delta.added, tree_delta.modified:
	for f in i:
            if f[0].endswith('.py'):
                files_to_check.append(f[0])

    cmd = [ 'pyflakes' ]
    cmd.extend(files_to_check)

    print
    result = subprocess.call(cmd)
 
    if result != 0:
        raise errors.BzrError("Fix pyflakes warnings before committing.")
 
branch.Branch.hooks.install_named_hook('pre_commit', pyflakes_check, 'pyflakes warnings prevent check-in')
