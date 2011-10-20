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

class analytic_distribution_wizard_lines(osv.osv_memory):
    _name = 'analytic.distribution.wizard.lines'
    _description = 'analytic.distribution.wizard.lines'

    _columns = {
        'analytic_id': fields.many2one('account.analytic.account', string="Analytic account", required=True),
        'amount': fields.float(string="Amount"),
        'percentage': fields.float(string="Percentage", required=True),
        'wizard_id': fields.many2one('analytic.distribution.wizard', string="Analytic Distribution Wizard", required=True),
        'currency_id': fields.many2one('res.currency', string="Currency", required=True),
        'distribution_line_id': fields.many2one('distribution.line', string="Distribution Line"),
        'type': fields.selection([('cost.center', 'Cost Center Lines'), ('funding.pool', 'Funding Pool Lines'), ('free.1', 'Free 1 Lines'), 
            ('free.2', 'Free 2 Lines')], string="Line type", help="Specify the type of lines"), # Important for some method that take this values 
            #+ to construct object research !
    }

    _defaults = {
        'amount': lambda *a: 0.0,
        'percentage': lambda *a: 0.0,
        'type': lambda *a: 'cost.center',
    }

    def onchange_percentage(self, cr, uid, ids, percentage, total_amount):
        """
        Change amount regarding percentage
        """
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not percentage or not total_amount:
            return False
        amount = (total_amount * percentage) / 100
        return {'value': {'amount': amount}}

    def onchange_amount(self, cr, uid, ids, amount, total_amount):
        """
        Change percentage regarding amount
        """
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not amount or not total_amount:
            return False
        percentage = (amount / total_amount) * 100
        return {'value': {'percentage': percentage}}

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        """
        Rewrite view in order "entry_mode" works
        """
        if not context:
            context = {}
        view = super(analytic_distribution_wizard_lines, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)
        oc_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'analytic_distribution', 'analytic_account_project')[1]
        if view_type=='tree':
            tree = etree.fromstring(view['arch'])
            # Change OC field
            fields = tree.xpath('/tree/field[@name="analytic_id"]')
            for field in fields:
                field.set('domain', "[('type', '!=', 'view'), ('id', 'child_of', [%s])]" % oc_id)
            # Change percentage and amount field
            for el in ['percentage', 'amount']:
                new_fields = tree.xpath('/tree/field[@name="%s"]' % el)
                for field in new_fields:
                    field.set('readonly', str(context['mode'] != el))
                    if context['mode'] == el:
                        field.set('on_change', "onchange_%s(%s, parent.total_amount)" % (el, el))
            view['arch'] = etree.tostring(tree)
        return view

    def create(self, cr, uid, vals, context={}):
        """
        Calculate amount and percentage regarding context content
        """
        if not context:
            context = {}
        res = super(analytic_distribution_wizard_lines, self).create(cr, uid, vals, context=context)
        if vals.get('wizard_id', False) and not context.get('skip_validation', False):
            self.pool.get('analytic.distribution.wizard').validate(cr, uid, vals.get('wizard_id'), context=context)
        return res

    def write(self, cr, uid, ids, vals, context={}):
        """
        Calculate amount and percentage regarding context content
        """
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
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

analytic_distribution_wizard_fp_lines()

class analytic_distribution_wizard_f1_lines(osv.osv_memory):
    _name = 'analytic.distribution.wizard.f1.lines'
    _description = 'analytic.distribution.wizard.lines'
    _inherit = 'analytic.distribution.wizard.lines'

    _defaults = {
        'type': lambda *a: 'free.1',
    }

analytic_distribution_wizard_f1_lines()

class analytic_distribution_wizard_f2_lines(osv.osv_memory):
    _name = 'analytic.distribution.wizard.f2.lines'
    _description = 'analytic.distribution.wizard.lines'
    _inherit = 'analytic.distribution.wizard.lines'

    _defaults = {
        'type': lambda *a: 'free.2',
    }

analytic_distribution_wizard_f2_lines()

