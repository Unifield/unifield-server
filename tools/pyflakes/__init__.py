#!/usr/bin/env python

from bzrlib import branch, errors
from distutils.spawn import find_executable
import subprocess

def pyflakes_check(local_branch, master_branch, old_revision_number, old_revision_id, future_revision_number, future_revision_id, tree_delta, future_tree):

    files_to_check = []
    for i in tree_delta.added, tree_delta.modified:
        for f in i:
            if f[0].endswith('.py'):
                files_to_check.append(f[0])

    if len(files_to_check) == 0:
        return

    for exe in [ 'autopep8', 'pyflakes' ]:
        if find_executable(exe) is None:
            raise errors.BzrError("Required command %s is missing." % exe)

    cmd = [ 'autopep8', '--select=E1', '--diff' ]
    cmd.extend(files_to_check)
    res = subprocess.check_output(cmd)
    if res != '':
        cmd[2] = '--in-place'
        raise errors.BzrError("Fix autopep8 warnings before committing. You might want to use this command: %s" % " ".join(cmd))

    cmd = [ 'pyflakes' ]
    cmd.extend(files_to_check)

    print
    result = subprocess.call(cmd)

    if result != 0:
        raise errors.BzrError("Fix pyflakes warnings before committing.")

branch.Branch.hooks.install_named_hook('pre_commit', pyflakes_check, 'pyflakes warnings prevent check-in')
