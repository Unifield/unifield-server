#!/usr/bin/env python
# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF. All Rights Reserved
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

from osv import osv
from osv import fields
from tools.translate import _
from tools.analytic import get_analytic_state
from lxml import etree

class hq_entries(osv.osv):
    _name = 'hq.entries'
    _description = 'HQ Entries'
    _trace = True


    def _get_cc_changed(self, cr, uid, ids, field_name, arg, context=None):
        """
        Return True if the CC value is different from the original one or if this line is a split from an original entry that have a different cost center value
        """
        # Checks
        if context is None:
            context = {}
        # Prepare some values
        res = {}
        for e in self.browse(cr, uid, ids):
            res[e.id] = False
            if e.cost_center_id.id != e.cost_center_id_first_value.id:
                res[e.id] = True
            elif e.original_id and e.original_id.cost_center_id.id != e.cost_center_id.id:
                res[e.id] = True
        return res

    def _get_account_changed(self, cr, uid, ids, field_name, arg, context=None):
        """
        Return True if the account is different from the original one or if this line is a split from an original entry that have a different account value
        """
        # Checks
        if context is None:
            context = {}
        # Prepare some values
        res = {}
        for e in self.browse(cr, uid, ids):
            res[e.id] = False
            if e.account_id.id != e.account_id_first_value.id:
                res[e.id] = True
            elif e.original_id and e.original_id.account_id.id != e.account_id.id:
                res[e.id] = True
        return res

    def _get_is_account_partner_compatible(self, cr, uid, ids, field_name, arg,
                                           context=None):
        if context is None:
            context = {}
        res = {}
        account_obj = self.pool.get('account.account')

        for r in self.browse(cr, uid, ids, context=context):
            is_compatible = True
            if r.account_id:
                # check the Allowed Partner Types
                is_compatible = account_obj.is_allowed_for_thirdparty(cr, uid, r.account_id.id,
                                                                      partner_txt=r.partner_txt or False,
                                                                      context=context)[r.account_id.id]
                # if the partner type compatibility is OK: also check the "Type for specific treatment"
                if is_compatible:
                    # will raise an error if the Third Party exists in Unifield, and isn't compatible with the account
                    context.update({'ignore_non_existing_tp': True})
                    account_obj.check_type_for_specific_treatment(cr, uid, r.account_id.id,
                                                                  partner_txt=r.partner_txt or False,
                                                                  currency_id=r.currency_id.id,
                                                                  context=context)

            res[r.id] = is_compatible
        return res

    def _get_current_instance_level(self, cr, uid, ids, name, args, context=None):
        """
        Returns a String with the level of the current instance (section, coordo, project)
        """
        if context is None:
            context = {}
        levels = {}
        user_obj = self.pool.get('res.users')
        company = user_obj.browse(cr, uid, uid, fields_to_fetch=['company_id'], context=context).company_id
        level = company.instance_id and company.instance_id.level or ''
        for hq_entry_id in ids:
            levels[hq_entry_id] = level
        return levels

    _columns = {
        'account_id': fields.many2one('account.account', "Account", required=True, select=1),
        'account_user_type_code': fields.related('account_id_first_value', 'user_type_code', string="Account Type",
                                                 type='char', size=32, readonly=True, store=False),
        'destination_id': fields.many2one('account.analytic.account', string="Destination", domain="[('category', '=', 'DEST'), ('type', '!=', 'view'), ('state', '=', 'open')]"),
        'cost_center_id': fields.many2one('account.analytic.account', "Cost Center", required=False, domain="[('category','=','OC'), ('type', '!=', 'view'), ('state', '=', 'open')]", select=1),
        'analytic_id': fields.many2one('account.analytic.account', "Funding Pool", domain="[('category', '=', 'FUNDING'), ('type', '!=', 'view'), ('state', '=', 'open')]"),
        'free_1_id': fields.many2one('account.analytic.account', "Free 1", domain="[('category', '=', 'FREE1'), ('type', '!=', 'view'), ('state', '=', 'open')]"),
        'free_2_id': fields.many2one('account.analytic.account', "Free 2", domain="[('category', '=', 'FREE2'), ('type', '!=', 'view'), ('state', '=', 'open')]"),
        'user_validated': fields.boolean("Validated", help="Is this line validated by a user in a OpenERP field instance?", readonly=True, select=1),
        'date': fields.date("Posting Date", readonly=True, select=1),
        'partner_txt': fields.char("Third Party", size=255, readonly=True),
        'period_id': fields.many2one("account.period", "Period", readonly=True),
        'name': fields.char('Description', size=255, required=True, readonly=True, select=1),
        'ref': fields.char('Reference', size=255, select=1),
        'document_date': fields.date("Document Date", readonly=True, select=1),
        'currency_id': fields.many2one('res.currency', "Book. Currency", required=True, readonly=True),
        'amount': fields.float('Amount', readonly=True, select=1),
        'account_id_first_value': fields.many2one('account.account', "Account @import", required=True, readonly=True),
        'cost_center_id_first_value': fields.many2one('account.analytic.account', "Cost Center @import", required=False, readonly=False),
        'analytic_id_first_value': fields.many2one('account.analytic.account', "Funding Pool @import", readonly=True),
        'destination_id_first_value': fields.many2one('account.analytic.account', "Destination @import", readonly=True),
        'analytic_state': fields.function(get_analytic_state, type='selection', method=True, readonly=True, string="Distribution State",
                                          selection=[('none', 'None'), ('valid', 'Valid'), ('invalid', 'Invalid')], help="Give analytic distribution state"),
        'is_original': fields.boolean("Has been split", help="This line has been split into other ones.", readonly=True),
        'is_split': fields.boolean("Is split?", help="This line comes from a split.", readonly=True),
        'original_id': fields.many2one("hq.entries", "Original HQ Entry", readonly=True, help="The Original HQ Entry from which this line comes from."),
        'split_ids': fields.one2many('hq.entries', 'original_id', "Split lines", help="All lines linked to this original HQ Entry."),
        'cc_changed': fields.function(_get_cc_changed, method=True, type='boolean', string='Have Cost Center changed?', help="When you change the cost center from the initial value (from a HQ Entry or a Split line), so the Cost Center changed is True."),
        'account_changed': fields.function(_get_account_changed, method=True, type='boolean', string='Have account changed?', help="When your entry have a different account from the initial one or from the original one."),
        'is_account_partner_compatible': fields.function(_get_is_account_partner_compatible, method=True, type='boolean', string='Account and partner compatible ?'),
        'original_asset_not_corrigible': fields.related('account_id_first_value', 'prevent_hq_asset', string="Can be an asset?", type='boolean'),
        'current_instance_level': fields.function(_get_current_instance_level, method=True, type='char',
                                                  string='Current Instance Level', store=False, readonly=True),
        'is_asset': fields.boolean(string="Asset", help="Is an asset?"),
        'is_asset_display': fields.boolean(string="Asset", help="Is an asset?", readonly=1), # bug on onchange is_asset
    }

    _defaults = {
        'user_validated': lambda *a: False,
        'amount': lambda *a: 0.0,
        'is_original': lambda *a: False,
        'is_split': lambda *a: False,
        'is_account_partner_compatible': lambda *a: True,
        'is_asset': lambda *a: False,
    }

    def _check_active_account(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        if context.get('sync_update_execution'):
            return True

        for hq in self.browse(cr, uid, ids, fields_to_fetch=['name', 'account_id', 'date']):
            if hq.date < hq.account_id.activation_date or (hq.account_id.inactivation_date and hq.date >= hq.account_id.inactivation_date):
                raise osv.except_osv(_('Error !'), _('HQ Entry %s: account %s is inactive') % (hq.name, hq.account_id.code))
        return True

    def split_forbidden(self, cr, uid, ids, context=None):
        """
        Split is forbidden for these lines:
         - original one
         - split one
         - validated lines
        """
        # Checks
        if context is None:
            context = {}
        # Prepare some values
        res = False
        for line in self.browse(cr, uid, ids, context=context):
            if line.is_original:
                res = True
                break
            if line.is_split:
                res = True
                break
            if line.user_validated == True:
                res = True
                break
        return res

    def get_linked_lines(self, cr, uid, ids, context=None):
        """
        Give all lines (split/original) linked to the given ones
        """
        res = set()
        if context is None:
            context = {}

        def add_split(original_browse):
            for split in original_browse.split_ids:
                res.add(split.id)

        for line in self.browse(cr, uid, ids, context=context):
            res.add(line.id)
            if line.is_original and line.split_ids:
                add_split(line)
            if line.is_split and line.original_id:
                # add original one
                res.add(line.original_id.id)
                # then other split lines
                add_split(line.original_id)
        return list(res)

    def unsplit_allowed_lines(self, cr, uid, ids, context=None):
        """
        You can unsplit a line if these one have the following criteria:
         - line is a draft one
         - line is original OR a split one
        This method return so the lines that can be unsplit
        """
        # Checks
        if context is None:
            context = {}
        # Prepare some values
        res = set()
        for line in self.browse(cr, uid, ids, context=context):
            line_original = line.is_original and line.split_ids
            line_split = line.is_split and line.original_id
            if not line.user_validated and (line_original or line_split):
                # First add original and split linked lines
                for el in self.get_linked_lines(cr, uid, [line.id]):
                    res.add(el)
                # Then add the line
                res.add(line.id)
        return list(res)

    def get_split_wizard(self, cr, uid, ids, context=None):
        """
        Launch HQ Entry Split Wizard
        """
        # Some checks
        if not context or not context.get('active_ids', False):
            raise osv.except_osv(_('Error'), _('No line found!'))
        # Prepare some values
        vals = {}
        ids = context.get('active_ids')
        if isinstance(ids, int):
            ids = [ids]
        if len(ids) > 1:
            raise osv.except_osv(_('Warning'), _('You can only split HQ Entries one by one!'))
        original_id = ids[0]
        original = self.browse(cr, uid, original_id, context=context)
        # some lines are forbidden to be split:
        if self.split_forbidden(cr, uid, ids, context=context):
            raise osv.except_osv(_('Error'), _('This line cannot be split.'))
        # Check if Original HQ Entry is valid (distribution state)
        if original.analytic_state != 'valid':
            raise osv.except_osv(_('Error'), _('You cannot split a HQ Entry which analytic distribution state is not valid!'))
        original_amount = original.amount
        vals.update({'original_id': original_id, 'original_amount': original_amount, 'date': original.date, 'document_date': original.document_date})
        wiz_id = self.pool.get('hq.entries.split').create(cr, uid, vals, context=context)
        # Return view with register_line id
        context.update({
            'active_id': wiz_id,
            'active_ids': [wiz_id],
        })
        return {
            'name': _("HQ Entry Split"),
            'type': 'ir.actions.act_window',
            'res_model': 'hq.entries.split',
            'target': 'new',
            'res_id': [wiz_id],
            'view_mode': 'form',
            'view_type': 'form',
            'context': context,
        }

    def get_unsplit_wizard(self, cr, uid, ids, context=None):
        """
        Open Unsplit wizard
        """
        # Some checks
        if not context or not context.get('active_ids', False):
            raise osv.except_osv(_('Error'), _('No selected line(s)!'))
        # Prepare some values
        vals = {}
        if context is None:
            context = {}
        ids = context.get('active_ids')
        if isinstance(ids, int):
            ids = [ids]
        # Update vals
        vals.update({'line_ids': [(6, 0, ids)], 'process_ids': [(6, 0, self.unsplit_allowed_lines(cr, uid, ids, context=context))]})
        wiz_id = self.pool.get('hq.entries.unsplit').create(cr, uid, vals, context=context)
        # Return view with register_line id
        context.update({
            'active_id': wiz_id,
            'active_ids': [wiz_id],
        })
        return {
            'name': _("HQ Entry Unsplit"),
            'type': 'ir.actions.act_window',
            'res_model': 'hq.entries.unsplit',
            'target': 'new',
            'res_id': [wiz_id],
            'view_mode': 'form',
            'view_type': 'form',
            'context': context,
        }

    def get_validation_wizard(self, cr, uid, ids, context=None):
        """
        Open Validation wizard
        """
        # Some checks
        if not context or not context.get('active_ids', False):
            raise osv.except_osv(_('Error'), _('No selected line(s)!'))
        # Prepare some values
        vals = {}
        if context is None:
            context = {}
        ids = context.get('active_ids')
        if isinstance(ids, int):
            ids = [ids]
        # Search lines that should be processed
        # - exclude validated lines (user_validated = False)
        # - search for original lines (get_linked_lines)
        # - search for split linked lines (get_linked_lines)
        process_ids = self.search(cr, uid, [('id', 'in', self.get_linked_lines(cr, uid, ids, context=context)), ('user_validated', '=', False)])
        txt = _('Are you sure you want to post %d HQ entries ?') % (len(process_ids) or 0,)
        # Update vals
        vals.update({'line_ids': [(6, 0, ids)], 'process_ids': [(6, 0, process_ids)], 'txt': txt,})
        wiz_id = self.pool.get('hq.entries.validation').create(cr, uid, vals, context=context)
        # Return view with register_line id
        context.update({
            'active_id': wiz_id,
            'active_ids': [wiz_id],
        })
        return {
            'name': _("HQ Entries Validation"),
            'type': 'ir.actions.act_window',
            'res_model': 'hq.entries.validation',
            'target': 'new',
            'res_id': [wiz_id],
            'view_mode': 'form',
            'view_type': 'form',
            'context': context,
        }

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        view = super().fields_view_get(cr, uid, view_id=view_id, view_type=view_type, context=context, toolbar=toolbar, submenu=submenu)
        if view_type == 'tree' and self.pool.get('unifield.setup.configuration').get_config(cr, uid, key='fixed_asset_ok'):
            found = False
            view_xml = etree.fromstring(view['arch'])
            for field in view_xml.xpath('//field[@name="is_asset"]|//field[@name="is_asset_display"]'):
                found = True
                field.set('invisible', "0")
            if found:
                view['arch'] = etree.tostring(view_xml, encoding='unicode')

        return view

    def onchange_cost_center(self, cr, uid, ids, cost_center_id=False, funding_pool_id=False):
        """
        Resets the FP and Dest if not compatible with CC and update DEST domain
        """
        return self.pool.get('analytic.distribution').\
            onchange_ad_cost_center(cr, uid, ids, cost_center_id=cost_center_id, funding_pool_id=funding_pool_id, fp_field_name='analytic_id')

    def onchange_destination(self, cr, uid, ids, destination_id=False, funding_pool_id=False, account_id=False):
        return self.pool.get('analytic.distribution').\
            onchange_ad_destination(cr, uid, ids, destination_id=destination_id, funding_pool_id=funding_pool_id, account_id=account_id)

    def onchange_asset_status(self, cr, uid, ids, is_asset=False, account_id=False, context=None):
        if isinstance(ids, int):
            ids = [ids]

        for line in self.browse(cr, uid, ids, fields_to_fetch=['account_id_first_value'], context=context):
            if line.account_id_first_value.prevent_hq_asset:
                raise {
                    'warning': {
                        'title': _('Error'),
                        'message': _('The account %s could not be capitalized') % line.account_id_first_value.code
                    },
                    'value': {'is_asset': False},
                }

        if not is_asset:
            account_id_first_value = self.browse(cr, uid, ids[0], fields_to_fetch=['account_id_first_value'], context=context).account_id_first_value.id
            return {'value': {'account_id': account_id_first_value}}
        if account_id:
            if not self.pool.get('account.account').search_exists(cr, uid, [('id', '=', account_id), ('type', '=', 'other'), ('user_type_code', '=', 'asset'), ('is_not_hq_correctible', '=', False)], context=context):
                return {'value': {'account_id': False}}
        return {}

    def _check_cc(self, cr, uid, ids, context=None):
        """
        At synchro time sets HQ entry to Not Run if the Cost Center used in the line doesn't exist or is inactive

        Note: if the CC is active but the Dest/CC combination is inactive, the sync update is NOT blocked:
              the HQ entry will be created with an invalid AD to be fixed before validation.
        """
        if isinstance(ids, int):
            ids = [ids]
        if context is None:
            context = {}
        if context.get('sync_update_execution'):
            for hq_entry in self.browse(cr, uid, ids, fields_to_fetch=['cost_center_id', 'date', 'name'], context=context):
                if not hq_entry.cost_center_id:
                    raise osv.except_osv(_('Warning'), _('The Cost Center of the HQ entry "%s" doesn\'t exist in the system.') % hq_entry.name)
                elif hq_entry.date:  # posting date
                    hq_date = hq_entry.date
                    cc_date_start = hq_entry.cost_center_id.date_start
                    cc_date_end = hq_entry.cost_center_id.date or False
                    if (hq_date < cc_date_start) or (cc_date_end and hq_date >= cc_date_end):
                        raise osv.except_osv(_('Warning'), _('The Cost Center %s used in the HQ entry "%s" is inactive.') %
                                             (hq_entry.cost_center_id.code or '', hq_entry.name))
        return True

    def _duplicate_is_asset(self, cr, uid, vals, context=None):
        if 'is_asset' in vals:
            vals['is_asset_display'] = vals['is_asset']
            return {'is_asset_display': vals['is_asset']}
        return {}

    def create(self, cr, uid, vals, context=None):
        self._duplicate_is_asset(cr, uid, vals, context)
        new_id = super(hq_entries, self).create(cr, uid, vals, context)
        self._check_active_account(cr, uid, [new_id], context=context)
        self._check_cc(cr, uid, [new_id], context=context)
        return new_id

    def write(self, cr, uid, ids, vals, context=None):
        """
        Change Expat salary account is not allowed
        """
        if not ids:
            return True
        if isinstance(ids, int):
            ids = [ids]
        if context is None:
            context={}

        #US-921: Only save the user_validated value if the update comes from sync!
        if context.get('sync_update_execution', False):
            sync_vals = {}
            if 'user_validated' in vals:
                sync_vals.update({'user_validated': vals['user_validated']})
            if 'is_original' in vals:  # US-4169 also enable to sync the is_original tag
                sync_vals.update({'is_original': vals['is_original']})
            if sync_vals:
                return super(hq_entries, self).write(cr, uid, ids, sync_vals, context)
            return True

        self._duplicate_is_asset(cr, uid, vals, context)
        if 'account_id' in vals:
            account = self.pool.get('account.account').browse(cr, uid, [vals.get('account_id')])[0]
            for line in self.browse(cr, uid, ids):
                if line.account_id_first_value and line.account_id_first_value.is_not_hq_correctible and not account.is_not_hq_correctible:
                    raise osv.except_osv(_('Warning'), _('Change Expat salary account is not allowed!'))
        self.check_ad_change_allowed(cr, uid, ids, vals, context=context)
        res = super(hq_entries, self).write(cr, uid, ids, vals, context)
        self._check_active_account(cr, uid, ids, context=context)
        self._check_cc(cr, uid, ids, context=context)
        return res

    def unlink(self, cr, uid, ids, context=None):
        """
        At synchro. only delete the entries having the tag is_split (= sync of an unsplit done in coordo). Otherwise:
        Do not permit user to delete:
         - validated HQ entries
         - split entries
         - original entries
        """
        if isinstance(ids, int):
            ids = [ids]
        if context is None:
            context = {}
        if context.get('sync_update_execution', False):
            new_ids = []
            for hq_entry in self.browse(cr, uid, ids, fields_to_fetch=['is_split'], context=context):
                if hq_entry.is_split:
                    new_ids.append(hq_entry.id)
            ids = new_ids
        if not context.get('from', False) or context.get('from') != 'code' and ids:
            if self.search(cr, uid, [('id', 'in', ids), ('user_validated', '=', True)]):
                raise osv.except_osv(_('Error'), _('You cannot delete validated HQ Entries lines!'))
            if self.search(cr, uid, [('id', 'in', ids), ('is_split', '=', True)]) and not context.get('sync_update_execution'):
                raise osv.except_osv(_('Error'), _('You cannot delete split entries!'))
            if self.search(cr, uid, [('id', 'in', ids), ('is_original', '=', True)]):
                raise osv.except_osv(_('Error'), _('You cannot delete original entries!'))
        return super(hq_entries, self).unlink(cr, uid, ids, context)

    def _is_dec_period_open(self, cr, uid, context):
        '''
        Returns True if at least one December period (12,13,14,15) is Open or Field-Closed,
        otherwise returns False
        '''
        if context is None:
            context = {}
        domain = [
            ('number', 'in', list(range(12, 16))),
            ('state', 'in', ['draft', 'field-closed', ]),
        ]
        if self.pool.get('account.period').search(cr, uid, domain, context=context, count=True):
            return True
        return False

    def check_hq_entry_transaction(self, cr, uid, ids, wizard_model,
                                   context=None):
        if not ids:
            raise osv.except_osv(_("Warning"),
                                 _("No HQ Entry selected for transaction"))

        # BKLG-77
        domain = [
            ('id', 'in', ids),
            ('user_validated', '=', True),
        ]
        if self.search(cr, uid, domain, context=context, count=True):
            raise osv.except_osv(_("Warning"),
                                 _("You can not perform this action on a validated HQ Entry" \
                                   " (please use the 'To Validate' filter in the HQ Entries list)"))

        # US-306: forbid to validate mission closed or + entries
        # => at coordo level you can not validate entries since field closed
        # period; but they can come from HQ mission opened via SYNC)
        hq_entries = self.browse(cr, uid, ids, context=context)
        period_ids = list(set([ he.period_id.id \
                                for he in hq_entries ]))
        # warning if an HQ Entry is in a non-opened period
        if period_ids:
            periods = self.pool.get("account.period").browse(cr, uid, period_ids, context)
            mission_closed_except = osv.except_osv(_("Warning"), _("You can not validate HQ Entry in a mission-closed" \
                                                                   " period"))
            for p in periods:
                if p.number != 12 and p.state in ['mission-closed', 'done', ]:
                    raise mission_closed_except
                elif p.number == 12 and not self._is_dec_period_open(cr, uid, context):
                    raise mission_closed_except

        # block edition and split on B/S entries
        if wizard_model in ['hq.entries.split', 'hq.analytic.reallocation', 'hq.reallocation']:
            for hq_entry in hq_entries:
                if hq_entry.account_id.user_type_code not in ['expense', 'income']:
                    raise osv.except_osv(_("Warning"),
                                         _("You can not perform this action on a B/S line."))

    def check_ad_change_allowed(self, cr, uid, ids, vals, context=None):
        """
        Raises a warning if the HQ entry Analytic Distribution is about to be modified although the general account is
        set as "is_not_ad_correctable"
        :param ids: ids of the HQ Entries
        :param vals: new values about to be written
        """
        if context is None:
            context = {}
        if not context.get('sync_update_execution'):
            account_obj = self.pool.get('account.account')
            fields_list = [
                'account_id', 'cost_center_id', 'free_1_id', 'free_2_id', 'destination_id', 'analytic_id',
                'is_asset', 'cost_center_id_first_value', 'destination_id_first_value', 'analytic_id_first_value'
            ]
            for hq_entry in self.browse(cr, uid, ids, fields_to_fetch=fields_list, context=context):
                if hq_entry.is_asset:
                    vals.update({
                        'cost_center_id': hq_entry.cost_center_id_first_value and hq_entry.cost_center_id_first_value.id or False,
                        'destination_id': hq_entry.destination_id_first_value and hq_entry.destination_id_first_value.id or False,
                        'analytic_id': hq_entry.analytic_id_first_value and hq_entry.analytic_id_first_value.id or False,
                    })
                else:
                    account_id = vals.get('account_id') and account_obj.browse(cr, uid, vals['account_id'], fields_to_fetch=['is_not_ad_correctable'], context=context)
                    hq_account = account_id or hq_entry.account_id
                    if hq_account.is_not_ad_correctable:
                        for field in ['cost_center_id', 'destination_id', 'analytic_id', 'free_1_id', 'free_2_id']:
                            value_changed = vals.get(field) and (not getattr(hq_entry, field) or getattr(hq_entry, field).id != vals[field])
                            value_removed = getattr(hq_entry, field) and field in vals and not vals[field]
                            if value_changed or value_removed:
                                raise osv.except_osv(_('Warning'), _('The account %s - %s is set as \"Prevent correction on'
                                                                     ' analytic accounts\".') % (hq_account.code, hq_account.name))

    def auto_import(self, cr, uid, file_to_import, context=None):
        import base64
        import os
        processed = []
        rejected = []
        headers = []

        import_obj = self.pool.get('hq.entries.import')
        import_id = import_obj.create(cr, uid, {
            'file': base64.b64encode(open(file_to_import, 'rb').read()),
            'filename': os.path.split(file_to_import)[1],
        })
        processed, rejected, headers = import_obj.button_validate(cr, uid, [import_id], auto_import=True)
        return processed, rejected, headers

hq_entries()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
