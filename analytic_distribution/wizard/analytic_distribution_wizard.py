#!/usr/bin/env python
# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF. All Rights Reserved
#    Developer: Olivier DOSSMANN
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
from lxml import etree
from tools.translate import _
import decimal_precision as dp


class analytic_distribution_wizard_lines(osv.osv_memory):
    _name = 'analytic.distribution.wizard.lines'
    _description = 'analytic.distribution.wizard.lines'

    def _get_amount(self, cr, uid, ids, name, args, context=None):
        """
        Give amount regarding percentage and wizard's total_amount
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        res = {}
        # Browse elements
        for line in self.browse(cr, uid, ids, context=context):
            wizard = line.wizard_id
            res[line.id] = 0
            if wizard and wizard.total_amount:
                res[line.id] = abs((wizard.total_amount * line.percentage) / 100.0)
        return res

    _columns = {
        'analytic_id': fields.many2one('account.analytic.account', string="Analytic account", required=True),
        'amount': fields.function(_get_amount, method=True, type='float', string="Amount", readonly=True, digits_compute=dp.get_precision('Account')),
        'percentage': fields.float(string="Percentage", required=True, digits=(16,4)),
        'wizard_id': fields.many2one('analytic.distribution.wizard', string="Analytic Distribution Wizard", required=True),
        'currency_id': fields.many2one('res.currency', string="Currency", required=True),
        'distribution_line_id': fields.many2one('distribution.line', string="Distribution Line", readonly=True),
        'type': fields.selection([('cost.center', 'Cost Center Lines'), ('funding.pool', 'Funding Pool Lines'), ('free.1', 'Free 1 Lines'), 
            ('free.2', 'Free 2 Lines')], string="Line type", help="Specify the type of lines"), # Important for some method that take this values 
            #+ to construct object research !
        'destination_id': fields.many2one('account.analytic.account', string="Destination", required=True, 
            domain="[('type', '!=', 'view'), ('category', '=', 'DEST'), ('state', '=', 'open')]"),
    }

    def default_get(self, cr, uid, fields, context=None):
        """
        Verify that percentage or amount are correctly set
        """
        res = super(analytic_distribution_wizard_lines, self).default_get(cr, uid, fields, context=context)
        # Fetch some values
        if not context or not context.get('mode', False) or not context.get('parent_id', False):
            return res
        if not 'percentage' in fields or not 'amount' in fields:
            return res
        mode = context.get('mode')
        parent_id = context.get('parent_id')
        percentage = abs(res.get('percentage', 0.0))
        amount = abs(res.get('amount', 0.0))
        wiz = self.pool.get('analytic.distribution.wizard').browse(cr, uid, [context.get('parent_id')], context=context)
        if wiz and wiz[0]:
            if 'destination_id' in fields and wiz[0].account_id:
                res['destination_id'] = wiz[0].account_id.default_destination_id and wiz[0].account_id.default_destination_id.id or False

            total_amount = wiz[0].total_amount
            if mode == 'percentage':
                res['amount'] = abs((total_amount * percentage) / 100.0)
            elif mode == 'amount' and total_amount:
                res['percentage'] = abs((amount / total_amount) * 100.0)
        return res

    def _get_remaining_allocation(self, cr, uid, context=None):
        """
        Get remaining allocation for this object
        """
        # Some verifications
        if context is None:
            context = {}
        id = None
        mode = None
        if context and context.get('parent_id', False):
            id = context.get('parent_id')
        if context and context.get('mode', False):
            mode = context.get('mode')
        if not id or not mode:
            return 0.0
        # Prepare some values
        res = 0.0
        allocated = 0.0
        wiz = self.pool.get('analytic.distribution.wizard').browse(cr, uid, [id], context=context)[0]
        amount = wiz and abs(wiz.total_amount) or 0.0
        search_ids = self.pool.get(self._name).search(cr, uid, [('wizard_id', '=', id)], context=context)
        for line in self.pool.get(self._name).browse(cr, uid, search_ids, context=context):
            if mode == 'percentage':
                allocated += abs(line.percentage)
            elif mode == 'amount':
                allocated += abs(line.amount)
        if mode == 'percentage':
            res = 100.0 - allocated
        elif mode == 'amount':
            res = amount - allocated
        return res

    _defaults = {
        'percentage': _get_remaining_allocation,
        'amount': _get_remaining_allocation,
        'type': lambda *a: 'cost.center',
    }

    def onchange_percentage(self, cr, uid, ids, percentage, total_amount):
        """
        Change amount regarding percentage
        """
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not percentage or not total_amount:
            return {}
        amount = abs((total_amount * percentage) / 100)
        return {'value': {'amount': amount}}

    def onchange_amount(self, cr, uid, ids, amount, total_amount):
        """
        Change percentage regarding amount
        """
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not amount or not total_amount:
            return {}
        percentage = abs((amount / total_amount) * 100)
        return {'value': {'percentage': percentage}}

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        """
        Rewrite view in order:
         - "entry_mode" works and Analytic Account field display only cost_center for Cost Center Lines
         - Cost Center field display only cost_center and Funding Pool only display attached Funding pool for Funding Pool Lines
         - Analytic Account field display only those from Free1
         - Analytic Account field display only those from Free2
        """
        if not context:
            context = {}
        view = super(analytic_distribution_wizard_lines, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)
        if view_type=='tree':
            tree = etree.fromstring(view['arch'])
            line_type = self._name
            data_obj = self.pool.get('ir.model.data')
            try:
                oc_id = data_obj.get_object_reference(cr, uid, 'analytic_distribution', 'analytic_account_project')[1]
            except ValueError:
                oc_id = 0
            ## COST CENTER
            if line_type == 'analytic.distribution.wizard.lines':
                # Change OC field
                fields = tree.xpath('/tree/field[@name="analytic_id"]')
                for field in fields:
                    field.set('domain', "[('type', '!=', 'view'), ('id', 'child_of', [%s])]" % oc_id)
                # Change Destination field
                dest_fields = tree.xpath('/tree/field[@name="destination_id"]')
                for field in dest_fields:
                    if (context.get('from_invoice', False) and isinstance(context.get('from_invoice'), int)) or (context.get('from_commitment', False) and isinstance(context.get('from_commitment'), int)) \
                        or (context.get('from_purchase', False) and isinstance(context.get('from_purchase'), int)):
                        field.set('domain', "[('type', '!=', 'view'), ('state', '=', 'open'), ('category', '=', 'DEST')]")
                    else:
                        field.set('domain', "[('type', '!=', 'view'), ('state', '=', 'open'), ('category', '=', 'DEST'), ('destination_ids', '=', parent.account_id)]")
            ## FUNDING POOL
            if line_type == 'analytic.distribution.wizard.fp.lines':
                # Change OC field
                fields = tree.xpath('/tree/field[@name="cost_center_id"]')
                for field in fields:
                    field.set('domain', "[('type', '!=', 'view'), ('state', '=', 'open'), ('id', 'child_of', [%s])]" % oc_id)
                # Change FP field
                try:
                    fp_id = data_obj.get_object_reference(cr, uid, 'analytic_distribution', 'analytic_account_msf_private_funds')[1]
                except ValueError:
                    fp_id = 0
                fp_fields = tree.xpath('/tree/field[@name="analytic_id"]')
                for field in fp_fields:
                    # for accrual lines, only Private Funds must be available
                    if context.get('from_accrual_line', False):
                        field.set('domain', "[('id', '=', %s)]" % fp_id)
                    # If context with 'from' exist AND its content is an integer (so an invoice_id)
                    elif (context.get('from_invoice', False) and isinstance(context.get('from_invoice'), int)) or (context.get('from_commitment', False) and isinstance(context.get('from_commitment'), int)):
                        # Filter is only on cost_center and MSF Private Fund on invoice header
                        field.set('domain', "[('type', '!=', 'view'), ('state', '=', 'open'), ('category', '=', 'FUNDING'), '|', ('cost_center_ids', '=', cost_center_id), ('id', '=', %s)]" % fp_id)
                    else:
                        # Add account_id constraints for invoice lines
                        field.set('domain', "[('type', '!=', 'view'), ('state', '=', 'open'), ('category', '=', 'FUNDING'), '|', '&', ('cost_center_ids', '=', cost_center_id), ('tuple_destination', '=', (parent.account_id, destination_id)), ('id', '=', %s)]" % fp_id)
                # Change Destination field
                dest_fields = tree.xpath('/tree/field[@name="destination_id"]')
                for field in dest_fields:
                    if (context.get('from_invoice', False) and isinstance(context.get('from_invoice'), int)) or (context.get('from_commitment', False) and isinstance(context.get('from_commitment'), int)):
                        field.set('domain', "[('type', '!=', 'view'), ('state', '=', 'open'), ('category', '=', 'DEST')]")
                    else:
                        field.set('domain', "[('type', '!=', 'view'), ('state', '=', 'open'), ('category', '=', 'DEST'), ('destination_ids', '=', parent.account_id)]")
            ## FREE 1
            if line_type == 'analytic.distribution.wizard.f1.lines':
                # Change Analytic Account field
                try:
                    f1_id = data_obj.get_object_reference(cr, uid, 'analytic_distribution', 'analytic_account_free_1')[1]
                except ValueError:
                    f1_id = 0
                fields = tree.xpath('/tree/field[@name="analytic_id"]')
                for field in fields:
                    field.set('domain', "[('type', '!=', 'view'), ('state', '=', 'open'), ('id', 'child_of', [%s])]" % f1_id)
            ## FREE 2
            if line_type == 'analytic.distribution.wizard.f2.lines':
                # Change Analytic Account field
                try:
                    f2_id = data_obj.get_object_reference(cr, uid, 'analytic_distribution', 'analytic_account_free_2')[1]
                except ValueError:
                    f2_id = 0
                fields = tree.xpath('/tree/field[@name="analytic_id"]')
                for field in fields:
                    field.set('domain', "[('type', '!=', 'view'), ('state', '=', 'open'), ('id', 'child_of', [%s])]" % f2_id)
            ## ALL FIELDS
            # Change percentage and amount field
            for el in ['percentage', 'amount']:
                new_fields = tree.xpath('/tree/field[@name="%s"]' % el)
                for field in new_fields:
                    field.set('readonly', str(context.get('mode', False) != el))
                    if context.get('mode', False) == el:
                        field.set('on_change', "onchange_%s(%s, parent.total_amount)" % (el, el))
            view['arch'] = etree.tostring(tree)
        return view

    def verify_analytic_account(self, cr, uid, vals, line_type=None, context=None):
        """
        Verify that analytic account match with line_type
        """
        # Some verifications
        if not context:
            context = {}
        if not vals:
            return False
        if not line_type:
            return False
        # Prepare some values
        ana_obj = self.pool.get('account.analytic.account')
        data = {
            'analytic.distribution.wizard.lines': ('OC', 'Cost Center'),
            'analytic.distribution.wizard.fp.lines': ('FUNDING', 'Funding Pool'),
            'analytic.distribution.wizard.f1.lines': ('FREE1', 'Free 1'),
            'analytic.distribution.wizard.f2.lines': ('FREE2', 'Free 2'),
        }
        # Verify analytic account regarding line_type
        if vals.get('analytic_id', False):
            ana_acc = ana_obj.browse(cr, uid, vals.get('analytic_id'), context=context)
            if ana_acc and ana_acc.category and data[line_type] and data[line_type][0]:
                if not ana_acc.category == data[line_type][0] and line_type != 'analytic.distribution.wizard.fp.lines':
                    raise osv.except_osv(_('Error'), _("Given account '%s' doesn't match with the type '%s'.") % (ana_acc.name, data[line_type][1]))
        # Verify cost_center_id if given
        if vals.get('cost_center_id', False):
            cc = ana_obj.browse(cr, uid, vals.get('cost_center_id'), context=context)
            if cc and cc.category:
                if not cc.category == 'OC':
                    raise osv.except_osv(_('Error'), _("Choosen cost center '%s' is not from OC Category.") % (cc.name,))
        return True

    def create(self, cr, uid, vals, context=None):
        """
        Calculate amount and percentage regarding context content
        """
        # Some verifications
        if not context:
            context = {}
        # Launch verifications on given analytic_account
        if not self.verify_analytic_account(cr, uid, vals, self._name, context=context):
            raise osv.except_osv(_('Error'), _('Analytic account validation error.'))
        # Verify that percentage is present, otherwise calculate it
        if not vals.get('percentage', False) and vals.get('amount', False) and vals.get('wizard_id', False):
            wiz = self.pool.get('analytic.distribution.wizard').browse(cr, uid, [vals.get('wizard_id')], context=context)
            if wiz and wiz[0] and wiz[0].total_amount:
                vals.update({'percentage': abs((vals.get('amount') / wiz[0].total_amount) * 100.0)})
        res = super(analytic_distribution_wizard_lines, self).create(cr, uid, vals, context=context)
        # Validate wizard
        if vals.get('wizard_id', False) and not context.get('skip_validation', False):
            self.pool.get('analytic.distribution.wizard').validate(cr, uid, vals.get('wizard_id'), context=context)
        return res

    def write(self, cr, uid, ids, vals, context=None):
        """
        Calculate amount and percentage regarding context content
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Launch verifications on given analytic_account
        if not self.verify_analytic_account(cr, uid, vals, self._name, context=context):
            raise osv.except_osv(_('Error'), _('Analytic account validation error.'))
        # If amount present in vals, change percentage
        if 'amount' in vals and 'percentage' not in vals:
            wiz = self.browse(cr, uid, ids, context=context)
            if wiz and wiz[0].wizard_id and wiz[0].wizard_id.total_amount:
                vals.update({'percentage': abs((vals.get('amount') / wiz[0].wizard_id.total_amount) * 100.0)})
        res = super(analytic_distribution_wizard_lines, self).write(cr, uid, ids, vals, context=context)
        # Retrieve wizard_id field
        data = self.read(cr, uid, [ids[0]], ['wizard_id'], context=context)
        wiz_id = data and data[0] and data[0].get('wizard_id')
        if wiz_id and not context.get('skip_validation', False):
            self.pool.get('analytic.distribution.wizard').validate(cr, uid, wiz_id, context=context)
        return res

