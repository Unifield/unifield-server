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

class wizard_distribution(osv.osv_memory):
    _name="wizard.distribution"
    
    _columns = {
        "total_amount": fields.float("Total amount to be allocated"),
        "distribution_id": fields.many2one("analytic.distribution", string='Analytic Distribution'),
        "currency_id": fields.many2one('res.currency', string="Currency"),
        "invoice_line": fields.many2one("account.invoice.line", "Invoice Line"),
    }

    def dummy(self, cr, uid, ids, context={}, *args, **kwargs):
        mode = self.read(cr, uid, ids, ['entry_mode'])[0]['entry_mode']
        self.write(cr, uid, [ids[0]], {'entry_mode': mode=='percent' and 'amount' or 'percent'})
        return {
                'type': 'ir.actions.act_window',
                'res_model': self._name,
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'res_id': ids[0],
                'context': context,
        }

    def store_distribution(self, cr, uid, wizard_id, date=False, source_date=False, context=None):
        wizard_obj = self.browse(cr, uid, wizard_id, context=context)
        distrib_obj = self.pool.get('analytic.distribution')
        distrib_id = wizard_obj.distribution_id.id
        distrib_obj.write(cr, uid, [distrib_id], vals={'global_distribution': False}, context=context)
        distrib = distrib_obj.browse(cr, uid, distrib_id, context=context)
        company_currency = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id.id
        if 'wizard_ids' in context:
            if 'cost_center' in context['wizard_ids']:
                cc_wizard_obj = self.pool.get('wizard.costcenter.distribution').browse(cr, uid, context['wizard_ids']['cost_center'], context=context)
                cc_distrib_line_obj = self.pool.get('cost.center.distribution.line')
                # remove old lines
                for cc_distrib_line in distrib.cost_center_lines:
                    cc_distrib_line_obj.unlink(cr, uid, cc_distrib_line.id)
                # and save the new lines in the distribution
                for cc_wizard_line in cc_wizard_obj.wizard_distribution_lines:
                    distrib_line_vals = {
                        'name': cc_wizard_line.name,
                        'analytic_id': cc_wizard_line.analytic_id.id,
                        'amount': cc_wizard_line.amount,
                        'percentage': cc_wizard_line.percentage,
                        'distribution_id': distrib_id,
                        'currency_id': wizard_obj.currency_id.id,
                    }
                    if source_date:
                        distrib_line_vals.update({'source_date': source_date})
                    if date:
                        distrib_line_vals.update({'date': date})
                    cc_distrib_line_obj.create(cr, uid, distrib_line_vals, context=context)
            if 'funding_pool' in context['wizard_ids']:
                fp_wizard_obj = self.pool.get('wizard.fundingpool.distribution').browse(cr, uid, context['wizard_ids']['funding_pool'], context=context)
                fp_distrib_line_obj = self.pool.get('funding.pool.distribution.line')
                # remove old lines
                for fp_distrib_line in distrib.funding_pool_lines:
                    fp_distrib_line_obj.unlink(cr, uid, fp_distrib_line.id)
                # and save the new lines in the distribution
                for fp_wizard_line in fp_wizard_obj.wizard_distribution_lines:
                    distrib_line_vals = {
                        'name': fp_wizard_line.name,
                        'analytic_id': fp_wizard_line.analytic_id.id,
                        'cost_center_id': fp_wizard_line.cost_center_id.id,
                        'amount': fp_wizard_line.amount,
                        'percentage': fp_wizard_line.percentage,
                        'distribution_id': distrib_id,
                        'currency_id': wizard_obj.currency_id.id,
                    }
                    if source_date:
                        distrib_line_vals.update({'source_date': source_date})
                    if date:
                        distrib_line_vals.update({'date': date})
                    fp_distrib_line_obj.create(cr, uid, distrib_line_vals, context=context)
            if 'free_1' in context['wizard_ids']:
                f1_wizard_obj = self.pool.get('wizard.free1.distribution').browse(cr, uid, context['wizard_ids']['free_1'], context=context)
                f1_distrib_line_obj = self.pool.get('free.1.distribution.line')
                # remove old lines
                for f1_distrib_line in distrib.free_1_lines:
                    f1_distrib_line_obj.unlink(cr, uid, f1_distrib_line.id)
                # and save the new lines in the distribution
                for f1_wizard_line in f1_wizard_obj.wizard_distribution_lines:
                    distrib_line_vals = {
                        'name': f1_wizard_line.name,
                        'analytic_id': f1_wizard_line.analytic_id.id,
                        'amount': f1_wizard_line.amount,
                        'percentage': f1_wizard_line.percentage,
                        'distribution_id': distrib_id,
                        'currency_id': wizard_obj.currency_id.id,
                    }
                    if source_date:
                        distrib_line_vals.update({'source_date': source_date})
                    if date:
                        distrib_line_vals.update({'date': date})
                    f1_distrib_line_obj.create(cr, uid, distrib_line_vals, context=context)
            if 'free_2' in context['wizard_ids']:
                f2_wizard_obj = self.pool.get('wizard.free2.distribution').browse(cr, uid, context['wizard_ids']['free_2'], context=context)
                f2_distrib_line_obj = self.pool.get('free.2.distribution.line')
                # remove old lines
                for f2_distrib_line in distrib.free_2_lines:
                    f2_distrib_line_obj.unlink(cr, uid, f2_distrib_line.id)
                # and save the new lines in the distribution
                for f2_wizard_line in f2_wizard_obj.wizard_distribution_lines:
                    distrib_line_vals = {
                        'name': f2_wizard_line.name,
                        'analytic_id': f2_wizard_line.analytic_id.id,
                        'amount': f2_wizard_line.amount,
                        'percentage': f2_wizard_line.percentage,
                        'distribution_id': distrib_id,
                        'currency_id': wizard_obj.currency_id.id,
                    }
                    if source_date:
                        distrib_line_vals.update({'source_date': source_date})
                    if date:
                        distrib_line_vals.update({'date': date})
                    f2_distrib_line_obj.create(cr, uid, distrib_line_vals, context=context)
            # if there are child distributions, we refresh them
            if 'child_distributions' in context and context['child_distributions']:
                for child in context['child_distributions']:
                    distrib_obj.copy_from_global_distribution(cr, uid, distrib_id, child[0], child[1], wizard_obj.currency_id.id, context=context)
        return

    def update_analytic_lines(self, cr, uid, ids, context={}):
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
            move_lines = [x.id for x in distrib.move_line_ids]
            aal_obj = self.pool.get('account.analytic.line')
            ml_obj = self.pool.get('account.move.line')
            if not distrib:
                return False
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

            if not move_lines and wizard.invoice_line:
                wizard.invoice_line.create_engagement_lines()
        return True

wizard_distribution()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
