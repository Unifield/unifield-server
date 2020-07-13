'''
Created on 9 juil. 2012

@author: openerp
'''


from osv import osv
from osv import fields
from tools.translate import _
import sync_server
from updater import base_version, server_version
import pooler

import logging
import time
import tools
from zipfile import is_zipfile
from base64 import decodestring
from cStringIO import StringIO
import hashlib
import threading
import requests

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
        disabled_obj = self.pool.get('sync.server.disabled')
        if disabled_obj and not disabled_obj.is_sync_active(cr, 1, context):
            data = disabled_obj.get_data(cr, 1, context)
            return (False, 'The Sync Server is down for maintenance. Sync is disabled until %s Geneva time.' % data['to_date'])
        return (True, self.pool.get('sync_server.version')._compare_with_last_rev(cr, 1, entity, rev_sum))

    @sync_server.sync_server.check_validated
    def get_zip(self, cr, uid, entity, revision, context=None):
        self._logger.info("::::::::[%s] download patch" % (entity.name, ))
        return self.pool.get('sync_server.version')._get_zip(cr, 1, revision)

sync_manager()


class sync_server_user_rights(osv.osv):

    _name = 'sync_server.user_rights'
    _order = 'id desc'

    _columns = {
        'name' : fields.char(string='Version', size=256),
        'zip_file' : fields.binary('File', readonly=True),
        'sum' : fields.char(string="Check Sum", size=256, readonly=True, select=1),
        'date' : fields.datetime(string="Revision Date", readonly=True),
        'state' : fields.selection([('draft','Draft'),('confirmed','Confirmed'),('deprecated', 'Deprecated')], string="State", readonly=True, select=1),
    }

    _defaults = {
        'state' : 'draft',
    }

    _sql_constraints = [
        ('unique_sum', 'unique(sum)', 'File must be unique!'),
        ('unique_name', 'unique(name)', 'Name must be unique!'),
    ]

    def _check_unicity(self, cr, uid, ids, context=None):
        ids = self.search(cr, uid, [('state', '=', 'confirmed')])
        if len(ids) > 1:
            return False
        return True

    _constraints = [
        (_check_unicity, 'You can activate only 1 UR file!', []),
    ]
    def get_active_user_rights(self, cr, uid, context=None):
        return self.search(cr, uid, [('state', '=', 'confirmed')], context=context)

    def get_last_user_rights_info(self, cr, uid, context=None):
        ids = self.search(cr, uid, [('state', '=', 'confirmed')], context=context)
        if not ids:
            return {'name': False, 'sum': False}
        data = self.read(cr, uid, ids[0], ['name', 'sum'], context=context)
        return {'name': data['name'], 'sum': data['sum']}

    def activate(self, cr, uid, ids, context=None):
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

class logger(object):
    def __init__(self, obj):
        self.message = []
        self.obj = obj

    def append(self, msg):
        self.message.append(msg)

    def write(self):
        self.obj.write({'message': "\n".join(self.message)})

