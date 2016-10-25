#!/usr/bin/env python

import subprocess

from bzrlib import branch, errors
from bzrlib.commands import Command, register_command
from bzrlib.workingtree import WorkingTree

from distutils.spawn import find_executable

def precommit(local_branch, master_branch, old_revision_number, old_revision_id, future_revision_number, future_revision_id, tree_delta, future_tree):

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
    res = subprocess.Popen(cmd, stdout=subprocess.PIPE).communicate()[0]

    if res != '':
        cmd[2] = '--in-place'
        raise errors.BzrError("Fix autopep8 warnings before committing. You might want to use this command: %s" % " ".join(cmd))

    cmd = [ 'pyflakes' ]
    cmd.extend(files_to_check)
    result = subprocess.call(cmd)

    if result != 0:
        raise errors.BzrError("Fix pyflakes warnings before committing.")


class cmd_precommit(Command):
    __doc__ = """Check changes with autopep8 and pyflakes.
    """
    takes_args = ['selected*']

    def run(self, message=None, selected_list=None):
        if hasattr(WorkingTree, "open_containing_paths"):
            tree, selected_list = WorkingTree.open_containing_paths(selected_list)
        else:
            # For bzr 2.1.x
            from bzrlib.builtins import tree_files
            tree, selected_list = tree_files(".")

        precommit(None, None, None, None, None, None, tree.changes_from(tree.basis_tree()), None)
        print "No problems found. Ready to commit."

register_command(cmd_precommit)
branch.Branch.hooks.install_named_hook('pre_commit', precommit, 'pyflakes warnings prevent check-in')