class analytic_distribution_wizard(osv.osv_memory):
    _name = 'analytic.distribution.wizard'
    _description = 'analytic.distribution.wizard'

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
        'invoice_id': fields.many2one('account.invoice', string="Invoice"),
        'distribution_id': fields.many2one('analytic.distribution', string="Analytic Distribution"),
    }

    _defaults = {
        'state': lambda *a: 'draft',
        'entry_mode': lambda *a: 'percentage',
    }

    def dummy(self, cr, uid, ids, context={}, *args, **kwargs):
        """
        Change entry mode
        """
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

    def create(self, cr, uid, vals, context={}):
        """
        Add distribution lines to the wizard
        """
        # Some verifications
        if not context:
            context = {}
        # Prepare some values
        ana_obj = self.pool.get('account.analytic.account')
        res = super(analytic_distribution_wizard, self).create(cr, uid, vals, context=context)
        wiz = self.browse(cr, uid, [res], context=context)[0]
        if wiz.distribution_id:
            distrib = self.pool.get('analytic.distribution').browse(cr, uid, wiz.distribution_id.id, context=context)
            # Retrieve Cost Center Lines values
            for line in distrib.cost_center_lines:
                vals = {
                    'analytic_id': line.analytic_id and line.analytic_id.id or False,
                    'amount': line.amount or 0.0,
                    'percentage': line.percentage or 0.0,
                    'wizard_id': wiz.id,
                    'currency_id': line.currency_id and line.currency_id.id or False,
                    'distribution_line_id': line.id or False,
                }
                self.pool.get('analytic.distribution.wizard.lines').create(cr, uid, vals, context=context)
                # Create funding pool lines if no one exists and that we come from an invoice (wizard.state == 'dispatch')
                if not distrib.funding_pool_lines and wiz.state == 'dispatch':
                    # Search MSF Private Fund
                    pf_id = self.pool.get('account.analytic.account').search(cr, uid, [('code', '=', 'PF'), ('category', '=', 'FUNDING')], context=context, limit=1)
                    if pf_id:
                        pf = ana_obj.browse(cr, uid, pf_id, context=context)[0]
                        vals.update({'analytic_id': pf.id, 'cost_center_id': line.analytic_id and line.analytic_id.id or False, 'type': 'funding.pool'})
                        self.pool.get('analytic.distribution.wizard.fp.lines').create(cr, uid, vals, context=context)
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
                                    'amount': line.amount or 0.0,
                                    'percentage': line.percentage or 0.0,
                                    'wizard_id': wiz.id,
                                    'currency_id': line.currency_id and line.currency_id.id or False,
                                    'distribution_line_id': line.id or False,
                                }
                                # Add cost_center_id value if we come from a funding_pool object
                                if line_type == 'funding.pool':
                                    vals.update({'cost_center_id': line.cost_center_id and line.cost_center_id.id or False})
                                self.pool.get(wiz_line_obj).create(cr, uid, vals, context=context)
        return res

    def wizard_verifications(self, cr, uid, ids, context={}):
        """
        Do some verifications on wizard:
         - Raise an exception if we come from a purchase order that have been approved 
        """
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        for wiz in self.browse(cr, uid, ids, context=context):
            # Verify that purchase is in good state if necessary
            if wiz.purchase_id and wiz.purchase_id.state in ['approved', 'done']:
                raise osv.except_osv(_('Error'), _('You cannot change the distribution.'))
            # Verify that invoice is in good state if necessary
            if wiz.invoice_id and wiz.invoice_id.state in ['open', 'paid']:
                raise osv.except_osv(_('Error'), _('You cannot change the distribution.'))
            # Verify that Cost Center are done
            if not wiz.line_ids:
                raise osv.except_osv(_('Warning'), _('No Cost Center Allocation done!'))
            if wiz.invoice_id and not wiz.fp_line_ids:
                raise osv.except_osv(_('Warning'), _('No Funding Pool Allocation done!'))
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
                if abs(total - 100.0) > 10**-4:
                    # Fancy name for user
                    type_name = ' '.join([x.capitalize() for x in line_type.split('.')])
                    raise osv.except_osv(_('Warning'), _('Allocation is not fully done for %s') % type_name)
            return True

    def compare_and_write_modifications(self, cr, uid, wizard_id, line_type=False, context={}):
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
        db_line_type = '_'.join([line_type.replace('.', '_'), 'lines'])
        wiz_line_types = {'cost.center': 'line_ids', 'funding.pool': 'fp_line_ids', 'free.1': 'f1_line_ids', 'free.2': 'f2_line_ids',}
        # Search database lines
        db_lines = []
        for x in getattr(distrib, db_line_type, False):
            db_lines_vals = {
                'id': x.id,
                'distribution_id': x.distribution_id and x.distribution_id.id,
                'currency_id': x.currency_id and x.currency_id.id,
                'analytic_id': x.analytic_id and x.analytic_id.id,
                'percentage': x.percentage,
            }
            # Add cost_center_id field if we come from a funding.pool object
            if line_type == 'funding.pool':
                db_lines_vals.update({'cost_center_id': x.cost_center_id and x.cost_center_id.id or False})
            db_lines.append(db_lines_vals)
        
        # Search wizard lines
        wiz_lines = []
        for x in getattr(wizard, wiz_line_types.get(line_type), False):
            wiz_lines_vals = {
                'id': x.distribution_line_id and x.distribution_line_id.id or False,
                'distribution_id': x.wizard_id.distribution_id and x.wizard_id.distribution_id.id,
                'currency_id': x.currency_id and x.currency_id.id,
                'analytic_id': x.analytic_id and x.analytic_id.id,
                'percentage': x.percentage,
            }
            # Add cost_center_id field if we come from a funding_pool object
            if line_type == 'funding.pool':
                wiz_lines_vals.update({'cost_center_id': x.cost_center_id and x.cost_center_id.id or False,})
            wiz_lines.append(wiz_lines_vals)
        
        processed_line_ids = []
        # Delete wizard lines that have not changed
        for line in db_lines:
            if line in wiz_lines:
                wiz_lines.remove(line)
                processed_line_ids.append(line.get('id'))
        if not wiz_lines:
            return False
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
                    'currency_id': line.get('currency_id'),
                    'cost_center_id': line.get('cost_center_id') or False,
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

    def button_confirm(self, cr, uid, ids, context={}):
        """
        Calculate total of lines and verify that it's equal to total_amount
        """
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        for wiz in self.browse(cr, uid, ids, context=context):
            self.wizard_verifications(cr, uid, wiz.id, context=context)
            # FIXME / TODO self.update_cost_center_lines
            
            # Then total of percentage for each type
            for lines in [wiz.line_ids, wiz.fp_line_ids, wiz.f1_line_ids, wiz.f2_line_ids]:
                total = 0.0
                for line in lines:
                    total += line.percentage or 0.0
                if abs(total - 100.0) > 10**-4 and lines:
                    raise osv.except_osv(_('Not fully allocated !'),_("You have to allocate the whole amount!"))
                # Get lines type in order to launch a comparison between database lines and wizard lines
                line_type = lines and lines[0] and lines[0].type or False
                if line_type:
                    # Compare and write modifications done on analytic lines
                    res = self.compare_and_write_modifications(cr, uid, wiz.id, line_type, context=context)
                    # If no result raise an error
                    if not res:
                        # but only on cost center if we come from a purchase, and only on funding pool, free 1 and free 2 if we come from an invoice
                        if (wiz.purchase_id and line_type == 'cost.center') or (wiz.invoice_id and line_type in ['funding.pool', 'free.1', 'free.2']):
                            raise osv.except_osv(_('Error'), _('No modification seen!'))
        return {'type': 'ir.actions.act_window_close'}

    def validate(self, cr, uid, wizard_id, context=None):
        """
        Calculate percentage and amount with round
        """
        wizard_obj = self.browse(cr, uid, wizard_id, context=context)
        company_currency = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id.id
        currency = wizard_obj.currency_id and wizard_obj.currency_id.id or company_currency
        # Create a temporary object to keep track of values
        sorted_wizard_lines = [{'id': x.id, 'amount': x.amount, 'percentage': x.percentage} for x in wizard_obj.line_ids]
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
                if amount < 0.0 or amount > wizard_obj.total_amount:
                    raise osv.except_osv(_('Amount not valid!'),_("Amount not valid!"))
                # Fill the other value
                percentage = round(amount * 10**4 / wizard_obj.total_amount) / 100.0
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

analytic_distribution_wizard()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
