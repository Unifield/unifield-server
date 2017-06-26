# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO consulting
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from __future__ import print_function
import bsdiff4
import cPickle
import cStringIO
import bz2
import os
import filecmp
import hashlib

def _defaultLog(*args):
    print(*args)

def _read_file(fn):
    with open(fn, 'rb') as f:
        data = f.read()
    return data

# mkpatch computes the binary patch necessary to change the
# directory old into new. Using the output of mkpatch
# with applyPatch(old, "a-new-dir") should result in "a-new-dir"
# containing precisely the same files as "new" does.
def mkPatch(old, new):
    patch = {
        # All filenames are relative to old.
        # Deletions: A list of files to delete
        'delete': [],
        # Additions: bz2 compressed copies of the files to add.
        'add': {},
        # Patches: key = filename, value = tuple of:
        #   (old-file-SHA1, patch, new-file-SHA1)
        # The SHA before is to make sure that we are applying the patch
        # to the correct base file. The SHA after is to be sure that bsdiff4
        # did his job correctly.
        'patch': {},
    }

    # walk old, looking for things that were deleted in new,
    # or that will be patched.
    for (dirpath, dirnames, filenames) in os.walk(old):
        relpath = dirpath.replace(old, '')
        if len(relpath) > 0 and relpath[0] == '/':
            relpath = relpath[1:]
        for f in filenames:
            oldf = os.path.join(dirpath, f)
            newf = os.path.join(new, relpath, f)
            dest = os.path.join(relpath, f)
            if not os.path.exists(newf):
                #print "del %s" % dest
                patch['delete'].append(dest)
            elif not filecmp.cmp(oldf, newf, False):
                #print "write mod %s" % dest
                oldData = _read_file(oldf)
                before = hashlib.sha1()
                before.update(oldData)

                newData = _read_file(newf)
                after = hashlib.sha1()
                after.update(newData)

                patch['patch'][dest] = (before.digest(), bsdiff4.diff(oldData, newData), after.digest())
        for d in dirnames:
            if not os.path.exists(os.path.join(new, relpath, d)):
                # a name in the delete list with a trailing slash
                # means, "delete this directory and everything in it"
                #print "del dir %s" % d
                patch['delete'].append(d + '/')
                dirnames.remove(d)

    # Now walk new looking for things we have not yet made a
    # patch for. These are adds, so add them, compressed.
    # The output of bsdiff4.diff() above is already bz2-format,
    # so we'd get almost no benefit from bzipping the pickle.
    for (dirpath, dirnames, filenames) in os.walk(new):
        relpath = dirpath.replace(new, '')
        if len(relpath) > 0 and relpath[0] == '/':
            relpath = relpath[1:]
        for f in filenames:
            newf = os.path.join(new, relpath, f)
            dest = os.path.join(relpath, f)
            if dest in patch['patch']:
                continue
            #print "add %s" % dest
            patch['add'][dest] = bz2.compress(_read_file(newf))

    return cPickle.dumps(patch)

# todir is expected to exist, because it should have any base
# files in it that will be needed for patching.
def applyPatch(patchdata, todir, log=_defaultLog):
    unpickler = cPickle.Unpickler(cStringIO.StringIO(patchdata))
    unpickler.find_global = None
    patch = unpickler.load()
    for fn in patch.get('delete', []):
        if fn.endswith('/'):
            fn = fn[0:-1]
            x = os.path.join(todir, fn)
            log("delete tree", x)
            shutil.rmtree(x)
        else:
            x = os.path.join(todir, fn)
            log("delete", x)
            os.remove(x)
    for fn,sumpatch in patch.get('patch', {}).items():
        (sumBefore, filepatch, sumAfter) = sumpatch
        fn = os.path.join(todir, fn)
        origData = _read_file(fn)

        h = hashlib.sha1()
        h.update(origData)
        if h.digest() != sumBefore:
            raise RuntimeError("SHA mismatch for input file %s" % fn)

        outData = bsdiff4.patch(origData, filepatch)

        h = hashlib.sha1()
        h.update(outData)
        if h.digest() != sumAfter:
            raise RuntimeError("SHA mismatch after patching file %s" % fn)

        with open(fn, 'wb') as outf:
            outf.write(outData)
        log('patched', fn)

    for fn,outData in patch.get('add', {}).items():
        fn = os.path.join(todir, fn)
        dirname = os.path.dirname(fn)
        #print "making dir ", dirname
        os.makedirs(dirname)
        outData = bz2.decompress(outData)
        with open(fn, 'wb') as outf:
            outf.write(outData)
        log('added', fn)

if __name__ == '__main__':
    import tempfile, shutil

    d = tempfile.mkdtemp()
    old = os.path.join(d, 'old')
    new = os.path.join(d, 'new')
    work = os.path.join(d, 'work')
    work2 = os.path.join(d, 'work2')

    os.makedirs(os.path.join(old, 'a'))
    with open(os.path.join(old, 'delete'), 'w') as f:
        f.write("to be deleted")
    os.makedirs(os.path.join(old, 'deldir'))
    with open(os.path.join(old, 'deldir', 'delete'), 'w') as f:
        f.write("to be deleted")
    with open(os.path.join(old, 'a', 'change'), 'w') as f:
        f.write('from this')
    # check with binaries too
    with open(os.path.join(old, 'a', 'change2'), 'w') as f:
        f.write("\0\1\2\3")
    #└── old
    #    ├── a
    #    │   └── change
    #    │   └── change2
    #    ├── deldir
    #    │   └── delete
    #    └── delete

    os.makedirs(os.path.join(new, 'a'))
    with open(os.path.join(new, 'a', 'change'), 'w') as f:
        f.write('to this')
    os.makedirs(os.path.join(new, 'a', 'adddir'))
    with open(os.path.join(new, 'a', 'adddir', 'add'), 'w') as f:
        f.write('add this')
    with open(os.path.join(new, 'a', 'change2'), 'w') as f:
        f.write("\0\1\3\2")
    #├── new
    #│   └── a
    #│       ├── adddir
    #│       │   └── add
    #│       └── change
    #│       └── change2

    p = mkPatch(old, new)
    shutil.copytree(old, work)
    shutil.copytree(old, work2)

    # First try a patch that should work
    applyPatch(p, work)
    assert not os.path.exists(os.path.join(work, 'delete'))
    assert not os.path.exists(os.path.join(work, 'deldir'))
    assert os.path.exists(os.path.join(work, 'a', 'change'))
    assert os.path.exists(os.path.join(work, 'a', 'adddir', 'add'))
    assert 'to this' == _read_file(os.path.join(work, 'a', 'change'))
    assert "\0\1\3\2" == _read_file(os.path.join(work, 'a', 'change2'))
    assert 'add this' == _read_file(os.path.join(work, 'a', 'adddir', 'add'))

    # Now corrupt a file in work2 and try applying the patch.
    with open(os.path.join(work2, 'a', 'change'), 'wb') as f:
        f.write("wrong contents")
    try:
        applyPatch(p, work2)
    except RuntimeError as r:
        if not str(r).startswith('SHA mismatch for input file'):
            raise
        else:
            pass

    shutil.rmtree(d)
