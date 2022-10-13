# encoding: utf-8
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO consulting
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
from osv import osv, fields
from tools.translate import _
from base import currency_date

import base64
import StringIO
import csv
import time
import threading
import pooler
import tools


class import_commitment_wizard(osv.osv_memory):
    _name = 'import.commitment.wizard'
    _description = 'Wizard for Importing Commitments'

    _columns = {
        'import_file': fields.binary("CSV File"),
        'start_date': fields.datetime('Import Date', readonly='1'),
        'in_progress': fields.boolean('In Progress', readonly='1'),
        'error': fields.text('Error', readonly='1'),
        'progress': fields.char('Import in progress', size=512, readonly='1'),
        'last_stop': fields.datetime('End Date', readonly='1'),
        'last_error': fields.datetime('Message', readonly='1'),
    }

    _defaults = {
        'in_progress': False,
    }

    def refresh(self, cr, uid, ids, context=None):
        wiz_ids = self.search(cr, 1, [('in_progress', '=', True)])
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'import.commitment.wizard',
            'res_id': wiz_ids and wiz_ids[0] or False,
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'context': context or {},
        }

    def default_get(self, cr, uid, fields, context=None, from_web=False):
        ids = self.search(cr, 1, [('in_progress', '=', True)])
        if ids:
            d = self.read(cr, 1, ids, ['start_date', 'progress'], context=context)
            return {
                'start_date': d[0]['start_date'],
                'progress':  d[0]['progress'],
                'in_progress': False,
            }

        d = super(import_commitment_wizard, self).default_get(cr, uid, fields, context, from_web=from_web)
        ir_config = self.pool.get('ir.config_parameter')
        d['last_stop'] = ir_config.get_param(cr, 1, 'LAST_COMMIT_DATE')
        d['last_error'] = ir_config.get_param(cr, 1, 'LAST_COMMIT_ERROR')
        d['in_progress'] = False
        return d

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        if view_type == 'form':
            if self.search(cr, 1, [('in_progress', '=', True)]):
                view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'analytic_distribution', 'import_commitment_wizard_progress_view')[1]

        return super(import_commitment_wizard, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)

    def open_ana_lines(self, cr, uid, ids, context=None):
        action = self.pool.get('ir.actions.act_window').for_xml_id(cr, uid,
                                                                   'analytic_distribution',
                                                                   'action_engagement_line_tree',
                                                                   context=context)
        if action:
            if action.get('context', False):
                action['context'] = action['context'].replace(
                    'search_default_engagements',
                    'search_default_intl_engagements')
            action['target'] = 'same'
        else:
            action = {'type' : 'ir.actions.act_window_close'}
        return action

    def import_csv_commitment_lines(self, cr, uid, ids, context=None):
        try:
            if self.search(cr, 1, [('in_progress', '=', True)]):
                return True

            self.write(cr, uid, ids, {'in_progress': True, 'start_date': time.strftime('%Y-%m-%d %H:%M:%S'), 'error': False}, context=context)
            new_thread = threading.Thread(target=self.import_csv_commitment_lines_bg, args=(cr, uid, ids, context))
            new_thread.start()
            new_thread.join(10.0)
            if new_thread.isAlive():
                return self.refresh(cr, uid, ids, context=context)
            else:
                error = self.read(cr, uid, ids[0], ['error'])['error']
                if error:
                    raise osv.except_osv(_('Error'), tools.ustr(error))
                # US-97: go to tree with intl engagements as default
                return self.open_ana_lines(cr, uid, ids, context)
        except:
            all_wiz = self.search(cr, 1, [])
            self.write(cr, 1, all_wiz, {'in_progress': False}, context=context)
            raise

    def import_csv_commitment_lines_bg(self, old_cr, uid, ids, context=None):
        def check_date_not_in_hq_closed_period(pool, cr, uid, dt, line_index,
                                               context=None):
            domain = [
                ('date_start', '<=', dt),
                ('date_stop', '>=', dt),
                ('state', '=', 'done'),  # hq-closed
            ]
            count = pool.get('account.period').search(cr, uid, domain,
                                                      count=True, context=context)
            if count and count > 0:
                msg_tpl = _("Line %d: No posting and/or document date set." \
                            " So today date should be used by default. But today is" \
                            " in a HQ-Closed period. Import aborted.")
                raise osv.except_osv(_('Error'), msg_tpl % (line_index, ))
            return True

        if context is None:
            context = {}
        cr = pooler.get_db(old_cr.dbname).cursor()
        try:
            analytic_obj = self.pool.get('account.analytic.line')
            instance_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.instance_id.id
            journal_ids = self.pool.get('account.analytic.journal').search(cr, uid, [('code', '=', 'ENGI'), ('is_current_instance', '=', True)], context=context)
            to_be_deleted_ids = analytic_obj.search(cr, uid, [('imported_commitment', '=', True)], context=context)
            functional_currency_obj = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id
            default_founding_pool_id = self.pool.get('account.analytic.account').search(
                cr, uid,  [('category', '=', 'FUNDING'), ('code', '=', 'PF')], context=context)
            if not default_founding_pool_id:
                raise osv.except_osv(_('Error'), _('Default PF Funding Pool not found'))
            default_founding_pool_id = default_founding_pool_id[0]

            now = False
            if not journal_ids:
                raise osv.except_osv(_('Error'), _('Analytic Journal ENGI doesn\'t exist!'))
            for wizard in self.browse(cr, uid, ids, context=context):
                if not wizard.import_file:
                    raise osv.except_osv(_('Error'), _('Nothing to import.'))
                import_file = base64.decodestring(wizard.import_file)
                import_string = StringIO.StringIO(import_file)
                import_data = list(csv.reader(import_string, quoting=csv.QUOTE_ALL, delimiter=','))
                total_line = len(import_data) - 1
                nb = 0
                sequence_number = 1
                for line in import_data[1:]:
                    nb += 1

                    if nb % 100 == 0:
                        self.write(cr, uid, ids, {'progress': '%s of %s lines.' % (nb, total_line)})

                    vals = {'imported_commitment': True,
                            'instance_id': instance_id,
                            'journal_id': journal_ids[0],
                            'imported_entry_sequence': 'ENGI-' + str(sequence_number).zfill(6)}
                    raise_msg_prefix = "Line %d: " % (sequence_number, )

                    # retrieve values
                    try:
                        description, reference, document_date, date, account_code, destination, \
                            cost_center, funding_pool, third_party,  booking_amount, booking_currency = line
                    except ValueError, e:
                        raise osv.except_osv(_('Error'), raise_msg_prefix + _('Unknown format.'))

                    # Dates
                    if not date:
                        if not now:
                            # 1st use of default posting/doc date from now
                            now = time.strftime('%Y-%m-%d')
                            check_date_not_in_hq_closed_period(self.pool, cr,
                                                               uid, now, sequence_number, context=context)
                        line_date = now  # now by default
                    else:
                        try:
                            line_date = time.strftime('%Y-%m-%d', time.strptime(date, '%d/%m/%Y'))
                        except ValueError, e:
                            raise osv.except_osv(_('Error'), raise_msg_prefix + (_('Posting date wrong format for date: %s: %s') % (date, e)))
                    context.update({'extend_december': True})  # To allow get_period_from_date to search special periods
                    period_ids = self.pool.get('account.period').get_period_from_date(cr, uid, line_date, context=context)
                    if not period_ids:
                        raise osv.except_osv(_('Warning'), raise_msg_prefix + (_('No open period found for given date: %s') % (date,)))
                    vals['date'] = line_date
                    vals['real_period_id'] = period_ids[0] or False
                    context.pop('extend_december')
                    if not document_date:
                        if not now:
                            # 1st use of default posting/doc date from now
                            now = time.strftime('%Y-%m-%d')
                            check_date_not_in_hq_closed_period(self.pool, cr,
                                                               uid, now, sequence_number, context=context)
                        line_document_date = now  # now by default
                    else:
                        try:
                            line_document_date = time.strftime('%Y-%m-%d', time.strptime(document_date, '%d/%m/%Y'))
                        except ValueError, e:
                            raise osv.except_osv(_('Error'), raise_msg_prefix + (_('Document date wrong format for date: %s: %s') % (document_date, e)))
                    vals['document_date'] = line_document_date

                    # G/L account
                    if account_code:
                        account_ids = self.pool.get('account.account').search(cr, uid, [('code', '=', account_code), ('type', '!=', 'view')])
                        if not account_ids:
                            raise osv.except_osv(_('Error'), raise_msg_prefix + (_('Account code %s doesn\'t exist!') % (tools.ustr(account_code),)))
                        vals.update({'general_account_id': account_ids[0]})
                    else:
                        raise osv.except_osv(_('Error'), raise_msg_prefix + _('No account code found!'))
                    # Destination
                    if destination:
                        dest_dom = [('code', '=', destination), ('category', '=', 'DEST'), ('type', '!=', 'view')]
                        dest_id = self.pool.get('account.analytic.account').search(cr, uid, dest_dom, context=context)
                        if dest_id:
                            vals.update({'destination_id': dest_id[0]})
                        else:
                            raise osv.except_osv(_('Error'), raise_msg_prefix + (_('Destination "%s" doesn\'t exist!') % (destination,)))
                    else:
                        # try to get default account destination by default
                        account_br = self.pool.get('account.account').browse(cr,
                                                                             uid, account_ids[0])
                        if account_br.default_destination_id:
                            vals['destination_id'] = account_br.default_destination_id.id
                            dest_id = [vals['destination_id']]
                        else:
                            msg = _("No destination code found and no default destination for account %s !") % account_code
                            raise osv.except_osv(_('Error'), raise_msg_prefix + msg)
                    # Cost Center
                    if cost_center:
                        cc_dom = [('code', '=', cost_center), ('category', '=', 'OC'), ('type', '!=', 'view')]
                        cc_id = self.pool.get('account.analytic.account').search(cr, uid, cc_dom, context=context)
                        if cc_id:
                            vals.update({'cost_center_id': cc_id[0]})
                        else:
                            raise osv.except_osv(_('Error'), raise_msg_prefix + (_('Cost Center "%s" doesn\'t exist!') % (cost_center,)))
                    else:
                        raise osv.except_osv(_('Error'), raise_msg_prefix + _('No cost center code found!'))
                    # Funding Pool
                    if funding_pool:
                        fp_dom = [('code', '=', funding_pool), ('category', '=', 'FUNDING'), ('type', '!=', 'view')]
                        fp_id = self.pool.get('account.analytic.account').search(cr, uid, fp_dom, context=context)
                        if fp_id:
                            vals.update({'account_id': fp_id[0]})
                        else:
                            raise osv.except_osv(_('Error'), raise_msg_prefix +_(('Funding Pool "%s" doesn\'t exist!') % (funding_pool,)))
                    else:
                        vals['account_id'] = default_founding_pool_id
                        fp_id = [default_founding_pool_id]
                    # description
                    if description:
                        vals.update({'name': description})
                        # Fetch reference
                    if reference:
                        vals.update({'ref': reference})
                    # Fetch 3rd party
                    if third_party:
                        vals.update({'imported_partner_txt': third_party})
                        # Search if 3RD party exists as partner
                        partner_domain = [('name', '=', third_party), ('partner_type', '=', 'esc'), ('active', 'in', ['t', 'f'])]
                        if not self.pool.get('res.partner').search_exist(cr, uid, partner_domain, context=context):
                            raise osv.except_osv(_('Error'), raise_msg_prefix + (_('No ESC partner found for code %s !') % (third_party)))
                    # currency
                    if booking_currency:
                        currency_ids = self.pool.get('res.currency').search(cr, uid, [('name', '=', booking_currency), ('active', 'in', [False, True])])
                        if not currency_ids:
                            raise osv.except_osv(_('Error'), raise_msg_prefix + (_('This currency was not found or is not active: %s') % (booking_currency,)))
                        if currency_ids and currency_ids[0]:
                            vals.update({'currency_id': currency_ids[0]})
                            # Functional currency
                            if functional_currency_obj.name == booking_currency:
                                vals.update({'amount': -float(booking_amount)})
                            else:
                                # lookup id for code
                                line_currency_id = self.pool.get('res.currency').search(cr,uid,[('name','=',booking_currency)])[0]
                                curr_date = currency_date.get_date(self, cr, line_document_date, line_date)
                                date_context = {'currency_date': curr_date}
                                converted_amount = self.pool.get('res.currency').compute(
                                    cr,
                                    uid,
                                    line_currency_id,
                                    functional_currency_obj.id,
                                    -float(booking_amount),
                                    round=True,
                                    context=date_context
                                )
                                vals.update({'amount': converted_amount})
                    else:
                        raise osv.except_osv(_('Error'), raise_msg_prefix +_('No booking currency found!'))
                    # Fetch amount
                    if booking_amount:
                        vals.update({'amount_currency': -float(booking_amount)})
                    else:
                        raise osv.except_osv(_('Error'), raise_msg_prefix + _('No booking amount found!'))

                    # Check AJI consistency
                    no_compat = analytic_obj.check_dest_cc_fp_compatibility(cr,
                                                                            uid, False,
                                                                            dest_id=dest_id[0], cc_id=cc_id[0], fp_id=fp_id[0],
                                                                            from_import=True,
                                                                            from_import_general_account_id=account_ids[0],
                                                                            from_import_posting_date=line_date,
                                                                            context=context)
                    if no_compat:
                        no_compat = no_compat[0]
                        # no compatible AD
                        msg = _("Dest / Cost Center / Funding Pool are not" \
                                " compatible for entry name:'%s', ref:'%s'" \
                                " reason: '%s'")
                        raise osv.except_osv(_('Error'), msg % (
                            tools.ustr(vals.get('name', '')), tools.ustr(vals.get('ref', '')),
                            _(no_compat[2]) or '', )
                        )

                    analytic_obj.create(cr, uid, vals, context=context)
                    sequence_number += 1


            self.write(cr, uid, ids, {'progress': 'deleting %s previous AJIs' % (len(to_be_deleted_ids), )})
            analytic_obj.unlink(cr, uid, to_be_deleted_ids, context=context)
            self.pool.get('ir.config_parameter').set_param(cr, 1, 'LAST_COMMIT_ERROR',  '%d lines imported.' % (nb,))
            self.pool.get('ir.config_parameter').set_param(cr, 1, 'LAST_COMMIT_DATE', time.strftime('%Y-%m-%d %H:%M:%S'))

        except Exception, e:
            msg = hasattr(e, 'value') and e.value or e.message
            self.write(cr, 1, ids, {'in_progress': False, 'error': tools.ustr(msg)})
            cr.rollback()
            self.pool.get('ir.config_parameter').set_param(cr, 1, 'LAST_COMMIT_ERROR',  tools.ustr(msg))
            self.pool.get('ir.config_parameter').set_param(cr, 1, 'LAST_COMMIT_DATE', time.strftime('%Y-%m-%d %H:%M:%S'))
        finally:
            self.write(cr, 1, ids, {'in_progress': False})
            cr.commit()
            cr.close(True)


