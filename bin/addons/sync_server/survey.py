from osv import osv
from osv import fields
import time
import requests
import tools
from tools.translate import _


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


    def _one_included_if_active(self, cr, uid, ids, context=None):
        active_ids = self.search(cr, uid, [('id', 'in', ids), ('activated', '=', True)], context=context)
        if active_ids:
            for survey in self.browse(cr, uid, active_ids, fields_to_fetch=['included_group_ids'], context=context):
                if not survey.included_group_ids:
                    return False
        return True

    _constraints = [
        (_one_included_if_active, 'Please set at least one Included Group', [])
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
        for x in self.read(cr, uid, ids, ['url_en', 'url_fr', 'included_group_ids'], context=context):
            if not x['included_group_ids']:
                raise osv.except_osv(_('Error'), _('Please set at least one Included Group'))

            for url in ['url_en', 'url_fr']:
                try:
                    r = requests.get(x[url])
                    if r.status_code != 200:
                        raise osv.except_osv(_('Error'), _('Unable to get %s, status code: %s') % (url, r.status_code))
                except requests.RequestException as e:
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

