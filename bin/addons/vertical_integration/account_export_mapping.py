#!/usr/bin/env python
#-*- encoding:utf-8 -*-

from osv import osv, fields
from lxml import etree
from tools.translate import _

class account_export_mapping(osv.osv):
    _name = 'account.export.mapping'
    _description = 'Mapping of UF code into AX code'
    _rec_name = 'account_id'

    _columns = {
        'account_id': fields.many2one('account.account', string="Unifield Account Code", required=True, select=1),
        'mapping_value': fields.char('HQ System Account Code', required=True, size=64, select=1)
    }

    _sql_constraints = [
        ('unique_account_id', 'unique(account_id)', 'A mapping already exists for this account')
    ]

    def menu_import_wizard(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        wiz_obj = self.pool.get('wizard.import.mapping')
        wiz_id = wiz_obj.create(cr, uid, {}, context=context)
        # we open a wizard
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'wizard.import.mapping',
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'res_id': [wiz_id],
            'context': context,
        }

    def _get_hq_system_acc(self, cr, uid, ids, field_name, args, obj, context=None):
        '''
            method used by account.move.line and account.analytic.line
            to get the mapping account value

        '''
        if context is None:
            context = {}
        mapping_dict = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        if not self._is_mapping_display_active(cr, uid, context):
            return dict.fromkeys(ids, False)

        mapping_ids = self.search(cr, uid, [('account_id', '!=', False)], context=context)

        if not mapping_ids:
            return dict.fromkeys(ids, False)

        res = {}
        for mapping_id in mapping_ids:
            mapping = self.browse(cr, uid, mapping_id, fields_to_fetch=['account_id', 'mapping_value'], context=context)
            mapping_dict[mapping.account_id.id] = mapping.mapping_value

        if obj._name == 'account.analytic.line':
            field = 'general_account_id'
        else:
            field = 'account_id'

        for aml in obj.browse(cr, uid, ids, fields_to_fetch=[field], context=context):
            res[aml.id] = mapping_dict.get(aml[field].id, False)
        return res

    def _search_hq_acc(self, cr, uid, ids, name, args, obj, context=None):
        """
            method used by account.move.line and account.analytic.line
            to filter records by mapping value
        """

        if not len(args):
            return []
        if len(args) != 1:
            msg = _("Domain %s not supported") % (str(args),)
            raise osv.except_osv(_('Error'), msg)

        if not args[0][2]:
            return []

        if args[0][1] not in ('ilike', 'not ilike', 'in', 'not in', '=', '<>'):
            msg = _("Operator %s not supported") % (args[0][1],)
            raise osv.except_osv(_('Error'), msg)

        mapping_ids = self.search(cr, uid, [('mapping_value', args[0][1], args[0][2])], context=context)
        account_ids = []
        for mapping in self.browse(cr, uid, mapping_ids, fields_to_fetch=['account_id'], context=context):
            account_ids.append(mapping.account_id.id)

        if obj._name == 'account.account':
            field = 'id'
        elif obj._name == 'account.analytic.line':
            field = 'general_account_id'
        else:
            field = 'account_id'
        return [(field, 'in', account_ids)]

    def _is_mapping_display_active(self, cr, uid, context=None):
        return self.pool.get('res.users').browse(cr, uid, uid, fields_to_fetch=['company_id'], context=context).company_id.display_hq_system_accounts_buttons

    def update_view_with_mapping_field(self, cr, uid, view_type, view, context=None):
        if view.get('arch') and view_type in ['tree', 'form'] and \
                self._is_mapping_display_active(cr, uid, context):

            arch = etree.fromstring(view['arch'])
            for el in arch.xpath('field[@name="hq_system_account"]'):
                el.set('invisible', '0')

            view['arch'] = etree.tostring(arch)

account_export_mapping()

class account_account(osv.osv):
    _name = 'account.account'
    _inherit = 'account.account'

    def _get_mapping_value(self, cr, uid, ids, field_name, args, context=None):
        if not ids:
            return {}

        cr.execute('''select acc.id, map.mapping_value
            from account_account acc
            left join account_export_mapping map on map.account_id = acc.id
            where
                acc.id in %s
        ''', (tuple(ids), ))

        res = {}
        for x in cr.fetchall():
            res[x[0]] = x[1]

        return res


    def _search_mapping_value(self, cr, uid, ids, name, args, context=None):
        return self.pool.get('account.export.mapping')._search_hq_acc(cr, uid, ids, name, args, self, context=None)

    _columns = {
        'mapping_value': fields.function(_get_mapping_value, method=True, type='char', size=64, string='HQ System Account Code', fnct_search=_search_mapping_value),
    }

account_account()
