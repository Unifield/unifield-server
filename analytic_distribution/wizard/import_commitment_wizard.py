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

import base64
import StringIO
import csv
import time

class import_commitment_wizard(osv.osv_memory):
    _name = 'import.commitment.wizard'
    _description = 'Wizard for Importing Commitments'

    _columns = {
        'import_file': fields.binary("CSV File"),
    }

    def import_csv_commitment_lines(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        analytic_obj = self.pool.get('account.analytic.line')
        instance_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.instance_id.id
        journal_ids = self.pool.get('account.analytic.journal').search(cr, uid, [('code', '=', 'ENGI')], context=context)
        to_be_deleted_ids = analytic_obj.search(cr, uid, [('imported_commitment', '=', True)], context=context)
        functional_currency_obj = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id

        if len(journal_ids) > 0:
            # read file
            for wizard in self.browse(cr, uid, ids, context=context):
                if not wizard.import_file:
                    raise osv.except_osv(_('Error'), _('Nothing to import.'))
                import_file = base64.decodestring(wizard.import_file)
                import_string = StringIO.StringIO(import_file)
                import_data = list(csv.reader(import_string, quoting=csv.QUOTE_ALL, delimiter=','))

                sequence_number = 1
                for line in import_data[1:]:
                    vals = {'imported_commitment': True,
                            'instance_id': instance_id,
                            'journal_id': journal_ids[0],
                            'imported_entry_sequence': 'ENGI-' + str(sequence_number).zfill(6)}

                    # retrieve values
                    try:
                        description, reference, document_date, date, account_code, destination, \
                        cost_center, funding_pool, third_party,  booking_amount, booking_currency = line
                    except ValueError, e:
                        raise osv.except_osv(_('Error'), _('Unknown format.'))

                    # Dates
                    now = time.strftime('%Y-%m-%d')
                    if not date:
                        line_date = now  # now by default
                    else:
                        try:
                            line_date = time.strftime('%Y-%m-%d', time.strptime(date, '%d/%m/%Y'))
                        except ValueError, e:
                            raise osv.except_osv(_('Error'), _('Wrong format for date: %s: %s') % (date, e))
                    period_ids = self.pool.get('account.period').get_period_from_date(cr, uid, line_date)
                    if not period_ids:
                        raise osv.except_osv(_('Warning'), _('No open period found for given date: %s') % (date,))
                    vals['date'] = line_date
                    if not document_date:
                        line_document_date = now  # now by default
                    else:
                        try:
                            line_document_date = time.strftime('%Y-%m-%d', time.strptime(document_date, '%d/%m/%Y'))
                        except ValueError, e:
                            raise osv.except_osv(_('Error'), _('Wrong format for date: %s: %s') % (document_date, e))
                    vals['document_date'] = line_document_date

                    # G/L account
                    if account_code:
                        account_ids = self.pool.get('account.account').search(cr, uid, [('code', '=', account_code)])
                        if not account_ids:
                            raise osv.except_osv(_('Error'), _('Account code %s doesn\'t exist!') % (account_code,))
                        vals.update({'general_account_id': account_ids[0]})
                    else:
                        raise osv.except_osv(_('Error'), _('No account code found!'))
                    # Destination
                    if destination:
                        dest_id = self.pool.get('account.analytic.account').search(cr, uid, ['|', ('code', '=', destination), ('name', '=', destination)])
                        if dest_id:
                            vals.update({'destination_id': dest_id[0]})
                        else:
                            raise osv.except_osv(_('Error'), _('Destination "%s" doesn\'t exist!') % (destination,))
                    else:
                        raise osv.except_osv(_('Error'), _('No destination code found!'))
                    # Cost Center
                    if cost_center:
                        cc_id = self.pool.get('account.analytic.account').search(cr, uid, ['|', ('code', '=', cost_center), ('name', '=', cost_center)])
                        if cc_id:
                            vals.update({'cost_center_id': cc_id[0]})
                        else:
                            raise osv.except_osv(_('Error'), _('Cost Center "%s" doesn\'t exist!') % (cost_center,))
                    else:
                        raise osv.except_osv(_('Error'), _('No cost center code found!'))
                    # Funding Pool
                    if funding_pool:
                        fp_id = self.pool.get('account.analytic.account').search(cr, uid, ['|', ('code', '=', funding_pool), ('name', '=', funding_pool)])
                        if fp_id:
                            vals.update({'account_id': fp_id[0]})
                        else:
                            raise osv.except_osv(_('Error'), _('Funding Pool "%s" doesn\'t exist!') % (funding_pool,))
                    else:
                        raise osv.except_osv(_('Error'), _('No funding pool code found!'))
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
                        partner_ids = self.pool.get('res.partner').search(cr, uid, [('&'), ('name', '=', third_party), ('partner_type', '=', 'esc')])
                        if not len(partner_ids) > 0:
                            raise osv.except_osv(_('Error'), _('No ESC partner found for code %s !') % (third_party))
                    # UFTP-60: Third party is not mandatory
#                    else:
#                        raise osv.except_osv(_('Error'), _('No third party found!'))
                    # currency
                    if booking_currency:
                        currency_ids = self.pool.get('res.currency').search(cr, uid, [('name', '=', booking_currency), ('active', 'in', [False, True])])
                        if not currency_ids:
                            raise osv.except_osv(_('Error'), _('This currency was not found or is not active: %s') % (booking_currency,))
                        if currency_ids and currency_ids[0]:
                            vals.update({'currency_id': currency_ids[0]})
                            # Functional currency
                            if functional_currency_obj.name == booking_currency:
                                vals.update({'amount': -float(booking_amount)})
                            else:
                                # lookup id for code
                                line_currency_id = self.pool.get('res.currency').search(cr,uid,[('name','=',booking_currency)])[0]
                                date_context = {'date': line_date }
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
                        raise osv.except_osv(_('Error'), _('No booking currency found!'))
                    # Fetch amount
                    if booking_amount:
                        vals.update({'amount_currency': -float(booking_amount)})
                    else:
                        raise osv.except_osv(_('Error'), _('No booking amount found!'))

                    analytic_obj.create(cr, uid, vals, context=context)
                    sequence_number += 1

        else:
            raise osv.except_osv(_('Error'), _('Analytic Journal ENGI doesn\'t exist!'))

        analytic_obj.unlink(cr, uid, to_be_deleted_ids, context=context)

        return {'type' : 'ir.actions.act_window_close'}

import_commitment_wizard()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
