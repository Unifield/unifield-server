'''
Created on 9 juil. 2012

@author: openerp
'''


from osv import osv
from osv import fields
from tools.translate import _
import sync_server
from updater import base_version, server_version

import logging
import time

from zipfile import ZipFile
from zipfile import is_zipfile
from base64 import decodestring, encodestring
from cStringIO import StringIO
import hashlib
import csv


class version(osv.osv):

    _name = "sync_server.version"

    _columns = {
        'name' : fields.char(string='Revision', size=256, readonly=True),
        'patch' : fields.binary('Patch', readonly=True),
        'sum' : fields.char(string="Check Sum", size=256, readonly=True),
        'date' : fields.datetime(string="Revision Date", readonly=True),
        'comment' : fields.text("Comment", readonly=True),
        'importance' : fields.selection([('required','Required'),('optional','Optional')], "Importance Flag", readonly=True),
        'state' : fields.selection([('draft','Draft'),('confirmed','Confirmed')], string="State", readonly=True),
    }

    _defaults = {
        'state' : 'draft',
    }

    _sql_constraints = [('unique_sum', 'unique(sum)', 'Patches must be unique!')]

    _logger = logging.getLogger('update_server')

    def init(self, cr):
        try:
            now = fields.datetime.now()
            current_versions = self.read(cr, 1, self.search(cr, 1, []), ['id','sum','state'])
            versions_id = dict([(x['sum'], x['id']) for x in current_versions])
            current_versions.append( {'sum':base_version,'state':'confirmed'} )
            # Create non-existing versions in db
            server_version_keys = [x['md5sum'] for x in server_version]
            for rev in set(server_version_keys) - set([x['sum'] for x in current_versions]):
                versions_id[rev] = self.create(cr, 1, {'sum':rev, 'state':'confirmed', 'date':now})
            # Update existing ones
            self.write(cr, 1, [x['id'] for x in current_versions \
                               if x['sum'] in server_version_keys and not x['state'] == 'confirmed'], \
                       {'state':'confirmed','date':now})
            # Set last revision (assure last update has the last applied date)
            time.sleep(1)
            if len(server_version_keys) > 1:
                self.write(cr, 1, [versions_id[server_version_keys[-1]]], {'date':fields.datetime.now()})
        except BaseException:
            self._logger.exception("version init failure!")

    def _get_last_revision(self, cr, uid, context=None):
        rev_ids = self.search(cr, uid, [('state','=','confirmed')], limit=1, context=context)
        return rev_ids[0] if rev_ids else False

    def _get_next_revisions(self, cr, uid, current, context=None):
        if current:
            active = self.browse(cr, uid, current)
            revisions = self.search(cr, uid, [('date','>',active.date),('state','=','confirmed')], order='date asc')
        else:
            revisions = self.search(cr, uid, [('state','=','confirmed')], order='date asc')
        return revisions

    def _compare_with_last_rev(self, cr, uid, entity, rev_sum, context=None):
        # Search the client's revision when exists
        if rev_sum and rev_sum != base_version:
            rev_client = self.search(cr, uid, [('sum', '=', rev_sum), ('state', '=', 'confirmed')], limit=1, context=context)
            if not rev_client:
                return {'status' : 'failed',
                        'message' : 'Cannot find revision %s on the server' % (rev_sum)}
            rev_client = rev_client[0]
            # Save client revision in our database
            self.pool.get("sync.server.entity")._set_version(cr, uid, entity.id, rev_client, context=context)

        # Otherwise, get the whole
        else:
            rev_client = None

        revisions = self._get_next_revisions(cr, uid, rev_client)

        if not revisions:
            return {'status' : 'ok',
                    'message' : "Last revision"}

        revisions = self.read(cr, uid, revisions, ('name','sum','date','importance','comment'), context=context)
        status = 'update'
        for rev in revisions:
            rev.pop('id')
            if rev['importance'] == 'required':
                status = 'failed'

        message = _("There is/are %d revision(s) available.") % len(revisions)

        return {'status' : status,
                'message' : message,
                'revisions' : revisions}

    def _get_zip(self, cr, uid, sum, context=None):
        ids = self.search(cr, uid, [('sum','=',sum)], context=context)
        if not ids:
            return (False, "Cannot find sum %s!" % sum)
        rec = self.browse(cr, uid, ids, context=context)[0]
        if rec.state != 'confirmed':
            return (False, "The revision %s is not enabled!" % sum)
        return (True, rec.patch)

    def delete_revision(self, cr, uid, ids, context=None):
        return self.unlink(cr, uid, ids, context=context)

    def activate_revision(self, cr, uid, ids, context=None):
        return self.write(cr, uid, ids, {'state':'confirmed'}, context)

    _order = 'date desc'

