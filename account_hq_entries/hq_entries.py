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
from time import strftime
from tools.translate import _
from lxml import etree
import netsvc

class hq_entries_validation_wizard(osv.osv_memory):
    _name = 'hq.entries.validation.wizard'

    def create_move(self, cr, uid, ids, period_id=False, currency_id=False, date=None):
        """
        Create a move with given hq entries lines
        Return created lines (except counterpart lines)
        """
        # Some verifications
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not period_id:
            raise osv.except_osv(_('Error'), _('Period is missing!'))
        if not currency_id:
            raise osv.except_osv(_('Error'), _('Currency is missing!'))
        if not date:
            date = strftime('%Y-%m-%d')
        # Prepare some values
        res = {}
        counterpart_account_id = self.pool.get('res.users').browse(cr, uid, uid).company_id.counterpart_hq_entries_default_account and \
            self.pool.get('res.users').browse(cr, uid, uid).company_id.counterpart_hq_entries_default_account.id or False
        if not counterpart_account_id:
            raise osv.except_osv(_('Warning'), _('Default counterpart for HQ Entries is not set. Please configure it to Company Settings.'))

        private_fund_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'analytic_distribution', 'analytic_account_msf_private_funds')[1]
        if ids:
            # prepare some values
            journal_ids = self.pool.get('account.journal').search(cr, uid, [('type', '=', 'hq'),
                                                                            ('is_current_instance', '=', True)])
            if not journal_ids:
                raise osv.except_osv(_('Warning'), _('No HQ journal found!'))
            journal_id = journal_ids[0]
            # create move
            move_id = self.pool.get('account.move').create(cr, uid, {
                'date': date,
                'document_date': date,
                'journal_id': journal_id,
                'period_id': period_id,
            })
            total_debit = 0
            total_credit = 0
            
            # Check if document_date is the same as all lines
            for line in self.pool.get('hq.entries').read(cr, uid, ids, ['date', 'free_1_id', 'free_2_id', 'name', 'amount', 'account_id_first_value', 
                'cost_center_id_first_value', 'analytic_id', 'partner_txt', 'cost_center_id', 'account_id', 'destination_id', 'document_date', 
                'destination_id_first_value', 'ref']):
                account_id = line.get('account_id_first_value', False) and line.get('account_id_first_value')[0] or False
                if not account_id:
                    raise osv.except_osv(_('Error'), _('An account is missing!'))
                account = self.pool.get('account.account').browse(cr, uid, account_id)
                # create new distribution (only for non-counterpart accounts)
                distrib_id = False
                cc_id = line.get('cost_center_id_first_value', False) and line.get('cost_center_id_first_value')[0] or (line.get('cost_center_id') and line.get('cost_center_id')[0]) or False
                fp_id = line.get('analytic_id', False) and line.get('analytic_id')[0] or False
                if line['cost_center_id'] != line['cost_center_id_first_value'] or line['account_id_first_value'] != line['account_id']:
                    fp_id = private_fund_id
                f1_id = line.get('free_1_id', False) and line.get('free_1_id')[0] or False
                f2_id = line.get('free_2_id', False) and line.get('free_2_id')[0] or False
                destination_id = (line.get('destination_id_first_value') and line.get('destination_id_first_value')[0]) or (account.default_destination_id and account.default_destination_id.id) or False
                distrib_id = self.pool.get('analytic.distribution').create(cr, uid, {})
                if distrib_id:
                    common_vals = {
                        'distribution_id': distrib_id,
                        'currency_id': currency_id,
                        'percentage': 100.0,
                        'date': line.get('date', False) or current_date,
                        'source_date': line.get('date', False) or current_date,
                        'destination_id': destination_id,
                    }
                    common_vals.update({'analytic_id': cc_id,})
                    self.pool.get('cost.center.distribution.line').create(cr, uid, common_vals)
                    common_vals.update({'analytic_id': fp_id, 'cost_center_id': cc_id})
                    self.pool.get('funding.pool.distribution.line').create(cr, uid, common_vals)
                    del common_vals['cost_center_id']
                    del common_vals['destination_id']
                    if f1_id:
                        common_vals.update({'analytic_id': f1_id,})
                        self.pool.get('free.1.distribution.line').create(cr, uid, common_vals)
                    if f2_id:
                        common_vals.update({'analytic_id': f2_id})
                        self.pool.get('free.2.distribution.line').create(cr, uid, common_vals)
                vals = {
                    'account_id': account_id,
                    'period_id': period_id,
                    'journal_id': journal_id,
                    'date': line.get('date'),
                    'date_maturity': line.get('date'),
                    'document_date': line.get('document_date'),
                    'move_id': move_id,
                    'analytic_distribution_id': distrib_id,
                    'name': line.get('name', ''),
                    'currency_id': currency_id,
                    'partner_txt': line.get('partner_txt', ''),
                    'reference': line.get('ref', '')
                }
                # Fetch debit/credit
                debit = 0.0
                credit = 0.0
                amount = line.get('amount', 0.0)
                if amount < 0.0:
                    credit = abs(amount)
                else:
                    debit = abs(amount)
                vals.update({'debit_currency': debit, 'credit_currency': credit,})
                move_line_id = self.pool.get('account.move.line').create(cr, uid, vals, context={}, check=False)
                res[line['id']] = move_line_id
                # Increment totals
                total_debit += debit
                total_credit += credit
            # counterpart line
            counterpart_vals = {}
            account_ids = self.pool.get('account.account').search(cr, uid, [('id', '=', counterpart_account_id)])
            if account_ids:
                counterpart_vals.update({'account_id': account_ids[0],})
            # vals
            counterpart_vals.update({
                'period_id': period_id,
                'journal_id': journal_id,
                'move_id': move_id,
                'date': date,
                'date_maturity': date,
                'document_date': date,
                'name': 'HQ Entry Counterpart',
                'currency_id': currency_id,
            })
            counterpart_debit = 0.0
            counterpart_credit = 0.0
            if (total_debit - total_credit) < 0:
                counterpart_debit = abs(total_debit - total_credit)
            else:
                counterpart_credit = abs(total_debit - total_credit)
            counterpart_vals.update({'debit_currency': counterpart_debit, 'credit_currency': counterpart_credit,})
            self.pool.get('account.move.line').create(cr, uid, counterpart_vals, context={}, check=False)
            # Post move
            self.pool.get('account.move').post(cr, uid, [move_id])
        return res

    def validate(self, cr, uid, ids, context=None):
        """
        Validate all given lines (in context)
        """
        # Some verifications
        if not context or not context.get('active_ids', False):
            return False
        active_ids = context.get('active_ids')
        if isinstance(active_ids, (int, long)):
            active_ids = [active_ids]
        # Fetch some data
        ana_line_obj = self.pool.get('account.analytic.line')
        distrib_fp_line_obj = self.pool.get('funding.pool.distribution.line')
        distrib_cc_line_obj = self.pool.get('cost.center.distribution.line')
        # Search an analytic correction journal
        acor_journal_id = False
        acor_journal_ids = self.pool.get('account.analytic.journal').search(cr, uid, [('type', '=', 'correction'),
                                                                                      ('is_current_instance', '=', True)])
        if acor_journal_ids:
            acor_journal_id = acor_journal_ids[0]
        # Tag active_ids as user validated
        to_write = {}
        account_change = []
        cc_change = []
        cc_account_change = []
        current_date = strftime('%Y-%m-%d')
        for line in self.pool.get('hq.entries').browse(cr, uid, active_ids, context=context):
            #UF-1956: interupt validation if currency is inactive
            if line.currency_id.active is False:
                raise osv.except_osv(_('Warning'), _('Currency %s is not active!') % (line.currency_id and line.currency_id.name or '',))
            if line.analytic_state != 'valid':
                raise osv.except_osv(_('Warning'), _('Invalid analytic distribution!'))
            if not line.user_validated:
                to_write.setdefault(line.currency_id.id, {}).setdefault(line.period_id.id, {}).setdefault(line.date, []).append(line.id)

                if line.account_id.id != line.account_id_first_value.id:
                    if line.cost_center_id.id != line.cost_center_id_first_value.id or line.destination_id.id != line.destination_id_first_value.id:
                        cc_account_change.append(line)
                    else:
                        account_change.append(line)
                elif line.cost_center_id.id != line.cost_center_id_first_value.id or line.destination_id.id != line.destination_id_first_value.id:
                    if line.cost_center_id_first_value and line.cost_center_id_first_value.id:
                        cc_change.append(line)
        all_lines = {}
        for currency in to_write:
            for period in to_write[currency]:
                for date in to_write[currency][period]:
                    lines = to_write[currency][period][date]
                    write = self.create_move(cr, uid, lines, period, currency, date)
                    all_lines.update(write)
                    if write:
                        self.pool.get('hq.entries').write(cr, uid, write.keys(), {'user_validated': True}, context=context)

        for line in account_change:
            corrected_distrib_vals = {
                'funding_pool_lines': [(0, 0, {
                    'percentage': 100,
                    'analytic_id': line.analytic_id.id,
                    'cost_center_id': line.cost_center_id.id,
                    'currency_id': line.currency_id.id,
                    'source_date': line.date,
                    'destination_id': line.destination_id.id,
                })]
            }
            # Add Free 1 and Free 2 analytic axis if exists in HQ Lines
            if line.free_1_id:
                corrected_distrib_vals.update({
                    'free_1_lines': [(0, 0, {
                        'percentage': 100,
                        'analytic_id': line.free_1_id.id,
                        'currency_id': line.currency_id.id,
                        'source_date': line.date,
                    })],
                })
            if line.free_2_id:
                corrected_distrib_vals.update({
                    'free_2_lines': [(0, 0, {
                        'percentage': 100,
                        'analytic_id': line.free_2_id.id,
                        'currency_id': line.currency_id.id,
                        'source_date': line.date,
                    })],
                })
            corrected_distrib_id = self.pool.get('analytic.distribution').create(cr, uid, corrected_distrib_vals)
            self.pool.get('account.move.line').correct_account(cr, uid, all_lines[line.id], current_date, line.account_id.id, corrected_distrib_id)

        for line in cc_change:
            # actual distrib_id
            distrib_id = self.pool.get('account.move.line').read(cr, uid, all_lines[line.id], ['analytic_distribution_id'])['analytic_distribution_id'][0]
            # update the distribution
            distrib_fp_lines = distrib_fp_line_obj.search(cr, uid, [('cost_center_id', '=', line.cost_center_id_first_value.id), ('distribution_id', '=', distrib_id)])
            distrib_fp_line_obj.write(cr, uid, distrib_fp_lines, {'cost_center_id': line.cost_center_id.id, 'source_date': line.date, 'destination_id': line.destination_id.id})
            distrib_cc_lines = distrib_cc_line_obj.search(cr, uid, [('analytic_id', '=', line.cost_center_id_first_value.id), ('distribution_id', '=', distrib_id)])
            distrib_cc_line_obj.write(cr, uid, distrib_cc_lines, {'analytic_id': line.cost_center_id.id, 'source_date': line.date, 'destination_id': line.destination_id.id})

            # reverse ana lines
            fp_old_lines = ana_line_obj.search(cr, uid, [
                ('cost_center_id', '=', line.cost_center_id_first_value.id),
                ('destination_id', '=', line.destination_id_first_value.id),
                ('move_id', '=', all_lines[line.id])
                ])
            # UTP-943: Add original date as reverse date
            res_reverse = ana_line_obj.reverse(cr, uid, fp_old_lines, posting_date=line.date)
            # Give them analytic correction journal (UF-1385 in comments)
            if not acor_journal_id:
                raise osv.except_osv(_('Warning'), _('No analytic correction journal found!'))
            ana_line_obj.write(cr, uid, res_reverse, {'journal_id': acor_journal_id})
            # create new lines
            if not fp_old_lines: # UTP-546 - this have been added because of sync that break analytic lines generation
                continue
            cor_ids = ana_line_obj.copy(cr, uid, fp_old_lines[0], {'date': current_date, 'source_date': line.date, 'cost_center_id': line.cost_center_id.id, 
                'account_id': line.analytic_id.id, 'destination_id': line.destination_id.id, 'journal_id': acor_journal_id, 'last_correction_id': fp_old_lines[0]})
            # update new ana line
            ana_line_obj.write(cr, uid, cor_ids, {'last_corrected_id': fp_old_lines[0]})
            # update old ana lines
            ana_line_obj.write(cr, uid, fp_old_lines, {'is_reallocated': True})

        for line in cc_account_change:
            # call correct_account with a new arg: new_distrib
            new_distrib_vals = {
                'cost_center_lines': [(0, 0, {
                    'percentage': 100, 
                    'analytic_id': line.cost_center_id.id,
                    'currency_id': line.currency_id.id,
                    'source_date': line.date,
                    'destination_id': line.destination_id.id,
                })],
                'funding_pool_lines': [(0, 0, {
                    'percentage': 100,
                    'analytic_id': line.analytic_id.id,
                    'cost_center_id': line.cost_center_id.id,
                    'currency_id': line.currency_id.id,
                    'source_date': line.date,
                    'destination_id': line.destination_id.id,
                })]
            }
            # Add Free 1 and Free 2 if exists
            if line.free_1_id:
                new_distrib_vals.update({
                    'free_1_lines': [(0, 0, {
                        'percentage': 100,
                        'analytic_id': line.free_1_id.id,
                        'currency_id': line.currency_id.id,
                        'source_date': line.date,
                    })],
                })
            if line.free_2_id:
                new_distrib_vals.update({
                    'free_2_lines': [(0, 0, {
                        'percentage': 100,
                        'analytic_id': line.free_2_id.id,
                        'currency_id': line.currency_id.id,
                        'source_date': line.date,
                    })],
                })
            corrected_distrib_id = self.pool.get('analytic.distribution').create(cr, uid, new_distrib_vals)
            self.pool.get('account.move.line').correct_account(cr, uid, all_lines[line.id], current_date, line.account_id.id, corrected_distrib_id)

        # Return HQ Entries Tree View in current view
        action_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'account_hq_entries', 'action_hq_entries_tree')
        res = self.pool.get('ir.actions.act_window').read(cr, uid, action_id[1], [], context=context)
        res['target'] = 'crush'
        return res

