# -*- encoding: utf-8 -*-

from osv import osv, fields
from tools.translate import _
import tools

class finance_sync_query(osv.osv):
    _name = 'finance.sync.query'
    _description = 'Finance Queries'
    _order = 'model, name, id'
    _auto = False

    _map_mcdb_model = {
        'account.mcdb.move': 'account.move.line',
        'account.mcdb.analytic': 'account.analytic.line',
        'account.mcdb.combined': 'combined.line',
    }

    def init(self, cr):
        tools.drop_view_if_exists(cr, 'finance_sync_query')
        CASE_QUERY = ' '.join(["WHEN model='%s' THEN '%s'" % (y,x) for x,y in self._map_mcdb_model.iteritems()])

        cr.execute("""CREATE OR REPLACE VIEW finance_sync_query AS (
        SELECT 2*id as id,
            name as name,
            wizard_name as model,
            id as template_id,
            create_date as creation_date,
            coalesce(last_modification, write_date, create_date) as last_modification,
            coalesce(hq_template,'f') as synced,
            coalesce(write_uid, create_uid) as last_editor,
            user_id as user_id
        FROM wizard_template
        WHERE coalesce(name, '') != ''

        UNION

        SELECT 2*id + 1 as id,
            description as name,
            CASE %s END as model,
            id as template_id,
            create_date as creation_date,
            coalesce(write_date, create_date) as last_modification,
            coalesce(hq_template, 'f') as synced,
            coalesce(write_uid, create_uid) as last_editor,
            "user" as user_id
        FROM account_mcdb
        WHERE coalesce(description,'') != ''
        )
        """ % (CASE_QUERY,)) # not_a_user_entry

    _columns = {
        'name': fields.char(size=128, string='Name', required=True),
        'model': fields.selection([
            ('account.mcdb.move', 'G/L Selector'),
            ('account.mcdb.analytic', 'Analytic Selector'),
            ('account.mcdb.combined', 'Combined Journals Report'),
            ('account.report.general.ledger', 'General Ledger'),
            ('account.balance.report', 'Trial Balance'),
            ('account.bs.report', 'Balance Sheet'),
            ('account.chart', 'Balance by account'),
            ('account.analytic.chart', 'Balance by analytic account'),
            ('account.partner.ledger', 'Partner Ledger'),
            ('wizard.account.partner.balance.tree', 'Partner Balance'),
        ], string='Type', size=128, readonly=1, required=1),
        'template_id': fields.integer('Template id', readonly=1),
        'last_modification': fields.datetime('Last Modification', readonly=1),
        'creation_date': fields.datetime('Creation Date', readonly=1),
        'synced': fields.boolean('Synced query', readonly=1),
        'user_id': fields.many2one('res.users', 'User', readonly=1),
        'last_editor': fields.many2one('res.users', 'Last Editor', readonly=1),
    }

    def create(self, cr, uid, values, context=None):
        if values['model'].startswith('account.mcdb'):
            template_id = self.pool.get('account.mcdb').create(cr, uid, {'description': values['name'], 'model': self._map_mcdb_model.get(values['model'])}, context=context)
        else:
            template_id = self.pool.get('wizard.template').create(cr, uid, {'name': values['name'], 'wizard_name': values['model'], 'values': '{}'}, context=context)

        return self.search(cr, uid, [('template_id', '=', template_id), ('model', '=', values['model'])], context=context)[0]

    def write(self, cr, uid, ids, values, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        if values.get('name'):
            for x in self.read(cr, uid, ids, ['template_id', 'model'], context=context):
                if x['template_id']:
                    if x['model'].startswith('account.mcdb'):
                        self.pool.get('account.mcdb').write(cr, uid, x['template_id'], {'description': values['name']}, context=context)
                    else:
                        self.pool.get('wizard.template').write(cr, uid, x['template_id'], {'name': values['name']}, context=context)
        return True


    def _get_target_obj(self, cr, uid, data):
        if data['model'].startswith('account.mcdb'):
            return self.pool.get('account.mcdb')
        return self.pool.get('wizard.template')


    def unlink(self, cr, uid, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        for x in self.read(cr, uid, ids, ['template_id', 'model'], context=context):
            if x['template_id']:
                model = self._get_target_obj(cr, uid, x)
                model.unlink(cr, uid, x['template_id'])
        return True

    def _set_sync_status(self, cr, uid, ids, status, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        for x in self.read(cr, uid, ids, ['template_id', 'model'], context=context):
            if x['template_id']:
                model =self._get_target_obj(cr, uid, x)
                to_write = {'hq_template': status}
                if status:
                    to_write['synced'] = True
                model.write(cr, uid, x['template_id'], to_write, context=context)
        return True

    def deactivate_sync(self, cr, uid, ids, context=None):
        return self._set_sync_status(cr, uid, ids, False, context=context)

    def activate_sync(self, cr, uid, ids, context=None):
        return self._set_sync_status(cr, uid, ids, True, context=context)

    def _get_window_from_menu(self, cr, uid, xmlid, context=None):
        module, xmlid = xmlid.split('.', 1)
        menu_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, module, xmlid)
        action = self.pool.get('ir.ui.menu').read(cr, uid, menu_id, ['action'], context=context)['action']
        model, res_id = action.split(',')
        return self.pool.get(model).read(cr, uid, [res_id],
                                         ['type', 'res_model', 'view_id', 'search_view_id', 'view_mode', 'view_ids', 'name', 'views', 'view_type'],
                                         context=context)[0]

    def open_template(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        query = self.read(cr, uid, ids[0], context=context)
        context['from_query'] = ids[0]
        template_id = query['template_id']

        if query['model'].startswith('account.mcdb'):
            # Selector
            child_wiz = self.pool.get('account.mcdb')
            view_name = {
                'account.mcdb.move': _('G/L Selector'),
                'account.mcdb.analytic': _('Analytic Selector'),
                'account.mcdb.combined': _('Combined Journals Report'),
            }
            context['from'] = self._map_mcdb_model.get(query['model'], '')

            new_id = child_wiz.create(cr, uid, {'template': template_id}, context=context)
            ret = child_wiz.load_mcdb_template(cr, uid, [new_id], context=context)
            # view_mode: to hide sidebar on button 'Add all Instances'
            ret.update({'context': context, 'target': 'new', 'view_mode': 'form'})
            ret['name'] = '%s "%s": %s' % (_('Template'), query['name'], view_name.get(query['model']))
            return ret

        # Report
        default_menu = {
            'account.report.general.ledger': 'account.menu_general_ledger',
            'account.balance.report': 'account.menu_general_Balance_report',
            'account.bs.report': 'account.menu_account_bs_report',
            'account.chart': 'account.menu_action_account_tree2',
            'account.analytic.chart': 'account.menu_action_analytic_account_tree2',
            'account.partner.ledger': 'account.menu_account_partner_ledger',
            'wizard.account.partner.balance.tree': 'finance.menu_account_partner_balance_tree',
        }

        child_wiz = self.pool.get(query['model'])
        wizard = child_wiz.create(cr, uid, {'saved_templates': template_id}, context=context)
        context['active_model'] = 'ir.ui.menu'
        context['active_id'] = self.pool.get('ir.model.data').get_object_reference(cr, uid, default_menu[query['model']].split('.')[0], default_menu[query['model']].split('.')[1])[1]
        ret = self.pool.get('wizard.template').load_template(cr, uid, [wizard], query['model'], context=context)
        ret['name'] = '%s "%s": %s' % (_('Template'), query['name'], ret.get('name', ''))
        return ret

finance_sync_query()

class finance_sync_query_activation_wizard(osv.osv_memory):
    _name = 'finance.sync.query.activation_wizard'
    _description = 'Wizard to mass (de)activate queries'

    _columns = {
        'state': fields.selection([('activate', 'Activate'), ('deactivate', 'Deactivate')], 'State', readonly=1),
        'nb': fields.integer('Number of selected queries', readonly=1),
        'list': fields.text('Queries', readonly=1),
    }

    def _get_list(self, cr, uid, context=None):
        if context is None:
            context = {}
        if not context.get('active_ids'):
            return ''
        txt = ''
        by_model = {}
        obj = self.pool.get('finance.sync.query')
        sel = dict(obj.fields_get(cr, uid, ['model'], context=context)['model']['selection'])
        for x in obj.read(cr, uid, context['active_ids'], ['name', 'model'], context=context):
            by_model.setdefault(x['model'], []).append(x['name'])

        for model in by_model:
            txt += "%s :\n" % sel.get(model, model)
            for name in by_model[model]:
                txt += "   - %s\n" % name
            txt += "\n"
        return txt

    _defaults = {
        'state': lambda self, cr, uid, context: context and context.get('state', 'activate') or 'activate',
        'nb': lambda self, cr, uid, context: context and len(context.get('active_ids', [])) or False,
        'list': _get_list
    }

    def deactivate_sync(self, cr, uid, ids, context=None):
        '''
        Executed from the sidebard
        '''
        if context is None:
            context = {}
        if context.get('active_ids'):
            self.pool.get('finance.sync.query').deactivate_sync(cr, uid, context['active_ids'], context=context)
        return {'type': 'ir.actions.act_window_close'}

    def activate_sync(self, cr, uid, ids, context=None):
        '''
        Executed from the sidebard
        '''
        if context is None:
            context = {}
        if context.get('active_ids'):
            self.pool.get('finance.sync.query').activate_sync(cr, uid, context['active_ids'], context=context)
        return {'type': 'ir.actions.act_window_close'}

finance_sync_query_activation_wizard()