version()



class entity(osv.osv):
    """ OpenERP entity name and unique identifier """
    _inherit = "sync.server.entity"

    _columns = {
        'version_id': fields.many2one('sync_server.version', 'Unifield Version', ondelete='set null', ),
    }

    def _set_version(self, cr, uid, ids, version_id, context=None):
        if version_id:
            return self.write(cr, uid, ids, {'version_id' : version_id}, context=context)
        else:
            return True

entity()



class sync_manager(osv.osv):
    _inherit = "sync.server.sync_manager"
    _logger = logging.getLogger('sync.server')

    @sync_server.sync_server.check_validated
    def get_next_revisions(self, cr, uid, entity, rev_sum, context=None):
        return (True, self.pool.get('sync_server.version')._compare_with_last_rev(cr, 1, entity, rev_sum))

    @sync_server.sync_server.check_validated
    def get_zip(self, cr, uid, entity, revision, context=None):
        return self.pool.get('sync_server.version')._get_zip(cr, 1, revision)

sync_manager()


class sync_server_user_rights(osv.osv):

    _name = 'sync_server.user_rights'
    _order = 'id desc'

    _columns = {
        'name' : fields.char(string='Version', size=256, readonly=True),
        'zip_file' : fields.binary('File', readonly=True),
        'sum' : fields.char(string="Check Sum", size=256, readonly=True),
        'date' : fields.datetime(string="Revision Date", readonly=True),
        'state' : fields.selection([('draft','Draft'),('confirmed','Confirmed'),('deprecated', 'Deprecated')], string="State", readonly=True),
    }

    _defaults = {
        'state' : 'draft',
    }

    _sql_constraints = [
        ('unique_sum', 'unique(sum)', 'File must be unique!'),
        ('unique_name', 'unique(name)', 'Name must be unique!'),
    ]
    # TODO: python constraint 1 active, confirmed status
    def unzip_file(self, cr, uid, zfile, raise_error=False, context=None):
        ur = {
            'UAC': False,
            'msf_button_access_rights.button_access_rule': [],
            'ir.model.access': False,
            'msf_field_access_rights.field_access_rule': False,
            'msf_field_access_rights.field_access_rule_line': False,
            'ir.rule': False,
            'ir.actions.act_window': False,
        }

        expected_files = 9
        z = ZipFile(zfile)
        nb = 0
        for f in z.infolist():
            if f.filename.endswith('/'):
                continue
            nb += 1
            if 'bar' in f.filename.lower():
                ur['msf_button_access_rights.button_access_rule'].append(f.filename)
            elif 'acl' in f.filename.lower():
                ur['ir.model.access'] = f.filename
            elif 'record rules' in f.filename.lower():
                ur['ir.rule'] = f.filename
            elif 'windows' in f.filename.lower():
                ur['ir.actions.act_window'] = f.filename
            elif f.filename.lower().endswith('xml'):
                ur['UAC'] = f.filename
            elif 'rule lines' in f.filename.lower():
                ur['msf_field_access_rights.field_access_rule_line'] = f.filename
            elif 'field access' in f.filename.lower():
                ur['msf_field_access_rights.field_access_rule'] = f.filename
            elif raise_error:
                raise osv.except_osv(_('Warning !'), _('Extra file "%s" found in zip !') % (f.filename))

        if raise_error:
            if nb != expected_files:
                raise osv.except_osv(_('Warning !'), _("%s files found, %s expected.") % (nb, expected_files))

        z.close()

        return ur

    def get_active_user_rights(self, cr, uid, context=None):
        return self.search(cr, uid, [('state', '=', 'confirmed')], context=context)

    def get_last_user_rights_info(self, cr, uid, context=None):
        ids = self.search(cr, uid, [('state', '=', 'confirmed')], context=context)
        if not ids:
            return {'name': False, 'sum': False}
        data = self.read(cr, uid, ids[0], ['name', 'sum'], context=context)
        return {'name': data['name'], 'sum': data['sum']}

    def activate(self, cr, uid, ids, context=None):
        rec = self.read(cr, uid, ids[0], ['zip_file'])
        plain_zip = decodestring(rec['zip_file'])
        zp = StringIO(plain_zip)

        ur = self.unzip_file(cr, uid, zp, context=context)
        z = ZipFile(zp)

        try:
            cr.commit_org, cr.commit = cr.commit, lambda:None

            uac_processor = self.pool.get('user.access.configurator')
            f = z.open(ur['UAC'])
            data = encodestring(f.read())
            f.close()
            wiz_id = uac_processor.create(cr, uid, {'file_to_import_uac': data})
            uac_processor.do_process_uac(cr, uid, [wiz_id])
            # TODO: check error
            for model in ['msf_button_access_rights.button_access_rule', 'ir.model.access', 'ir.rule', 'ir.actions.act_window', 'msf_field_access_rights.field_access_rule', 'msf_field_access_rights.field_access_rule_line']:
                zip_to_import = ur[model]
                if not isinstance(zip_to_import, list):
                    zip_to_import = [zip_to_import]

                for zp_f in zip_to_import:
                    with z.open(zp_f, 'r') as csvfile:
                        reader = csv.reader(csvfile, delimiter=',')
                        fields = False
                        data = []
                        for row in reader:
                            if not fields:
                                fields = row
                            else:
                                data.append(row)
                        ret = self.pool.get(model).import_data(cr, uid, fields, data, display_all_errors=False, has_header=True)
                        if ret and ret[0] == -1:
                            raise osv.except_osv(_('Warning !'), _("Import %s failed\n Data: %s\n%s" % (zp_f,ret[1], ret[2])))
        finally:
            cr.rollback()
            cr.commit = cr.commit_org
        z.close()
        current_active = self.get_active_user_rights(cr, uid, context=context)
        self.write(cr, uid, current_active, {'state': 'deprecated'}, context=context)
        self.write(cr, uid, ids[0], {'state': 'confirmed', 'date': time.strftime('%Y-%m-%d %H:%M:%S')}, context=context)
        return True


    def download_file(self, cr, uid, ids, context=None):
        name = self.read(cr, uid, ids[0], ['name'], context=context)['name']
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'sync_server.user_rights.download',
            'datas': {'ids': [ids[0]], 'target_filename': name}
        }

    def get_md5_zip(self, cr, uid, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        return self.read(cr, uid, ids[0], ['zip_file'], context=context)['zip_file']

    def get_plain_zip(self, cr, uid, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        zip_content = self.read(cr, uid, ids[0], ['zip_file'], context=context)['zip_file']
        return decodestring(zip_content)

sync_server_user_rights()

class sync_server_user_rights_add_file(osv.osv_memory):
    _name = 'sync_server.user_rights.add_file'

    _columns = {
        'name': fields.char(string='Version', size=256, required=1),
        'zip_file': fields.binary('File', required=1),
    }

    def import_zip(self, cr, uid, ids, context=None):
        wiz = self.browse(cr, uid, ids[0], context=context)
        plain_zip = decodestring(wiz.zip_file)
        zp = StringIO(plain_zip)
        if not is_zipfile(zp):
            raise osv.except_osv(_('Warning !'), _("The file is not a zip file !"))


        ur_meaning = {
            'UAC': 'User Access from file',
            'msf_button_access_rights.button_access_rule': 'Button Access Rules',
            'ir.model.access': 'Access Control List',
            'msf_field_access_rights.field_access_rule': 'Field Access Rules',
            'msf_field_access_rights.field_access_rule_line': 'Field Access Rule Lines',
            'ir.rule': 'Record Rules',
            'ir.actions.act_window': 'Actions Windows',
        }

        ur_obj = self.pool.get('sync_server.user_rights')

        ur = ur_obj.unzip_file(cr, uid, zp, True, context=context)
        if len(ur['msf_button_access_rights.button_access_rule']) != 3:
            raise osv.except_osv(_('Warning !'), _("Found %d BAR files, expected 3.") % (len(ur['msf_button_access_rights.button_access_rule'])))
        for x in ur:
            if not ur[x]:
                raise osv.except_osv(_('Warning !'), _("File %s not found!") % (ur_meaning[x]))

        self.pool.get('sync_server.user_rights').create(cr, uid, {'name': wiz.name, 'sum': hashlib.md5(plain_zip).hexdigest(), 'zip_file': wiz.zip_file}, context=context)
        return {'type': 'ir.actions.act_window_close'}

sync_server_user_rights_add_file()