import_commitment_wizard()


class int_commitment_clear_wizard(osv.osv_memory):
    _name = 'int.commitment.clear.wizard'
    _description = 'Clear Intl Commitments Wizard'

    def _get_to_del_ids(self, cr, uid, context=None, count=False):
        domain = [
            ('type', '=', 'engagement'),
            ('code', '=', 'ENGI'),
        ]
        journal_ids = self.pool.get('account.analytic.journal').search(cr, uid,
                                                                       domain, context=context)
        if not journal_ids:
            return False

        domain = [
            ('imported_commitment', '=', True),
            ('journal_id', 'in', journal_ids),
        ]
        res_ids = self.pool.get('account.analytic.line').search(cr, uid, domain,
                                                                context=context, count=count)
        return res_ids

    _columns = {
        'entries_count': fields.integer('Count Intl Commitments to delete'),
    }

    _defaults = {
        'entries_count': lambda s, cr, uid, context: s._get_to_del_ids(cr, uid, context=context, count=True),
    }

    def mass_delete(self, cr, uid, ids, context=None):
        to_del_ids = self._get_to_del_ids(cr, uid, context=context, count=False)
        if to_del_ids:
            self.pool.get('account.analytic.line').unlink(cr, uid, to_del_ids,
                                                          context=context)
        return {'type': 'ir.actions.act_window_close'}

