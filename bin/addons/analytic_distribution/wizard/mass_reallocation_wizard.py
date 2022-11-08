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
import logging
from msf_field_access_rights.osv_override import _get_instance_level

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
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not context:
            context = {}
        # browse elements
        for wiz in self.browse(cr, uid, ids, context=context):
            res[wiz.id] = {'nb_error': len(wiz.error_ids),
                           'nb_process': len(wiz.process_ids),
                           'nb_other': len(wiz.other_ids)}
        return res

    _columns = {
        'account_id': fields.many2one('account.analytic.account', string="Analytic Account", required=True, readonly=True),
        'date': fields.date('Posting date', required=True, readonly=True),
        'error_ids': fields.many2many('account.analytic.line', 'mass_reallocation_error_rel', 'wizard_id', 'analytic_line_id', string="Errors", readonly=True),
        'other_ids': fields.many2many('account.analytic.line', 'mass_reallocation_non_supported_rel', 'wizard_id', 'analytic_line_id', string="Non supported", readonly=True),
        'process_ids': fields.many2many('account.analytic.line', 'mass_reallocation_process_rel', 'wizard_id', 'analytic_line_id', string="Allocatable", readonly=True),
        'reallocated_ids': fields.many2many('account.analytic.line', 'mass_reallocation_reallocated_rel', 'wizard_id','analytic_line_id', string="Allocated", readonly=True),
        'nb_error': fields.function(_get_total, string="Items excluded from reallocation", type='integer', method=True, store=False, multi="mass_reallocation_check"),
        'nb_process': fields.function(_get_total, string="Allocatable items", type='integer', method=True, store=False, multi="mass_reallocation_check"),
        'nb_reallocated': fields.integer('Reallocated items', readonly=True),
        'nb_other': fields.function(_get_total, string="Excluded lines", type='integer', method=True, store=False, multi="mass_reallocation_check"),
        'display_fp': fields.boolean('Display FP'),
        'process_in_progress': fields.boolean('Process in progress'),
        'state': fields.selection([('draft', 'Draft'), ('inprogress', 'In Progress'), ('done', 'Done')], string='State', readonly=True),
        'percent': fields.float('Process percentage', readonly=True),
        'message': fields.char(string='Message', size=256, readonly=True),
    }

    _defaults = {
        'display_fp': lambda *a: False,
        'process_in_progress': lambda *a: False,
        'state': lambda *a: 'draft',
        'percent': 0.0,
        'message': _('Processing to the Mass Reallocation...'),
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

    def process_thread(self, cr, uid, ids, context=None):
        cr = pooler.get_db(cr.dbname).cursor()
        reallocated_ids = []
        # Browse all given wizard
        try:
            for wiz in self.browse(cr, uid, ids, context=context):
                values = {'process_in_progress': True}
                super(mass_reallocation_verification_wizard, self).write(cr, uid, [wiz.id], values, context=context)
                # If no supporteds_ids, raise an error
                if not wiz.process_ids:
                    raise osv.except_osv(_('Error'), _('No lines to be processed.'))
                # Prepare some values
                account_id = wiz.account_id and wiz.account_id.id
                # Sort by distribution
                lines = defaultdict(list)
                for line in wiz.process_ids:
                    lines[line.distribution_id.id].append(line)
                # Process each distribution
                for distrib_id in lines:
                    # UF-2205: fix problem with lines that does not have any distribution line or distribution id (INTL engagement lines)
                    if not distrib_id:
                        continue
                    for line in lines[distrib_id]:
                        # Update distribution
                        self.pool.get('analytic.distribution').update_distribution_line_account(cr, uid, line.distrib_line_id.id, account_id, context=context)
                        reallocated_ids.append(line)
                        # Then update the wizard to show advancement
                        values = {'reallocated_ids': [(6, 0, reallocated_ids)],
                                  'nb_reallocated': len(reallocated_ids),
                                  'percent': len(reallocated_ids) * 100 / int(wiz.nb_process)}
                        self.write(cr, uid, ids, values, context=context)
                    # Then update analytic line
                    self.pool.get('account.analytic.line').update_account(cr, uid, [x.id for x in lines[distrib_id]], account_id, wiz.date, context=context)
            cr.commit()
        finally:
            values = {'process_in_progress': False}
            super(mass_reallocation_verification_wizard, self).write(cr, uid, ids, values, context=context)
            cr.close(True)

    def button_cancel(self, cr, uid, ids, context=None):
        """
        Cancel the reallocation process
        """
        return False

    def button_update(self, cr, uid, ids, context=None):
        """
        Updates view to update the progress bar
        """
        return False

    def _update_percent(self, cr, uid, ids, percent, context=None, use_new_cursor=False):
        """
        Update the process percentage
        """
        self.write(cr, uid, ids, {'percent': percent}, context=context)

    def _update_message(self, cr, uid, ids, message, context=None, use_new_cursor=False):
        """
        Updates the message displayed in the wizard
        """
        self.write(cr, uid, ids, {'message': message}, context=context)

    def _mass_reallocation_process(self, cr, uid, ids, context=None, use_new_cursor=False):
        """
        Updates all the allocatable AJIs
        """
        if context is None:
            context = {}
        if use_new_cursor:
            cr = pooler.get_db(cr.dbname).cursor()
        try:
            self.write(cr, uid, ids, {'state': 'inprogress'}, context=context)
            # TODO: update AJI (see process_thread) + update msg + update percent + create & update Reallocated items list
            self._update_percent(cr, uid, ids, 1, context, use_new_cursor)  # 1% of the total process time
            self._update_message(cr, uid, ids, _('Processing...'), context, use_new_cursor)
            self.process_thread(cr, uid, ids, context=context)
        except Exception as e:
            logger = logging.getLogger('mass.reallocation.process')
            logger.error(e)
            if use_new_cursor:
                cr.rollback()
            if isinstance(e, osv.except_osv):
                error = e.value
            else:
                error = e
            error_msg = _("An error occurred%s") % (error and ':\n%s' % error or '')
            self._update_message(cr, uid, ids, error_msg, context, use_new_cursor)
        finally:
            self.write(cr, uid, ids, {'state': 'done'}, context=context)
            if use_new_cursor:
                cr.commit()
                cr.close(True)

    def button_validate(self, cr, uid, ids, context=None):
        """
        Launches the mass reallocation process in a separate thread
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        # US_366: Check if a wizard is already in progress
        wiz_mass_obj = self.pool.get('mass.reallocation.verification.wizard')
        wiz_in_progress = wiz_mass_obj.search(cr, 1, [('process_in_progress', '=', True)], context=context)
        if wiz_in_progress:
            raise osv.except_osv(_('Error'), _('A Mass Reallocation process is already in progress'))
        th = threading.Thread(
            target=self._mass_reallocation_process,
            args=(cr, uid, ids, context, True),
        )
        th.start()
        return True

    def button_ok(self, cr, uid, ids, context=None):
        """
        Goes back to the analytic lines view
        """
        ir_model_obj = self.pool.get('ir.model.data')
        # TODO: update the context to display either the AJI or the Free1/2 view + the domain if necessary + the name of the view returned
        if context is None:
            context = {}
        domain = []
        view_id = ir_model_obj.get_object_reference(cr, uid, 'account', 'view_account_analytic_line_tree')
        view_id = view_id and view_id[1] or False
        search_view_id = ir_model_obj.get_object_reference(cr, uid, 'account', 'view_account_analytic_line_filter')
        search_view_id = search_view_id and search_view_id[1] or False
        return {
            'name': _('Analytic Journal Items'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.analytic.line',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'view_id': [view_id],
            'search_view_id': [search_view_id],
            'context': context,
            'domain': domain,
            'target': 'new',
        }

mass_reallocation_verification_wizard()

class mass_reallocation_wizard(osv.osv_memory):
    _name = 'mass.reallocation.wizard'
    _description = 'Mass Reallocation Wizard'

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
            if isinstance(ids, (int, long)):
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
            view['arch'] = etree.tostring(tree)
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

    def button_validate(self, cr, uid, ids, context=None):
        """
        Launch mass reallocation process
        """
        # Some verifications
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        # US_366: Check if a wizard is already in progress
        wiz_mass_obj = self.pool.get('mass.reallocation.verification.wizard')
        wiz_in_progress = wiz_mass_obj.search(cr, 1, [('process_in_progress', '=', True)], context=context)
        if wiz_in_progress:
            raise osv.except_osv(_('Error'), _('A Mass Reallocation process is already in progress'))

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
        self.check_date(cr, uid, ids, process_ids, date, context)
        verif_id = self.pool.get('mass.reallocation.verification.wizard').create(cr, uid, vals, context=context)
        # Create Mass Reallocation Verification Wizard
        return {
            'name': "Verification Result",
            'type': 'ir.actions.act_window',
            'res_model': 'mass.reallocation.verification.wizard',
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'current',
            'res_id': [verif_id],
            'context': context,
        }

mass_reallocation_wizard()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
