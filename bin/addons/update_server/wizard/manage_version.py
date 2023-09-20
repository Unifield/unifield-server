'''
Created on 9 juil. 2012

@author: openerp
'''


from osv import osv
from osv import fields
from datetime import datetime
from dateutil.relativedelta import relativedelta
import hashlib
from base64 import b64decode
import mimetypes

mimetypes.init()

class manage_version(osv.osv):

    _name = "sync_server.version.manager"

    _columns = {
        'name' : fields.char('Revision', size=256),
        'patch' : fields.binary('Patch'),
        'date' : fields.datetime('Date', readonly=True),
        'comment' : fields.text("Comment"),
        'version_ids' : fields.many2many('sync_server.version', 'sync_server_version_rel', 'wiz_id', 'version_id', string="History of Revision", readonly=True, limit=10000),
        'create_date' : fields.datetime("Create Date"),
        'importance' : fields.selection([('required','Required'),('optional','Optional')], "Importance Flag"),
        'state' : fields.selection([('upload','Upload'), ('error', 'Error')], "State"),
        'message' : fields.text("Message"),
    }

    def _get_version(self, cr, uid, context=None):
        return self.pool.get("sync_server.version").search(cr, uid, [], context=context)

    _defaults = {
        'date' : fields.datetime.now,
        'version_ids' : _get_version,
        'state' : 'upload',
    }

    def back(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {
            'state' : 'upload',
            'message' : '',
            'patch' : False,
        }, context=context)

    def add_revision(self, cr, uid, ids, context=None):
        for wiz in self.browse(cr, uid, ids, context=context):
            if not wiz.patch:
                return self.write(cr, uid, ids, {
                    'state' : 'error',
                    'message' : "Missing patch file.",
                }, context=context)
            patch = b64decode(wiz.patch)
            #TODO import zipfile from python 2.7
            #fh_patch = StringIO(patch)
            #if not is_zipfile(fh_patch):
            if not patch[:2] == 'PK':
                return self.write(cr, uid, ids, {
                    'state' : 'error',
                    'message' : "The patch you tried to upload doesn't looks like a ZIP file! Please upload only zip files.",
                }, context=context)

            # Compute the MD5 checksum for this patch
            checksum = hashlib.md5(patch).hexdigest()

            # Look for existing versions with this checksum
            version_pool = self.pool.get("sync_server.version")

            version_with_same_sum = version_pool.search(cr, uid,
                                                        [('sum', '=', checksum)],
                                                        context=context)

            # If no version already exist with this sum, simply create a new
            # one with data from wizard
            if not version_with_same_sum:
                data = {
                    'name':  wiz.name,
                    'sum': checksum,
                    'date': fields.datetime.now(),
                    'comment': wiz.comment,
                    'importance': wiz.importance,
                }
                res_id = version_pool.create(cr, uid, data, context=context)

            # If a version already exists with this checksum, we basically want
            # to only append the patch
            else:

                # Assert that there's only one version already existing with
                # this checksum (otherwise we have bigger issues with the
                # DB because the "unique checksum" constrain has been bypassed)
                assert len(version_with_same_sum) == 1

                # Get the existing version with same checksum
                res_id = version_with_same_sum[0]
                existing_version = version_pool.browse(cr, uid,
                                                       [res_id],
                                                       context=context)[0]

                # Don't allow to override patches : possible security hazard ?
                # Someone with admin access could craft a malicious patch with
                # same MD5 sum and replace the existing patch...
                if existing_version.patch:
                    return self.write(cr, uid, ids, {
                        'state': 'error',
                        'message': "A version already exists with same checksum and a non-empty patch. You cannot (and probably don't need to) override it.",
                    }, context=context)

                data = {
                    'name': wiz.name,
                    'date': fields.datetime.now(),
                    'comment': wiz.comment,
                    'importance': wiz.importance,
                }

                version_pool.write(cr, uid, [res_id], data, context=context)

            patch_file = version_pool._get_patch_path(cr, uid, res_id)
            f = open(patch_file, 'wb')
            f.write(patch)
            f.close()


            self.write(cr, uid, [wiz.id], {'version_ids' : [(4, res_id)],
                                           'name' : False,
                                           'patch' : False,
                                           'importance' : False,
                                           'date' : fields.datetime.now(),
                                           'comment' : False},
                       context=context)
        return True


    def vacuum(self, cr, uid):
        now = (datetime.now() + relativedelta(hours=-1)).strftime("%Y-%m-%d %H:%M:%S")
        unlink_ids = self.search(cr, uid, [('create_date', '<', now)])
        if unlink_ids:
            self.unlink(cr, uid, unlink_ids)
        return True


manage_version()

