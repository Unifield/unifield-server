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
    
class wizard_costcenter_distribution_line(osv.osv_memory):
    _name="wizard.costcenter.distribution.line"
    
    _columns = {
        'name': fields.char('Name', size=16, required=True), #required by one2many, never used
        "wizard_id": fields.many2one('wizard.costcenter.distribution', 'Associated Wizard'),
        "analytic_id": fields.many2one('account.analytic.account', 'Cost Center', required=True),
        "percentage": fields.float('Percentage'),
        "amount": fields.float('Amount'),
    }
    
    _defaults ={
        'name': 'CC Line', #required by one2many, never used
        'percentage': 0.0,
        'amount': 0.0
    }
    
    def create(self, cr, uid, vals, context=None):
        res = super(wizard_costcenter_distribution_line, self).create(cr, uid, vals, context=context)
        if 'wizard_id' in vals:
            if 'skip_validation' not in context or context['skip_validation'] == False:
                self.pool.get('wizard.costcenter.distribution').validate(cr, uid, vals['wizard_id'], context=context)
        return res
    
    def write(self, cr, uid, ids, vals, context=None):
        res = super(wizard_costcenter_distribution_line, self).write(cr, uid, ids, vals, context=context)
        # retrieve the wizard_id field from first line
        if len(ids) > 0:
            if 'skip_validation' not in context or context['skip_validation'] == False:
                line_obj = self.browse(cr, uid, ids[0])
                self.pool.get('wizard.costcenter.distribution').validate(cr, uid, line_obj.wizard_id.id, context=context)
        return res
    
wizard_costcenter_distribution_line()


class wizard_costcenter_distribution(osv.osv_memory):
    _name="wizard.costcenter.distribution"
    
    def _get_initial_lines(self, cr, uid, wizard_id, context=None):
        wizard_obj = self.browse(cr, uid, wizard_id, context=context)
        distrib_obj = self.pool.get('analytic.distribution').browse(cr, uid, wizard_obj.distribution_id.id, context=context)
        for cost_center_line in distrib_obj.cost_center_lines:
            wizard_line_vals = {
                'name': 'Cost Center Line', #required by one2many, never used
                'wizard_id': wizard_id,
                'analytic_id': cost_center_line.analytic_id.id,
                'amount': cost_center_line.amount,
                'percentage': cost_center_line.percentage,
            }
            self.pool.get('wizard.costcenter.distribution.line').create(cr, uid, wizard_line_vals, context=context)
        return
    
    def _cleanup_and_store(self, cr, uid, wizard_id, context=None):
        wizard_obj = self.browse(cr, uid, wizard_id, context=context)
        cc_distrib_line_obj = self.pool.get('cost_center_distribution_line')
        fp_distrib_line_obj = self.pool.get('funding_pool_distribution_line')
        f1_distrib_line_obj = self.pool.get('free_1_distribution_line')
        f2_distrib_line_obj = self.pool.get('free_2_distribution_line')
        distrib_obj = self.pool.get('analytic.distribution')
        # first, distribution is not derived from a global one; the flag is set
        distrib_id = wizard_obj.distribution_id.id
        distrib_obj.write(cr, uid, [distrib_id], vals={'global_distribution': False}, context=context)
        distrib = distrib_obj.browse(cr, uid, distrib_id, context=context)
        # remove old lines
        for cost_center_line in distrib.cost_center_lines:
            cc_distrib_line_obj.unlink(cr, uid, cost_center_line.id)
        for funding_pool_line in distrib.funding_pool_lines:
            fp_distrib_line_obj.unlink(cr, uid, funding_pool_line.id)
        for free_1_line in distrib.free_1_lines:
            f1_distrib_line_obj.unlink(cr, uid, free_1_line.id)
        for free_2_line in distrib.free_2_lines:
            f2_distrib_line_obj.unlink(cr, uid, free_2_line.id)
        # and save the new lines in the distribution
        for wizard_line in wizard_obj.wizard_distribution_lines:
            distrib_line_vals = {
                'name': wizard_line.name,
                'analytic_id': wizard_line.analytic_id.id,
                'amount': wizard_line.amount,
                'percentage': wizard_line.percentage,
                'distribution_id': wizard_obj.distribution_id.id
            }
            cc_distrib_line_obj.create(cr, uid, distrib_line_vals, context=context)
        # if there are child distributions, we refresh them
        if 'child_distributions' in context:
            for child in context['child_distributions']:
                distrib_obj.copy_from_global_distribution(cr,
                                                          uid,
                                                          distrib_id,
                                                          child[0],
                                                          child[1],
                                                          context=context)
        return
    
    _columns = {
        "entry_mode": fields.selection([('percent','Percentage'),
                                        ('amount','Amount')], 'Entry Mode', select=1),
        "total_amount": fields.float("Total amount to be allocated"),
        "distribution_id": fields.many2one("analytic.distribution", string='Analytic Distribution'),
        "wizard_distribution_lines": fields.one2many("wizard.costcenter.distribution.line", "wizard_id", string='Wizard Lines'),
        "modified_line": fields.boolean('Was a line modified')
    }
    
    _defaults = {  
        'entry_mode': 'percent',
        'modified_line': False
    }
    
    def create(self, cr, uid, vals, context={}):
        wizard_id = super(wizard_costcenter_distribution, self).create(cr, uid, vals, context=context)
        self._get_initial_lines(cr, uid, wizard_id, context=context)
        self.write(cr, uid, [wizard_id], vals={'modified_line': False}, context=context)
        return wizard_id
    
    def validate(self, cr, uid, wizard_id, context=None):
        allocated_amount = 0.0
        allocated_percentage = 0.0
        wizard_obj = self.browse(cr, uid, wizard_id, context=context)
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
            self.pool.get('wizard.costcenter.distribution.line').write(cr,
                                                                       uid,
                                                                       [wizard_line['id']],
                                                                       vals={'amount': wizard_line['amount'],
                                                                             'percentage': wizard_line['percentage']},
                                                                       context={'skip_validation': True})
        return
            
    def button_next_step(self, cr, uid, ids, context={}):
        # check if the allocation is fully done
        allocated_percentage = 0.0
        wizard_obj = self.browse(cr, uid, ids[0], context=context)
        for wizard_line in wizard_obj.wizard_distribution_lines:
            allocated_percentage += wizard_line.percentage
        if abs(allocated_percentage - 100.0) > 10**-4:
            raise osv.except_osv(_('Not fully allocated !'),_("You have to allocate the whole amount!"))
        if wizard_obj.modified_line:
            self._cleanup_and_store(cr, uid, ids[0], context=context)
        # and we open the following state
        newwiz_obj = self.pool.get('wizard.fundingpool.distribution')
        newwiz_id = newwiz_obj.create(cr, uid, {'total_amount': wizard_obj.total_amount, 'distribution_id': wizard_obj.distribution_id.id}, context=context)
        # we open a wizard
        return {
                'type': 'ir.actions.act_window',
                'res_model': 'wizard.fundingpool.distribution',
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'res_id': [newwiz_id],
                'context': {
                    'active_id': context.get('active_id'),
                    'active_ids': context.get('active_ids'),
                    'child_distributions': context.get('child_distributions'),
               }
        }
    
wizard_costcenter_distribution()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
