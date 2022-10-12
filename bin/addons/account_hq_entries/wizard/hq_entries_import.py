#!/usr/bin/env python
# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2012 TeMPO Consulting, MSF. All Rights Reserved
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
from base64 import decodestring
from tempfile import NamedTemporaryFile
import csv
from tools.translate import _
import time
from account_override import ACCOUNT_RESTRICTED_AREA
from tools.misc import ustr
import threading
import pooler
import tools

class hq_entries_import_wizard(osv.osv_memory):
    _name = 'hq.entries.import'
    _description = 'HQ Entries Import Wizard'

    _columns = {
        'file': fields.binary(string="File", filters="*.csv", required=True),
        'filename': fields.char(string="Imported filename", size=256),
        'progress': fields.integer(string="Progression", readonly=True),
        'state': fields.selection([('draft', 'Draft'), ('inprogress', 'In-progress'), ('error', 'Error'), ('done', 'Done'), ('ack', 'ack')],'State', readonly=1),
        'created': fields.integer('Processed', readonly=1),
        'total': fields.integer('Total', readonly=1),
        'nberrors': fields.integer('Errors', readonly=1),
        'error': fields.text('Error', readonly=1),
        'start_date': fields.datetime('Start Date', readonly=1),
        'end_date': fields.datetime('End Date', readonly=1),
    }

    _defaults = {
        'state': 'draft',
    }
    def open_wizard(self, cr, uid, ids, context=None):
        """
            on click on menutim: display the running hq import
        """
        ids = self.search(cr, uid, [('state', 'in', ['inprogress', 'error', 'done'])], context=context)
        if ids:
            res_id = ids[0]
            view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'account_hq_entries', 'hq_entries_import_progress_wizard')[1]
        else:
            res_id = False
            view_id = False
        return {
            'name': _('HQ Entries Import'),
            'type': 'ir.actions.act_window',
            'res_model': 'hq.entries.import',
            'view_mode': 'form',
            'view_type': 'form',
            'view_id': [view_id],
            'res_id': res_id,
            'target': 'new',
            'context': context,
        }

    def parse_date(self, date):
        try:
            pdate = time.strptime(date, '%d/%m/%y')
        except ValueError:
            pdate = time.strptime(date, '%d/%m/%Y')
        return pdate
        #return time.strftime('%Y-%m-%d', pdate)

    def update_hq_entries(self, cr, uid, line, cache_data, context=None):
        """
        Import hq entry regarding all elements given in "line"
        """

        # Seems that some line could be empty
        if line.count('') == 12:
            return False
        for x in xrange(0,12-len(line)):
            line.append('')
        # Prepare some values
        vals = {
            'user_validated': False,
        }
        try:
            description, reference, document_date, date, account_description, third_party, booking_amount, booking_currency, \
                destination, cost_center, funding_pool, free1, free2 = line
        except ValueError, e:
            raise osv.except_osv(_('Error'), _('Unknown format.'))
        acc_obj = self.pool.get('account.account')
        anacc_obj = self.pool.get('account.analytic.account')
        hq_obj = self.pool.get('hq.entries')
        ### TO USE IF DATE HAVE some JAN or MAR or OCT instead of 01 ####
        ### Set locale 'C' because of period
        ## locale.setlocale(locale.LC_ALL, 'C')
        # Check period
        if not date:
            raise osv.except_osv(_('Warning'), _('A date is missing!'))
        try:
            line_date_dt = self.parse_date(date)
        except ValueError, e:
            raise osv.except_osv(_('Error'), _('Wrong format for date: %s: %s') % (date, e))

        line_date = time.strftime('%Y-%m-%d', line_date_dt)
        year_month = time.strftime('%Y-%m', line_date_dt)
        if year_month not in cache_data.setdefault('period', {}):
            cache_data['period'][year_month] = self.pool.get('account.period').get_period_from_date(cr, uid, line_date)

        period_ids = cache_data['period'][year_month]

        if not period_ids:
            raise osv.except_osv(_('Warning'), _('No open period found for given date: %s') % (line_date,))
        if len(period_ids) > 1:
            raise osv.except_osv(_('Warning'), _('More than one period found for given date: %s') % (line_date,))
        period_id = period_ids[0]
        vals.update({'period_id': period_id, 'date': line_date})
        dd = False
        if document_date:
            try:
                dd_dt = self.parse_date(document_date)
                dd = time.strftime('%Y-%m-%d', dd_dt)
                vals.update({'document_date': dd})
            except ValueError, e:
                raise osv.except_osv(_('Error'), _('Wrong format for date: %s: %s') % (document_date, e))
        # [utp-928]
        # Make it impossible to import HQ entries where Doc Date > Posting Date,
        # it will spare trouble at HQ entry validation.
        self.pool.get('finance.tools').check_document_date(cr, uid,
                                                           dd, line_date, show_date=True)
        # Retrieve account
        if not account_description:
            raise osv.except_osv(_('Error'), _('No account code found!'))

        account_data = account_description.split(' ')
        account_code = account_data and account_data[0] or False
        if not account_code:
            raise osv.except_osv(_('Error'), _('No account code found!'))

        if account_code not in cache_data.setdefault('account_gl', {}):
            cache_data['account_gl'][account_code] = acc_obj.search(cr, uid, [('code', '=', account_code)] + ACCOUNT_RESTRICTED_AREA['hq_lines_import'])
        account_ids = cache_data['account_gl'][account_code]

        if not account_ids:
            raise osv.except_osv(_('Error'), _('Account code %s doesn\'t exist or is not allowed in HQ Entries!') % (account_code,))

        if account_ids[0] not in cache_data.setdefault('account_gl_data', {}):
            account_gl_data = acc_obj.browse(cr, uid, account_ids[0], fields_to_fetch=['filter_active', 'default_destination_id', 'user_type'], context={'date': line_date})

            cache_data['account_gl_data'][account_ids[0]] = {
                'filter_active': account_gl_data.filter_active,
                'default_destination_id': account_gl_data.default_destination_id and account_gl_data.default_destination_id.id or False,
                'user_type': account_gl_data.user_type.code,
            }

        if not cache_data['account_gl_data'][account_ids[0]]['filter_active']:
            raise osv.except_osv(_('Error'), _('Account code %s is inactive for this date %s') % (account_code, date))

        vals.update({'account_id': account_ids[0], 'account_id_first_value': account_ids[0]})
        destination_id = False
        fp_id = False
        free1_id = False
        free2_id = False
        if not cost_center:
            # CC is needed for synchro (and usually it can't be added after the import in HQ because of the user rights)
            raise osv.except_osv(_('Error'), _('Cost Center is missing for the account %s.') % (account_description,))
        if cache_data['account_gl_data'][account_ids[0]]['user_type'] not in ['expense', 'income']:  # B/S accounts
            if destination or funding_pool or free1 or free2:
                raise osv.except_osv(_('Error'), _('The B/S account %s cannot have an Analytic Distribution. '
                                                   'Only a Cost Center should be given.') % (account_description,))
        else:  # expense or income accounts
            # Retrieve Destination
            # Set default destination
            if not cache_data['account_gl_data'][account_ids[0]]['default_destination_id']:
                raise osv.except_osv(_('Warning'), _('No default Destination defined for account: %s') % (account_code or '',))
            destination_id = cache_data['account_gl_data'][account_ids[0]]['default_destination_id']
            # But use those from CSV file if given
            if destination:
                if destination not in cache_data.setdefault('destination', {}):
                    cache_data['destination'][destination] = anacc_obj.search(cr, uid, ['|', ('code', '=', destination), ('name', '=', destination), ('type', '!=', 'view')])
                if not cache_data['destination'][destination]:
                    raise osv.except_osv(_('Error'), _('Destination "%s" doesn\'t exist!') % (destination,))
                destination_id = cache_data['destination'][destination][0]

            # Retrieve Funding Pool
            if funding_pool:
                if funding_pool not in cache_data.setdefault('funding_pool', {}):
                    cache_data['funding_pool'][funding_pool] = anacc_obj.search(cr, uid, ['|', ('code', '=', funding_pool), ('name', '=', funding_pool), ('category', '=', 'FUNDING'), ('type', '!=', 'view')])
                fp_id = cache_data['funding_pool'][funding_pool]
                if not fp_id:
                    raise osv.except_osv(_('Error'), _('Funding Pool "%s" doesn\'t exist!') % (funding_pool,))
                fp_id = fp_id[0]
            else:
                fp_id = cache_data['funding_pool']['private_fund']
            # Retrieve Free 1 / Free 2
            if free1:
                if free1 not in cache_data.setdefault('free1', {}):
                    cache_data['free1'][free1] = anacc_obj.search(cr, uid, ['|', ('code', '=', free1), ('name', '=', free1), ('category', '=', 'FREE1'), ('type', '!=', 'view')])
                free1_id = cache_data['free1'][free1]
                if not free1_id:
                    raise osv.except_osv(_('Error'), _('Free 1 "%s" doesn\'t exist!') % (free1,))
                free1_id = free1_id[0]
            if free2:
                if free2 not in cache_data.setdefault('free2', {}):
                    cache_data['free2'][free2] = anacc_obj.search(cr, uid, ['|', ('code', '=', free2), ('name', '=', free2), ('category', '=', 'FREE2'), ('type', '!=', 'view')])
                if not free2_id:
                    raise osv.except_osv(_('Error'), _('Free 2 "%s" doesn\'t exist!') % (free2,))
                free2_id = free2_id[0]

        # Retrieve Cost Center
        cc_id = False
        if cost_center:
            if cost_center not in cache_data.setdefault('cc', {}):
                cache_data['cc'][cost_center] = anacc_obj.search(cr, uid, ['|', ('code', '=', cost_center), ('name', '=', cost_center), ('category', '=', 'OC'), ('type', '!=', 'view')])
            cc_id = cache_data['cc'][cost_center]
            if not cc_id:
                raise osv.except_osv(_('Error'), _('Cost Center "%s" doesn\'t exist!') % (cost_center,))
            cc_id = cc_id[0]
            if cc_id:
                # check that the CC or its parent is targeted to an instance
                if cc_id not in cache_data.setdefault('cc_target', {}):
                    cache_data['cc_target'][cc_id] = hq_obj.get_target_id(cr, uid, cc_id, context=context)
                if not cache_data['cc_target'][cc_id]:
                    raise osv.except_osv(_('Error'), _('The Cost Center "%s" (or its parent) must be "targeted" to a Proprietary Instance.') % (cost_center,))

        vals.update({'destination_id_first_value': destination_id, 'destination_id': destination_id, 'cost_center_id': cc_id, 'analytic_id': fp_id, 'cost_center_id_first_value': cc_id, 'analytic_id_first_value': fp_id, 'free_1_id': free1_id, 'free_2_id': free2_id,})

        # Fetch description
        if description:
            vals.update({'name': description})
        # Fetch reference
        if reference:
            vals.update({'ref': reference})
        # Fetch 3rd party
        if third_party:
            vals.update({'partner_txt': third_party})
        # Fetch currency
        if booking_currency:
            if booking_currency not in cache_data.setdefault('currency', {}):
                cache_data['currency'][booking_currency] = self.pool.get('res.currency').search(cr, uid, [('name', '=', booking_currency), ('active', 'in', [False, True])])
            currency_ids = cache_data['currency'][booking_currency]
            if not currency_ids:
                raise osv.except_osv(_('Error'), _('This currency was not found or is not active: %s') % (booking_currency,))
            vals.update({'currency_id': currency_ids[0]})
        # Fetch amount
        if booking_amount:
            vals.update({'amount': booking_amount})

        # BKLG-63/US-414: unicity check
        # Description (name), Reference (ref), Posting date (date),
        # Document date (document_date), Amount (amount),
        # and Account (account_id) and 3rd Party and CC
        unicity_fields = [
            'name', 'ref', 'date', 'document_date', 'amount', 'account_id',
            'cost_center_id',
        ]

        unicity_domain = [
            (f, '=', vals.get(f, False)) for f in unicity_fields
        ]
        # US-414: add 3rd party for unicity check
        unicity_domain.append(('partner_txt', '=', third_party or False))

        if hq_obj.search(cr, uid, unicity_domain, limit=1, context=context):
            # raise unicity check failure
            # (fields listed like in csv order for user info)

            pattern = _("Entry already imported: %s / %s / %s (doc) /" \
                        " %s (posting) / %s (account) / %s (amount) / %s (3rd party) /" \
                        " %s (%s)")
            raise osv.except_osv(_('Error'), pattern % (
                ustr(description), ustr(reference), document_date, date,
                ustr(account_description), booking_amount,
                ustr(third_party),
                ustr(cost_center),
                'CC'
            ))

        # Line creation
        hq_obj.create(cr, uid, vals)

        if vals['cost_center_id_first_value']:
            aa_data = (account_ids[0], vals['destination_id'], vals['cost_center_id'], vals['analytic_id'], vals['date'], vals['document_date'])
            if aa_data not in cache_data.setdefault('distrib_state', {}):
                cache_data['distrib_state'][aa_data] = self.pool.get('analytic.distribution').analytic_state_from_info(cr, uid, *aa_data, check_analytic_active=True, context=context)
            state, reason = cache_data['distrib_state'][aa_data]
            if state == 'invalid':
                raise osv.except_osv(_('Error'), '%s: %s' %( _('Analytic distribution is invalid!'), reason))
            return True
        return True

    def button_validate(self, cr, uid, ids, context=None, auto_import=False):
        """
        Take a CSV file and fetch some informations for HQ Entries
        """
        # Do verifications
        if not context:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        # Verify that an HQ journal exists
        journal_ids = self.pool.get('account.journal').search(cr, uid, [('type', '=', 'hq'),
                                                                        ('is_current_instance', '=', True)])
        if not journal_ids:
            raise osv.except_osv(_('Error'), _('You cannot import HQ entries because no HQ Journal exists.'))

        # Prepare some values
        filename = ""

        # Browse all given wizard
        read_result = self.read(cr, uid, ids, ['file', 'filename'],
                                context=context)
        wiz = read_result[0]
        if not wiz['file']:
            raise osv.except_osv(_('Error'), _('Nothing to import.'))
        # Decode file string
        fileobj = NamedTemporaryFile('w+', delete=False)
        fileobj.write(decodestring(wiz['file']))
        # now we determine the file format
        fileobj.seek(0)
        # Read CSV file
        try:
            reader = csv.reader(fileobj, delimiter=',', quotechar='"')
            filename = wiz['filename'] or ""
        except:
            fileobj.close()
            raise osv.except_osv(_('Error'), _('Problem to read given file.'))
        if filename:
            if filename.split('.')[-1] != 'csv':
                raise osv.except_osv(_('Warning'), _('You are trying to import a file with the wrong file format; please import a CSV file.'))
        try:
            reader.next()
        except StopIteration:
            raise osv.except_osv(_('Error'), _('File is empty!'))

        num_line = 0
        for x in reader:
            num_line += 1

        if auto_import:
            return self.load_bg(cr.dbname, uid, wiz['id'], fileobj.name, num_line, auto_import=True, context=context)
        else:
            threading.Thread(target=self.load_bg, args=(cr.dbname, uid, wiz['id'], fileobj.name, num_line, False, context)).start()
            self.write(cr, uid, wiz['id'], {'state': 'inprogress', 'progress': 0}, context=context)

        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'account_hq_entries', 'hq_entries_import_progress_wizard')[1]
        return {
            'name': _('HQ Entries Import'),
            'type': 'ir.actions.act_window',
            'res_model': 'hq.entries.import',
            'view_mode': 'form',
            'view_type': 'form',
            'view_id': [view_id],
            'res_id': wiz['id'],
            'target': 'new',
            'context': context,
        }


    def load_bg(self, dbname, uid, wiz_id, filename, num_line, auto_import=False, context=None):
        def manage_error(line_index, msg, name='', code='', status=''):
            if auto_import:
                rejected_lines.append((line_index, [name, code, status], msg))
            else:
                errors.append(_('Line %s, %s') % (line_index, _(msg)))

        cr = pooler.get_db(dbname).cursor()
        cache_data = {}
        cache_data['funding_pool'] = {'private_fund': self.pool.get('ir.model.data').get_object_reference(cr, uid, 'analytic_distribution', 'analytic_account_msf_private_funds')[1]}
        self.write(cr, uid, wiz_id, {'start_date': time.strftime('%Y-%m-%d %H:%M:%S')}, context=context)
        try:
            fileobj = open(filename, 'r')
            reader = csv.reader(fileobj, delimiter=',', quotechar='"')
            headers = reader.next()
            line_index = 1
            processed = 0
            created = 0
            errors = []
            processed_lines = []
            rejected_lines = []
            for line in reader:
                line_index += 1
                processed += 1
                if auto_import:
                    processed_lines.append((line_index, []))
                try:
                    self.update_hq_entries(cr, uid, line, cache_data, context=context)
                    created += 1
                except osv.except_osv, e:
                    manage_error(line_index, e.value)
                if processed%10 == 0:
                    self.write(cr, uid, wiz_id, {'progress': int(processed/float(num_line)*100), 'created': created, 'nberrors': len(errors), 'error': "\n".join(errors)}, context=context)

            state = 'done'
            if errors or rejected_lines:
                cr.rollback()
                state = 'error'
                msg = "\n".join(errors)
            else:
                msg = _("HQ Entries import successful")

            if auto_import:
                return processed_lines, rejected_lines, headers

            self.write(cr, uid, wiz_id, {'progress': 100, 'state': state, 'created': created, 'total': processed, 'error': msg, 'nberrors': len(errors), 'end_date': time.strftime('%Y-%m-%d %H:%M:%S')}, context=context)

        except Exception, e:
            cr.rollback()
            if isinstance(e, osv.except_osv):
                error = e.value
            else:
                error = e
            msg = self.read(cr, uid, wiz_id, ['error'])['error'] or ''
            self.write(cr, uid, wiz_id, {'state': 'error', 'progress': 100, 'error': "%s\n%s\n%s" % (msg, tools.ustr(error), tools.get_traceback(e)), 'end_date': time.strftime('%Y-%m-%d %H:%M:%S')})
        finally:
            cr.commit()
            fileobj.close()
            cr.close(True)

    def done(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state': 'ack'}, context=context)
        d = self.pool.get('ir.actions.act_window').open_view_from_xmlid(cr, uid, 'account_hq_entries.action_hq_entries_tree', context=context)
        return d

    def ack(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state': 'ack'}, context=context)
        return {'type': 'ir.actions.act_window_close'}

hq_entries_import_wizard()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
