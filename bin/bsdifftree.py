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


import bsdiff4
import pickle
import io
import bz2
import os
import shutil
import filecmp
import hashlib

def _defaultLog(*args):
    print(args)

def _read_file(fn):
    with open(fn, 'rb') as f:
        data = f.read()
    return data

# mkpatch computes the binary patch necessary to change the
# directory old into new. Using the output of mkpatch
# with applyPatch(old, "a-new-dir") should result in "a-new-dir"
# containing precisely the same files as "new" does.
def mkPatch(old, new, log=_defaultLog):
    patch = {
        # All filenames are relative to old.
        # Deletions: A list of files to delete
        'delete': [],
        # Additions: key = filename -> value = data of files
        'add': {},
        # Patches: key = filename -> value = tuple of:
        #   (old-file-SHA1, patch, new-file-SHA1)
        # The SHA before is to make sure that we are applying the patch
        # to the correct base file. The SHA after is to be sure that bsdiff4
        # did his job correctly.
        'patch': {},
    }
    seen = {}

    # walk old, looking for things that were deleted in new,
    # or that will be patched.
    for (dirpath, dirnames, filenames) in os.walk(old):
        relpath = dirpath.replace(old, '')
        if len(relpath) > 0 and relpath[0] == os.path.sep:
            relpath = relpath[1:]
        for f in filenames:
            oldf = os.path.join(dirpath, f)
            newf = os.path.join(new, relpath, f)
            dest = os.path.join(relpath, f)
            seen[dest] = True
            if not os.path.exists(newf):
                log("del %s" % dest)
                patch['delete'].append(dest)
            elif not filecmp.cmp(oldf, newf, False):
                oldData = _read_file(oldf)
                before = hashlib.sha1()
                before.update(oldData)

                newData = _read_file(newf)
                after = hashlib.sha1()
                after.update(newData)
                thePatch = bsdiff4.diff(oldData, newData)
                log("write mod %s (len=%d)" % (dest, len(thePatch)))
                patch['patch'][dest] = (before.digest(), thePatch, after.digest())
        for d in dirnames:
            dest = os.path.join(relpath, d)
            if not os.path.exists(os.path.join(new, relpath, d)):
                # a name in the delete list with a trailing slash
                # means, "delete this directory and everything in it"
                log("del dir %s" % dest)
                patch['delete'].append(dest + '/')
                dirnames.remove(d)

    # Now walk new looking for things we have not yet made a
    # patch for.
    for (dirpath, dirnames, filenames) in os.walk(new):
        relpath = dirpath.replace(new, '')
        if len(relpath) > 0 and relpath[0] == os.path.sep:
            relpath = relpath[1:]
        for f in filenames:
            newf = os.path.join(new, relpath, f)
            dest = os.path.join(relpath, f)
            if dest in seen:
                continue
            log("add %s" % dest)
            patch['add'][dest] = _read_file(newf)

    return bz2.compress(pickle.dumps(patch))

# todir is expected to exist, because it should have any base
# files in it that will be needed for patching.
# Note: files that exist in todir, but which are not mentioned
# in the patch will continue existing after the patch is applied.
# TODO: Figure out if this is dangerous, fix it?
def applyPatch(patchdata, todir, doIt=True, log=_defaultLog):
    patchdata = bz2.decompress(patchdata)
    unpickler = pickle.Unpickler(io.BytesIO(patchdata))
    #unpickler.find_global = None
    patch = unpickler.load()
    for fn in patch.get('delete', []):
        if fn.endswith('/'):
            fn = fn[0:-1]
            x = os.path.join(todir, fn)
            log("delete tree", x)
            if doIt:
                shutil.rmtree(x)
        else:
            x = os.path.join(todir, fn)
            log("delete", x)
            if doIt:
                os.remove(x)
    for fn,sumpatch in list(patch.get('patch', {}).items()):
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

        if doIt:
            with open(fn, 'wb') as outf:
                outf.write(outData)
        log('patched', fn)

    for fn,outData in list(patch.get('add', {}).items()):
        fn = os.path.join(todir, fn)
        dirname = os.path.dirname(fn)
        if doIt:
            if not os.path.exists(dirname):
                os.makedirs(dirname)
            with open(fn, 'wb') as outf:
                outf.write(outData)
        log('added', fn)

if __name__ == '__main__':
    import sys, tempfile

    # To make a patch run this script with mkpatch as an argument.
    if len(sys.argv) >= 2 and sys.argv[1] == 'mkpatch':
        if len(sys.argv) != 5:
            print('Expected args: mkpatch <from> <to> <patch>')
            sys.exit(1)
        with open(sys.argv[4], 'wb') as f:
            f.write(mkPatch(sys.argv[2], sys.argv[3]))
        print("Patch saved into:", sys.argv[4])
        sys.exit(0)

    # Otherwise run the unit tests.

    d = tempfile.mkdtemp()
    old = os.path.join(d, 'old')
    new = os.path.join(d, 'new')
    work = os.path.join(d, 'work')
    work2 = os.path.join(d, 'work2')

    os.makedirs(os.path.join(old, 'a'))
    with open(os.path.join(old, 'delete'), 'w') as f:
        f.write("to be deleted")
    os.makedirs(os.path.join(old, 'a', 'deldir'))
    with open(os.path.join(old, 'a', 'deldir', 'delete'), 'w') as f:
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
    print("test ok")