class sync_server_user_rights_add_file(osv.osv_memory):
    _name = 'sync_server.user_rights.add_file'

    _columns = {
        'name': fields.char(string='Version', size=256, required=1),
        'zip_file': fields.binary('File', required=1),
        'state': fields.selection([('draft', 'Draft'), ('inprogress', 'In-progress'), ('error', 'Error'), ('done', 'Done')],'State', readonly=1),
        'message': fields.text('Message', readonly=1),
    }

    _defaults = {
        'state': 'draft',
    }
    def load_bg(self, dbname, uid, wiz_id, plain_zip, context=None):
        cr = pooler.get_db(dbname).cursor()
        try:
            cr.commit_org, cr.commit = cr.commit, lambda:None
            wiz = self.browse(cr, uid, wiz_id, context=context)
            self.pool.get('user_rights.tools').load_ur_zip(cr, uid, plain_zip, sync_server=True, logger=logger(wiz), context=context)
            wiz.write({'state': 'done', 'message': 'Import Done'})
        except Exception, e:
            cr.rollback()
            if isinstance(e, osv.except_osv):
                error = e.value
            else:
                error = e
            msg = self.read(cr, uid, wiz_id, ['message'])['message'] or ''
            wiz.write({'state': 'error', 'message': "%s\n%s" % (msg, tools.ustr(error))})
        finally:
            cr.rollback()
            cr.commit = cr.commit_org
            cr.close(True)

    def dummy(self, *a, **b):
        return True

    def done(self, cr, uid, ids, context=None):
        wiz = self.browse(cr, uid, ids[0], context=context)
        plain_zip = decodestring(wiz.zip_file)

        ur_obj = self.pool.get('sync_server.user_rights')
        new_ur_id = ur_obj.create(cr, uid, {'name': wiz.name, 'sum': hashlib.md5(plain_zip).hexdigest(), 'zip_file': wiz.zip_file}, context=context)
        ur_obj.activate(cr, uid, [new_ur_id], context=context)
        return {'type': 'ir.actions.act_window_close'}

    def import_zip(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        expected_bar = 1
        wiz = self.browse(cr, uid, ids[0], context=context)
        plain_zip = decodestring(wiz.zip_file)
        zp = StringIO(plain_zip)
        if not is_zipfile(zp):
            raise osv.except_osv(_('Warning !'), _("The file is not a zip file !"))


        md5 = hashlib.md5(plain_zip).hexdigest()
        if self.pool.get('sync_server.user_rights').search_exist(cr, uid, [('sum', '=', md5)]):
            raise osv.except_osv(_('Warning !'), _("Sum %s exists on server") % (md5,))

        if self.pool.get('sync_server.user_rights').search_exist(cr, uid, [('name', '=', wiz.name)]):
            raise osv.except_osv(_('Warning !'), _("Version %s exists on server") % (wiz.name,))

        ur_meaning = {
            'UAC': 'User Access from file',
            'msf_button_access_rights.button_access_rule': 'Button Access Rules',
            'ir.model.access': 'Access Control List',
            'msf_field_access_rights.field_access_rule': 'Field Access Rules',
            'msf_field_access_rights.field_access_rule_line': 'Field Access Rule Lines',
            'ir.rule': 'Record Rules',
            'ir.actions.act_window': 'Actions Windows',
        }


        ur = self.pool.get('user_rights.tools').unzip_file(cr, uid, zp, True, context=context)

        if len(ur['msf_button_access_rights.button_access_rule']) != expected_bar:
            raise osv.except_osv(_('Warning !'), _("Found %d BAR files, expected %s.") % (len(ur['msf_button_access_rights.button_access_rule'], expected_bar)))
        for x in ur:
            if not ur[x]:
                raise osv.except_osv(_('Warning !'), _("File %s not found!") % (ur_meaning[x]))
        if context.get('run_foreground'):
            self.load_bg(cr.dbname, uid, wiz.id, plain_zip, context)
        else:
            threading.Thread(target=self.load_bg, args=(cr.dbname, uid, wiz.id, plain_zip, context)).start()
            self.write(cr, uid, ids[0], {'state': 'inprogress', 'message': 'Import in progess'}, context=context)
        return True

sync_server_user_rights_add_file()

class res_groups_instances(osv.osv):
    _name = 'res.groups.instances'
    _description = 'Instances Groups'
    _order = 'name'
    _columns = {
        'name': fields.char('Name', size=256),
    }

    def search(self, cr, uid, args, offset=0, limit=None, order=None, context=None, count=False):
        if context and context.get('hide'):
            if isinstance(context['hide'], list) and isinstance(context['hide'][0], tuple) and len(context['hide'][0]) == 3 and context['hide'][0][2]:
                args.append(('id', 'not in', context['hide'][0][2]))
        return super(res_groups_instances, self).search(cr, uid, args, offset=offset, limit=limit, order=order, context=context, count=count)

res_groups_instances()

class sync_server_survey(osv.osv):
    _inherit = 'survey.common'
    _name = 'sync_server.survey'
    _description = 'Survey'
    _order = 'start_date desc'
    _auto = True

    def _get_group(self, cr, uid, ids, name, args, context=None):
        ret = {}
        for survey in self.browse(cr, uid, ids, fields_to_fetch=['included_group_ids', 'excluded_group_ids'], context=context):
            ret[survey.id] = {
                'included_group_txt': ','.join([x.name for x in survey.included_group_ids]),
                'excluded_group_txt': ','.join([x.name for x in survey.excluded_group_ids]),
            }
        return ret

    _columns = {
        'included_group_ids': fields.many2many('res.groups.instances', 'server_survey_group_included_rel', 'survey_id', 'group_id', 'Included Groups'),
        'excluded_group_ids': fields.many2many('res.groups.instances', 'server_survey_group_excluded_rel', 'survey_id', 'group_id', 'Excluded Groups'),
        'activated': fields.boolean('Synced'),
        'included_group_txt': fields.function(_get_group, method=True, string='Text List included', type='char', multi='_group'),
        'excluded_group_txt': fields.function(_get_group, method=True, string='Text List excluded', type='char', multi='_group'),
    }

    _defaults = {
        'activated': False,
    }
    _sql_constraints = [
        ('check_dates', 'check (start_date < end_date)', 'Date Start must be before Date End')
    ]

    def write(self, cr, uid, ids, vals, context=None):
        vals['server_write_date'] = time.strftime('%Y-%m-%d %H:%M:%S')
        return super(sync_server_survey, self).write(cr, uid, ids, vals, context=context)

    def copy(self, cr, uid, id, default=None, context=None):
        if default is None:
            default = {}

        if 'activated' not in default:
            default['activated'] = False

        return super(sync_server_survey, self).copy(cr, uid, id, default, context)

    def activate(self, cr, uid, ids, context=None):
        for x in self.read(cr, uid, ids, ['url_en', 'url_fr'], context=context):
            for url in ['url_en', 'url_fr']:
                try:
                    r = requests.get(x[url])
                    if r.status_code != 200:
                        raise osv.except_osv(_('Error'), _('Unable to get %s, status code: %s') % (url, r.status_code))
                except requests.RequestException, e:
                    raise osv.except_osv(_('Error'), _('Unable to get %s, error: %s') % (url, tools.ustr(e)))
        self.write(cr, uid, ids, {'activated': True}, context=context)
        return True

    def deactivate(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'activated': False}, context=context)
        return True

    def unlink(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'active': False}, context=context)
        return True

sync_server_survey()