analytic_distribution_wizard_lines()

class analytic_distribution_wizard_fp_lines(osv.osv_memory):
    _name = 'analytic.distribution.wizard.fp.lines'
    _description = 'analytic.distribution.wizard.lines'
    _inherit = 'analytic.distribution.wizard.lines'

    _columns = {
        'cost_center_id': fields.many2one('account.analytic.account', string="Cost Center", required=True),
    }

    _defaults = {
        'type': lambda *a: 'funding.pool',
    }

    def onchange_destination(self, cr, uid, ids, destination_id=False, analytic_id=False, account_id=False):
        """
        Check given funding pool with destination
        """
        # Prepare some values
        res = {}
        # If all elements given, then search FP compatibility
        if destination_id and analytic_id and account_id:
            fp_line = self.pool.get('account.analytic.account').browse(cr, uid, analytic_id)
            # Search MSF Private Fund element, because it's valid with all accounts
            try:
                fp_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'analytic_distribution', 
                'analytic_account_msf_private_funds')[1]
            except ValueError:
                fp_id = 0
            # Delete analytic_id if not valid with tuple "account_id/destination_id".
            # but do an exception for MSF Private FUND analytic account
            if (account_id, destination_id) not in [x.account_id and x.destination_id and (x.account_id.id, x.destination_id.id) for x in fp_line.tuple_destination_account_ids] and analytic_id != fp_id:
                res = {'value': {'analytic_id': False}}
        # If no destination, do nothing
        elif not destination_id:
            res = {}
        # Otherway: delete FP
        else:
            res = {'value': {'analytic_id': False}}
        # If destination given, search if given 
        return res