hq_entries_validation_wizard()

class hq_entries(osv.osv):
    _name = 'hq.entries'
    _description = 'HQ Entries'

    def _get_analytic_state(self, cr, uid, ids, name, args, context=None):
        """
        Get state of distribution:
         - if compatible with the line, then "valid"
         - all other case are "invalid"
        """
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Prepare some values
        res = {}
        logger = netsvc.Logger()
        # Search MSF Private Fund element, because it's valid with all accounts
        try:
            fp_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'analytic_distribution', 
            'analytic_account_msf_private_funds')[1]
        except ValueError:
            fp_id = 0
        # Browse all given lines to check analytic distribution validity
        ## TO CHECK:
        # A/ if no CC
        # B/ if FP = MSF Private FUND
        # C/ (account/DEST) in FP except B
        # D/ CC in FP except when B
        # E/ DEST in list of available DEST in ACCOUNT
        # F/ Check posting date with cost center and destination if exists
        # G/ Check document date with funding pool
        ## CASES where FP is filled in (or not) and/or DEST is filled in (or not).
        ## CC is mandatory, so always available:
        # 1/ no FP, no DEST => Distro = valid
        # 2/ FP, no DEST => Check D except B
        # 3/ no FP, DEST => Check E
        # 4/ FP, DEST => Check C, D except B, E
        ## 
        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = 'valid' # by default
            #### SOME CASE WHERE DISTRO IS OK
            # if account is not expense, so it's valid
            if line.account_id and line.account_id.user_type_code and line.account_id.user_type_code != 'expense':
                continue
            # Date checks
            # F Check
            if line.cost_center_id:
                cc = self.pool.get('account.analytic.account').browse(cr, uid, line.cost_center_id.id, context={'date': line.date})
                if cc and cc.filter_active is False:
                    res[line.id] = 'invalid'
                    logger.notifyChannel('account_hq_entries', netsvc.LOG_WARNING, _('%s: inactive CC (%s)') % (line.id or '', cc.code or ''))
                    continue
            if line.destination_id:
                dest = self.pool.get('account.analytic.account').browse(cr, uid, line.destination_id.id, context={'date': line.date})
                if dest and dest.filter_active is False:
                    res[line.id] = 'invalid'
                    logger.notifyChannel('account_hq_entries', netsvc.LOG_WARNING, _('%s: inactive DEST (%s)') % (line.id or '', dest.code or ''))
                    continue
            # G Check
            if line.analytic_id:
                fp = self.pool.get('account.analytic.account').browse(cr, uid, line.analytic_id.id, context={'date': line.document_date})
                if fp and fp.filter_active is False:
                    res[line.id] = 'invalid'
                    logger.notifyChannel('account_hq_entries', netsvc.LOG_WARNING, _('%s: inactive FP (%s)') % (line.id or '', fp.code or ''))
                    continue
            # if just a cost center, it's also valid! (CASE 1/)
            if not line.analytic_id and not line.destination_id:
                continue
            # if FP is MSF Private Fund and no destination_id, then all is OK.
            if line.analytic_id and line.analytic_id.id == fp_id and not line.destination_id:
                continue
            #### END OF CASES
            if not line.cost_center_id:
                res[line.id] = 'invalid'
                logger.notifyChannel('account_hq_entries', netsvc.LOG_WARNING, _('%s: No CC') % (line.id or ''))
                continue
            if line.analytic_id and not line.destination_id: # CASE 2/
                # D Check, except B check
                if line.cost_center_id.id not in [x.id for x in line.analytic_id.cost_center_ids] and line.analytic_id.id != fp_id:
                    res[line.id] = 'invalid'
                    logger.notifyChannel('account_hq_entries', netsvc.LOG_WARNING, _('%s: CC (%s) not found in FP (%s)') % (line.id or '', line.cost_center_id.code or '', line.analytic_id.code or ''))
                    continue
            elif not line.analytic_id and line.destination_id: # CASE 3/
                # E Check
                account = self.pool.get('account.account').browse(cr, uid, line.account_id.id)
                if line.destination_id.id not in [x.id for x in account.destination_ids]:
                    res[line.id] = 'invalid'
                    logger.notifyChannel('account_hq_entries', netsvc.LOG_WARNING, _('%s: DEST (%s) not compatible with account (%s)') % (line.id or '', line.destination_id.code or '', account.code or ''))
                    continue
            else: # CASE 4/
                # C Check, except B
                if (line.account_id.id, line.destination_id.id) not in [x.account_id and x.destination_id and (x.account_id.id, x.destination_id.id) for x in line.analytic_id.tuple_destination_account_ids] and line.analytic_id.id != fp_id:
                    res[line.id] = 'invalid'
                    logger.notifyChannel('account_hq_entries', netsvc.LOG_WARNING, _('%s: Tuple Account/DEST (%s/%s) not found in FP (%s)') % (line.id or '', line.account_id.code or '', line.destination_id.code or '', line.analytic_id.code or ''))
                    continue
                # D Check, except B check
                if line.cost_center_id.id not in [x.id for x in line.analytic_id.cost_center_ids] and line.analytic_id.id != fp_id:
                    res[line.id] = 'invalid'
                    logger.notifyChannel('account_hq_entries', netsvc.LOG_WARNING, _('%s: CC (%s) not found in FP (%s)') % (line.id or '', line.cost_center_id.code or '', line.analytic_id.code or ''))
                    continue
                # E Check
                account = self.pool.get('account.account').browse(cr, uid, line.account_id.id)
                if line.destination_id.id not in [x.id for x in account.destination_ids]:
                    res[line.id] = 'invalid'
                    logger.notifyChannel('account_hq_entries', netsvc.LOG_WARNING, _('%s: DEST (%s) not compatible with account (%s)') % (line.id or '', line.destination_id.code or '', account.code or ''))
                    continue
        return res

    _columns = {
        'account_id': fields.many2one('account.account', "Account", required=True),
        'destination_id': fields.many2one('account.analytic.account', string="Destination", required=True, domain="[('category', '=', 'DEST'), ('type', '!=', 'view'), ('state', '=', 'open')]"),
        'cost_center_id': fields.many2one('account.analytic.account', "Cost Center", required=False, domain="[('category','=','OC'), ('type', '!=', 'view'), ('state', '=', 'open')]"),
        'analytic_id': fields.many2one('account.analytic.account', "Funding Pool", required=True, domain="[('category', '=', 'FUNDING'), ('type', '!=', 'view'), ('state', '=', 'open')]"),
        'free_1_id': fields.many2one('account.analytic.account', "Free 1", domain="[('category', '=', 'FREE1'), ('type', '!=', 'view'), ('state', '=', 'open')]"),
        'free_2_id': fields.many2one('account.analytic.account', "Free 2", domain="[('category', '=', 'FREE2'), ('type', '!=', 'view'), ('state', '=', 'open')]"),
        'user_validated': fields.boolean("User validated?", help="Is this line validated by a user in a OpenERP field instance?", readonly=True),
        'date': fields.date("Posting Date", readonly=True),
        'partner_txt': fields.char("Third Party", size=255, readonly=True),
        'period_id': fields.many2one("account.period", "Period", readonly=True),
        'name': fields.char('Description', size=255, readonly=True),
        'ref': fields.char('Reference', size=255, readonly=True),
        'document_date': fields.date("Document Date", readonly=True),
        'currency_id': fields.many2one('res.currency', "Book. Currency", required=True, readonly=True),
        'amount': fields.float('Amount', readonly=True),
        'account_id_first_value': fields.many2one('account.account', "Account @import", required=True, readonly=True),
        'cost_center_id_first_value': fields.many2one('account.analytic.account', "Cost Center @import", required=False, readonly=False),
        'analytic_id_first_value': fields.many2one('account.analytic.account', "Funding Pool @import", required=True, readonly=True),
        'destination_id_first_value': fields.many2one('account.analytic.account', "Destination @import", required=True, readonly=True),
        'analytic_state': fields.function(_get_analytic_state, type='selection', method=True, readonly=True, string="Distribution State",
            selection=[('none', 'None'), ('valid', 'Valid'), ('invalid', 'Invalid')], help="Give analytic distribution state"),
    }

    _defaults = {
        'user_validated': lambda *a: False,
        'amount': lambda *a: 0.0,
    }

    
    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        """
        Change funding pool domain in order to include MSF Private fund
        """
        if not context:
            context = {}
        view = super(hq_entries, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)
        arch = etree.fromstring(view['arch'])
        fields = arch.xpath('field[@name="analytic_id"]')
        if fields:
            try:
                fp_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'analytic_distribution', 'analytic_account_msf_private_funds')[1]
            except ValueError:
                fp_id = 0
            fields[0].set('domain', "[('type', '!=', 'view'), ('state', '=', 'open'), ('category', '=', 'FUNDING'), '|', '&', ('cost_center_ids', '=', cost_center_id), ('tuple_destination', '=', (account_id, destination_id)), ('id', '=', %s)]" % fp_id)
        # Change Destination field
        dest_fields = arch.xpath('field[@name="destination_id"]')
        for field in dest_fields:
            field.set('domain', "[('type', '!=', 'view'), ('state', '=', 'open'), ('category', '=', 'DEST'), ('destination_ids', '=', account_id)]")
            view['arch'] = etree.tostring(arch)
        return view

    def onchange_destination(self, cr, uid, ids, destination_id=False, funding_pool_id=False, account_id=False):
        """
        Check given funding pool with destination
        """
        # Prepare some values
        res = {}
        # If all elements given, then search FP compatibility
        if destination_id and funding_pool_id and account_id:
            fp_line = self.pool.get('account.analytic.account').browse(cr, uid, funding_pool_id)
            # Search MSF Private Fund element, because it's valid with all accounts
            try:
                fp_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'analytic_distribution', 
                'analytic_account_msf_private_funds')[1]
            except ValueError:
                fp_id = 0
            # Delete funding_pool_id if not valid with tuple "account_id/destination_id".
            # but do an exception for MSF Private FUND analytic account
            if (account_id, destination_id) not in [x.account_id and x.destination_id and (x.account_id.id, x.destination_id.id) for x in fp_line.tuple_destination_account_ids] and funding_pool_id != fp_id:
                res = {'value': {'analytic_id': False}}
        # If no destination, do nothing
        elif not destination_id:
            res = {}
        # Otherway: delete FP
        else:
            res = {'value': {'analytic_id': False}}
        # If destination given, search if given 
        return res

    def write(self, cr, uid, ids, vals, context=None):
        """
        Change Expat salary account is not allowed
        """
        if not context:
            context={}
        if 'account_id' in vals:
            account = self.pool.get('account.account').browse(cr, uid, [vals.get('account_id')])[0]
            for line in self.browse(cr, uid, ids):
                if line.account_id_first_value and line.account_id_first_value.is_not_hq_correctible and not account.is_not_hq_correctible:
                    raise osv.except_osv(_('Warning'), _('Change Expat salary account is not allowed!'))
        return super(hq_entries, self).write(cr, uid, ids, vals, context)

    def unlink(self, cr, uid, ids, context=None):
        """
        Do not permit user to delete HQ Entries lines
        """
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not context.get('from', False) or context.get('from') != 'code' and ids:
            if self.search(cr, uid, [('id', 'in', ids), ('user_validated', '=', True)]):
                raise osv.except_osv(_('Error'), _('You cannot delete validated HQ Entries lines!'))
        return super(hq_entries, self).unlink(cr, uid, ids, context)

hq_entries()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
