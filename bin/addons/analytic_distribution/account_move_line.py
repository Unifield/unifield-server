# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO consulting
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
from tools.translate import _


class account_move_line(osv.osv):
    _inherit = 'account.move.line'

    def _display_analytic_button(self, cr, uid, ids, name, args, context=None):
        """
        Return True for all element that correspond to some criteria:
         - The journal entry state is draft (unposted)
         - The account is analytic-a-holic
        """
        res = {}
        for ml in self.browse(cr, uid, ids, context=context):
            res[ml.id] = True
            # False if account not anlaytic-a-holic
            if not ml.account_id.is_analytic_addicted:
                res[ml.id] = False
        return res

    def _get_distribution_state(self, cr, uid, ids, name, args, context=None):
        """
        Get state of distribution:
         - if compatible with the move line, then "valid"
         - if no distribution, take a tour of move distribution, if compatible, then "valid"
         - if no distribution on move line and move, then "none"
         - all other case are "invalid"
        """
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        # Prepare some values
        res = {}
        distrib_obj = self.pool.get('analytic.distribution')
        sql = """
            SELECT aml.id, aml.analytic_distribution_id AS distrib_id, m.analytic_distribution_id AS move_distrib_id, aml.account_id, 
            aml.document_date, aml.date, m.status, aml.amount_currency
            FROM account_move_line AS aml, account_move AS m
            WHERE aml.move_id = m.id
            AND aml.id IN %s
            ORDER BY aml.id;"""
        cr.execute(sql, (tuple(ids),))
        for line in cr.fetchall():
            manual = line[6] == 'manu'
            amount = False
            if manual or context.get('from_correction'):  # in the standard JE view check amount only for manual entries
                amount = line[7]
            res[line[0]] = distrib_obj._get_distribution_state(cr, uid, line[1], line[2], line[3], doc_date=line[4],
                                                               posting_date=line[5], manual=manual, amount=amount)
        return res

    def _have_analytic_distribution_from_header(self, cr, uid, ids, name, arg, context=None):
        """
        If move have an analytic distribution, return False, else return True
        """
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        res = {}
        for ml in self.browse(cr, uid, ids, context=context):
            res[ml.id] = True
            if ml.analytic_distribution_id:
                res[ml.id] = False
        return res

    def _get_distribution_state_recap(self, cr, uid, ids, name, arg, context=None):
        """
        Get a recap from analytic distribution state and if it come from header or not.
        """
        if isinstance(ids, int):
            ids = [ids]
        res = {}
        get_sel = self.pool.get('ir.model.fields').get_browse_selection
        for ml in self.browse(cr, uid, ids):
            res[ml.id] = ''
            from_header = ''
            if ml.have_analytic_distribution_from_header:
                from_header = _(' (from header)')
            d_state = get_sel(cr, uid, ml, 'analytic_distribution_state', context)
            res[ml.id] = "%s%s" % (d_state, from_header)
            # Do not show any recap for non analytic-a-holic accounts
            if ml.account_id and not ml.account_id.is_analytic_addicted:
                res[ml.id] = ''
        return res

    _columns = {
        'analytic_distribution_id': fields.many2one('analytic.distribution', 'Analytic Distribution'),
        'display_analytic_button': fields.function(_display_analytic_button, method=True, string='Display analytic button?', type='boolean', readonly=True,
                                                   help="This informs system that we can display or not an analytic button", store=False),
        'analytic_distribution_state': fields.function(_get_distribution_state, method=True, type='selection',
                                                       selection=[('none', 'None'), ('valid', 'Valid'),
                                                                  ('invalid', 'Invalid'), ('invalid_small_amount', 'Invalid')],
                                                       string="Distribution state", help="Informs from distribution state among 'none', 'valid', 'invalid."),
        'have_analytic_distribution_from_header': fields.function(_have_analytic_distribution_from_header, method=True, type='boolean',
                                                                  string='Header Distrib.?'),
        'analytic_distribution_state_recap': fields.function(_get_distribution_state_recap, method=True, type='char', size=30,
                                                             string="Distribution",
                                                             help="Informs you about analaytic distribution state among 'none', 'valid', 'invalid', from header or not, or no analytic distribution"),
    }

    #def create_analytic_lines(self, cr, uid, ids, context=None):
    # method moved to bin/addons/account/account_move_line.py

    def unlink(self, cr, uid, ids, context=None, check=True):
        """
        Delete analytic lines before unlink move lines.
        Update Manual Journal Entries.
        """
        if context is None:
            context = {}
        move_obj = self.pool.get('account.move')
        if context.get('sync_update_execution'):
            # US-836: no need to cascade actions in sync context
            # AJI deletion and JE validation are sync'ed
            moves = [aml.move_id.id for aml in self.browse(cr, uid, ids, fields_to_fetch=['move_id'], context=context)]
            res = super(account_move_line, self).unlink(cr, uid, ids, context=context, check=False)
            # US-3963 1) re-trigger the computation that ensures the move is balanced in case of a small diff in the converted amounts
            reconcile_set = set()
            move_set = set(moves)
            reconcile_set.update(move_obj.balance_move(cr, uid, list(move_set), context=context))
            # 2) adapt the amounts of the related FXAs accordingly
            if reconcile_set:
                self.reconciliation_update(cr, uid, list(reconcile_set), context=context)
            # 3) validate the moves
            move_obj.validate_sync(cr, uid, list(move_set), context=context)
            return res
        move_ids = []
        if ids:
            # Search manual moves to revalidate
            sql = """
                SELECT m.id
                FROM account_move_line AS ml, account_move AS m
                WHERE ml.move_id = m.id
                AND m.status = 'manu'
                AND ml.id IN %s
                GROUP BY m.id
                ORDER BY m.id;"""
            cr.execute(sql, (tuple(ids),))
            move_ids += [x and x[0] for x in cr.fetchall()]
        # Search analytic lines
        ana_ids = self.pool.get('account.analytic.line').search(cr, uid, [('move_id', 'in', ids)], context=context)
        self.pool.get('account.analytic.line').unlink(cr, uid, ana_ids, context=context)
        res = super(account_move_line, self).unlink(cr, uid, ids, context=context, check=check) #ITWG-84: Pass also the check flag to the super!
        # Revalidate move
        # US-3251 exclude moves about to be deleted
        moves_to_validate = [move_id for move_id in move_ids if move_id not in context.get('move_ids_to_delete', [])]
        move_obj.validate(cr, uid, moves_to_validate, context=context)
        return res

    def button_analytic_distribution(self, cr, uid, ids, context=None):
        """
        Launch analytic distribution wizard on an move line
        """
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        if not ids:
            raise osv.except_osv(_('Error'), _('No journal item given. Please save your line before.'))
        # Prepare some values
        ml = self.browse(cr, uid, ids[0], context=context)
        amount = ml.debit_currency - ml.credit_currency
        # Search elements for currency
        company_currency = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id.id
        currency = ml.currency_id and ml.currency_id.id or company_currency
        # Get analytic distribution id from this line
        distrib_id = ml and ml.analytic_distribution_id and ml.analytic_distribution_id.id or False
        # Prepare values for wizard
        vals = {
            'total_amount': amount,
            'move_line_id': ml.id,
            'currency_id': currency or False,
            'state': 'dispatch',
            'account_id': ml.account_id and ml.account_id.id or False,
            'posting_date': ml.date,
            'document_date': ml.document_date,
        }
        if distrib_id:
            vals.update({'distribution_id': distrib_id,})
        # Create the wizard
        wiz_obj = self.pool.get('analytic.distribution.wizard')
        wiz_id = wiz_obj.create(cr, uid, vals, context=context)
        # Update some context values
        context.update({
            'active_id': ids[0],
            'active_ids': ids,
        })
        # Open it!
        return {
            'name': _('Analytic distribution'),
            'type': 'ir.actions.act_window',
            'res_model': 'analytic.distribution.wizard',
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'res_id': [wiz_id],
            'context': context,
        }

    def _check_employee_analytic_distribution(self, cr, uid, ids, context=None):
        """
        Check that analytic distribution could be retrieved from given employee.
        If not employee, return True.
        """
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        ad_obj = self.pool.get('analytic.distribution')
        aml_duplication = '__copy_data_seen' in context and 'account.move.line' in context['__copy_data_seen'] or False
        from_duplication = context.get('copy', False) or aml_duplication
        if context.get('from_je_import', False) or from_duplication:
            return True
        for l in self.browse(cr, uid, ids):
            # Next line if this one comes from a non-manual move (journal entry) or an imported one
            if l.move_id.status != 'manu' or l.move_id.imported:
                continue
            # Do not continue if no employee or no cost center (could not be invented)
            if not l.employee_id or not l.employee_id.cost_center_id:
                continue
            if l.account_id and l.account_id.is_analytic_addicted:
                vals = {'cost_center_id': l.employee_id.cost_center_id.id}
                if l.employee_id.destination_id:
                    if ad_obj.check_gl_account_destination_compatibility(cr, uid, l.account_id.id, l.employee_id.destination_id.id):
                        vals.update({'destination_id': l.employee_id.destination_id.id})
                    else:
                        vals.update({'destination_id': l.account_id.default_destination_id.id})
                if l.employee_id.funding_pool_id:
                    vals.update({'analytic_id': l.employee_id.funding_pool_id.id})
                    use_default_pf = False
                    if not ad_obj.check_fp_cc_compatibility(cr, uid, l.employee_id.funding_pool_id.id, l.employee_id.cost_center_id.id,
                                                            context=context):
                        use_default_pf = True
                    elif 'destination_id' in vals and not ad_obj.check_fp_acc_dest_compatibility(cr, uid, l.employee_id.funding_pool_id.id,
                                                                                                 l.account_id.id, vals['destination_id'],
                                                                                                 context=context):
                        use_default_pf = True
                    if use_default_pf:
                        # Fetch default funding pool: MSF Private Fund
                        try:
                            msf_fp_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'analytic_distribution', 'analytic_account_msf_private_funds')[1]
                        except ValueError:
                            msf_fp_id = 0
                        vals.update({'analytic_id': msf_fp_id})
                # Create analytic distribution
                if 'cost_center_id' in vals and 'analytic_id' in vals and 'destination_id' in vals:
                    to_change = False

                    ad = l.analytic_distribution_id
                    if not ad:
                        to_change = True
                    elif l.employee_id.free1_id and (not ad.free_1_lines or len(ad.free_1_lines) or ad.free_1_lines[0].account_id.id != l.employee_id.free1_id.id):
                        to_change = True
                    elif l.employee_id.free2_id and (not ad.free_2_lines or len(ad.free_2_lines) or ad.free_2_lines[0].account_id.id != l.employee_id.free2_id.id):
                        to_change = True
                    elif not ad.funding_pool_lines or len(ad.funding_pool_lines) != 1:
                        to_change = True
                    elif ad.funding_pool_lines[0].destination_id.id != vals['destination_id'] or \
                            ad.funding_pool_lines[0].analytic_id.id != vals['analytic_id'] or \
                            ad.funding_pool_lines[0].cost_center_id.id != vals['cost_center_id']:
                        to_change = True

                    if to_change:
                        distrib_id = ad_obj.create(cr, uid, {'name': 'check_employee_analytic_distribution'}, context=context)
                        vals.update({'distribution_id': distrib_id, 'percentage': 100.0, 'currency_id': l.currency_id.id})
                        # Create funding pool lines
                        self.pool.get('funding.pool.distribution.line').create(cr, uid, vals)
                        # Then cost center lines
                        vals.update({'analytic_id': vals.get('cost_center_id'),})
                        self.pool.get('cost.center.distribution.line').create(cr, uid, vals)
                        # finally free1 and free2
                        if l.employee_id.free1_id:
                            self.pool.get('free.1.distribution.line').create(cr, uid, {'distribution_id': distrib_id, 'percentage': 100.0, 'currency_id': l.currency_id.id, 'analytic_id': l.employee_id.free1_id.id})
                        if l.employee_id.free2_id:
                            self.pool.get('free.2.distribution.line').create(cr, uid, {'distribution_id': distrib_id, 'percentage': 100.0, 'currency_id': l.currency_id.id, 'analytic_id': l.employee_id.free2_id.id})
                        if context.get('from_write', False):
                            return {'analytic_distribution_id': distrib_id}
                        # Write analytic distribution on the move line
                        self.pool.get('account.move.line').write(cr, uid, [l.id], {'analytic_distribution_id': distrib_id}, check=False, update_check=False)
                else:
                    return False
        return True

    def create(self, cr, uid, vals, context=None, check=True):
        """
        Check analytic distribution for employee (if given)
        """
        res = super(account_move_line, self).create(cr, uid, vals, context, check)
        self._check_employee_analytic_distribution(cr, uid, res, context)
        return res

    def write(self, cr, uid, ids, vals, context=None, check=True, update_check=True):
        """
        Check line if we come from web (from_web_menu)
        """
        if not ids:
            return True
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        if context.get('from_web_menu', False):
            res = []
            for ml in self.browse(cr, uid, ids):
                distrib_state = self.pool.get('analytic.distribution')._get_distribution_state(cr, uid, ml.analytic_distribution_id.id,
                                                                                               ml.move_id and ml.move_id.analytic_distribution_id and ml.move_id.analytic_distribution_id.id or False,
                                                                                               vals.get('account_id') or ml.account_id.id,
                                                                                               doc_date=ml.document_date, posting_date=ml.date, manual=ml.move_id.status=='manu')
                if distrib_state in ['invalid', 'none']:
                    vals.update({'state': 'draft'})
                # Add account_id because of an error with account_activable module for checking date
                if not 'account_id' in vals and 'date' in vals:
                    vals.update({'account_id': ml.account_id and ml.account_id.id or False})
                tmp_res = super(account_move_line, self).write(cr, uid, [ml.id], vals, context, False, False)
                res.append(tmp_res)
            return res
        res = super(account_move_line, self).write(cr, uid, ids, vals, context, check, update_check)
        return res

    def copy(self, cr, uid, aml_id, default=None, context=None):
        """
        Copy analytic_distribution
        """
        # Some verifications
        if context is None:
            context = {}
        if default is None:
            default = {}
        # Default method
        res = super(account_move_line, self).copy(cr, uid, aml_id, default, context)
        # Update analytic distribution
        if res:
            c = self.browse(cr, uid, res, context=context)
        if res and c.analytic_distribution_id:
            new_distrib_id = self.pool.get('analytic.distribution').copy(cr, uid, c.analytic_distribution_id.id, {}, context=context)
            if new_distrib_id:
                self.write(cr, uid, [res], {'analytic_distribution_id': new_distrib_id}, context=context)
        return res

    def get_analytic_move_lines(self, cr, uid, ids, context=None):
        """
        Return FP analytic lines attached to move lines
        """
        # Some verifications
        if context is None:
            context = {}
        if 'active_ids' in context:
            ids = context.get('active_ids')
        if isinstance(ids, int):
            ids = [ids]
        # Search valid ids
        domain = [('move_id', 'in', ids), ('account_id.category', '=', 'FUNDING')]
        context.update({'display_fp': True})
        return {
            'name': _('Analytic lines (FP) from Journal Items'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.analytic.line',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'context': context,
            'domain': domain,
            'target': 'current',
        }

    def get_analytic_move_free1_lines(self, cr, uid, ids, context=None):
        """
        Return FREE1 analytic lines attached to move lines
        """
        # Some verifications
        if context is None:
            context = {}
        if 'active_ids' in context:
            ids = context.get('active_ids')
        if isinstance(ids, int):
            ids = [ids]
        # Search valid ids
        domain = [('move_id', 'in', ids), ('account_id.category', '=', 'FREE1')]
        context.update({'display_fp': False, 'categ': 'FREE1'})
        return {
            'name': _('Analytic Lines (Free 1) from Journal Items'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.analytic.line',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'context': context,
            'domain': domain,
            'target': 'current',
        }

    def get_analytic_move_free2_lines(self, cr, uid, ids, context=None):
        """
        Return FREE2 analytic lines attached to move lines
        """
        # Some verifications
        if context is None:
            context = {}
        if 'active_ids' in context:
            ids = context.get('active_ids')
        if isinstance(ids, int):
            ids = [ids]
        # Search valid ids
        domain = [('move_id', 'in', ids), ('account_id.category', '=', 'FREE2')]
        context.update({'display_fp': False, 'categ': 'FREE2'})
        return {
            'name': _('Analytic Lines (Free 2) from Journal Items'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.analytic.line',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'context': context,
            'domain': domain,
            'target': 'current',
        }

account_move_line()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
