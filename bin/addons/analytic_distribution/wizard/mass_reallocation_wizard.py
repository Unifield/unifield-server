#!/usr/bin/env python
# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF. All Rights Reserved
#    Developer: TeMPO Consulting
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
from collections import defaultdict
from time import strftime
from lxml import etree
import threading
import pooler
from msf_field_access_rights.osv_override import _get_instance_level
from base import currency_date
import logging
from tools.misc import get_traceback

class mass_reallocation_verification_wizard(osv.osv_memory):
    _name = 'mass.reallocation.verification.wizard'
    _description = 'Mass Reallocation Verification Wizard'

    def _get_total(self, cr, uid, ids, field_name, arg, context=None):
        """
        Get total of lines for given field_name
        """
        # Prepare some value
        res = {}
        # Some verifications
        if isinstance(ids, int):
            ids = [ids]
        if not context:
            context = {}
        # browse elements
        for wiz in self.browse(cr, uid, ids, context=context):
            res[wiz.id] = {'nb_error': len(wiz.error_ids), 'nb_process': len(wiz.process_ids), 'nb_other': len(wiz.other_ids)}
        return res

    _columns = {
        'account_id': fields.many2one('account.analytic.account', string="Analytic Account", required=True, readonly=True),
        'date': fields.date('Posting date', required=True, readonly=True),
        'error_ids': fields.many2many('account.analytic.line', 'mass_reallocation_error_rel', 'wizard_id', 'analytic_line_id', string="Errors", readonly=True),
        'other_ids': fields.many2many('account.analytic.line', 'mass_reallocation_non_supported_rel', 'wizard_id', 'analytic_line_id', string="Non supported", readonly=True),
        'process_ids': fields.many2many('account.analytic.line', 'mass_reallocation_process_rel', 'wizard_id', 'analytic_line_id', string="Allocatable", readonly=True),
        'done_ids': fields.many2many('account.analytic.line', 'mass_reallocation_done_rel', 'wizard_id', 'analytic_line_id', string="Processed", readonly=True),
        'nb_error': fields.function(_get_total, string="Items excluded from reallocation", type='integer', method=True, store=False, multi="mass_reallocation_check"),
        'nb_process': fields.function(_get_total, string="Allocatable items", type='integer', method=True, store=False, multi="mass_reallocation_check"),
        'nb_done': fields.char('NB lines done', readonly=1, size=256),
        'nb_other': fields.function(_get_total, string="Excluded lines", type='integer', method=True, store=False, multi="mass_reallocation_check"),
        'display_fp': fields.boolean('Display FP'),
        'process_in_progress': fields.boolean('Process in progress'),
        'state': fields.selection([('draft', 'Draft'), ('inprogress', 'In Progress'), ('done', 'Done'), ('error', 'Error'), ('cancel', 'Cancel'), ('ack', 'ack')], string='State', readonly=True),
        'message': fields.char(string='Message', size=256, readonly=True),
    }

    _defaults = {
        'display_fp': lambda *a: False,
        'process_in_progress': lambda *a: False,
        'state': lambda *a: 'draft',
        'percent': 0.0,
        'nb_done': '',
        'message': lambda obj, cr, uid, context:_('Processing to the Mass Reallocation...'),
    }

    def default_get(self, cr, uid, fields=None, context=None, from_web=False):
        """
        Fetch display_fp in context
        """
        if fields is None:
            fields = []
        # Some verifications
        if not context:
            context = {}
        # Default behaviour
        res = super(mass_reallocation_verification_wizard, self).default_get(cr, uid, fields, context=context, from_web=from_web)
        # Populate line_ids field
        res['display_fp'] = context.get('display_fp', False)
        return res

    def button_cancel(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state': 'cancel', 'nb_done': '0', 'done_ids': [(6, 0, [])]}, context=None)
        return True

    def button_close(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state': 'ack'}, context=None)
        return {'type': 'ir.actions.act_window_close'}

    def process_thread(self, dbname, uid, ids, context=None):
        cr = pooler.get_db(dbname).cursor()
        # Browse all given wizard
        aline_num = ''
        aal_obj = self.pool.get('account.analytic.line')
        try:
            wiz = self.browse(cr, uid, ids[0], context=context)
            values = {'process_in_progress': True, 'state': 'inprogress'}
            self.write(cr, uid, [wiz.id], values, context=context)
            # If no supporteds_ids, raise an error
            if not wiz.process_ids:
                raise osv.except_osv(_('Error'), _('No lines to be processed.'))
            # Prepare some values
            account_id = wiz.account_id and wiz.account_id.id
            # Sort by distribution
            lines = defaultdict(list)
            total_nb_lines = 0
            distrib_line_ids = set()
            for line in wiz.process_ids:
                if line.distribution_id:
                    lines[line.distribution_id.id].append(line)
                    distrib_line_ids.add(line.distrib_line_id.id)
                    total_nb_lines += 1

            date = wiz.date
            if not date:
                date = strftime('%Y-%m-%d')
            # UTP-943: Check that period is open
            correction_period_id = self.pool.get('mass.reallocation.wizard').check_period_open(cr, uid, date, context=context)

            # Prepare some value
            context.update({'from': 'mass_reallocation'}) # this permits reallocation to be accepted when rewrite analaytic lines
            move_prefix = self.pool.get('res.users').browse(cr, uid, uid, context).company_id.instance_id.move_prefix

            ir_seq_obj = self.pool.get('ir.sequence')

            aaj_obj = self.pool.get('account.analytic.journal')
            od_analytic_journal_id = aaj_obj.get_correction_analytic_journal(cr, uid, context=context)
            if not od_analytic_journal_id:
                raise osv.except_osv(_('Error'), _('No analytic journal found for corrections!'))

            # sequence info from GL journal
            aj_obj = self.pool.get('account.journal')
            gl_correction_journal_id = aj_obj.get_correction_journal(cr, uid, context=context)
            if not gl_correction_journal_id:
                raise osv.except_osv(_('Error'), _('No GL journal found for corrections!'))
            gl_correction_journal_rec = aj_obj.browse(cr, uid, gl_correction_journal_id, context=context)

            if wiz.account_id.category == 'OC':
                vals = {'cost_center_id': account_id}
            elif wiz.account_id.category == 'DEST':
                vals = {'destination_id': account_id}
            else:
                vals = {'analytic_id': account_id}
            if wiz.account_id.category == 'FREE1':
                obj = self.pool.get('free.1.distribution.line')
            elif wiz.account_id.category == 'FREE2':
                obj = self.pool.get('free.2.distribution.line')
            else:
                obj = self.pool.get('funding.pool.distribution.line')
            obj.write(cr, uid, list(distrib_line_ids), vals, context=context)

            is_donation = {}
            gl_correction_odx_journal_rec = False
            gl_correction_odhq_journal_rec = False
            nb_done = 0
            for distrib_id in lines:
                done_ids = []
                for aline in lines[distrib_id]:
                    if self.search_exists(cr, uid, [('id', '=', wiz.id), ('state', '=', 'cancel')]):
                        self.write(cr, uid, wiz.id, {'nb_done': '0', 'done_ids': [(6, 0, [])], 'message': _('Cancelled by user')}, context=None)
                        return True
                    done_ids.append((4, aline.id))
                    aline_num = aline.entry_sequence
                    curr_date = currency_date.get_date(self, cr, aline.document_date, aline.date, source_date=aline.source_date)
                    if wiz.account_id.category not in ['OC', 'DEST']:
                        # Update account
                        aal_obj.write(cr, uid, [aline.id], {'account_id': account_id, 'ad_updated': True}, context=context)
                    else:
                        # Period verification
                        period = aline.period_id
                        # Prepare some values
                        fieldname = 'cost_center_id'
                        if wiz.account_id.category == 'DEST':
                            fieldname = 'destination_id'

                        # update or reverse ?
                        update = period and period.state not in ['done', 'mission-closed']
                        if aline.journal_id.type == 'hq':
                            # US-773/2: if HQ entry always like period closed fashion
                            update = False

                        if update:
                            # not mission close: override line
                            # Update account # Date: UTP-943 speak about original date for non closed periods
                            vals = {
                                fieldname: account_id,
                                'date': aline.date,
                                'source_date': curr_date,
                                'ad_updated': True,
                            }
                            aal_obj.write(cr, uid, [aline.id], vals, context=context)
                        # else reverse line before recreating them with right values
                        else:
                            # mission close or + or HQ entry: reverse

                            seq_num_ctx = period and {'fiscalyear_id': period.fiscalyear_id.id} or None
                            if aline.move_id.account_id.id not in is_donation:
                                is_donation[aline.move_id.account_id.id] = aline.move_id.account_id.type_for_register == 'donation'

                            if is_donation[aline.move_id.account_id.id]:
                                if not gl_correction_odx_journal_rec:
                                    gl_correction_odx_journal_id = aj_obj.get_correction_journal(cr, uid, corr_type='extra', context=context)
                                    if not gl_correction_odx_journal_id:
                                        raise osv.except_osv(_('Error'), _('No GL journal found for ODX'))
                                    gl_correction_odx_journal_rec = aj_obj.browse(cr, uid, gl_correction_odx_journal_id, context=context)
                                    odx_analytic_journal_id = aaj_obj.get_correction_analytic_journal(cr, uid, corr_type='extra', context=context)
                                    if not odx_analytic_journal_id:
                                        raise osv.except_osv(_('Error'), _('No analytic journal found for ODX!'))

                                seqnum = ir_seq_obj.get_id(cr, uid, gl_correction_odx_journal_rec.sequence_id.id, context=seq_num_ctx)
                                entry_seq = "%s-%s-%s" % (move_prefix, gl_correction_odx_journal_rec.code, seqnum)
                                corr_j = odx_analytic_journal_id
                            # Correction: of an HQ entry, or of a correction of an HQ entry
                            elif aline.journal_id.type in ('hq', 'correction_hq'):
                                if not gl_correction_odhq_journal_rec:
                                    gl_correction_odhq_journal_id = aj_obj.get_correction_journal(cr, uid, corr_type='hq', context=context)
                                    if not gl_correction_odhq_journal_id:
                                        raise osv.except_osv(_('Error'), _('No "correction HQ" journal found!'))
                                    gl_correction_odhq_journal_rec = aj_obj.browse(cr, uid, gl_correction_odhq_journal_id,
                                                                                   fields_to_fetch=['sequence_id', 'code'], context=context)
                                    odhq_analytic_journal_id = aaj_obj.get_correction_analytic_journal(cr, uid, corr_type='hq', context=context)
                                    if not odhq_analytic_journal_id:
                                        raise osv.except_osv(_('Error'), _('No "correction HQ" analytic journal found!'))
                                seqnum = ir_seq_obj.get_id(cr, uid, gl_correction_odhq_journal_rec.sequence_id.id, context=seq_num_ctx)
                                entry_seq = "%s-%s-%s" % (move_prefix, gl_correction_odhq_journal_rec.code, seqnum)
                                corr_j = odhq_analytic_journal_id
                            else:
                                # compute entry sequence
                                seqnum = ir_seq_obj.get_id(cr, uid, gl_correction_journal_rec.sequence_id.id, context=seq_num_ctx)
                                entry_seq = "%s-%s-%s" % (move_prefix, gl_correction_journal_rec.code, seqnum)
                                corr_j = od_analytic_journal_id

                            # First reverse line
                            rev_ids = aal_obj.reverse(cr, uid, [aline.id], posting_date=date)
                            # UTP-943: Shoud have a correction journal on these lines
                            aal_obj.write(cr, uid, rev_ids, {'journal_id': corr_j, 'is_reversal': True, 'reversal_origin': aline.id, 'last_corrected_id': False})
                            # then create new lines
                            cor_name = aal_obj.join_without_redundancy(aline.name, 'COR')
                            cor_ids = aal_obj.copy(cr, uid, aline.id, {fieldname: account_id, 'date': date,
                                                                       'source_date': curr_date, 'journal_id': corr_j,
                                                                       'name': cor_name, 'ref': aline.entry_sequence, 'real_period_id': correction_period_id}, context=context)
                            aal_obj.write(cr, uid, cor_ids, {'last_corrected_id': aline.id})
                            # finally flag analytic line as reallocated
                            aal_obj.write(cr, uid, [aline.id], {'is_reallocated': True})

                            if isinstance(rev_ids, int):
                                rev_ids = [rev_ids]
                            if isinstance(cor_ids, int):
                                cor_ids = [cor_ids]
                            for rev_cor_id in rev_ids + cor_ids:
                                cr.execute('update account_analytic_line set entry_sequence = %s where id = %s', (entry_seq, rev_cor_id))
                    # Set line as corrected upstream if we are in COORDO/HQ instance
                    if aline.move_id:
                        self.pool.get('account.move.line').corrected_upstream_marker(cr, uid, [aline.move_id.id], context=context)
                    nb_done += 1
                self.write(cr, uid, ids[0], {'nb_done': '%s / %s' % (nb_done, total_nb_lines), 'done_ids': done_ids}, context=context)

            self.write(cr, uid, ids[0], {'state': 'done', 'message': _('Done')}, context=context)
            cr.commit()
        except Exception as e:
            cr.rollback()
            logging.getLogger('mass.reallocation').error(get_traceback(e))
            self.write(cr, uid, ids[0], {'nb_done': '0', 'state': 'error', 'message': '%s %s' % (aline_num or '', str(e))}, context=context)
        finally:
            values = {'process_in_progress': False}
            self.write(cr, uid, ids[0], values, context=context)
            cr.close(True)

    def button_validate(self, cr, uid, ids, context=None):
        """
        Launch mass reallocation on "process_ids".
        """
        # Some verifications
        if not context:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        # US_366: Check if a wizard is already in progress
        wiz_mass_obj = self.pool.get('mass.reallocation.verification.wizard')
        wiz_in_progress = wiz_mass_obj.search(cr, 1, [('process_in_progress', '=', True)], context=context)
        if wiz_in_progress:
            raise osv.except_osv(_('Error'), _('A wizard is already \
                                               in progress'))
        process = threading.Thread(None,
                                   wiz_mass_obj.process_thread, None,
                                   (cr.dbname, uid, ids), {'context': context})
        process.start()
        process.join(1.0)
        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'analytic_distribution', 'mass_reallocation_progress_wizard_view')[1]
        all_str = ''
        if context.get('all_search'):
            all_str = _('- All search results')
        return {
            'name': '%s %s' % (_('Mass reallocation'), all_str),
            'type': 'ir.actions.act_window',
            'res_model': 'mass.reallocation.verification.wizard',
            'view_mode': 'form',
            'view_type': 'form',
            'view_id': [view_id],
            'res_id': ids[0],
            'target': 'self',
            'context': context,
            'no_pager': True,
        }


mass_reallocation_verification_wizard()

class mass_reallocation_wizard(osv.osv_memory):
    _name = 'mass.reallocation.wizard'
    _description = 'Mass Reallocation Wizard'

    def open_wizard(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        context['active_model'] = 'account.analytic.line'
        if context.get('all_search'):
            name = _('Mass reallocation - All search results')
        else:
            name = _('Mass reallocation')

        running = self.pool.get('mass.reallocation.verification.wizard').search(cr, uid, [('state', 'in', ['inprogress', 'done', 'error'])], context=context)
        if running:
            view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'analytic_distribution', 'mass_reallocation_progress_wizard_view')[1]
            return {
                'name': name,
                'type': 'ir.actions.act_window',
                'res_model': 'mass.reallocation.verification.wizard',
                'view_type': 'form',
                'view_mode': 'form',
                'view_id': [view_id],
                'context': context,
                'target': 'current',
                'res_id': running[0],
                'no_pager': True,
            }

        return {
            'name': name,
            'type': 'ir.actions.act_window',
            'res_model': 'mass.reallocation.wizard',
            'view_type': 'form',
            'view_mode': 'form',
            'context': context,
            'target': 'current',
            'no_pager': True,
        }

    def _is_process_in_progress(self, cr, uid, fields, context=None):
        wiz_mass_obj = self.pool.get('mass.reallocation.verification.wizard')
        wiz_in_progress = wiz_mass_obj.search(cr, 1, [('process_in_progress', '=', True)], context=context)
        if wiz_in_progress:
            return True
        return False

    _columns = {
        'account_id': fields.many2one('account.analytic.account', string="Analytic Account", required=True),
        'date': fields.date('Posting date', required=True),
        'line_ids': fields.many2many('account.analytic.line', 'mass_reallocation_rel', 'wizard_id', 'analytic_line_id',
                                     string="Analytic Journal Items", required=True),
        'state': fields.selection([('normal', 'Normal'), ('blocked', 'Blocked')], string="State", readonly=True),
        'display_fp': fields.boolean('Display FP'),
        'other_ids': fields.many2many('account.analytic.line', 'mass_reallocation_other_rel', 'wizard_id', 'analytic_line_id',
                                      string="Non eligible analytic journal items", required=False, readonly=True),
        'is_process_in_progress': fields.boolean(string="Is process is in progress"),
    }

    _defaults = {
        'state': lambda *a: 'normal',
        'display_fp': lambda *a: False,
        'date': lambda *a: strftime('%Y-%m-%d'),
        'is_process_in_progress': _is_process_in_progress,
    }

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        """
        Change domain for mass reallocation wizard to filter free1/free2 if we are in this case.
        Otherwise only accept OC/Dest/FP.
        """
        ids = False
        view = super(mass_reallocation_wizard, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)

        if view_type == 'form' and context and context.get('search_domain', False):
            # account.analytic.line: as soon as a search has been made the search_domain contains the criteria selected
            # and the original_domain contains the filter on account category (FUNDING, FREE1...)
            aal_obj = self.pool.get('account.analytic.line')
            args = context.get('search_domain', [])
            if context.get('original_domain'):
                args.extend(context['original_domain'])
            ids = aal_obj.search(cr, uid, args, context=context)
            context['active_ids'] = ids
        elif view_type == 'form' and context and context.get('active_ids', False):
            ids = context.get('active_ids')

        if ids:
            if isinstance(ids, int):
                ids = [ids]
            first_line = self.pool.get('account.analytic.line').browse(cr, uid, ids)[0]
            if _get_instance_level(self, cr, uid) == 'hq':
                domain = "[('category', '=', 'FUNDING'), ('type', '!=', 'view')]"
            else:
                domain = "[('category', 'in', ['OC', 'FUNDING', 'DEST']), ('type', '!=', 'view')]"
            for free in ['FREE1', 'FREE2']:
                if first_line.account_id and first_line.account_id.category == free:
                    domain = "[('category', '=', '" + free + "'), ('type', '!=', 'view')]"
            tree = etree.fromstring(view['arch'])
            fields = tree.xpath("/form/field[@name='account_id']")
            for field in fields:
                field.set('domain', domain)
            view['arch'] = etree.tostring(tree, encoding='unicode')
        return view

    def default_get(self, cr, uid, fields=None, context=None, from_web=False):
        """
        Fetch context active_ids to populate line_ids wizard field
        """
        if fields is None:
            fields = []
        # Some verifications
        if context is None:
            context = {}
        gl_acc_obj = self.pool.get('account.account')
        # Default behaviour
        res = super(mass_reallocation_wizard, self).default_get(cr, uid, fields, context=context, from_web=from_web)

        if context.get('search_domain', False):
            # account.analytic.line: as soon as a search has been made the search_domain contains the criteria selected
            # and the original_domain contains the filter on account category (FUNDING, FREE1...)
            aal_obj = self.pool.get('account.analytic.line')
            args = context.get('search_domain', [])
            if context.get('original_domain'):
                args.extend(context['original_domain'])
            ids = aal_obj.search(cr, uid, args, context=context)
            context['active_ids'] = ids

        # Populate line_ids field
        if context.get('analytic_account_from'):
            res['state'] = 'blocked'
            res['account_id'] =  context['analytic_account_from']
        if context.get('active_ids', False) and context.get('active_model', False) == 'account.analytic.line':
            res['line_ids'] = context.get('active_ids')
            # Search which lines are eligible (add another criteria if we come from project)
            not_ad_correctable_acc_ids = gl_acc_obj.search(cr, uid, [('is_not_ad_correctable', '=', True)],
                                                           order='NO_ORDER', context=context)
            search_args = [
                ('id', 'in', context.get('active_ids')), '|', '|', '|', '|', '|', '|',
                ('commitment_line_id', '!=', False), ('is_reallocated', '=', True),
                ('is_reversal', '=', True),
                ('journal_id.type', 'in', ['engagement', 'revaluation', 'cur_adj']),
                ('from_write_off', '=', True),
                ('move_state', '=', 'draft'),
                ('general_account_id', 'in', not_ad_correctable_acc_ids),
            ]
            company = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id
            if company and company.instance_id and company.instance_id.level == 'project':
                search_args = [
                    ('id', 'in', context.get('active_ids')), '|', '|', '|', '|', '|', '|', '|', '|',
                    ('commitment_line_id', '!=', False), ('is_reallocated', '=', True),
                    ('is_reversal', '=', True),
                    ('journal_id.type', 'in', ['engagement', 'revaluation', 'cur_adj']),
                    ('from_write_off', '=', True),
                    ('move_state', '=', 'draft'),
                    ('move_id', '=', False),
                    ('move_id.corrected_upstream', '=', True),
                    ('general_account_id', 'in', not_ad_correctable_acc_ids),
                ]

            search_ns_ids = self.pool.get('account.analytic.line').search(cr, uid, search_args, context=context)
            # Process lines if exist
            if search_ns_ids:
                # add non eligible lines to the right field.
                res['other_ids'] = search_ns_ids
                res['line_ids'] = [x for x in context.get('active_ids') if x not in search_ns_ids]
        res['display_fp'] = context.get('display_fp', False)
        return res

    def check_date(self, cr, uid, ids, al_ids=[], date=False, context=None):
        """
        Date should be after document date and after posting date. So for all selected lines, the date should be:
        - the youngest document date for all lines. For an example with 2 lines that have a document date to 5 januray and 6 february, the youngest date should be after February, the 6th.
        - the youngest posting date for all lines. For an example with 2 lines that have a document date to 3 March and 26 March, the new posting date should be after the 26 March.
        If the youngest document date is after the youngest posting date, there is a problem with lines. So user should refine its filtering.
        """
        # Some verifications
        if not context:
            context = {}
        if not date or not al_ids:
            if not al_ids:
                raise osv.except_osv(_('Warning'), _('No items are eligible to be mass reallocated with the given analytic account.'))
            raise osv.except_osv(_('Error'), _('Some missing args in check_date method. Please contact an administrator.'))
        # Initialisation of Document Date and Posting Date
        dd = False
        pd = False
        for l in self.pool.get('account.analytic.line').browse(cr, uid, al_ids):
            if not dd:
                dd = l.document_date
            if not pd:
                pd = l.date
            if l.document_date > dd:
                dd = l.document_date
            if l.date > pd:
                pd = l.date

        if dd > pd:
            raise osv.except_osv(_('Error'), _('Maximum document date is superior to maximum of posting date. Check selected analytic lines dates first.'))

        # US-192 posting date regarding max doc date
        msg = _('Posting date should be later than all Document Dates. Please change it to be greater than or equal to %s') % (dd,)
        self.pool.get('finance.tools').check_document_date(cr, uid,
                                                           dd, date, custom_msg=msg, context=context)

        if date < pd:
            raise osv.except_osv(_('Warning'), _('Posting date should be later than all Posting Dates. You cannot post lines before the earliest one. Please change it to be greater than or equal to %s') % (pd,))

        return True

    def check_period_open(self, cr, uid, date, context=None):
        correction_period_id = self.pool.get('account.period').get_open_period_from_date(cr, uid, date, check_extra_config=True, context=context)
        if not correction_period_id:
            raise osv.except_osv(_('Error'), _('No open period found for this date: %s') % (date,))
        return correction_period_id


    def button_validate(self, cr, uid, ids, context=None):
        """
        Launch mass reallocation process
        """
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        # US_366: Check if a wizard is already in progress
        wiz_mass_obj = self.pool.get('mass.reallocation.verification.wizard')
        wiz_in_progress = wiz_mass_obj.search(cr, 1, [('process_in_progress', '=', True)], context=context)
        if wiz_in_progress:
            raise osv.except_osv(_('Error'), _('A wizard is already \
                                               in progress'))

        # Prepare some values
        error_ids = []
        non_supported_ids = []
        process_ids = []
        account_id = False
        date = False
        gl_acc_obj = self.pool.get('account.account')
        company = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id
        level = company and company.instance_id and company.instance_id.level or ''
        # Browse given wizard
        for wiz in self.browse(cr, uid, ids, context=context):
            to_process = [x.id for x in wiz.line_ids] or []
            account_id = wiz.account_id.id

            date = wiz.date or strftime('%Y-%m-%d')
            # Don't process lines:
            # - that have same account (or cost_center_id)
            # - that are commitment lines
            # - that have been reallocated
            # - that have been reversed
            # - that come from an engagement journal
            # - that come from a write-off (is_write_off = True)
            # - that are booked on G/L account set as is_not_ad_correctable
            # - that are booked on a Currency Adj. Analytic Journal
            account_field_name = 'account_id'
            if wiz.account_id.category == 'OC':
                account_field_name = 'cost_center_id'

            if _get_instance_level(self, cr, uid) == 'hq' and wiz.account_id.category in ['OC', 'DEST']:
                raise osv.except_osv(_('Error'), _('At HQ level you can only mass reallocate FP !'))

            not_ad_correctable_acc_ids = gl_acc_obj.search(cr, uid, [('is_not_ad_correctable', '=', True)],
                                                           order='NO_ORDER', context=context)
            search_args = [
                ('id', 'in', to_process), '|', '|', '|', '|', '|', '|', '|',
                (account_field_name, '=', account_id),
                ('commitment_line_id', '!=', False), ('is_reallocated', '=', True),
                ('is_reversal', '=', True),
                ('journal_id.type', 'in', ['engagement', 'cur_adj']),
                ('from_write_off', '=', True),
                ('move_state', '=', 'draft'),
                ('general_account_id', 'in', not_ad_correctable_acc_ids),
            ]
            if level == 'project':
                search_args = [
                    ('id', 'in', context.get('active_ids')), '|', '|', '|', '|', '|', '|', '|', '|',
                    ('commitment_line_id', '!=', False), ('is_reallocated', '=', True),
                    ('is_reversal', '=', True),
                    ('journal_id.type', 'in', ['engagement', 'revaluation', 'cur_adj']),
                    ('from_write_off', '=', True),
                    ('move_state', '=', 'draft'),
                    ('move_id', '=', False),
                    ('move_id.corrected_upstream', '=', True),
                    ('general_account_id', 'in', not_ad_correctable_acc_ids),
                ]
            search_ns_ids = self.pool.get('account.analytic.line').search(cr, uid, search_args)
            if search_ns_ids:
                non_supported_ids.extend(search_ns_ids)
            # Delete non_supported element from to_process and write them to tmp_process_ids
            tmp_to_process = [x for x in to_process if x not in non_supported_ids]
            if tmp_to_process:
                valid_ids = self.pool.get('account.analytic.line').check_analytic_account(cr, uid, tmp_to_process, account_id, date, context=context)
                process_ids.extend(valid_ids)
                error_ids.extend([x for x in tmp_to_process if x not in valid_ids])
        vals = {'account_id': account_id, 'date': date,}
        # Display of elements
        if error_ids:
            vals.update({'error_ids': [(6, 0, error_ids)]})
        if non_supported_ids:
            vals.update({'other_ids': [(6, 0, non_supported_ids)]})
        if process_ids:
            vals.update({'process_ids': [(6, 0, process_ids)]})
        # Check process_ids and date
        self.check_period_open(cr, uid, date, context)
        self.check_date(cr, uid, ids, process_ids, date, context)
        verif_id = self.pool.get('mass.reallocation.verification.wizard').create(cr, uid, vals, context=context)
        # Create Mass Reallocation Verification Wizard
        return {
            'name': "Verification Result",
            'type': 'ir.actions.act_window',
            'res_model': 'mass.reallocation.verification.wizard',
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'self',
            'res_id': [verif_id],
            'context': context,
            'no_pager': True,
        }

mass_reallocation_wizard()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