int_commitment_clear_wizard()


class int_commitment_export_wizard(osv.osv_memory):
    _name = 'int.commitment.export.wizard'
    _description = 'Export Intl Commitments'

    _csv_filename_pattern = 'Intl_Commitments_%s.csv'
    _csv_delimiter = ','
    _csv_header = ['Description', 'Ref', 'Document Date', 'Posting Date',
                   'General Account', 'Destination', 'Cost Center' , 'Funding Pool',
                   'Third Party', 'Booking Amount', 'Booking Currency', ]

    _columns = {
        'data': fields.binary('File', readonly=True),
        'name': fields.char('File Name', 128, readonly=True),
        'state': fields.selection((('choose','choose'), ('get','get'), ),
                                  readonly=True, invisible=True),
    }

    _defaults = {
        'state': lambda *a: 'choose',
    }

    def button_export(self, cr, uid, ids, context=None):
        aal_obj = self.pool.get('account.analytic.line')

        instance_name = self.pool.get('res.users').browse(cr, uid, [uid],
                                                          context=context)[0].company_id.instance_id.name or ''
        file_name = self._csv_filename_pattern % (instance_name, )

        # csv prepare and header
        csv_buffer = StringIO.StringIO()
        csv_writer = csv.writer(csv_buffer, delimiter=self._csv_delimiter,
                                quoting=csv.QUOTE_MINIMAL)
        csv_writer.writerow(self._csv_header)

        # data lines
        domain = [
            ('journal_id.type', '=', 'engagement'),
            ('journal_id.code', '=', 'ENGI'),
        ]
        export_ids = aal_obj.search(cr, uid, domain, context=context)
        for export_br in aal_obj.browse(cr, uid, export_ids, context=context):
            line_data = self._export_entry(export_br)
            csv_writer.writerow(map(lambda x: isinstance(x, unicode) and x.encode('utf8') or x, line_data))

        # download csv
        vals = {
            'state': 'get',
            'data': base64.encodestring(csv_buffer.getvalue()),
            'name': file_name,
        }
        csv_buffer.close()
        return self.write(cr, uid, ids, vals, context=context)

    def _export_entry(self, item_br):
        def decode_m2o(m2o, want_code=False):
            if not m2o:
                return ''
            res = m2o.code if want_code else m2o.name
            return res or ''

        def decode_date(dt):
            # '%Y-%m-%d' orm -> '%d/%m/%Y' of import csv format
            return dt and time.strftime('%d/%m/%Y', time.strptime(dt, '%Y-%m-%d')) or ''

        return [
            # Description
            decode_m2o(item_br),

            # Ref
            item_br.ref or '',

            # Document Date
            decode_date(item_br.document_date),

            # Posting Date
            decode_date(item_br.date),

            # General Account
            decode_m2o(item_br.general_account_id, want_code=True),

            # Destination
            decode_m2o(item_br.destination_id, want_code=True),

            # Cost Center
            decode_m2o(item_br.cost_center_id, want_code=True),

            # Funding Pool
            decode_m2o(item_br.account_id, want_code=True),

            # Third Party
            item_br.partner_txt or '',

            # Booking Amount
            str(-1. * item_br.amount_currency),

            # Booking Currency
            decode_m2o(item_br.currency_id),
        ]


int_commitment_export_wizard()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
