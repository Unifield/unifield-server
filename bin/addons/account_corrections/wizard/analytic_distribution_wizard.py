#!/usr/bin/env python
#-*- encoding:utf-8 -*-
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
from tools.translate import _
import time
from collections import defaultdict
from base import currency_date


class analytic_distribution_wizard(osv.osv_memory):
    _inherit = 'analytic.distribution.wizard'

    _columns = {
        'date': fields.date(string="Date", help="This date is taken from analytic distribution corrections"),
        'state': fields.selection([('draft', 'Draft'), ('cc', 'Cost Center only'), ('dispatch', 'All other elements'), ('done', 'Done'),
                                   ('correction', 'Correction')], string="State", required=True, readonly=True),
        'old_account_id': fields.many2one('account.account', "Original account of the line to be corrected", readonly=True),
        'old_partner_id': fields.many2one('res.partner', "Original partner of the line to be corrected", readonly=True),
        'old_employee_id': fields.many2one('hr.employee', "Original employee of the line to be corrected", readonly=True),
        'new_partner_id': fields.many2one('res.partner', "New partner selected in the correction wizard", readonly=True),
        'new_employee_id': fields.many2one('hr.employee', "New employee selected in the correction wizard", readonly=True),
        'invalid_small_amount': fields.boolean(string='Invalid small amount', invisible=True,
                                               help="Displays in the wizard a warning message regarding small amount analytic distribution"),
    }

    _defaults = {
        'state': lambda *a: 'draft',
        'date': lambda *a: time.strftime('%Y-%m-%d'),
        'invalid_small_amount': False,
    }

    def _check_lines(self, cr, uid, distribution_line_id, wiz_line_id, ltype):
        """
        Check components compatibility
        """
        # Prepare some values
        wiz_line_types = {'cost.center': '', 'funding.pool': 'fp', 'free.1': 'f1', 'free.2': 'f2',}
        obj = '.'.join([ltype, 'distribution', 'line'])
        oline = self.pool.get(obj).browse(cr, uid, distribution_line_id)
        nline_type = '.'.join([wiz_line_types.get(ltype), 'lines'])
        nline_obj = '.'.join(['analytic.distribution.wizard', nline_type])
        nline = self.pool.get(nline_obj).browse(cr, uid, wiz_line_id)
        to_reverse = []
        to_override = defaultdict(list)
        period = nline.wizard_id and nline.wizard_id.move_line_id and nline.wizard_id.move_line_id.period_id or False
        if not period:
            raise osv.except_osv(_('Error'), _('No attached period to the correction wizard. Do you come from a correction wizard attached to a journal item?'))
        # Some cases
        if ltype == 'funding.pool':
            old_component = [oline.destination_id.id, oline.analytic_id.id, oline.cost_center_id.id, oline.percentage]
            new_component = [nline.destination_id.id, nline.analytic_id.id, nline.cost_center_id.id, nline.percentage]
            if old_component != new_component:
                # Don't do anything if the old FP account is on a soft/hard closed contract!
                if oline.analytic_id.id != nline.analytic_id.id:
                    check_fp = self.pool.get('account.analytic.account').is_blocked_by_a_contract(cr, uid, [oline.analytic_id.id])
                    if check_fp and oline.analytic_id.id in check_fp:
                        return False, _("Old funding pool is on a soft/hard closed contract: %s") % (oline.analytic_id.code,), to_reverse, to_override
                    to_override[oline.id].append(('account_id', nline.analytic_id.id))
                # Override CC on open period, otherwise reverse line
                if oline.cost_center_id.id != nline.cost_center_id.id:
                    # if period is open, do an override, except if FP needs to reverse the line
                    if period.state not in ['done', 'mission-closed'] and oline.id not in to_reverse:
                        to_override[oline.id].append(('cost_center_id', nline.cost_center_id.id))
                    elif period.state in ['done', 'mission-closed']:
                        to_reverse.append(oline.id)
                # Only reverse line if destination have changed
                if oline.destination_id.id != nline.destination_id.id:
                    if period.state not in ['done', 'mission-closed'] and oline.id not in to_reverse:
                        to_override[oline.id].append(('destination_id', nline.destination_id.id))
                    elif period.state in ['done', 'mission-closed']:
                        to_reverse.append(oline.id)
                # Override line if percentage have changed
                if oline.percentage != nline.percentage and oline.id not in to_reverse:
                    to_override[oline.id].append(('percentage', nline.percentage))
                # Check that if old_component and new_component have changed we should find oline.id in to_reverse OR to_override
                if oline.id not in to_override and oline.id not in to_reverse:
                    raise osv.except_osv(_('Error'), _('Code error: A case has not been taken.'))
        else:
            old_component = [oline.analytic_id.id, oline.percentage]
            new_component = [nline.analytic_id.id, nline.percentage]
            if old_component != new_component:
                field_name = ''
                value = None
                if oline.analytic_id.id != nline.analytic_id.id:
                    field_name = 'account_id'
                    value = nline.analytic_id.id
                if oline.percentage != nline.percentage:
                    field_name = 'percentage'
                    value = nline.percentage
                if not value:
                    raise osv.except_osv(_('Error'), _('A value is missing.'))
                to_override[oline.id].append((field_name, value))
        # Delete lines that are in override if they are in to_reverse
        if oline.id in to_override and oline.id in to_reverse:
            del to_override[oline.id]
        return True, _("All is OK."), to_reverse, to_override

    def _check_period_closed_on_fp_distrib_line(self, cr, uid, distrib_line_id,
                                                context=None, is_HQ_origin=None):
        ana_obj = self.pool.get('account.analytic.line')
        aa_ids = ana_obj.search(cr, uid, [('distrib_line_id', '=', 'funding.pool.distribution.line,%d'%distrib_line_id), ('is_reversal', '=', False), ('is_reallocated', '=', False)], context=context)
        closed = []
        if aa_ids:
            for ana in ana_obj.browse(cr, uid, aa_ids, context=context):
                # US-1398 HQ origin and not from OD AJI: like period close
                # behaviour
                if (ana.period_id
                        and ana.period_id.state in ('done', 'mission-closed', )) \
                        or (is_HQ_origin and not is_HQ_origin.get('from_od', False)):
                    closed.append(ana.id)
        return closed

    def do_analytic_distribution_changes(self, cr, uid, wizard_id, distrib_id, context=None):
        """
        For each given wizard compare old (distrib_id) and new analytic distribution. Then adapt analytic lines.
        """
        # US-900: get the next OD journal sequence only 1st time it is needed
        # for the correction transaction
        def get_entry_seq(entry_seq_data):
            res = entry_seq_data.get('sequence', False)
            if not res:
                seqnum = self.pool.get('ir.sequence').get_id(cr, uid, journal.sequence_id.id,
                                                             context={'fiscalyear_id': period.fiscalyear_id.id})
                res = "%s-%s-%s" % (move_prefix, code, seqnum)
                entry_seq_data['sequence'] = res
            return res

        if context is None:
            context = {}
        # Prepare some values
        wizard = self.browse(cr, uid, wizard_id)
        ad_obj = self.pool.get('analytic.distribution')
        ana_line_obj = self.pool.get('account.analytic.line')
        journal_obj = self.pool.get('account.journal')
        analytic_journal_obj = self.pool.get('account.analytic.journal')
        company_currency_id = self.pool.get('res.users').browse(cr, uid, uid).company_id.currency_id.id
        ml = wizard.move_line_id
        # US-5848: orig_date left unchanged not to break historical behavior,
        # but the value set here seems overwritten later in the process if there is a source_date
        orig_date = ml.source_date or ml.date
        orig_document_date = ml.document_date
        posting_date = wizard.date
        curr_date = currency_date.get_date(self, cr, ml.document_date, ml.date, source_date=ml.source_date)
        working_period_id = []
        new_line_ids = []
        entry_seq_data = {}

        # get the last reversal AJI created BEFORE this correction
        biggest_reversal_aji_ids = ana_line_obj.search(cr, uid, [('move_id', '=', ml.id),
                                                                 ('is_reversal', '=', True)],
                                                       order='id DESC', limit=1, context=context)
        if biggest_reversal_aji_ids:
            biggest_reversal_aji = ana_line_obj.browse(cr, uid, biggest_reversal_aji_ids[0],
                                                       fields_to_fetch=['period_id', 'entry_sequence', 'date'], context=context)
            # use the period / date and Entry Sequence of the reversal AJI in case its period is still open
            if biggest_reversal_aji.period_id and biggest_reversal_aji.period_id.state == 'draft':  # Open
                working_period_id = [biggest_reversal_aji.period_id.id]
                posting_date = biggest_reversal_aji.date
                entry_seq_data['sequence'] = biggest_reversal_aji.entry_sequence

        jtype = 'correction'
        if ml.account_id.type_for_register == 'donation':
            jtype = 'extra'
        # Correction: of an HQ entry, or of a correction of an HQ entry
        elif ml.journal_id.type in ('hq', 'correction_hq'):
            jtype = 'hq'
        correction_journal_id = analytic_journal_obj.get_correction_analytic_journal(cr, uid, corr_type=jtype, context=context)
        if not correction_journal_id:
            raise osv.except_osv(_('Error'), _('No analytic journal found for corrections!'))
        to_create = []
        to_override = []
        to_delete = []
        to_reverse = []
        old_line_ok = []
        any_reverse = False
        # Prepare journal and period information for entry sequences
        journal_id = journal_obj.get_correction_journal(cr, uid, corr_type=jtype, context=context)
        if not journal_id:
            raise osv.except_osv(_('Error'), _('No journal found for corrections!'))
        journal = journal_obj.browse(cr, uid, journal_id, context=context)
        code = journal.code
        period_ids = self.pool.get('account.period').get_period_from_date(cr, uid, date=posting_date, context=context)
        if not period_ids:
            raise osv.except_osv(_('Warning'), _('No period found for creating sequence on the given date: %s') % (posting_date or ''))
        period = self.pool.get('account.period').browse(cr, uid, period_ids)[0]
        move_prefix = self.pool.get('res.users').browse(cr, uid, uid, context).company_id.instance_id.move_prefix

        # US-676: check wizard lines total matches JI amount
        # the wizard already check distri is 100% allocated
        # => so if gap: due to distri input mode changes (rounding issues)
        # (distri done for example in amount mode, later corrected in defaults
        # mode (percentage))
        # => deduce the gap (as we are in 100% distri) to the greater amount
        # line like was done for US-119
        # => apply these deduce only if: lines are created as some line are
        # created/resplit. do nothing if only cc/dest of lines changes.
        total_rounded_amount = 0.
        #####
        ## FUNDING POOL
        ###
        # OK let's go on funding pool lines
        # Search old line and new lines
        old_line_ids = self.pool.get('funding.pool.distribution.line').search(cr, uid, [('distribution_id', '=', distrib_id)])
        wiz_line_ids = self.pool.get('analytic.distribution.wizard.fp.lines').search(cr, uid, [('wizard_id', '=', wizard_id), ('type', '=', 'funding.pool')])

        # block applying several AD lines to booking amount <= 1
        if abs(ml.amount_currency) <= 1:
            nb_fp_lines = len(wiz_line_ids)
            nb_free1 = self.pool.get('analytic.distribution.wizard.f1.lines').search(cr, uid,
                                                                                     [('wizard_id', '=', wizard_id), ('type', '=', 'free.1')],
                                                                                     count=True, context=context)
            nb_free2 = self.pool.get('analytic.distribution.wizard.f2.lines').search(cr, uid,
                                                                                     [('wizard_id', '=', wizard_id), ('type', '=', 'free.2')],
                                                                                     count=True, context=context)
            if not all(n <= 1 for n in [nb_fp_lines, nb_free1, nb_free2]):
                raise osv.except_osv(_('Error'),
                                     _("Journal Items with a booking amount inferior or equal to 1 "
                                       "can't have several analytic distribution lines."))

        # US-1398: determine if AD chain is from an HQ entry and from a pure AD
        # correction: analytic reallocation of HQ entry before validation
        # if yes this flag represents that we have to maintain OD sequence
        # consistency
        is_HQ_origin = False
        for old_line_id in old_line_ids:
            original_al_id = ana_line_obj.search(cr, uid, [
                ('distrib_line_id', '=', 'funding.pool.distribution.line,%d' % (old_line_id, )),
                ('is_reversal', '=', False),
                ('is_reallocated', '=', False),
            ])
            if original_al_id and len(original_al_id) == 1:
                original_al = ana_line_obj.browse(cr, uid, original_al_id[0], context)
                # AJI correction journal and HQ JI
                if original_al \
                    and original_al.move_id and \
                        original_al.move_id.journal_id.type == 'hq':
                        # US-1343/2: flag that the chain origin is an HQ
                        # entry: in other terms OD AJI from a HQ JI
                    is_HQ_origin = {
                        'from_od': original_al.journal_id.type in ('correction', 'correction_hq'),
                    }
                    break

        for wiz_line in self.pool.get('analytic.distribution.wizard.fp.lines').browse(cr, uid, wiz_line_ids):
            if not ad_obj.check_dest_cc_compatibility(cr, uid, wiz_line.destination_id.id, wiz_line.cost_center_id.id, context=context):
                raise osv.except_osv(_('Error'),
                                     _('The Cost Center %s is not compatible with the Destination %s.') %
                                     (wiz_line.cost_center_id.code or '', wiz_line.destination_id.code or ''))

            if not ad_obj.check_fp_cc_compatibility(cr, uid, wiz_line.analytic_id.id, wiz_line.cost_center_id.id, context=context):
                raise osv.except_osv(_('Error'),
                                     _('The Cost Center %s is not compatible with the Funding Pool %s.') %
                                     (wiz_line.cost_center_id.code or '', wiz_line.analytic_id.code or ''))

            if not wiz_line.distribution_line_id or wiz_line.distribution_line_id.id not in old_line_ids:
                # new distribution line
                #if self.pool.get('account.analytic.account').is_blocked_by_a_contract(cr, uid, [wiz_line.analytic_id.id]):
                #    raise osv.except_osv(_('Error'), _("Funding pool is on a soft/hard closed contract: %s")%(wiz_line.analytic_id.code))
                to_create.append(wiz_line)
            else:
                old_line = self.pool.get('funding.pool.distribution.line').browse(cr, uid, wiz_line.distribution_line_id.id)

                if old_line:
                    # existing line, test modifications
                    # for FP, percentage, CC or destination changes regarding contracts
                    if old_line.analytic_id.id != wiz_line.analytic_id.id \
                            or old_line.percentage != wiz_line.percentage \
                            or old_line.cost_center_id.id != wiz_line.cost_center_id.id \
                            or old_line.destination_id.id != wiz_line.destination_id.id:
                        # FP account changed or % modified
                        if self.pool.get('account.analytic.account').is_blocked_by_a_contract(cr, uid, [old_line.analytic_id.id]):
                            raise osv.except_osv(_('Error'), _("Funding pool is on a soft/hard closed contract: %s")%(old_line.analytic_id.code))

                    if (old_line.cost_center_id.id != wiz_line.cost_center_id.id or
                            old_line.destination_id.id != wiz_line.destination_id.id or
                            old_line.percentage != wiz_line.percentage):
                        if self._check_period_closed_on_fp_distrib_line(cr, uid, old_line.id, is_HQ_origin=is_HQ_origin):
                            to_reverse.append(wiz_line)
                        else:
                            to_override.append(wiz_line)
                    elif old_line.analytic_id.id != wiz_line.analytic_id.id:
                        to_override.append(wiz_line)

                    old_line_ok.append(old_line.id)

        reversed_lines_ids = []  # to store the ids corresponding to all the lines of which the AD has been either edited or deleted
        for wiz_line in self.pool.get('funding.pool.distribution.line').browse(cr, uid, [x for x in old_line_ids if x not in old_line_ok]):
            # distribution line deleted by user
            if self.pool.get('account.analytic.account').is_blocked_by_a_contract(cr, uid, [wiz_line.analytic_id.id]):
                raise osv.except_osv(_('Error'), _("Funding pool is on a soft/hard closed contract: %s")%(wiz_line.analytic_id.code))
            to_reverse_ids = self._check_period_closed_on_fp_distrib_line(cr, uid, wiz_line.id, is_HQ_origin=is_HQ_origin)
            if to_reverse_ids:
                reversed_lines_ids += to_reverse_ids
                # reverse the line
                #to_reverse_ids = ana_obj.search(cr, uid, [('distrib_line_id', '=', 'funding.pool.distribution.line,%d'%wiz_line.id)])
                if period.state != 'draft':
                    raise osv.except_osv(_('Error'), _('Period (%s) is not open.') % (period.name,))
                reversed_ids = ana_line_obj.reverse(cr, uid, to_reverse_ids, posting_date=posting_date)
                # Set initial lines as non correctible
                ana_line_obj.write(cr, uid, to_reverse_ids, {'is_reallocated': True})
                # Set right journal and right entry sequence
                ana_line_obj.write(cr, uid, reversed_ids, {'journal_id': correction_journal_id})
                for reversed_id in reversed_ids:
                    cr.execute('update account_analytic_line set entry_sequence = %s where id = %s', (get_entry_seq(entry_seq_data), reversed_id) )
                # delete the distribution line
                wiz_line.unlink()
                any_reverse = True
            else:
                to_delete.append(wiz_line)

        keep_seq_and_corrected = False
        period_closed =  ml.period_id and ml.period_id.state and ml.period_id.state in ['done', 'mission-closed'] or ml.have_an_historic or False
        if (period_closed or is_HQ_origin) and to_create and (to_override or to_delete or any_reverse):
            already_corr_ids = ana_line_obj.search(cr, uid, [('distribution_id', '=', distrib_id), ('last_corrected_id', '!=', False)])
            if already_corr_ids:
                for ana in ana_line_obj.read(cr, uid, already_corr_ids, ['entry_sequence', 'last_corrected_id', 'date', 'ref', 'reversal_origin']):
                    if ana['entry_sequence'] and ana['last_corrected_id']:
                        rev_name = ana['reversal_origin'] and ana['reversal_origin'][1] or ana['last_corrected_id'] and ana['last_corrected_id'][1] or False
                        keep_seq_and_corrected = (ana['entry_sequence'], ana['last_corrected_id'][0], ana['date'], ana['ref'], rev_name)
                        break

        #####
        ## FP: TO CREATE
        ###
        have_been_created = []
        for line in to_create:
            # create the new distrib line
            new_distrib_line = self.pool.get('funding.pool.distribution.line').create(cr, uid, {
                'analytic_id': line.analytic_id.id,
                'cost_center_id': line.cost_center_id.id,
                'percentage': line.percentage,
                'destination_id': line.destination_id.id,
                'distribution_id': distrib_id,
                'currency_id': ml and  ml.currency_id and ml.currency_id.id or company_currency_id,
            })
            # But regarding UFTP-194, we should set this date to the wizard date when we have some reveral + correction
            create_date = orig_date
            # UFTP-169: Use the correction line date in case we are correcting a line that is a correction of another line.
            if ml.corrected_line_id:
                create_date = ml.date
            # create the ana line (pay attention to take original date as posting date as UF-2199 said it.
            name = False
            if period_closed or is_HQ_origin:
                create_date = posting_date
                name = ana_line_obj.join_without_redundancy(ml.name, 'COR')
                if keep_seq_and_corrected:
                    create_date = keep_seq_and_corrected[2]  # is_HQ_origin keep date too
                    if keep_seq_and_corrected[4]:
                        name = ana_line_obj.join_without_redundancy(keep_seq_and_corrected[4], 'COR')

            created_analytic_line_ids = self.pool.get('funding.pool.distribution.line').\
                create_analytic_lines(cr, uid, [new_distrib_line], ml.id, date=create_date, document_date=orig_document_date,
                                      source_date=curr_date, name=name, context=context)
            new_line_ids.extend(created_analytic_line_ids.values())
            working_period_id = working_period_id or \
                self.pool.get('account.period').get_period_from_date(cr, uid, date=create_date, context=context)
            # Set right analytic correction journal to these lines
            if period_closed or is_HQ_origin:
                sql_to_cor = ['journal_id=%s']
                sql_data = [correction_journal_id]
                if keep_seq_and_corrected:
                    sql_to_cor += ['entry_sequence=%s', 'last_corrected_id=%s', 'ref=%s']
                    sql_data += [keep_seq_and_corrected[0], keep_seq_and_corrected[1], keep_seq_and_corrected[3] or '']
                sql_data += [created_analytic_line_ids[new_distrib_line]]
                cr.execute('update account_analytic_line set '+','.join(sql_to_cor)+' where id = %s',  # not_a_user_entry
                           sql_data)
            have_been_created.append(created_analytic_line_ids[new_distrib_line])

        #####
        ## FP: TO DELETE
        ###
        for line in to_delete:
            # delete distrib line
            self.pool.get('funding.pool.distribution.line').unlink(cr, uid, [line.id])
            # delete associated analytic line
            to_delete_ids = ana_line_obj.search(cr, uid, [('distrib_line_id', '=', 'funding.pool.distribution.line,%d'%line.id), ('is_reversal', '=', False), ('is_reallocated', '=', False)])
            ana_line_obj.unlink(cr, uid, to_delete_ids)

        #####
        ## FP: TO REVERSE
        ###
        for line in to_reverse:
            # reverse the line
            to_reverse_ids = ana_line_obj.search(cr, uid, [('distrib_line_id', '=', 'funding.pool.distribution.line,%d'%line.distribution_line_id.id), ('is_reversal', '=', False), ('is_reallocated', '=', False)])
            reversed_lines_ids += to_reverse_ids

            # get the original sequence
            orig_line = ana_line_obj.browse(cr, uid, to_reverse_ids)[0]

            # UTP-943: Set wizard date as date for REVERSAL AND CORRECTION lines
            reversed_id = ana_line_obj.reverse(cr, uid, to_reverse_ids[0], posting_date=posting_date, context=context)[0]
            # Add reversal origin link (to not loose it). last_corrected_id is to prevent case where you do a reverse a line that have been already corrected

            ana_line_obj.write(cr, uid, [reversed_id], {'reversal_origin': to_reverse_ids[0], 'last_corrected_id': False, 'journal_id': correction_journal_id, 'ref': orig_line.entry_sequence})
            # Mark old lines as non reallocatable (ana_ids): why reverse() don't set this flag ?
            ana_line_obj.write(cr, uid, [to_reverse_ids[0]], {'is_reallocated': True})
            cr.execute('update account_analytic_line set entry_sequence = %s where id = %s', (get_entry_seq(entry_seq_data), reversed_id) )

            # update the distrib line
            name = False
            fp_distrib_obj = self.pool.get('funding.pool.distribution.line')
            if to_reverse_ids:
                name = ana_line_obj.join_without_redundancy(ana_line_obj.read(cr, uid, to_reverse_ids[0], ['name'])['name'], 'COR')
            fp_distrib_obj.write(cr, uid, [line.distribution_line_id.id], {
                'analytic_id': line.analytic_id.id,
                'cost_center_id': line.cost_center_id.id,
                'percentage': line.percentage,
                'destination_id': line.destination_id.id,
            })
            # UTP-943: Check that new ana line is on an open period
            correction_period_ids = period_ids
            for cp in self.pool.get('account.period').browse(cr, uid, correction_period_ids):
                if cp.state != 'draft':
                    raise osv.except_osv(_('Error'), _('Period (%s) is not open.') % (cp.name,))
            # Create the new ana line
            ret = fp_distrib_obj.create_analytic_lines(cr, uid, line.distribution_line_id.id, ml.id, date=posting_date,
                                                       document_date=orig_document_date, source_date=curr_date, name=name, context=context)
            new_line_ids.extend(ret.values())
            working_period_id = working_period_id or period_ids
            # Add link to first analytic lines
            for ret_id in ret:
                ana_line_obj.write(cr, uid, [ret[ret_id]], {'last_corrected_id': to_reverse_ids[0], 'journal_id': correction_journal_id, 'ref': orig_line.entry_sequence })
                cr.execute('update account_analytic_line set entry_sequence = %s where id = %s', (get_entry_seq(entry_seq_data), ret[ret_id]) )
        # UFTP-194: Set missing entry sequence for created analytic lines
        if have_been_created and reversed_lines_ids:
            reversed_line_id = max(reversed_lines_ids)  # always consider that the line corrected is the most recent one
            corrected_aji = ana_line_obj.read(cr, uid, reversed_line_id, ['entry_sequence', 'name'], context=context)
            new_description = ana_line_obj.join_without_redundancy(corrected_aji['name'], 'COR')
            cr.execute('update account_analytic_line '
                       'set entry_sequence = %s, last_corrected_id = %s, ref = %s, name = %s '
                       'where id in %s;', (get_entry_seq(entry_seq_data), reversed_line_id,
                                           corrected_aji['entry_sequence'] or '', new_description, tuple(have_been_created)))

        #####
        ## FP: TO OVERRIDE
        ###
        for line in to_override:
            # update the ana line
            to_override_ids = ana_line_obj.search(cr, uid, [('distrib_line_id', '=', 'funding.pool.distribution.line,%d'%line.distribution_line_id.id), ('is_reversal', '=', False), ('is_reallocated', '=', False)])
            ctx = {'currency_date': curr_date}
            amount_cur = (ml.credit_currency - ml.debit_currency) * line.percentage / 100
            if abs(ml.credit_currency - ml.debit_currency) >= 10**10:
                amount_cur = round(amount_cur)

            amount = self.pool.get('res.currency').compute(cr, uid, ml.currency_id.id, company_currency_id, amount_cur, round=False, context=ctx)

            vals = {
                'account_id': line.analytic_id.id,
                'cost_center_id': line.cost_center_id.id,
                'destination_id': line.destination_id.id,
                'amount_currency': amount_cur,
                'amount': amount,
            }

            # get the actual AJI date (can differ from the ML orig_date if an AD correction has already been made)
            aal_date = ana_line_obj.browse(cr, uid, to_override_ids[0], fields_to_fetch=['date'], context=context).date
            # original dates are kept but we add them in vals to trigger the check on dates with the new AD
            vals.update({
                'date': aal_date,
                'document_date': orig_document_date,
            })
            working_period_id = working_period_id or self.pool.get('account.period').get_period_from_date(cr, uid, date=aal_date, context=context)
            ana_line_obj.write(cr, uid, to_override_ids, vals)
            # update the distib line
            self.pool.get('funding.pool.distribution.line').write(cr, uid, [line.distribution_line_id.id], {
                'analytic_id': line.analytic_id.id,
                'cost_center_id': line.cost_center_id.id,
                'percentage': line.percentage,
                'destination_id': line.destination_id.id
            })

        # US-6100 in case of a corr. the adjustment should be made on the biggest COR amount
        # instead of the biggest amount of all AJIs (cf. don't modify the entry being corrected)
        has_generated_cor = False
        if new_line_ids and (to_reverse or any_reverse):  # check if COR lines have been generated
            has_generated_cor = True
        # compute the adjustment amount
        all_aji_ids = ana_line_obj.search(cr, uid, [
            ('move_id', '=', ml.id),
            ('is_reversal', '=', False),
            ('is_reallocated', '=', False),
            ('account_id.category', '=', 'FUNDING'),  # exclude free lines
        ], order='NO_ORDER', context=context)
        max_line = {'amount': 0, 'aji_bro': False}
        aji_fields = ['amount_currency', 'period_id', 'currency_id', 'source_date', 'document_date', 'date']
        for aji in ana_line_obj.browse(cr, uid, all_aji_ids, fields_to_fetch=aji_fields, context=context):

            total_rounded_amount += round(abs(aji.amount_currency or 0.0), 2)
            if has_generated_cor and aji.id in new_line_ids and abs(aji.amount_currency or 0.0) > max_line['amount']:
                max_line = {'aji_bro': aji, 'amount': abs(aji.amount_currency or 0.0)}
            elif not has_generated_cor and working_period_id and aji.period_id.id == working_period_id[0] and \
                    abs(aji.amount_currency or 0.0) > max_line['amount']:
                max_line = {'aji_bro': aji, 'amount': abs(aji.amount_currency or 0.0)}

        amount_diff = total_rounded_amount - abs(wizard.amount)
        if abs(amount_diff) > 10 ** -3 and max_line['aji_bro']:

            # get data from the biggest AJI, on which the adjustment will be applied
            fix_aji_old_amount = max_line['aji_bro'].amount_currency or 0.0
            fix_aji_currency_id = max_line['aji_bro'].currency_id and max_line['aji_bro'].currency_id.id or False

            # fix booking amount
            fix_aji_amount_currency = round(abs(fix_aji_old_amount), 2) - amount_diff
            if fix_aji_old_amount < 0:
                fix_aji_amount_currency *= -1
            aji_fix_vals = {
                'amount_currency': fix_aji_amount_currency,
            }

            # then recompute functional amount
            if fix_aji_currency_id:
                new_context = context.copy()
                max_line_curr_date = currency_date.get_date(self, cr, max_line['aji_bro'].document_date, max_line['aji_bro'].date,
                                                            source_date=max_line['aji_bro'].source_date)
                new_context['currency_date'] = max_line_curr_date
                aji_fix_vals['amount'] = \
                    self.pool.get('res.currency').compute(cr, uid,
                                                          fix_aji_currency_id, company_currency_id,
                                                          fix_aji_amount_currency, round=False,
                                                          context=new_context)

                # fix aji
                ana_line_obj.write(cr, uid, [max_line['aji_bro'].id], aji_fix_vals, context=context)

        #####
        ## Set move line as corrected upstream if needed
        ###
        if to_reverse or to_override or to_create:
            self.pool.get('account.move.line').corrected_upstream_marker(cr, uid, [ml.id], context=context)

        #####
        ## FREE 1 / FREE 2
        ###
        for free in [('free.1', 'f1'), ('free.2', 'f2')]:
            obj_name = free[0] + '.distribution.line'
            corr_name = 'analytic.distribution.wizard.' + free[1] + '.lines'
            old_line_ids = False
            wiz_line_ids = False
            to_create = []
            to_delete = []
            to_override = []
            old_line_ok = []
            old_line_ids = self.pool.get(obj_name).search(cr, uid, [('distribution_id', '=', distrib_id)])
            wiz_line_ids = self.pool.get(corr_name).search(cr, uid, [('wizard_id', '=', wizard_id), ('type', '=', free[0])])
            # To create OR to override
            for wiz_line in self.pool.get(corr_name).browse(cr, uid, wiz_line_ids):
                if not wiz_line.distribution_line_id or wiz_line.distribution_line_id.id not in old_line_ids:
                    to_create.append(wiz_line)
                else:
                    old_line = self.pool.get(obj_name).browse(cr, uid, wiz_line.distribution_line_id.id)
                    # existing line, test modifications
                    if old_line.analytic_id.id != wiz_line.analytic_id.id or old_line.percentage != wiz_line.percentage:
                        to_override.append(wiz_line)
                    # validate line
                    old_line_ok.append(old_line.id)
            # To delete
            for wiz_line in self.pool.get(obj_name).browse(cr, uid, [x for x in old_line_ids if x not in old_line_ok]):
                # distribution line deleted by user
                to_delete.append(wiz_line)
            # Delete lines that should be
            for line in to_delete:
                # delete distrib line
                self.pool.get(obj_name).unlink(cr, uid, [line.id])
                # delete associated analytic line
                to_delete_ids = ana_line_obj.search(cr, uid, [('distrib_line_id', '=', '%s,%d' % (obj_name,line.id))])
                ana_line_obj.unlink(cr, uid, to_delete_ids)
            # Override those that should be
            for line in to_override:
                # update the ana line
                to_override_ids = ana_line_obj.search(cr, uid, [('distrib_line_id', '=', '%s,%d' % (obj_name, line.distribution_line_id.id)), ('is_reversal', '=', False), ('is_reallocated', '=', False)])
                ctx = {'currency_date': curr_date}
                amount_cur = (ml.credit_currency - ml.debit_currency) * line.percentage / 100
                amount = self.pool.get('res.currency').compute(cr, uid, ml.currency_id.id, company_currency_id, amount_cur, round=False, context=ctx)
                # the posting date is the one of the entry corrected
                ana_line_obj.write(cr, uid, to_override_ids, {
                    'account_id': line.analytic_id.id,
                    'amount_currency': amount_cur,
                    'amount': amount,
                    'date': ml.date,
                    'source_date': curr_date,
                    'document_date': orig_document_date,
                })
                # update the distib line
                self.pool.get(obj_name).write(cr, uid, [line.distribution_line_id.id], {
                    'analytic_id': line.analytic_id.id,
                    'percentage': line.percentage,
                })
            # Create lines that should be
            for line in to_create:
                # create the new distrib line
                new_distrib_line = self.pool.get(obj_name).create(cr, uid, {
                    'analytic_id': line.analytic_id.id,
                    'percentage': line.percentage,
                    'distribution_id': distrib_id,
                    'currency_id': ml and  ml.currency_id and ml.currency_id.id or company_currency_id,
                })
                # create the ana line
                # the posting date is the one of the entry corrected
                self.pool.get(obj_name).create_analytic_lines(cr, uid, [new_distrib_line], ml.id, date=ml.date,
                                                              document_date=orig_document_date, source_date=curr_date, ref=ml.ref)
        # Set move line as corrected upstream if needed
        if to_reverse or to_override or to_create:
            self.pool.get('account.move.line').corrected_upstream_marker(cr, uid, [ml.id], context=context)

        # In case of no REV/COR, set the analytic lines as ad_updated. This shows that the Corr. Wizard has been used,
        # whatever the changes made (even if no change has been made, or e.g. only a Free1/2 line has been deleted)
        if not has_generated_cor:
            # get all the analytic lines related to the JI, INCLUDING the free1/2 lines
            all_analytic_lines_ids = ana_line_obj.search(cr, uid, [
                ('move_id', '=', ml.id),
                ('is_reversal', '=', False),  # no need to include the REV lines...
                ('is_reallocated', '=', False),  # ...or the lines set as reallocated from a previous corr.
            ], order='NO_ORDER', context=context)
            if all_analytic_lines_ids:
                ana_line_obj.write(cr, uid, all_analytic_lines_ids, {'ad_updated': True}, context=context)

        if context and 'ji_correction_account_or_tp_changed' in context:
            if (any_reverse or to_reverse) and \
                    not context['ji_correction_account_or_tp_changed']:
                # BKLG-12 pure AD correction flag marker
                # (do this bypassing model write)
                return osv.osv.write(self.pool.get('account.move.line'), cr,
                                     uid, [ml.id], {'last_cor_was_only_analytic': True})
            del context['ji_correction_account_or_tp_changed']

    def button_cancel(self, cr, uid, ids, context=None):
        """
        Close wizard and return on another wizard if 'from' and 'wiz_id' are in context
        """
        # Some verifications
        if not context:
            context = {}
        if 'from' in context and 'wiz_id' in context:
            wizard_name = context.get('from')
            wizard_id = context.get('wiz_id')
            return {
                'type': 'ir.actions.act_window',
                'res_model': wizard_name,
                'target': 'new',
                'view_mode': 'form,tree',
                'view_type': 'form',
                'res_id': wizard_id,
                'context': context,
            }
        return super(analytic_distribution_wizard, self).button_cancel(cr, uid, ids, context=context)

    def button_confirm(self, cr, uid, ids, context=None):
        """
        Change wizard state in order to use normal method
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        # Change wizard state if current is 'correction'
        for wiz in self.browse(cr, uid, ids, context=context):
            if wiz.state == 'correction':
                self.write(cr, uid, ids, {'state': 'dispatch'}, context=context)
            if context.get('from', False) == 'wizard.journal.items.corrections' and 'wiz_id' in context:
                # Update cost center lines
                #if not self.update_cost_center_lines(cr, uid, wiz.id, context=context):
                #    raise osv.except_osv(_('Error'), _('Cost center update failure.'))
                # Do some verifications before writing elements
                self.wizard_verifications(cr, uid, wiz.id, context=context)
                # Verify old account and new account
                account_or_tp_changed = False
                new_account_id = wiz.account_id and wiz.account_id.id or False
                old_account_id = wiz.old_account_id and wiz.old_account_id.id or False
                new_tp = wiz.new_partner_id or wiz.new_employee_id or False
                old_tp = wiz.old_partner_id or wiz.old_employee_id or False
                if (old_account_id != new_account_id) or (new_tp != old_tp):
                    account_or_tp_changed = True

                # Account and/or Third Party AND/OR Distribution have changed
                context['ji_correction_account_or_tp_changed'] = account_or_tp_changed
                if account_or_tp_changed:
                    # Create new distribution
                    new_distrib_id = self.pool.get('analytic.distribution').create(cr, uid, {})
                    # Write current distribution to the new one
                    self.write(cr, uid, [wiz.id], {'distribution_id': new_distrib_id})
                    super(analytic_distribution_wizard, self).button_confirm(cr, uid, ids, context=context)
                    # Return to the default corrections wizard
                    self.pool.get('wizard.journal.items.corrections').write(cr, uid, [context.get('wiz_id')], {'date': wiz.date})
                    return self.pool.get('wizard.journal.items.corrections').action_confirm(cr, uid, context.get('wiz_id'), distrib_id=new_distrib_id)
                # JUST Distribution have changed
                else:
                    # Check all lines to proceed to change
                    self.do_analytic_distribution_changes(cr, uid, wiz.id, wiz.distribution_id.id, context=context)
                    return {'type': 'ir.actions.act_window_close'}
        # Get default method
        return super(analytic_distribution_wizard, self).button_confirm(cr, uid, ids, context=context)

analytic_distribution_wizard()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