analytic_distribution_wizard_fp_lines()

class analytic_distribution_wizard_f1_lines(osv.osv_memory):
    _name = 'analytic.distribution.wizard.f1.lines'
    _description = 'analytic.distribution.wizard.lines'
    _inherit = 'analytic.distribution.wizard.lines'

    _columns = {
        'destination_id': fields.many2one('account.analytic.account', string="Destination", required=False, 
            domain="[('type', '!=', 'view'), ('category', '=', 'DEST'), ('state', '=', 'open')]"),
    }

    _defaults = {
        'type': lambda *a: 'free.1',
    }

analytic_distribution_wizard_f1_lines()

class analytic_distribution_wizard_f2_lines(osv.osv_memory):
    _name = 'analytic.distribution.wizard.f2.lines'
    _description = 'analytic.distribution.wizard.lines'
    _inherit = 'analytic.distribution.wizard.lines'

    _columns = {
        'destination_id': fields.many2one('account.analytic.account', string="Destination", required=False, 
            domain="[('type', '!=', 'view'), ('category', '=', 'DEST'), ('state', '=', 'open')]"),
    }

    _defaults = {
        'type': lambda *a: 'free.2',
    }

analytic_distribution_wizard_f2_lines()

class analytic_distribution_wizard(osv.osv_memory):
    _name = 'analytic.distribution.wizard'
    _description = 'analytic.distribution.wizard'

    def _is_writable(self, cr, uid, ids, name, args, context=None):
        """
        Give possibility to write or not on this wizard
        """
        if context is None:
            context = {}
        # Prepare some values
        res = {}
        # Browse all given wizard
        for el in self.browse(cr, uid, ids, context=context):
            res[el.id] = True
            # verify purchase state
            if el.purchase_id and el.purchase_id.state in ['approved', 'done']:
                res[el.id] = False
            # verify purchase line state
            if el.purchase_line_id and el.purchase_line_id.order_id and el.purchase_line_id.order_id.state in ['approved', 'done']:
                res[el.id] = False
            # verify invoice state
            if el.invoice_id and el.invoice_id.state in ['open', 'paid']:
                res[el.id] = False
            # verify invoice line state
            if el.invoice_line_id and el.invoice_line_id.invoice_id and el.invoice_line_id.invoice_id.state in ['open', 'paid']:
                res[el.id] = False
            # verify commitment state
            if el.commitment_id and el.commitment_id.state in ['done']:
                res[el.id] = False
            # verify commitment line state
            if el.commitment_line_id and el.commitment_line_id.commit_id and el.commitment_line_id.commit_id.state in ['done']:
                res[el.id] = False
            # verify accrual line state
            if el.accrual_line_id and el.accrual_line_id.state in ['posted']:
                res[el.id] = False
            # verify sale order state
            if el.sale_order_id and el.sale_order_id.state in ['done', 'manual', 'progress', 'shipping_except', 'invoice_except']:
                res[el.id] = False
            # verify sale order line state
            if el.sale_order_line_id and el.sale_order_line_id.order_id and el.sale_order_line_id.order_id.state in ['done', 'manual', 'progress', 'shipping_except', 'invoice_except']:
                res[el.id] = False
        return res

    def _have_header(self, cr, uid, ids, name, args, context=None):
        """
        Return true if this wizard is on a line and if the parent has a distrib
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        res = {}
        # Browse given wizards
        for wiz in self.browse(cr, uid, ids, context=context):
            res[wiz.id] = False
            if wiz.invoice_line_id and wiz.invoice_line_id.invoice_id and wiz.invoice_line_id.invoice_id.analytic_distribution_id:
                res[wiz.id] = True
            elif wiz.purchase_line_id and wiz.purchase_line_id.order_id and wiz.purchase_line_id.order_id.analytic_distribution_id:
                res[wiz.id] = True
            elif wiz.direct_invoice_line_id and wiz.direct_invoice_line_id.invoice_id and wiz.direct_invoice_line_id.invoice_id.analytic_distribution_id:
                res[wiz.id] = True
            elif wiz.commitment_line_id and wiz.commitment_line_id.commit_id and wiz.commitment_line_id.commit_id.analytic_distribution_id:
                res[wiz.id] = True
        return res

    def _get_amount(self, cr, uid, ids, name, args, context=None):
        """
        Get amount regarding total_amount field
        """
        # Prepare some values
        res = {}
        for wiz in self.browse(cr, uid, ids):
            res[wiz.id] = 0.0
            if wiz.total_amount:
                res[wiz.id] = abs(wiz.total_amount)
        return res

    _columns = {
        'total_amount': fields.float(string="Total amount", size=64, readonly=True),
        'state': fields.selection([('draft', 'Draft'), ('cc', 'Cost Center only'), ('dispatch', 'All other elements'), ('done', 'Done')], 
            string="State", required=True, readonly=True),
        'entry_mode': fields.selection([('percentage','Percentage'), ('amount','Amount')], 'Entry Mode', select=1),
        'line_ids': fields.one2many('analytic.distribution.wizard.lines', 'wizard_id', string="Cost Center Allocation"),
        'fp_line_ids': fields.one2many('analytic.distribution.wizard.fp.lines', 'wizard_id', string="Funding Pool Allocation"),
        'f1_line_ids': fields.one2many('analytic.distribution.wizard.f1.lines', 'wizard_id', string="Free 1 Allocation"),
        'f2_line_ids': fields.one2many('analytic.distribution.wizard.f2.lines', 'wizard_id', string="Free 2 Allocation"),
        'currency_id': fields.many2one('res.currency', string="Currency"),
        'purchase_id': fields.many2one('purchase.order', string="Purchase Order"),
        'purchase_line_id': fields.many2one('purchase.order.line', string="Purchase Order Line"),
        'invoice_id': fields.many2one('account.invoice', string="Invoice"),
        'invoice_line_id': fields.many2one('account.invoice.line', string="Invoice Line"),
        'register_line_id': fields.many2one('account.bank.statement.line', string="Register Line"),
        'move_line_id': fields.many2one('account.move.line', string="Journal Item"),
        'commitment_id': fields.many2one('account.commitment', string="Commitment Voucher"),
        'commitment_line_id': fields.many2one('account.commitment.line', string="Commitment Voucher Line"),
        'model_line_id': fields.many2one('account.model.line', string="Account Model Line"),
        'accrual_line_id': fields.many2one('msf.accrual.line', string="Accrual Line"),
        'distribution_id': fields.many2one('analytic.distribution', string="Analytic Distribution"),
        'is_writable': fields.function(_is_writable, method=True, string='Is this wizard writable?', type='boolean', readonly=True, 
            help="This informs wizard if it could be saved or not regarding invoice state or purchase order state", store=False),
        'have_header': fields.function(_have_header, method=True, string='Is this wizard come from an invoice line?', 
            type='boolean', readonly=True, help="This informs the wizard if we are on a line and if the parent has an distrib."),
        'account_id': fields.many2one('account.account', string="Account from invoice", readonly=True,
            help="This account come from an invoice line. When filled in it permits to test compatibility for each funding pool and display those that was linked with."),
        'direct_invoice_id': fields.many2one('wizard.account.invoice', string="Direct Invoice"),
        'direct_invoice_line_id': fields.many2one('wizard.account.invoice.line', string="Direct Invoice Line"),
        'sale_order_id': fields.many2one('sale.order', string="Sale Order"),
        'sale_order_line_id': fields.many2one('sale.order.line', string="Sale Order Line"),
        'amount': fields.function(_get_amount, method=True, string="Total amount", type="float", readonly=True)
    }

    _defaults = {
        'state': lambda *a: 'draft',
        'entry_mode': lambda *a: 'percentage',
    }

    def dummy(self, cr, uid, ids, context=None, *args, **kwargs):
        """
        Change entry mode
        """
        if context is None:
            context = {}
        mode = self.read(cr, uid, ids, ['entry_mode'])[0]['entry_mode']
        self.write(cr, uid, [ids[0]], {'entry_mode': mode=='percentage' and 'amount' or 'percentage'})
        return {
                'type': 'ir.actions.act_window',
                'res_model': self._name,
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'res_id': ids[0],
                'context': context,
        }

    def _get_lines_from_distribution(self, cr, uid, ids, distrib_id=None, context=None):
        """
        Get lines from a distribution and copy them to the wizard
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not distrib_id:
            raise osv.except_osv(_('Error'), _('No analytic distribution'))
        # Prepare some values
        ana_obj = self.pool.get('account.analytic.account')
        for wiz in self.browse(cr, uid, ids, context=context):
            distrib = self.pool.get('analytic.distribution').browse(cr, uid, distrib_id, context=context)
            # Retrieve Cost Center Lines values
            cc_obj = self.pool.get('analytic.distribution.wizard.lines')
            fp_obj = self.pool.get('analytic.distribution.wizard.fp.lines')
            for line in distrib.cost_center_lines:
                vals = {
                    'analytic_id': line.analytic_id and line.analytic_id.id or False,
                    'amount': (wiz.total_amount * line.percentage) / 100.0 or 0.0,
                    'percentage': line.percentage or 0.0,
                    'wizard_id': wiz.id,
                    'currency_id': line.currency_id and line.currency_id.id or False,
                    'distribution_line_id': line.id or False,
                    'destination_id': line.destination_id and line.destination_id.id or False,
                }
                new_line_id = cc_obj.create(cr, uid, vals, context=context)
                # update amount regarding percentage
                cc_obj.onchange_percentage(cr, uid, new_line_id, line.percentage, wiz.total_amount)
            # Retrieve all other elements if we come from a purchase (wizard.state == 'dispatch')
            if wiz.state == 'dispatch':
                # Prepare some values
                distrib_line_objects = {'funding.pool': 'fp'}
                # Browse all distribution lines
                for lines in [distrib.funding_pool_lines, distrib.free_1_lines, distrib.free_2_lines]:
                    for line in lines:
                        # Get line type. For an example 'funding.pool'
                        line_type = line._name and str(line._name).split('.distribution.line') and str(line._name).split('.distribution.line')[0] or False
                        if line_type:
                            # Contract line_type to have something like that: 'fp'
                            contraction = ''
                            for word in line_type.split('.'):
                                contraction += word and word[0] or ''
                            if contraction:
                                # Construct line obj. Example: 'analytic.distribution.wizard.fp.lines'
                                wiz_line_obj = '.'.join(['analytic.distribution.wizard', contraction, 'lines'])
                                vals = {
                                    'analytic_id': line.analytic_id and line.analytic_id.id or False,
                                    'amount': (wiz.total_amount * line.percentage) / 100.0 or 0.0,
                                    'percentage': line.percentage or 0.0,
                                    'wizard_id': wiz.id,
                                    'currency_id': line.currency_id and line.currency_id.id or False,
                                    'distribution_line_id': line.id or False,
                                    'destination_id': line.destination_id and line.destination_id.id or False,
                                }
                                # Add cost_center_id value if we come from a funding_pool object
                                if line_type == 'funding.pool':
                                    vals.update({'cost_center_id': line.cost_center_id and line.cost_center_id.id or False, })
                                self.pool.get(wiz_line_obj).create(cr, uid, vals, context=context)
            return True

    def create(self, cr, uid, vals, context=None):
        """
        Add distribution lines to the wizard
        """
        # Some verifications
        if not context:
            context = {}
        # Prepare some values
        res = super(analytic_distribution_wizard, self).create(cr, uid, vals, context=context)
        wiz = self.browse(cr, uid, [res], context=context)[0]
        if wiz.distribution_id:
            # Retrieve all lines
            self._get_lines_from_distribution(cr, uid, [wiz.id], wiz.distribution_id.id, context=context)
        return res

    def wizard_verifications(self, cr, uid, ids, context=None):
        """
        Do some verifications on wizard:
         - Raise an exception if we come from a purchase order that have been approved
         - Raise an exception if we come from an invoice that have been validated
         - Verify that all mandatory allocations have been done
         - Verify that all allocations have 100% from amount
        """
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        for wiz in self.browse(cr, uid, ids, context=context):
            # Verify that purchase is in good state if necessary
            if wiz.purchase_id and wiz.purchase_id.state in ['approved', 'done']:
                raise osv.except_osv(_('Error'), _('You cannot change the distribution.'))
            # Verify that purchase from purchase line is in good state if necessary
            if wiz.purchase_line_id and wiz.purchase_line_id.order_id and wiz.purchase_line_id.order_id.state in ['approved', 'done']:
                raise osv.except_osv(_('Error'), _('You cannot change the distribution.'))
            # Verify that invoice is in good state if necessary
            if wiz.invoice_id and wiz.invoice_id.state in ['open', 'paid']:
                raise osv.except_osv(_('Error'), _('You cannot change the distribution.'))
            # Verify that invoice from invoice line is in good state if necessary
            if wiz.invoice_line_id and wiz.invoice_line_id.invoice_id and wiz.invoice_line_id.invoice_id.state in ['open', 'paid']:
                raise osv.except_osv(_('Error'), _('You cannot change the distribution.'))
            # Verify that commitment is in good state if necessary
            if wiz.commitment_id and wiz.commitment_id.state in ['done']:
                raise osv.except_osv(_('Error'), _('You cannot change the distribution.'))
            if wiz.commitment_line_id and wiz.commitment_line_id.commit_id and wiz.commitment_line_id.commit_id.state in ['done']:
                raise osv.except_osv(_('Error'), _('You cannot change the distribution.'))
            # Verify that sale order is in good state if necessary
            if wiz.sale_order_id and wiz.sale_order_id.state in ['done', 'manual', 'progress', 'shipping_except', 'invoice_except']:
                raise osv.except_osv(_('Error'), _('You cannot change the distribution.'))
            # Verify that sale order from sale order line is in good state if we come from a purchase order
            if wiz.sale_order_line_id and wiz.sale_order_line_id.order_id and wiz.sale_order_line_id.order_id.state in ['done', 'manual', 'progress', 'shipping_except', 'invoice_except']:
                raise osv.except_osv(_('Error'), _('You cannot change the distribution.'))
            # Verify that Cost Center are done if we come from a purchase order
            if not wiz.line_ids and (wiz.purchase_id or wiz.purchase_line_id):
                raise osv.except_osv(_('Warning'), _('No Allocation done!'))
            # Verify that Funding Pool Lines are done if we come from an invoice, invoice line, direct invoice, direct invoice line, register line, 
            #+ move line, commitment or commitment line
            if not wiz.fp_line_ids and (wiz.invoice_id or wiz.invoice_line_id) :
                raise osv.except_osv(_('Warning'), _('No Allocation done!'))
            if not wiz.fp_line_ids and (wiz.direct_invoice_id or wiz.direct_invoice_line_id):
                raise osv.except_osv(_('Warning'), _('No Allocation done!'))
            if not wiz.fp_line_ids and wiz.register_line_id:
                raise osv.except_osv(_('Warning'), _('No Allocation done!'))
            if not wiz.fp_line_ids and wiz.move_line_id:
                raise osv.except_osv(_('Warning'), _('No Allocation done!'))
            if not wiz.fp_line_ids and (wiz.commitment_id or wiz.commitment_line_id):
                raise osv.except_osv(_('Warning'), _('No Allocation done!'))
            if not wiz.fp_line_ids and wiz.accrual_line_id:
                raise osv.except_osv(_('Warning'), _('No Allocation done!'))
            # Verify that allocation is 100% on each type of distribution, but only if there some lines
            for lines in [wiz.line_ids, wiz.fp_line_ids, wiz.f1_line_ids, wiz.f2_line_ids]:
                # Do nothing if there no lines for the current type
                if not lines:
                    continue
                # Verify that allocation is 100% on each type
                total = 0.0
                line_type = ''
                for line in lines:
                    total += line.percentage or 0.0
                    line_type = line.type
                if abs(total - 100.0) >= 10**-2:
                    # Fancy name for user
                    type_name = ' '.join([x.capitalize() for x in line_type.split('.')])
                    raise osv.except_osv(_('Warning'), _('Allocation is not fully done for %s') % type_name)
            return True

    def update_cost_center_lines(self, cr, uid, wizard_id, context=None):
        """
        Update cost_center_lines from wizard regarding funding pool lines
        """
        # Some verifications
        if not context:
            context = {}
        if not wizard_id:
            return False
        # Prepare some values
        wizard = self.browse(cr, uid, wizard_id, context=context)
        if not wizard:
            raise osv.except_osv(_('Warning'), _('No wizard found.'))
        # If no funding pool lines, raise an error, except when we come from a purchase order or a purchase order line ('cc' state)
        if not wizard.fp_line_ids and wizard.state == 'dispatch':
            raise osv.except_osv(_('Warning'), _('No allocation done.'))
        # If we come from 'cc' state, no need to update cost center lines
        elif not wizard.fp_line_ids and wizard.state == 'cc':
            return True
        # Process funding pool lines to retrieve cost centers and their total percentage
        cc_data = {}
        for line in wizard.fp_line_ids:
            if not cc_data.get(line.cost_center_id.id, False):
                cc_data[line.cost_center_id.id] = 0.0
            cc_data[line.cost_center_id.id] += line.percentage
        # Do update of cost center lines
        update_lines = [] # lines that have been updated
        cc_obj = self.pool.get('analytic.distribution.wizard.lines')
        for el in cc_data:
            res = False
            search_ids = cc_obj.search(cr, uid, [('analytic_id', '=', el), ('wizard_id', '=', wizard.id)], context=context)
            # Create a new entry if no one for this cost center
            if not search_ids:
                res = cc_obj.create(cr, uid, {'wizard_id': wizard.id, 'percentage': cc_data[el], 'type': 'cost.center',
                    'currency_id': wizard.currency_id and wizard.currency_id.id or False, 'analytic_id': el,}, context=context)
            # else change current cost center
            else:
                res = cc_obj.write(cr, uid, search_ids, {'percentage': cc_data[el]}, context=context)
            if res:
                update_lines.append(res)
        # Delete useless cost center lines
        for line_id in [x.id for x in wizard.line_ids]:
            if line_id not in update_lines:
                cc_obj.unlink(cr, uid, [line_id], context=context)
        return True

    def distrib_lines_to_list(self, cr, uid, distrib_ids, line_type=False):
        """
        Return a list containing distribution lines from first given distribution
        """
        # Some verifications
        if not distrib_ids:
            return False
        if isinstance(distrib_ids, (int, long)):
            distrib_ids = [distrib_ids]
        if not line_type:
            return False
        # Prepare some values
        db_line_type = '_'.join([line_type.replace('.', '_'), 'lines'])
        distrib = self.pool.get('analytic.distribution').browse(cr, uid, distrib_ids)[0]
        res = []
        for x in getattr(distrib, db_line_type, False):
            db_lines_vals = {
                'id': x.id,
                'distribution_id': x.distribution_id and x.distribution_id.id,
                'currency_id': x.currency_id and x.currency_id.id,
                'analytic_id': x.analytic_id and x.analytic_id.id,
                'percentage': x.percentage,
                'destination_id': x.destination_id and x.destination_id.id or False,
            }
            # Add cost_center_id field if we come from a funding.pool object
            if line_type == 'funding.pool':
                db_lines_vals.update({'cost_center_id': x.cost_center_id and x.cost_center_id.id or False, })
            res.append(db_lines_vals)
        return res

    def wizard_lines_to_list(self, cr, uid, ids, line_type=False):
        """
        Return a list containing distribution linked to given wizard
        """
        # Some verifications
        if not ids:
            return False
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not line_type:
            return False
        # Prepare some values
        res = []
        wizard = self.browse(cr, uid, ids)[0]
        wiz_line_types = {'cost.center': 'line_ids', 'funding.pool': 'fp_line_ids', 'free.1': 'f1_line_ids', 'free.2': 'f2_line_ids',}
        for x in getattr(wizard, wiz_line_types.get(line_type), False):
            wiz_lines_vals = {
                'id': x.distribution_line_id and x.distribution_line_id.id or False,
                'distribution_id': x.wizard_id.distribution_id and x.wizard_id.distribution_id.id,
                'currency_id': x.currency_id and x.currency_id.id,
                'analytic_id': x.analytic_id and x.analytic_id.id,
                'percentage': x.percentage,
                'destination_id': x.destination_id and x.destination_id.id or False,
            }
            # Add cost_center_id field if we come from a funding_pool object
            if line_type == 'funding.pool':
                wiz_lines_vals.update({'cost_center_id': x.cost_center_id and x.cost_center_id.id or False,})
            res.append(wiz_lines_vals)
        return res

    def compare_and_write_modifications(self, cr, uid, wizard_id, line_type=False, context=None):
        """
        Compare wizard lines to database lines and write modifications done
        """
        # Some verifications
        if not context:
            context = {}
        if not wizard_id:
            return False
        if not line_type:
            return False
        # Prepare some values
        wizard = self.browse(cr, uid, [wizard_id], context=context)[0]
        distrib = wizard.distribution_id
        line_obj_name = '.'.join([line_type, 'distribution.line']) # get something like "cost.center.distribution.line"
        line_obj = self.pool.get(line_obj_name)
        # Search database lines
        db_lines = self.distrib_lines_to_list(cr, uid, distrib.id, line_type)
        # Search wizard lines
        wiz_lines = self.wizard_lines_to_list(cr, uid, wizard_id, line_type)
        # Begin comparison process
        processed_line_ids = []
        # Delete wizard lines that have not changed
        for line in db_lines:
            if line in wiz_lines:
                wiz_lines.remove(line)
                processed_line_ids.append(line.get('id'))
        # Write changes for line that already exists
        for i in range(0,len(wiz_lines)):
            line = wiz_lines[i]
            if line.get('id', False) and line.get('id', False) in [x.get('id') for x in db_lines]:
                line_obj.write(cr, uid, line.get('id'), line, context=context)
                processed_line_ids.append(line.get('id'))
            else:
                vals = {
                    'analytic_id': line.get('analytic_id'),
                    'percentage': line.get('percentage'),
                    'distribution_id': distrib.id,
                    'currency_id': wizard.currency_id and wizard.currency_id.id,
                    'cost_center_id': line.get('cost_center_id') or False,
                    'destination_id': line.get('destination_id') or False,
                }
                new_line = line_obj.create(cr, uid, vals, context=context)
                processed_line_ids.append(new_line)
            wiz_lines[i] = None
        # Search lines that have been deleted
        search_ids = line_obj.search(cr, uid, [('distribution_id', '=', distrib.id)], context=context)
        for id in search_ids:
            if id not in processed_line_ids:
                line_obj.unlink(cr, uid, id, context=context)
        return True

    def button_confirm(self, cr, uid, ids, context=None):
        """
        Calculate total of lines and verify that it's equal to total_amount
        """
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        for wiz in self.browse(cr, uid, ids, context=context):
            # Then update cost center lines
            if not self.update_cost_center_lines(cr, uid, wiz.id, context=context):
                raise osv.except_osv(_('Error'), _('Cost center update failure.'))
            # First do some verifications before writing elements
            self.wizard_verifications(cr, uid, wiz.id, context=context)
            # And do distribution creation if necessary
            distrib_id = wiz.distribution_id and wiz.distribution_id.id or False
            if not distrib_id:
                # create a new analytic distribution
                distrib_id = self.pool.get('analytic.distribution').create(cr, uid, {}, context=context)
                # link it to the wizard
                self.write(cr, uid, [wiz.id], {'distribution_id': distrib_id,}, context=context)
                # link it to the element we come from (purchase order, invoice, purchase order line, invoice line, etc.)
                for el in [('invoice_id', 'account.invoice'), ('invoice_line_id', 'account.invoice.line'), ('purchase_id', 'purchase.order'), 
                    ('purchase_line_id', 'purchase.order.line'), ('register_line_id', 'account.bank.statement.line'), 
                    ('move_line_id', 'account.move.line'), ('direct_invoice_id', 'wizard.account.invoice'), 
                    ('direct_invoice_line_id', 'wizard.account.invoice.line'), ('commitment_id', 'account.commitment'), 
                    ('commitment_line_id', 'account.commitment.line'), ('model_line_id', 'account.model.line'),
                    ('accrual_line_id', 'msf.accrual.line'), ('sale_order_id', 'sale.order'), ('sale_order_line_id', 'sale.order.line')]:
                    if getattr(wiz, el[0], False):
                        id = getattr(wiz, el[0], False).id
                        self.pool.get(el[1]).write(cr, uid, [id], {'analytic_distribution_id': distrib_id}, context=context)
            # Finally do registration for each type
            for line_type in ['cost.center', 'funding.pool', 'free.1', 'free.2']:
                # Compare and write modifications done on analytic lines
                type_res = self.compare_and_write_modifications(cr, uid, wiz.id, line_type, context=context)
                # Create funding pool lines from CC lines if wizard is from PO/FO
                # PAY ATTENTION THAT break avoid problem that delete new created funding pool
                if line_type == 'cost.center' and wiz.state == 'cc' and (wiz.purchase_id or wiz.purchase_line_id):
                    fp_ids = self.pool.get('funding.pool.distribution.line').search(cr, uid, [('distribution_id', '=', distrib_id)])
                    if fp_ids:
                        self.pool.get('funding.pool.distribution.line').unlink(cr, uid, fp_ids)
                    account_id = wiz.account_id and wiz.account_id.id or False
                    self.pool.get('analytic.distribution').create_funding_pool_lines(cr, uid, distrib_id, account_id)
                    break
        # Return on direct invoice if we come from this one
        wiz = self.browse(cr, uid, ids, context=context)[0]
        if wiz and (wiz.direct_invoice_id or wiz.direct_invoice_line_id):
            # Get direct_invoice id
            direct_invoice_id = (wiz.direct_invoice_id and wiz.direct_invoice_id.id) or \
                (wiz.direct_invoice_line_id and wiz.direct_invoice_line_id.invoice_id.id) or False
            # Get register from which we come from
            direct_invoice = self.pool.get('wizard.account.invoice').browse(cr, uid, [direct_invoice_id], context=context)[0]
            register_id = direct_invoice and direct_invoice.register_id and direct_invoice.register_id.id or False
            if register_id:
                return {
                    'name': "Supplier Invoice",
                    'type': 'ir.actions.act_window',
                    'res_model': 'wizard.account.invoice',
                    'target': 'new',
                    'view_mode': 'form',
                    'view_type': 'form',
                    'res_id': direct_invoice_id,
                    'context':
                    {
                        'active_id': register_id,
                        'type': 'in_invoice',
                        'journal_type': 'purchase',
                        'active_ids': register_id,
                    }
                }
        # Update analytic lines
        self.update_analytic_lines(cr, uid, ids, context=context)
        
        return_wiz =  {'type': 'ir.actions.act_window_close'}
        if context.get("from_cash_return_analytic_dist"):
            # If the wizard was called from the cash return line, the perform some actions before returning back to the caller wizard
            wizard_name = context.get('from')
            wizard_id = context.get('wiz_id')
            cash_return_line_id = context.get('cash_return_line_id')
            
            distr_id = False
            if wiz and wiz.distribution_id and wiz.distribution_id.id: 
                distr_id = wiz.distribution_id.id
            # write the distribution analytic to this cash return line    
            self.pool.get('wizard.advance.line').write(cr, uid, [cash_return_line_id], {'analytic_distribution_id': distr_id}, context=context)
            return_wiz = {
                 'name': "Cash Return- Wizard",
                    'type': 'ir.actions.act_window',
                    'res_model': wizard_name,
                    'target': 'new',
                    'view_mode': 'form',
                    'view_type': 'form',
                    'res_id': wizard_id,
                    'context': context,
                 }

        return return_wiz

    def validate(self, cr, uid, wizard_id, context=None):
        """
        Calculate percentage and amount with round
        """
        wizard_obj = self.browse(cr, uid, wizard_id, context=context)
        company_currency = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id.id
        currency = wizard_obj.currency_id and wizard_obj.currency_id.id or company_currency
        # Create a temporary object to keep track of values
        sorted_wizard_lines = [{'id': x.id, 'amount': x.amount or 0.0, 'percentage': x.percentage or 0.0,} for x in wizard_obj.line_ids]
        # Re-evaluate all lines (to remove previous roundings)
        sorted_wizard_lines.sort(key=lambda x: x[wizard_obj.entry_mode], reverse=True)
        for wizard_line in sorted_wizard_lines:
            amount = 0.0
            percentage = 0.0
            if wizard_obj.entry_mode == 'percentage':
                percentage = wizard_line['percentage']
                # Check that the value is in the correct range
                if percentage < 0.0 or percentage > 100.0:
                    raise osv.except_osv(_('Percentage not valid!'),_("Percentage not valid!"))
                # Fill the other value
                amount = round(wizard_obj.total_amount * percentage) / 100.0
                wizard_line['amount'] = amount
            elif wizard_obj.entry_mode == 'amount':
                amount = wizard_line['amount']
                # Check that the value is in the correct range
                if abs(amount) > abs(wizard_obj.total_amount):
                    raise osv.except_osv(_('Amount not valid!'),_("Amount not valid!"))
                # Fill the other value
                percentage = 0
                if wizard_obj.total_amount:
                    percentage = abs(amount / wizard_obj.total_amount * 100.0)
                wizard_line['percentage'] = percentage
        # FIXME: do rounding
        # Writing values
        for wizard_line in sorted_wizard_lines:
            vals={
                'amount': wizard_line['amount'],
                'percentage': wizard_line['percentage'],
                'currency_id': currency,
            }
            self.pool.get('analytic.distribution.wizard.lines').write(cr, uid, [wizard_line.get('id')], vals, 
                context={'skip_validation': True})
        return True

    def button_get_header_distribution(self, cr, uid, ids, context=None):
        """
        Get distribution from invoice or purchase
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        object_type = None
        distrib = None
        for wiz in self.browse(cr, uid, ids, context=context):
            # Take distribution from invoice if we come from an invoice line
            if wiz.invoice_line_id:
                il = wiz.invoice_line_id
                distrib = il.invoice_id and il.invoice_id.analytic_distribution_id and il.invoice_id.analytic_distribution_id or False
            # Same thing for purchase order line
            elif wiz.purchase_line_id:
                pl = wiz.purchase_line_id
                distrib = pl.order_id and pl.order_id.analytic_distribution_id and pl.order_id.analytic_distribution_id or False
            elif wiz.commitment_line_id:
                pl = wiz.commitment_line_id
                distrib = pl.commit_id and pl.commit_id.analytic_distribution_id or False

            if distrib:
                # First delete all current lines
                self.pool.get('analytic.distribution.wizard.lines').unlink(cr, uid, [x.id for x in wiz.line_ids], context=context)
                self.pool.get('analytic.distribution.wizard.fp.lines').unlink(cr, uid, [x.id for x in wiz.fp_line_ids], context=context)
                self.pool.get('analytic.distribution.wizard.f1.lines').unlink(cr, uid, [x.id for x in wiz.f1_line_ids], context=context)
                self.pool.get('analytic.distribution.wizard.f2.lines').unlink(cr, uid, [x.id for x in wiz.f2_line_ids], context=context)
                # Then retrieve all lines
                self._get_lines_from_distribution(cr, uid, [wiz.id], distrib.id, context=context)
        return {
                'type': 'ir.actions.act_window',
                'res_model': self._name,
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'res_id': ids[0],
                'context': context,
        }

    def button_cancel(self, cr, uid, ids, context=None):
        """
        Close the wizard or return on Direct Invoice wizard if we come from this one.
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Retrieve some values to verify if we come from a direct invoice
        wiz = self.browse(cr, uid, ids, context=context)[0]
        if wiz and (wiz.direct_invoice_id or wiz.direct_invoice_line_id):
            # Get direct_invoice id
            direct_invoice_id = (wiz.direct_invoice_id and wiz.direct_invoice_id.id) or \
                (wiz.direct_invoice_line_id and wiz.direct_invoice_line_id.invoice_id.id) or False
            # Get register from which we come from
            direct_invoice = self.pool.get('wizard.account.invoice').browse(cr, uid, [direct_invoice_id], context=context)[0]
            register_id = direct_invoice and direct_invoice.register_id and direct_invoice.register_id.id or False
            if register_id:
                return {
                    'name': "Supplier Invoice",
                    'type': 'ir.actions.act_window',
                    'res_model': 'wizard.account.invoice',
                    'target': 'new',
                    'view_mode': 'form',
                    'view_type': 'form',
                    'res_id': direct_invoice_id,
                    'context':
                    {
                        'active_id': register_id,
                        'type': 'in_invoice',
                        'journal_type': 'purchase',
                        'active_ids': register_id,
                    }
                }
        return {'type' : 'ir.actions.act_window_close'}

    def update_analytic_lines(self, cr, uid, ids, context=None):
        """
        Update analytic lines with an ugly method: delete old lines and create new ones
        """
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Process all given wizards
        for wizard in self.browse(cr, uid, ids, context=context):
            # Prepare some values
            distrib = wizard.distribution_id or False
            aal_obj = self.pool.get('account.analytic.line')
            ml_obj = self.pool.get('account.move.line')
            if not distrib:
                return False
            if wizard.move_line_id:
                move_lines = [x.id for x in distrib.move_line_ids]
                # Search account analytic lines attached to this move lines
                operator = 'in'
                if len(move_lines) == 1:
                    operator = '='
                aal_ids = aal_obj.search(cr, uid, [('move_id', operator, move_lines)], context=context)
                if aal_ids:
                    # delete old analytic lines
                    aal_obj.unlink(cr, uid, aal_ids, context=context)
                    # create new analytic lines
                    ml_obj.create_analytic_lines(cr, uid, move_lines, context=context)
            elif wizard.commitment_line_id:
                # Do process only if commitment is on 'open' state
                if wizard.commitment_line_id.commit_id and wizard.commitment_line_id.commit_id.state == 'open':
                    self.pool.get('account.commitment.line').update_analytic_lines(cr, uid, [wizard.commitment_line_id.id], wizard.total_amount, context=context)
            elif wizard.commitment_id:
                if wizard.commitment_id.state == 'open':
                    # Search commitment lines that doesn't have any distribution and that are linked to this commitment
                    cl_ids = self.pool.get('account.commitment.line').search(cr, uid, [('commit_id', '=', wizard.commitment_id.id), 
                        ('analytic_distribution_id', '=', False)], context=context)
                    if cl_ids:
                        operator = 'in'
                        if len(cl_ids) == 1:
                            operator = '='
                        # Search all analytic lines linked to this commitment lines
                        aal_ids = aal_obj.search(cr, uid, [('commitment_line_id', operator, cl_ids)], context=context)
                        if aal_ids:
                            # delete old analytic lines
                            aal_obj.unlink(cr, uid, aal_ids, context=context)
                            # create new analytic lines
                            self.pool.get('account.commitment').create_analytic_lines(cr, uid, [wizard.commitment_id.id], context=context)
        return True

analytic_distribution_wizard()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
