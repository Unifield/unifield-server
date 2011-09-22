# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO Consulting.
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

from osv import fields, osv
import tools
from tools.translate import _
import decimal_precision as dp

# This code is shared across all wizards,
# since all matters of inheritance won't work
    
class wizard_free1_distribution_line(osv.osv_memory):
    _name="wizard.free1.distribution.line"

    _columns = {
        'name': fields.char('Name', size=16, required=True), #required by one2many, never used
        "wizard_id": fields.many2one('wizard.free1.distribution', 'Associated Wizard'),
        "analytic_id": fields.many2one('account.analytic.account', 'Free Allocation', required=True),
        "percentage": fields.float('Percentage'),
        "amount": fields.float('Amount'),
        'currency_id': fields.many2one('res.currency', string="Currency"),
    }

    _defaults ={
        'name': 'Free1 Line', #required by one2many, never used
        'percentage': 0.0,
        'amount': 0.0
    }

    def create(self, cr, uid, vals, context=None):
        res = super(wizard_free1_distribution_line, self).create(cr, uid, vals, context=context)
        if 'wizard_id' in vals:
            if 'skip_validation' not in context or context['skip_validation'] == False:
                self.pool.get('wizard.free1.distribution').validate(cr, uid, vals['wizard_id'], context=context)
        return res
    
    def write(self, cr, uid, ids, vals, context=None):
        res = super(wizard_free1_distribution_line, self).write(cr, uid, ids, vals, context=context)
        # retrieve the wizard_id field from first line
        if len(ids) > 0:
            if 'skip_validation' not in context or context['skip_validation'] == False:
                line_obj = self.browse(cr, uid, ids[0])
                self.pool.get('wizard.free1.distribution').validate(cr, uid, line_obj.wizard_id.id, context=context)
        return res

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        if not context:
            context = {}
        view = super(wizard_free1_distribution_line, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)
        if view_type=='tree' and context.get('mode'):
            view['arch'] = """<tree string="" editable="top">
    <field name="analytic_id"/>
    <field name="percentage" sum="Total Percentage" readonly="%s"/>
    <field name="amount" sum="Total Amount" readonly="%s"/>
</tree>"""%(context['mode']=='amount', context['mode']=='percent')
        return view

wizard_free1_distribution_line()

class wizard_free1_distribution(osv.osv_memory):
    _name="wizard.free1.distribution"
    _inherit="wizard.distribution"
    
    def _get_initial_lines(self, cr, uid, wizard_id, context=None):
        wizard_obj = self.browse(cr, uid, wizard_id, context=context)
        distrib_obj = self.pool.get('analytic.distribution').browse(cr, uid, wizard_obj.distribution_id.id, context=context)
        company_currency = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id.id
        for free_1_line in distrib_obj.free_1_lines:
            wizard_line_vals = {
                'name': 'Free 1 Line', #required by one2many, never used
                'wizard_id': wizard_id,
                'analytic_id': free_1_line.analytic_id.id,
                'amount': free_1_line.amount,
                'percentage': free_1_line.percentage,
                'currency_id': free_1_line.currency_id and free_1_line.currency_id.id or company_currency,
            }
            self.pool.get('wizard.free1.distribution.line').create(cr, uid, wizard_line_vals, context=context)
        return
    
    _columns = {
        "entry_mode": fields.selection([('percent','Percentage'),
                                        ('amount','Amount')], 'Entry Mode', select=1, readonly=True),
        "wizard_distribution_lines": fields.one2many("wizard.free1.distribution.line", "wizard_id", string='Wizard Lines'),
        "modified_line": fields.boolean('Was a line modified')
    }
    
    _defaults = {  
        'entry_mode': 'percent',
        'modified_line': False
    }
    
    def create(self, cr, uid, vals, context={}):
        wizard_id = super(wizard_free1_distribution, self).create(cr, uid, vals, context=context)
        self._get_initial_lines(cr, uid, wizard_id, context=context)
        self.write(cr, uid, [wizard_id], vals={'modified_line': False}, context=context)
        return wizard_id
    
    def validate(self, cr, uid, wizard_id, context=None):
        allocated_amount = 0.0
        allocated_percentage = 0.0
        wizard_obj = self.browse(cr, uid, wizard_id, context=context)
        company_currency = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id.id
        currency = wizard_obj.currency_id and wizard_obj.currency_id.id or company_currency
        # Something was written; we modify the flag in the wizard
        self.write(cr, uid, [wizard_id], vals={'modified_line': True}, context={})
        # Create a temporary object to keep track of values
        sorted_wizard_lines = []
        for wizard_line in wizard_obj.wizard_distribution_lines:
            sorted_wizard_lines.append({'id': wizard_line.id,
                                        'amount': wizard_line.amount,
                                        'percentage': wizard_line.percentage,
                                        })
        # Re-evaluate all lines (to remove previous roundings)
        if wizard_obj.entry_mode == 'percent':
            sorted_wizard_lines.sort(key=lambda x: x['percentage'], reverse=True)
        elif wizard_obj.entry_mode == 'amount':
            sorted_wizard_lines.sort(key=lambda x: x['amount'], reverse=True)
        for wizard_line in sorted_wizard_lines:
            amount = 0.0
            percentage = 0.0
            if wizard_obj.entry_mode == 'percent':
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
            allocated_amount += amount
            allocated_percentage += percentage
        # Rounding
        if len(sorted_wizard_lines) >= 2:
            if wizard_obj.entry_mode == 'amount' and abs(100.0 - allocated_percentage) > 10**-4 and abs(wizard_obj.total_amount - allocated_amount) < 10**-4:
                # percentage is not correct, but amounts are; we round the second-biggest percentage
                line_to_be_balanced = sorted_wizard_lines[0]
                line_to_be_balanced['percentage'] += 100.0 - allocated_percentage
            elif wizard_obj.entry_mode == 'percent' and abs(100.0 - allocated_percentage) < 10**-4 and abs(wizard_obj.total_amount - allocated_amount) > 10**-4:
                line_to_be_balanced = sorted_wizard_lines[0]
                line_to_be_balanced['amount'] += wizard_obj.total_amount - allocated_amount
                
        # Writing values
        for wizard_line in sorted_wizard_lines:
            self.pool.get('wizard.free1.distribution.line').write(cr,
                                                                  uid,
                                                                  [wizard_line['id']],
                                                                  vals={'amount': wizard_line['amount'],
                                                                        'percentage': wizard_line['percentage'],
                                                                        'currency_id': currency},
                                                                  context={'skip_validation': True})
        return
            
    def button_previous_step(self, cr, uid, ids, context={}):
        # and we open the previous state
        if 'funding_pool' not in context['wizard_ids']:
            # we should never be there
            raise osv.except_osv(_('Previous wizard missing!'),_("Previous wizard missing!"))
        # we open a wizard
        return {
                'type': 'ir.actions.act_window',
                'res_model': 'wizard.fundingpool.distribution',
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'res_id': [context['wizard_ids']['funding_pool']],
                'context': context
        }
            
    def button_next_step(self, cr, uid, ids, context={}):
        # check if the allocation is fully done
        allocated_percentage = 0.0
        wizard_obj = self.browse(cr, uid, ids[0], context=context)
        company_currency = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id.id
        currency = wizard_obj.currency_id and wizard_obj.currency_id.id or company_currency
        for wizard_line in wizard_obj.wizard_distribution_lines:
            allocated_percentage += wizard_line.percentage
        if abs(allocated_percentage - 100.0) > 10**-4:
            raise osv.except_osv(_('Not fully allocated !'),_("You have to allocate the whole amount!"))
        if 'free_2' not in context['wizard_ids']:
            newwiz_obj = self.pool.get('wizard.free2.distribution')
            newwiz_id = newwiz_obj.create(cr, uid, {'total_amount': wizard_obj.total_amount, 'distribution_id': wizard_obj.distribution_id.id,
                'currency_id': currency, 'entry_mode': wizard_obj.entry_mode, 'invoice_line': wizard_obj.invoice_line and wizard_obj.invoice_line.id or False}, context=context)
            context['wizard_ids']['free_2'] = newwiz_id
        else:
            # Write some change to the wizard:
            # - entry_mode
            self.pool.get('wizard.free2.distribution').write(cr, uid, [context['wizard_ids']['free_2']], 
                {'entry_mode': wizard_obj.entry_mode}, context=context)
        # we open a wizard
        return {
                'type': 'ir.actions.act_window',
                'res_model': 'wizard.free2.distribution',
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'res_id': [context['wizard_ids']['free_2']],
                'context': context
        }

    def button_save(self, cr, uid, ids, context={}):
        # check if the allocation is fully done
        allocated_percentage = 0.0
        wizard_obj = self.browse(cr, uid, ids[0], context=context)
        for wizard_line in wizard_obj.wizard_distribution_lines:
            allocated_percentage += wizard_line.percentage
        if abs(allocated_percentage - 100.0) > 10**-4:
            raise osv.except_osv(_('Not fully allocated !'),_("You have to allocate the whole amount!"))
        # First save distribution
        self.store_distribution(cr, uid, ids[0], context=context)
        # then update analytic lines
        self.update_analytic_lines(cr, uid, ids, context=context)
        # finally open the following state with another abstract method
        return {'type': 'ir.actions.act_window_close'}

    def button_cancel(self, cr, uid, ids, context={}):
        """
        Close the wizard
        """
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        return {'type' : 'ir.actions.act_window_close'}

wizard_free1_distribution()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
