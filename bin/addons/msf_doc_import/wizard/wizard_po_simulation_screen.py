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

# Module imports
import threading
import pooler
import base64
import time
import xml.etree.ElementTree as ET
from lxml import etree
from lxml.etree import XMLSyntaxError
import logging
import os
import netsvc

from mx import DateTime

# Server imports
from osv import osv
from osv import fields
from tools.translate import _
import tools

# Addons imports
from msf_order_date import TRANSPORT_TYPE
from spreadsheet_xml.spreadsheet_xml import SpreadsheetXML


NB_OF_HEADER_LINES = 20
NB_LINES_COLUMNS = 20


LINES_COLUMNS = [(0, _('Line number'), 'optionnal'),
                 (1, _('External ref'), 'optionnal'),
                 (2, _('Product Code'), 'mandatory'),
                 (3, _('Product Description'), 'optionnal'),
                 (4, _('Product Qty'), 'mandatory'),
                 (5, _('Product UoM'), 'mandatory'),
                 (6, _('Price Unit'), 'mandatory'),
                 (7, _('Currency'), 'mandatory'),
                 (8, _('Origin'), 'optionnal'),
                 (11, _('Delivery Confirmed Date'), 'optionnal'),
                 (15, _('Comment'), 'optionnal'),
                 (17, _('Project Ref.'), 'optionnal'),
                 (18, _('Message ESC 1'), 'optionnal'),
                 (19, _('Message ESC 2'), 'optionnal'),
                 ]

HEADER_COLUMNS = [(1, _('Order Reference'), 'mandatory'),
                  (5, _('Supplier Reference'), 'optionnal'),
                  (10, _('Ready To Ship Date'), 'optionnal'),
                  (15, _('Shipment Date'), 'optionnal'),
                  (19, _('Message ESC'), 'optionnal')
                  ]


class wizard_import_po_simulation_screen(osv.osv):
    _name = 'wizard.import.po.simulation.screen'
    _rec_name = 'order_id'

    def _get_po_lines(self, cr, uid, ids, field_name, args, context=None):
        '''
        Return the number of lines in the PO
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]

        res = {}
        for wiz in self.browse(cr, uid, ids, context=context):
            res[wiz.id] = 0
            if wiz.order_id:
                res[wiz.id] = len(wiz.order_id.order_line)

        return res

    def _get_import_lines(self,cr, uid, ids, field_name, args, context=None):
        '''
        Return the number of lines after the import
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]

        res = {}
        for wiz in self.browse(cr, uid, ids, context=context):
            res[wiz.id] = 0
            if wiz.state == 'done':
                res[wiz.id] = len(wiz.line_ids)

        return res

    def _get_totals(self, cr, uid, ids, field_name, args, context=None):
        '''
        Return the totals after the simulation
        '''
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        res = {}

        for wiz in self.browse(cr, uid, ids, context=context):
            imp_amount_untaxed = 0.00
            amount_discrepancy = 0.00

            cr.execute('''SELECT
                            sum(l.imp_qty * l.imp_price) AS imp_amount_untaxed,
                            sum(imp_discrepancy) AS amount_discrepancy
                          FROM
                            wizard_import_po_simulation_screen_line l
                          WHERE l.simu_id = %(simu_id)s''', {'simu_id': wiz.id})
            db_res = cr.dictfetchall()
            for r in db_res:
                imp_amount_untaxed += r['imp_amount_untaxed'] or 0.00
                amount_discrepancy += r['amount_discrepancy'] or 0.00

            res[wiz.id] = {'imp_amount_untaxed': imp_amount_untaxed,
                           'imp_amount_total': imp_amount_untaxed,
                           'imp_total_price_include_transport': imp_amount_untaxed + wiz.in_transport_cost,
                           'amount_discrepancy': amount_discrepancy}

        return res

    _columns = {
        'order_id': fields.many2one('purchase.order', string='Order',
                                    required=True,
                                    readonly=True),
        'message': fields.text(string='Import message',
                               readonly=True),
        'state': fields.selection([('draft', 'Draft'),
                                   ('simu_progress', 'Simulation in progress'),
                                   ('simu_done', 'Simulation done'),
                                   ('import_progress', 'Import in progress'),
                                   ('error', 'Error'),
                                   ('done', 'Done')],
                                  string='State',
                                  readonly=True),
        'with_ad': fields.selection(
            selection=[
                ('yes', 'Yes'),
                ('no', 'No'),
            ],
            string='File contains Analytic Distribution',
            required=True,
        ),
        # File information
        'file_to_import': fields.binary(string='File to import'),
        'filename': fields.char(size=64, string='Filename'),
        'filetype': fields.selection([('excel', 'Excel file'),
                                      ('xml', 'XML file')], string='Type of file',),
        'error_file': fields.binary(string='File with errors'),
        'error_filename': fields.char(size=64, string='Lines with errors'),
        'nb_file_lines': fields.integer(string='Total of file lines',
                                        readonly=True),
        'nb_treated_lines': fields.integer(string='Nb treated lines',
                                           readonly=True),
        'percent_completed': fields.float(string='Percent completed',
                                          readonly=True),
        'import_error_ok': fields.boolean(string='Error at import'),
        'import_warning_ok': fields.boolean(string='Warning at import'),
        # PO Header information
        'in_creation_date': fields.related('order_id', 'date_order',
                                           type='date',
                                           string='Creation date',
                                           readonly=True),
        'in_supplier_ref': fields.related('order_id', 'partner_ref',
                                          type='char',
                                          string='Supplier Reference',
                                          readonly=True),
        'in_dest_addr': fields.related('order_id', 'dest_address_id',
                                       type='many2one',
                                       relation='res.partner.address',
                                       string='Destination Address',
                                       readonly=True),
        'in_transport_type': fields.related('order_id', 'transport_type',
                                            type='selection',
                                            selection=TRANSPORT_TYPE,
                                            string='Transport mode',
                                            readonly=True),
        'in_notes': fields.related('order_id', 'notes', type='text',
                                   string='Header notes', readonly=True),
        'in_currency': fields.related('order_id', 'pricelist_id',
                                      type='relation',
                                      relation='product.pricelist',
                                      string='Currency',
                                      readonly=True),
        'in_ready_to_ship_date': fields.related('order_id', 'ready_to_ship_date',
                                                type='date',
                                                string='RTS Date',
                                                readonly=True),
        'in_shipment_date': fields.related('order_id', 'shipment_date',
                                           type='date',
                                           string='Shipment date',
                                           readonly=True),
        'in_amount_untaxed': fields.related('order_id', 'amount_untaxed',
                                            string='Untaxed Amount',
                                            readonly=True),
        'in_amount_tax': fields.related('order_id', 'amount_tax',
                                        string='Taxes',
                                        readonly=True),
        'in_amount_total': fields.related('order_id', 'amount_total',
                                          string='Total',
                                          readonly=True),
        'in_transport_cost': fields.related('order_id', 'transport_cost',
                                            string='Transport mt',
                                            readonly=True),
        'in_total_price_include_transport': fields.related('order_id', 'total_price_include_transport',
                                                           string='Total incl. transport',
                                                           readonly=True),
        'nb_po_lines': fields.function(_get_po_lines, method=True, type='integer',
                                       string='Nb PO lines', readonly=True),
        # Import fiels
        'imp_supplier_ref': fields.char(size=256, string='Supplier Ref',
                                        readonly=True),
        'imp_transport_type': fields.selection(selection=TRANSPORT_TYPE,
                                               string='Transport mode',
                                               readonly=True),
        'imp_ready_to_ship_date': fields.date(string='RTS Date',
                                              readonly=True),
        'imp_shipment_date': fields.date(string='Shipment date',
                                         readonly=True),
        'imp_notes': fields.text(string='Header notes',
                                 readonly=True),  # UFTP-59
        'imp_message_esc': fields.text(string='Message ESC Header',
                                       readonly=True),
        'imp_amount_untaxed': fields.function(_get_totals, method=True,
                                              type='float', string='Untaxed Amount',
                                              readonly=True, store=False, multi='simu'),
        'imp_amount_total': fields.function(_get_totals, method=True,
                                            type='float', string='Total Amount',
                                            readonly=True, store=False, multi='simu'),
        'imp_total_price_include_transport': fields.function(_get_totals, method=True,
                                                             type='float', string='Total incl. transport',
                                                             readonly=True, store=False, multi='simu'),
        'amount_discrepancy': fields.function(_get_totals, method=True,
                                              type='float', string='Discrepancy',
                                              readonly=True, store=False, multi='simu'),
        'imp_nb_po_lines': fields.function(_get_import_lines, method=True,
                                           type='integer', string='Nb Import lines',
                                           readonly=True),
        'simu_line_ids': fields.one2many('wizard.import.po.simulation.screen.line',
                                         'simu_id', string='Lines', readonly=True),
        'ad_info': fields.text(string='New Header AD', readonly=1),
    }

    _defaults = {
        'state': 'draft',
        'with_ad': lambda *a: 'yes',
    }

    def write(self, cr, uid, ids, vals, context=None):
        if not ids:
            return True
        if context is None:
            context = {}

        if context.get('button') in ('go_to_simulation', 'print_simulation_report', 'return_to_po'):
            return True

        try:
            return super(wizard_import_po_simulation_screen, self).write(cr, uid, ids, vals, context=context)
        except Exception, e:
            if e[0] == 'ConcurrencyException':
                return True
            else:
                raise e

    '''
    Action buttons
    '''
    def print_simulation_report(self, cr, uid, ids, context=None):
        '''
        Print the PDF report of the simulation
        '''
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        datas = {}
        datas['ids'] = ids
        report_name = 'po.simulation.screen.xls'

        return {
            'type': 'ir.actions.report.xml',
            'report_name': report_name,
            'datas': datas,
            'context': context,
        }

    def return_to_po(self, cr, uid, ids, context=None):
        '''
        Go back to PO
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]

        for wiz in self.read(cr, uid, ids, ['order_id'], context=context):
            order_id = wiz['order_id'][0]
            return {'type': 'ir.actions.act_window',
                    'res_model': 'purchase.order',
                    'view_type': 'form',
                    'view_mode': 'form, tree',
                    'target': 'crush',
                    'res_id': order_id,
                    'context': context,
                    }

    def go_to_simulation(self, cr, uid, ids, context=None):
        '''
        Display the simulation screen
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]

        if ids and self.browse(cr, uid, ids, context=context)[0].state == 'done':
            return self.return_to_po(cr, uid, ids, context=context)

        return {'type': 'ir.actions.act_window',
                'res_model': self._name,
                'view_mode': 'form',
                'view_type': 'form',
                'res_id': ids[0],
                'target': 'same',
                'context': context}

    def populate(self, cr, uid, imp_id, context=None):
        if context is None:
            context = {}

        wiz = self.browse(cr, uid, imp_id, fields_to_fetch=['order_id'], context=context)
        for line in wiz.order_id.order_line:
            self.pool.get('wizard.import.po.simulation.screen.line').create(cr, uid, {
                'po_line_id': line.id,
                'in_line_number': line.line_number,
                'in_ext_ref': line.external_ref,
                'simu_id': imp_id,
                'imp_origin': line.origin,
                'type_change': 'ignore',
                'imp_uom': line.product_uom and line.product_uom.id,
            }, context=context)

        return True

    def launch_simulate(self, cr, uid, ids, context=None, thread=True):
        '''
        Launch the simulation routine in background
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]

        for wiz in self.browse(cr, uid, ids, context=context):
            if wiz.filetype == 'excel':
                xml_file = base64.decodestring(wiz.file_to_import)
                excel_file = SpreadsheetXML(xmlstring=xml_file)
                if not excel_file.getWorksheets():
                    raise osv.except_osv(_('Error'), _('The given file is not a valid Excel 2003 Spreadsheet file !'))
            else:
                try:
                    xml_file = base64.decodestring(wiz.file_to_import)
                    dtd_path = os.path.join(tools.config['root_path'], 'tools/import_po.dtd')
                    dtd = etree.DTD(dtd_path)
                    tree = etree.fromstring(xml_file)
                except XMLSyntaxError as ex:
                    raise osv.except_osv(_('Error'), _('The given file is not a valid XML file !\nTechnical details:\n%s') % tools.ustr(ex))

                if not dtd.validate(tree):
                    # build error message:
                    error_msg = ""
                    for line_obj in dtd.error_log.filter_from_errors():
                        line = tools.ustr(line_obj)
                        err_line = line.split(':')[1]
                        err_str = line.split(':')[-1]
                        err_type = line.split(':')[5]
                        if err_type != 'DTD_UNKNOWN_ELEM':
                            continue
                        error_msg += "Line %s: The tag '%s' is not supported\n" % (err_line, err_str.split()[-1])

                    raise osv.except_osv(_('Error'), _("The given XML file is not structured as expected in the DTD:\n %s") % error_msg)

        self.write(cr, uid, ids, {'state': 'simu_progress', 'error_filename': False, 'error_file': False,
                                  'simu_line_ids': [(6, 0, [])], 'percent_completed': 0, 'import_error_ok': False},
                   context=context)

        self.populate(cr, uid, ids[0], context=context)
        cr.commit()
        if thread:
            new_thread = threading.Thread(target=self.simulate, args=(cr.dbname, uid, ids, context))
            new_thread.start()
            new_thread.join(10.0)

            return self.go_to_simulation(cr, uid, ids, context=context)

        self.simulate(cr.dbname, uid, ids, context)
        return True

    def get_values_from_xml(self, cr, uid, file_to_import, context=None):
        '''
        Read the XML file and put data in values
        '''
        values = {}
        # Read the XML file
        xml_file = base64.decodestring(file_to_import)

        root = ET.fromstring(xml_file)
        if root.tag != 'data':
            return values

        records = []
        rec_lines = []
        rec = False

        ad_field_names = [
            'analytic_distribution_id',
            'ad_destination_name',
            'ad_cost_center_name',
            'ad_percentage',
            'ad_subtotal',
        ]

        index = 0
        for record in root:
            if record.tag == 'record':
                records.append(record)

        if len(records) > 0:
            rec = records[0]

        def get_field_index(node, index):
            if not index:
                index = 0
            if node.getchildren():
                for subnode in node:
                    index = get_field_index(subnode, index)
                return index
            else:
                index += 1
                values[index] = [node.attrib['name'], node.text or '']
                return index

        field_parser = {
            'product_qty': lambda a: float(a),
        }
        for field in rec:
            ad_field = field.attrib['name'] in ad_field_names
            if field.attrib['name'] != 'order_line' and not ad_field:
                index = get_field_index(field, index)
            elif not ad_field:
                index += 1
                values[index] = ['line_number', 'external_ref',
                                 'product_code', 'product_name',
                                 'product_qty', 'product_uom',
                                 'price_unit', 'currency_id',
                                 'origin', 'stock_take_date','comment', 'date_planned',
                                 'confirmed_delivery_date',
                                 'nomen_manda_0', 'nomen_manda_1',
                                 'nomen_manda_2',
                                 'notes', 'project_ref',
                                 'message_esc1', 'message_esc2']
                for line in field:
                    rec_lines.append(line)
            elif field.attrib['name'] == 'analytic_distribution_id':
                index += 1
                values[index] = []
                index += 1
                ad_info = ['']
                for ad_node in field:
                    if ad_node.text:
                        ad_info.append(ad_node.text)
                values[index] = ad_info

        for line in rec_lines:
            index += 1
            values[index] = []
            for fl in line:
                if fl.attrib['name'] == 'analytic_distribution_id':
                    for ad_node in fl:
                        if ad_node.text:
                            values[index].append(ad_node.text or '')
                elif not fl.getchildren():
                    if fl.attrib['name'] in field_parser:
                        try:
                            value = field_parser[fl.attrib['name']](fl.text)
                        except:
                            value = fl.text or ''
                    else:
                        value = fl.text or ''
                    values[index].append(value)
                else:
                    for sfl in fl:
                        values[index].append(sfl.text or '')
        return values


    def get_values_from_excel(self, cr, uid, file_to_import, context=None):
        '''
        Read the Excel XML file and put data in values
        '''
        values = {}
        # Read the XML Excel file
        xml_file = base64.decodestring(file_to_import)
        fileobj = SpreadsheetXML(xmlstring=xml_file)

        # Read all lines
        rows = fileobj.getRows()

        # Get values per line
        index = 0
        for row in rows:
            index += 1
            values.setdefault(index, [])
            for cell_nb in range(len(row)):
                cell_data = row.cells and row.cells[cell_nb] and \
                    row.cells[cell_nb].data
                values[index].append(cell_data)

        return values

    def create_ad(self, cr, uid, ad_info, partner_type, currency_id, context):
        ad_infos = tools.safe_eval(ad_info)
        cc_lines = []
        for ad_info in ad_infos:
            info = ad_info.split('-')
            cc_lines.append((0, 0, {
                'partner_type': partner_type,
                'destination_id': int(info[0]),
                'analytic_id': int(info[1]),
                'percentage': float(info[2]),
                'currency_id': currency_id,
            }
            ))
        distrib_id = self.pool.get('analytic.distribution').create(cr, uid, {'partner_type': partner_type, 'cost_center_lines': cc_lines}, context=context)
        self.pool.get('analytic.distribution').create_funding_pool_lines(cr, uid, [distrib_id], context=context)
        return distrib_id

    def check_ad(self, cr, uid, values, existing_ad, product_id=False, po_type=False, cc_cache=None, context=None):
        errors = []

        if context is None:
            context = {}
        if cc_cache is None:
            cc_cache = {}

        cc_cache.setdefault('aa_ko', {'DEST': {}, 'OC': {}})
        cc_cache.setdefault('aa_ok', {'DEST': {}, 'OC': {}})
        existing_ad_set = set()
        if existing_ad:
            for cc_line in existing_ad.cost_center_lines:
                existing_ad_set.add('%s-%s-%s'%(cc_line.destination_id.id, cc_line.analytic_id.id, round(cc_line.percentage,2)))
        ad = []
        if len(values) < 4 or len(values) % 4 != 0:
            errors.append(_('Invalid AD format: %d columns found, multiple of 4 expected') % (len(values), ))
        else:
            idx = 0
            sum_percent = 0
            while idx < len(values):
                if not values[idx]:
                    break
                try:
                    percent = float(values[idx+2])
                except (TypeError, ValueError):
                    errors.append(_('%% in AD must be a number (value found %s), AD in file ignored') % (values[idx+2]))
                    ad = []
                    break
                ad.append(['%s'%values[idx], '%s'%values[idx+1], percent])
                sum_percent += percent
                idx += 4
        if ad and abs(100-sum_percent) > 0.001:
            ad = []
            errors.append(_('Sum of AD %% must be 100 (value found %s), AD in file ignored') % (sum_percent))

        valid_ad = True
        data_ad_set = set()
        add_detail = []
        aa_ko = cc_cache['aa_ko']
        aa_ok = cc_cache['aa_ok']

        msf_pf_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'analytic_distribution', 'analytic_account_msf_private_funds')[1]

        for ad_value in ad:
            ad = {'DEST': False, 'OC': False}
            for x in [(0, 'DEST', _('Destination')), (1, 'OC', _('Cost Center'))]:
                account = ad_value[x[0]].strip()
                if account not in aa_ko[x[1]] and account not in aa_ok[x[1]]:
                    dom = [('category', '=', x[1]), ('type','!=', 'view'), ('code', '=ilike', account), ('filter_active', '=', True)]
                    account_ids = self.pool.get('account.analytic.account').search(cr, uid, dom, context=context)
                    if not account_ids:
                        aa_ko[x[1]][account] = True
                        errors.append(_('%s %s not found or inactive , AD in file ignored') % (x[2], account))
                    else:
                        aa_ok[x[1]][account] = account_ids[0]
                ad[x[1]] = aa_ok[x[1]].get(account)

            if not ad['DEST'] or not ad['OC']:
                valid_ad = False
                break
            data_ad_set.add('%s-%s-%s' % (ad['DEST'], ad['OC'], round(ad_value[2], 2)))
            add_detail.append(ad)

        if existing_ad_set:
            if valid_ad and data_ad_set and data_ad_set != existing_ad_set:
                errors.append(_('Already has a valid Analytical Distribution'))
            data_ad_set = set()
        elif not valid_ad:
            data_ad_set = set()
        else:
            gl_account_id = False
            if product_id:
                product_record = self.pool.get('product.product').browse(cr, uid, product_id, context=context)
                gl_account_id = self.pool.get('purchase.order.line').get_distribution_account(cr, uid, product_record, False, po_type, context=None)
            for ad_line in add_detail:
                if gl_account_id:
                    ad_info = self.pool.get('account.analytic.line').check_dest_cc_fp_compatibility(cr, uid, [], dest_id=ad_line['DEST'], cc_id=ad_line['OC'], from_import=True, from_import_general_account_id=gl_account_id, fp_id=msf_pf_id, from_import_posting_date=time.strftime('%Y-%m-%d'), context=context)
                    if ad_info:
                        errors.append(_('Invalid Analytical Distribution'))
                        data_ad_set = set()
                        break
                else:
                    if not self.pool.get('analytic.distribution').check_dest_cc_compatibility(cr, uid, ad_line['DEST'], ad_line['OC'], context=context):
                        errors.append(_('Invalid Analytical Distribution'))
                        data_ad_set = set()
                        break

        return errors, list(data_ad_set)

    def best_matching_lines(self, cr, uid, candidate_ids, prod_code, qty, context):
        if not candidate_ids:
            return False
        if len(candidate_ids) == 1:
            return candidate_ids[0]

        wl_obj = self.pool.get('wizard.import.po.simulation.screen.line')
        if prod_code:
            prod_code = prod_code.strip()

        matching_ids = wl_obj.search(cr, uid, [('id', 'in', candidate_ids), ('in_product_code', '=ilike', prod_code), ('in_qty', '=', qty)], context=context)
        if matching_ids:
            return matching_ids[0]

        matching_ids = wl_obj.search(cr, uid, [('id', 'in', candidate_ids), ('in_product_code', '=ilike', prod_code)], context=context)
        if matching_ids:
            return matching_ids[0]

        return candidate_ids[0]


    '''
    Simulate routine
    '''
    def simulate(self, dbname, uid, ids, context=None):
        '''
            Import the file
            Check header validity
            Check mandatory values on lines
            Check if the xls line matches an existing simu line or create a new simu line
            For each line call update_simu_line
        '''
        cr = pooler.get_db(dbname).cursor()
        #cr = dbname
        try:
            wl_obj = self.pool.get('wizard.import.po.simulation.screen.line')


            # Declare global variables (need this explicit declaration to clear
            # them at the end of the treatment)

            PRODUCT_CODE_ID = {}
            UOM_NAME_ID = {}
            SIMU_LINES = {}
            LN_BY_EXT_REF = {}
            EXT_REF_BY_LN = {}

            if context is None:
                context = {}

            if isinstance(ids, (int, long)):
                ids = [ids]

            for wiz in self.browse(cr, uid, ids, context=context):
                nb_treated_lines = 0
                # No file => Return to the simulation screen
                if not wiz.file_to_import:
                    self.write(cr, uid, [wiz.id], {'message': _('No file to import'),
                                                   'state': 'draft'}, context=context)
                    continue

                nb_file_header_lines = NB_OF_HEADER_LINES
                nb_file_lines_columns = NB_LINES_COLUMNS
                first_line_index = nb_file_header_lines + 1
                if wiz.with_ad == 'yes':
                    nb_file_header_lines += 2
                    first_line_index += 2

                SIMU_LINES.setdefault('line_ids', [])
                SIMU_LINES.setdefault('ext_ref', {})

                for line in wiz.simu_line_ids:
                    # 1st step : simu_line_ids contain a copy of po line
                    # Put data in cache
                    if line.in_product_id:
                        PRODUCT_CODE_ID.setdefault(line.in_product_id.default_code, line.in_product_id.id)
                    if line.in_uom:
                        UOM_NAME_ID.setdefault(line.in_uom.name, line.in_uom.id)

                    '''
                    First of all, we build a cache for simulation screen lines
                    '''
                    l_num = line.in_line_number
                    # By line number
                    SIMU_LINES.setdefault(l_num, {})
                    SIMU_LINES[l_num].setdefault('line_ids', [])
                    SIMU_LINES[l_num]['line_ids'].append(line.id)
                    SIMU_LINES[l_num].setdefault(line.in_ext_ref or False, []).append(line.id)

                    if line.in_ext_ref:
                        LN_BY_EXT_REF.setdefault(tools.ustr(line.in_ext_ref), []).append(l_num)
                        EXT_REF_BY_LN.setdefault(l_num, []).append(tools.ustr(line.in_ext_ref))
                        SIMU_LINES['ext_ref'].setdefault(line.in_ext_ref, []).append(line.id)


                # Variables
                lines_to_ignored = []   # Bad formatting lines
                file_format_errors = []
                values_header_errors = []
                values_line_errors = []
                values_line_warnings = []
                message = ''
                header_values = {}

                if wiz.filetype == 'excel':
                    values = self.get_values_from_excel(cr, uid, wiz.file_to_import, context=context)
                else:
                    values = self.get_values_from_xml(cr, uid, wiz.file_to_import, context=context)

                '''
                We check for each line if the number of columns is consistent
                with the expected number of columns :
                  * For PO header information : 2 columns
                  * For the line information : 17 columns
                '''
                # Check number of columns on lines

                for x in xrange(1, nb_file_header_lines+1):
                    nb_to_check = 2
                    if x > NB_OF_HEADER_LINES and x <= nb_file_header_lines:
                        continue
                    if len(values.get(x, [])) != nb_to_check:
                        lines_to_ignored.append(x)
                        error_msg = _('Line %s of the imported file: The header \
information must be on two columns : Column A for name of the field and column\
 B for value.') % x
                        file_format_errors.append(error_msg)

                if len(values.get(first_line_index, [])) < nb_file_lines_columns:
                    error_msg = _('Line %s of the Excel file: This line is \
mandatory and must have at least %s columns. The values on this line must be the name \
of the field for PO lines.') % (first_line_index, nb_file_lines_columns)
                    file_format_errors.append(error_msg)

                for x in xrange(first_line_index, len(values)+1):
                    if len(values.get(x, [])) < nb_file_lines_columns:
                        lines_to_ignored.append(x)
                        error_msg = _('Line %s of the imported file: The line \
information must be on at least %s columns. The line %s has %s columns') % (x, nb_file_lines_columns, x, len(values.get(x, [])))
                        file_format_errors.append(error_msg)

                nb_file_lines = len(values) - first_line_index
                self.write(cr, uid, [wiz.id], {'nb_file_lines': nb_file_lines}, context=context)

                if len(file_format_errors):
                    message = '''## IMPORT STOPPED ##

    Nothing has been imported because of bad file format. See below :

    ## File format errors ##\n\n'''
                    for err in file_format_errors:
                        message += '%s\n' % err

                    self.write(cr, uid, [wiz.id], {'message': message, 'state': 'error'}, context)
                    res = self.go_to_simulation(cr, uid, [wiz.id], context=context)
                    cr.commit()
                    cr.close(True)
                    return res

                '''
                Now, we know that the file has the good format, you can import
                data for header.
                '''
                # Line 1: Order reference
                order_ref = values.get(1, [])[1]
                if (order_ref or '').lower() != wiz.order_id.name.lower():
                    message = '''## IMPORT STOPPED ##

    LINE 1 OF THE IMPORTED FILE: THE ORDER REFERENCE \
IN THE FILE IS NOT THE SAME AS THE ORDER REFERENCE OF THE SIMULATION SCREEN. \

    YOU SHOULD IMPORT A FILE THAT HAS THE SAME ORDER REFERENCE THAN THE SIMULATION \
SCREEN !'''
                    self.write(cr, uid, [wiz.id], {'message': message, 'state': 'error'}, context)
                    res = self.go_to_simulation(cr, uid, [wiz.id], context=context)
                    cr.commit()
                    cr.close(True)
                    return res


                # Line 2: Order Type
                # Nothing to do

                # Line 3: Order Category
                # Nothing to do

                # Line 4: Creation Date
                # Nothing to do

                # Line 5: Supplier Reference
                supplier_ref = values.get(5, [])[1]
                if supplier_ref:
                    header_values['imp_supplier_ref'] = supplier_ref

                # Line 6: Details
                # Nothing to do

                # Line 7: Stock take date
                # Nothing to do

                # Line 8: Delivery Requested Date
                # Nothing to do

                # Line 9: Transport mode
                transport_type = values.get(9, [])[1]
                if transport_type:
                    transport_select = self.fields_get(cr, uid, ['imp_transport_type'], context=context)
                    for x in transport_select['imp_transport_type']['selection']:
                        if x[1] == transport_type:
                            header_values['imp_transport_type'] = x[0]
                            break
                    else:
                        possible_type = ', '.join(x[1] for x in transport_select['imp_transport_type']['selection'] if x[1])
                        err_msg = _('Line 9 of the file: The transport mode \'%s\' is not \
a valid transport mode. Valid transport modes: %s') % (transport_type, possible_type)
                        values_header_errors.append(err_msg)


                # Line 10: RTS Date
                rts_date = values.get(10, [])[1]
                if rts_date:
                    if type(rts_date) == type(DateTime.now()):
                        rts_date = rts_date.strftime('%Y-%m-%d')
                        header_values['imp_ready_to_ship_date'] = rts_date
                    else:
                        try:
                            time.strptime(rts_date, '%Y-%m-%d')
                            header_values['imp_ready_to_ship_date'] = rts_date
                        except:
                            err_msg = _('Line 10 of the file: The date \'%s\' is not \
    a valid date. A date must be formatted like \'YYYY-MM-DD\'') % rts_date
                            values_header_errors.append(err_msg)

                # Line 11: Delivery address name
                # Nothing to do

                # Line 12: Delivery address
                # Nothing to do

                # Line 13: Customer address name
                # Nothing to do

                # Line 14: Customer address
                # Nothing to do

                # Line 15: Shipment date
                shipment_date = values.get(15, [])[1]
                if shipment_date:
                    if type(shipment_date) == type(DateTime.now()):
                        shipment_date = shipment_date.strftime('%Y-%m-%d')
                        header_values['imp_shipment_date'] = shipment_date
                    else:
                        try:
                            time.strptime(shipment_date, '%Y-%m-%d')
                            header_values['imp_shipment_date'] = shipment_date
                        except:
                            err_msg = _('Line 15 of the file: The date \'%s\' is not \
    a valid date. A date must be formatted like \'YYYY-MM-DD\'') % shipment_date
                            values_header_errors.append(err_msg)

                # Line 16: Notes
                # UFTP-59
                if wiz.filetype != 'excel':
                    header_values['imp_notes'] = values.get(16, [])[1]

                # Line 17: Origin
                # Nothing to do

                # Line 18: Project Ref.
                # Nothing to do

                # Line 19: Message ESC Header
                if values.get(19, False):
                    header_values['imp_message_esc'] = values.get(19)[1]

                # Line 20: Sourcing group
                # Nothing to do

                cc_cache = {}
                # Line 22: AD
                if values.get(22) and len(values[22]) > 1:
                    errors, ad_info = self.check_ad(cr, uid, values[22][1:], wiz.order_id.analytic_distribution_id, cc_cache=cc_cache, context=context)
                    if errors:
                        values_header_errors.append(_('Line 22 of the file: Analytical Distribution ignored: \n - %s') % (" - \n".join(errors)))
                    elif ad_info:
                        header_values['ad_info'] = ad_info


                    #header_values['ad'] = [(x[1], x[2], x[3]) for x in
                '''
                The header values have been imported, start the importation of
                lines
                '''

                found_wiz_lines = {}
                # Loop on lines
                for x in xrange(first_line_index+1, len(values)+1):

                    nb_treated_lines += 1
                    percent_completed = int(float(nb_treated_lines) / float(nb_file_lines) * 100)
                    self.write(cr, uid, [wiz.id], {'nb_treated_lines': nb_treated_lines,
                                                   'percent_completed': percent_completed}, context=context)



                    # Check mandatory fields
                    try:
                        line_number = values.get(x, [''])[0] and int(values.get(x, [''])[0]) or False
                    except:
                        line_number = False

                    for manda_field in LINES_COLUMNS:
                        if manda_field[0] == 4: #product qty
                            try:
                                values[x][4] = float(values[x][4])
                                if values[x][4] < 0:
                                    values[x][4] = 0
                            except:
                                values[x][4] = 0
                        if manda_field[2] == 'mandatory' and not values.get(x, [])[manda_field[0]]:
                            if manda_field[0] == 4:  # Product Qty
                                err1 = _('You can not have an order line with a negative or zero quantity. Updated quantity is ignored')
                            else:
                                err1 = _('The column \'%s\' mustn\'t be empty%s') % (manda_field[1], manda_field[0] == 0 and ' - Line not imported' or '')
                            if line_number:
                                err = _('Line %s of the PO: %s') % (line_number, err1)
                            else:
                                err = _('Line ref %s of the PO: %s') % (values.get(x, ['', ''])[1], err1)

                            values_line_errors.append(err)

                    ext_ref = values.get(x, ['', ''])[1] and tools.ustr(values.get(x, ['', ''])[1])


                    is_delete_line = values[x][15] and values[x][15].strip() == '[DELETE]'

                    if not line_number and not ext_ref:
                        # error 0
                        err1 = _('The line must have either the line number or the external ref. set')
                        values_line_errors.append(err1)
                        continue

                    if line_number and ext_ref and line_number not in SIMU_LINES:
                        # error 1
                        err1 = _('Combination of line number %s and ext ref %s not consistent') % (line_number, ext_ref)
                        values_line_errors.append(_('Line %s of the PO: %s') % (line_number, err1))
                        continue

                    if line_number and not ext_ref and line_number not in SIMU_LINES:
                        # warning error 2
                        values_line_warnings.append(_('Line %s of the PO: %s') % (line_number, _('Cannot find line. Ignored')))
                        continue

                    if is_delete_line and line_number and ext_ref and ext_ref not in EXT_REF_BY_LN.get(line_number, []):
                        # error 3
                        err1 = _('Combination of line number %s and ext ref %s not consistent') % (line_number, ext_ref)
                        values_line_errors.append(_('Line %s of the PO: %s') % (line_number, err1))
                        continue

                    if not is_delete_line and line_number and ext_ref and ext_ref not in  EXT_REF_BY_LN.get(line_number, []) and ext_ref in LN_BY_EXT_REF:
                        # error 4
                        err1 = _('Combination of line number %s and ext ref %s not consistent') % (line_number, ext_ref)
                        values_line_errors.append( _('Line %s of the PO: %s') % (line_number, err1))
                        continue

                    to_delete = False
                    to_update = False
                    to_split = False
                    to_create = False
                    type_of_change = ''
                    if is_delete_line:
                        if line_number:
                            if ext_ref:
                                # UC 4
                                to_delete = self.best_matching_lines(cr, uid, [lx for lx in SIMU_LINES[line_number][ext_ref] if lx not in found_wiz_lines], values[x][2], values[x][4], context)
                            else:
                                # UC 6: multiple deletion
                                to_delete = SIMU_LINES[line_number]['line_ids']
                        elif ext_ref:
                            # UC10
                            to_delete = self.best_matching_lines(cr, uid, [lx for lx in SIMU_LINES['ext_ref'].get(ext_ref, []) if lx not in found_wiz_lines], values[x][2], values[x][4], context)


                    else:
                        if line_number and ext_ref:
                            if ext_ref not in SIMU_LINES['ext_ref'] and SIMU_LINES[line_number].get(False):
                                # UC 1
                                to_update = self.best_matching_lines(cr, uid, [lx for lx in SIMU_LINES[line_number].get(False) if lx not in found_wiz_lines], values[x][2], values[x][4], context)

                            elif SIMU_LINES[line_number].get(ext_ref):
                                # UC 2
                                to_update = self.best_matching_lines(cr, uid, [lx for lx in SIMU_LINES[line_number].get(ext_ref) if lx not in found_wiz_lines], values[x][2], values[x][4], context)
                            elif ext_ref not in SIMU_LINES['ext_ref'] and not SIMU_LINES[line_number].get(False):
                                # UC 3
                                to_split = SIMU_LINES[line_number]['line_ids'][0]

                        elif line_number and not ext_ref:
                            if SIMU_LINES[line_number]['line_ids']:
                                # UC 5
                                to_update = self.best_matching_lines(cr, uid, [lx for lx in SIMU_LINES[line_number]['line_ids'] if lx not in found_wiz_lines], values[x][2], values[x][4], context)
                                if not to_update:
                                    # UC 7
                                    to_split = SIMU_LINES[line_number]['line_ids'][0]

                        elif not line_number and ext_ref:
                            if ext_ref in SIMU_LINES['ext_ref']:
                                to_update = self.best_matching_lines(cr, uid, [lx for lx in SIMU_LINES['ext_ref'][ext_ref] if lx not in found_wiz_lines], values[x][2], values[x][4], context)
                            else:
                                # UC 8
                                to_create = True

                    if to_create and wiz.order_id.partner_type in ['internal', 'intermission', 'section']:
                        err1 = _('Adding a new line is not allowed on a Validated PO if the Supplier is Internal, Intermission or Inter-section')
                        values_line_errors.append(_('Line Ext. Ref. %s of the PO: %s') % (ext_ref, err1))
                        continue


                    if to_split:
                        new_wl_id = wl_obj.copy(cr, uid, to_split,
                                                {'type_change': 'split',
                                                 'parent_line_id': to_split,
                                                 'imp_dcd': False,
                                                 'error_msg': False,
                                                 'info_msg': False,
                                                 'in_ext_ref': False,
                                                 'po_line_id': False}, context=context)
                        type_of_change = 'split'
                        wiz_line_ids = new_wl_id
                    elif to_create:
                        new_wl_id = wl_obj.create(cr, uid, {'type_change': 'new', 'simu_id': wiz.id}, context=context)
                        type_of_change = 'new'
                        wiz_line_ids = new_wl_id
                    elif to_update:
                        type_of_change = 'match'
                        wiz_line_ids = to_update
                    elif to_delete:
                        type_of_change = 'delete'
                        wiz_line_ids = to_delete
                    else:
                        err1 = _('Combination of line number %s and ext ref %s not consistent or line duplicated in file') % (line_number, ext_ref)
                        values_line_errors.append(_('Line %s of the PO: %s') % (line_number, err1))
                        continue

                    if isinstance(wiz_line_ids, (int, long)):
                        found_wiz_lines[wiz_line_ids] = True
                    else:
                        for line_id in wiz_line_ids:
                            found_wiz_lines[line_id] = True

                    err_msg, warn_msg = wl_obj.update_simu_line(cr, uid, wiz_line_ids, values[x], cc_cache, type_of_change, PRODUCT_CODE_ID, UOM_NAME_ID, context=context)
                    locate_error = []
                    if err_msg or warn_msg:
                        if line_number:
                            locate_error.append(_('Line %s of the PO') % line_number)
                        if ext_ref:
                            locate_error.append(_('ExtRef %s') % ext_ref)
                        if wiz.filetype == 'excel':
                            locate_error.append(_('Line %s of the file') % x)
                        else:
                            locate_error.append(_('Record node #%s') % nb_treated_lines)

                    if err_msg:
                        values_line_errors.append('%s: %s' % (', '.join(locate_error), ' '.join(err_msg)))
                    if warn_msg:
                        values_line_warnings.append('%s: %s' % (', '.join(locate_error), ' '.join(warn_msg)))

                '''
                We generate the message which will be displayed on the simulation
                screen. This message is a merge between all errors and warnings.
                '''
                # Generate the message
                import_error_ok = False
                import_warning_ok = False
                if len(values_header_errors):
                    import_error_ok = True
                    message += '\n## %s ##\n\n' % (_('Error on header values'), )
                    for err in values_header_errors:
                        message += '%s\n' % err

                if len(values_line_errors):
                    import_error_ok = True
                    message += '\n## %s ##\n\n' % (_('Error on line values'), )
                    for err in values_line_errors:
                        message += '%s\n' % err

                if len(values_line_warnings):
                    import_warning_ok = True
                    message += _('\n## Warning on line values ##\n\n')
                    for warn in values_line_warnings:
                        message += '%s\n' % warn

                header_values.update({
                    'message': message,
                    'state': 'simu_done',
                    'percent_completed': 100.0,
                    'import_error_ok': import_error_ok,
                    'import_warning_ok': import_warning_ok,
                })
                self.write(cr, uid, [wiz.id], header_values, context=context)

            cr.commit()
            cr.close(True)

        except Exception, e:
            logging.getLogger('po.simulation simulate').warn('Exception', exc_info=True)
            self.write(cr, uid, ids, {'state': 'error', 'message': "Unknown error:\n%s\n---\n%s" % (e, tools.misc.get_traceback(e))}, context=context)
            cr.commit()
            cr.close(True)
        finally:
            try:
                # Clear the cache
                del UOM_NAME_ID
                del PRODUCT_CODE_ID
                del SIMU_LINES
                del LN_BY_EXT_REF
                del EXT_REF_BY_LN
            except:
                pass

        return True

    def launch_import(self, cr, uid, ids, context=None, thread=True):
        '''
        Launch the simulation routine in background
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]

        active_wiz = self.browse(cr, uid, ids, fields_to_fetch=['state', 'order_id'], context=context)[0]

        # To prevent adding multiple lines by clicking multiple times on the import button
        if active_wiz.state != 'simu_done':
            return {'type': 'ir.actions.act_window',
                    'res_model': 'purchase.order',
                    'res_id': active_wiz.order_id.id,
                    'view_type': 'form',
                    'view_mode': 'form, tree',
                    'target': 'crush',
                    'context': context}

        self.write(cr, uid, ids, {'state': 'import_progress', 'percent_completed': 0.00}, context=context)
        for wiz in self.browse(cr, uid, ids, context=context):
            filename = wiz.filename.split('\\')[-1]
            self.pool.get('purchase.order.simu.import.file').create(cr, uid, {'order_id': wiz.order_id.id,
                                                                              'filename': filename,}, context=context)
        cr.commit()
        if thread:
            new_thread = threading.Thread(target=self.run_import, args=(cr.dbname, uid, ids, context))
            new_thread.start()
            new_thread.join(10.0)

            if new_thread.isAlive():
                return self.go_to_simulation(cr, uid, ids, context=context)
            else:
                state = self.read(cr, uid, ids[0], ['state'], context=context)
                if state['state'] != 'error':
                    return {'type': 'ir.actions.act_window',
                            'res_model': 'purchase.order',
                            'res_id': active_wiz.order_id.id,
                            'view_type': 'form',
                            'view_mode': 'form, tree',
                            'target': 'crush',
                            'context': context}
                return self.go_to_simulation(cr, uid, ids, context=context)
        else:
            self.run_import(cr.dbname, uid, ids, context)
            return True

    def run_import(self, dbname, uid, ids, context=None):
        '''
        Launch the real import
        '''
        line_obj = self.pool.get('wizard.import.po.simulation.screen.line')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        cr = pooler.get_db(dbname).cursor()

        context['from_vi_import'] = True
        try:
            for wiz in self.browse(cr, uid, ids, context=context):
                w_vals = {'state': 'import_progress',}
                self.write(cr, uid, [wiz.id], w_vals, context=context)

                po_vals = {
                    'partner_ref': wiz.imp_supplier_ref or wiz.in_supplier_ref,
                    'ready_to_ship_date': wiz.imp_ready_to_ship_date or wiz.in_ready_to_ship_date,
                    'shipment_date': wiz.imp_shipment_date or wiz.in_shipment_date,
                }
                if wiz.ad_info:
                    po_vals['analytic_distribution_id'] = self.create_ad(cr, uid, wiz.ad_info, wiz.order_id.partner_id.partner_type, wiz.order_id.currency_id.id, context)

                self.pool.get('purchase.order').write(cr, uid, [wiz.order_id.id], po_vals, context=context)

                lines = [x.id for x in wiz.simu_line_ids]
                line_obj.update_po_line(cr, uid, lines, context=context)

            if ids:
                self.write(cr, uid, ids, {'state': 'done', 'percent_completed': 100.00}, context=context)
                res =self.go_to_simulation(cr, uid, [wiz.id], context=context)
            else:
                res = True

            cr.commit()
            cr.close(True)
        except Exception, e:
            cr.rollback()
            logging.getLogger('po.simulation.run').warn('Exception', exc_info=True)
            self.write(cr, uid, ids, {'message': e, 'state': 'error'}, context=context)
            res = True
            cr.commit()
            cr.close(True)
        context['from_vi_import'] = False
        return res

wizard_import_po_simulation_screen()


class wizard_import_po_simulation_screen_line(osv.osv):
    _name = 'wizard.import.po.simulation.screen.line'
    _order = 'is_new_line, in_line_number, in_ext_ref, in_product_id, id'
    _rec_name = 'in_line_number'

    def _get_line_info(self, cr, uid, ids, field_name, args, context=None):
        '''
        Get values for each lines
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]


        res = {}
        chg_dict = dict(self.fields_get(cr, uid, ['type_change'], context=context).get('type_change', {}).get('selection', []))
        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = {
                'in_product_id': False,
                'in_product_code': '',
                'in_nomen': False,
                'in_comment': False,
                'in_qty': 0.00,
                'in_uom': False,
                'in_drd': False,
                'in_dcd': False,
                'in_price': 0.00,
                'in_currency': False,
                'imp_discrepancy': 0.00,
                'change_ok': False,
            }
            chg = []
            if line.type_change != 'match' and line.type_change:
                chg.append(chg_dict.get(line.type_change))

            if line.po_line_id:
                l = line.po_line_id
                res[line.id]['in_product_id'] = l.product_id and l.product_id.id or False
                res[line.id]['in_product_code'] =  l.product_id and l.product_id.default_code or False
                res[line.id]['in_nomen'] = l.nomenclature_description
                res[line.id]['in_comment'] = l.comment
                res[line.id]['in_qty'] = l.product_qty
                res[line.id]['in_uom'] = l.product_uom and l.product_uom.id or False
                res[line.id]['in_drd'] = l.date_planned
                res[line.id]['in_dcd'] = l.confirmed_delivery_date
                res[line.id]['in_price'] = l.price_unit
                res[line.id]['in_currency'] = l.currency_id and l.currency_id.id or False
                if line.type_change not in ('warning', 'del', 'ignore'):
                    if line.imp_qty and line.imp_price:
                        disc = (line.imp_qty*line.imp_price)-(line.in_qty*line.in_price)
                        res[line.id]['imp_discrepancy'] = disc

                    prod_change = False
                    if res[line.id]['in_product_id'] and not line.imp_product_id or \
                            not res[line.id]['in_product_id'] and line.imp_product_id or \
                            res[line.id]['in_product_id'] != line.imp_product_id.id:
                        prod_change = True
                        if line.imp_product_id or (not line.imp_product_id and line.in_comment):
                            chg.append(_('PROD'))
                    qty_change = not(res[line.id]['in_qty'] == line.imp_qty)
                    if (line.imp_product_id or (not line.imp_product_id and line.in_comment)) \
                            and qty_change:
                        chg.append(_('QTY'))
                    price_change = not(res[line.id]['in_price'] == line.imp_price)
                    if (line.imp_product_id or (not line.imp_product_id and line.in_comment)) \
                            and price_change:
                        chg.append(_('PRICE'))
                    if line.ad_info:
                        chg.append(_('AD'))

                    #if line.imp_external_ref != l.external_ref:
                    #    chg.append(_('ExtRef'))
                    drd_change = not(res[line.id]['in_drd'] == line.imp_drd)
                    dcd_change = not(res[line.id]['in_dcd'] == line.imp_dcd)

                    if line.simu_id.state != 'draft' and (prod_change or qty_change or price_change or drd_change or dcd_change or line.ad_info):
                        res[line.id]['change_ok'] = True
                elif line.type_change == 'del':
                    res[line.id]['imp_discrepancy'] = -(l.product_qty*l.price_unit)
                    res[line.id]['change_ok'] = True
            else:
                if line.ad_info:
                    chg.append(_("AD"))
                #if line.imp_external_ref:
                #    chg.append(_('ExtRef'))
                res[line.id]['imp_discrepancy'] = line.imp_qty*line.imp_price
                if line.imp_uom:
                    res[line.id]['in_uom'] = line.imp_uom.id
            res[line.id]['chg_text'] = "\n".join(chg)
        return res

    def _get_str_line_number(self, cr, uid, ids, field_name, args, context=None):
        '''
        Return the str of the line according to the line number or nothing
        if the line number is 0
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]

        res = {}
        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = {}
            if line.in_line_number and line.in_line_number > 0:
                res[line.id]['str_in_line_number'] = line.in_line_number
                res[line.id]['is_new_line'] = 0
            else:
                res[line.id]['str_in_line_number'] = ''
                res[line.id]['is_new_line'] = 1

        return res

    _columns = {
        'po_line_id': fields.many2one('purchase.order.line', string='Line',
                                      readonly=True),
        'simu_id': fields.many2one('wizard.import.po.simulation.screen',
                                   string='Simulation screen',
                                   readonly=True, ondelete='cascade'),
        'in_product_id': fields.function(_get_line_info, method=True, multi='line',
                                         type='many2one', relation='product.product',
                                         string='Product', readonly=True, store=True),
        'in_product_code': fields.function(_get_line_info, method=True, multi='line', type='char', size=256, string='Product Code', readonly=True, store=True, select=1, _fnct_migrate=lambda *a: ''),
        'in_nomen': fields.function(_get_line_info, method=True, multi='line',
                                    type='char', size=1024, string='Nomenclature',
                                    readonly=True, store=True),
        'in_comment': fields.function(_get_line_info, method=True, multi='line',
                                      type='char', size=1024, string='Comment',
                                      readonly=True, store=True),
        'in_qty': fields.function(_get_line_info, method=True, multi='line',
                                  type='float', string='Qty',
                                  readonly=True, store=True, related_uom='in_uom'),
        'in_uom': fields.function(_get_line_info, method=True, multi='line',
                                  type='many2one', relation='product.uom', string='UoM',
                                  readonly=True, store=True),
        'in_drd': fields.function(_get_line_info, method=True, multi='line',
                                  type='date', string='Delivery Requested Date',
                                  readonly=True, store=True),
        'in_dcd': fields.function(_get_line_info, method=True, multi='line',
                                  type='date', string='Delivery Confirmed Date',
                                  readonly=True, store=True),
        'in_price': fields.function(_get_line_info, method=True, multi='line',
                                    type='float', string='Price Unit',
                                    readonly=True, store=True),
        'in_currency': fields.function(_get_line_info, method=True, multi='line',
                                       type='many2one', relation='res.currency', string='Currency',
                                       readonly=True, store=True),
        'in_line_number': fields.integer(string='Line', readonly=True),
        'str_in_line_number': fields.function(_get_str_line_number, method=True, string='Line',
                                              type='char', size=24, readonly=True, multi='new_line',
                                              store={'wizard.import.po.simulation.screen.line': (lambda self, cr, uid, ids, c={}: ids, ['in_line_number'], 20),}),
        'is_new_line': fields.function(_get_str_line_number, method=True, string='Is new line ?',
                                       type='boolean', readonly=True, multi='new_line',
                                       store={'wizard.import.po.simulation.screen.line': (lambda self, cr, uid, ids, c={}: ids, ['in_line_number'], 20),}),
        'in_ext_ref': fields.char(size=256, string='External Ref.', readonly=True),
        'type_change': fields.selection([('', ''), ('error', 'Error'), ('new', 'New'),
                                         ('split', 'Split'), ('del', 'Del'), ('match', 'Match'),
                                         ('ignore', 'Ignore'), ('warning', 'Warning'), ('cdd', 'CDD')],
                                        string='Change type', readonly=True),
        'imp_product_id': fields.many2one('product.product', string='Product',
                                          readonly=True),
        'imp_qty': fields.float(digits=(16,2), string='Qty', readonly=True, related_uom='imp_uom'),
        'imp_uom': fields.many2one('product.uom', string='UoM', readonly=True),
        'imp_price': fields.float(digits=(16,2), string='Price Unit', readonly=True),
        'imp_discrepancy': fields.function(_get_line_info, method=True, multi='line',
                                           type='float', string='Discrepancy',
                                           store={'wizard.import.po.simulation.screen.line': (lambda self, cr, uid, ids, c={}: ids, ['imp_qty', 'imp_price', 'in_qty', 'in_price', 'type_change', 'po_line_id'], 20),}),
        'imp_currency': fields.many2one('res.currency', string='Currency', readonly=True),
        'imp_stock_take_date': fields.date(string='Stock Take Date', readonly=True),
        'imp_drd': fields.date(string='Delivery Requested Date', readonly=True),
        'imp_dcd': fields.date(string='Delivery Confirmed Date', readonly=True),
        'esc_conf': fields.boolean(string='ESC Confirmed', readonly=True),
        'imp_esc1': fields.char(size=256, string='Message ESC1', readonly=True),
        'imp_esc2': fields.char(size=256, string='Message ESC2', readonly=True),
        'imp_comment': fields.text(string='Comment', readonly=True),
        'imp_external_ref': fields.char(size=256, string='External Ref.', readonly=True),
        'imp_project_ref': fields.char(size=256, string='Project Ref.', readonly=True),
        'imp_origin': fields.char(size=256, string='Origin Ref.', readonly=True),
        'imp_sync_order_ref': fields.many2one('sync.order.label', string='Order in sync. instance', readonly=True),
        'change_ok': fields.function(_get_line_info, method=True, multi='line',
                                     type='boolean', string='Change', store=False),
        'error_msg': fields.text(string='Error message', readonly=True),
        'info_msg': fields.text(string='Message', readonly=True),
        'ad_error': fields.char(string='Display warning on line', size=12, readonly=True),
        'parent_line_id': fields.many2one('wizard.import.po.simulation.screen.line',
                                          string='Parent line id',
                                          help='Use to split the good PO line',
                                          readonly=True),
        'chg_text': fields.function(_get_line_info, method=True, multi='line', type='char', size=216, string='CHG',
                                    readonly=True, store=True),
        'ad_info': fields.text(string='New AD', readonly=True),
    }

    _defaults = {
        'ad_error': '',
    }
    def get_error_msg(self, cr, uid, ids, context=None):
        '''
        Display the error message
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]

        for line in self.browse(cr, uid, ids, context=context):
            if line.error_msg:
                raise osv.except_osv(_('Error'), line.error_msg)

        return True

    def update_simu_line(self, cr, uid, ids, values, cc_cache, import_type, PRODUCT_CODE_ID, UOM_NAME_ID, context=None):
        '''
        Write the simu line with the values
        '''

        assert import_type in ('match', 'split', 'new', 'delete')

        prod_obj = self.pool.get('product.product')
        uom_obj = self.pool.get('product.uom')
        sale_obj = self.pool.get('sale.order')
        sync_order_obj = self.pool.get('sync.order.label')

        if isinstance(ids, (int, long)):
            ids = [ids]

        errors = []
        warnings = []
        max_qty = self.pool.get('purchase.order.line')._max_qty

        for line in self.browse(cr, uid, ids, context=context):
            write_vals = {}
            info_msg = []

            # Comment
            write_vals['imp_comment'] = values[15] and values[15].strip()

            if line.po_line_id.state in ['cancel', 'cancel_r']:
                self.write(cr, uid, [line.id], {'type_change': 'ignore'}, context=context)
                continue

            if line.po_line_id.state == 'done':
                self.write(cr, uid, [line.id], {'type_change': 'warning', 'error_msg': _('PO line has been confirmed and consequently is not editable')}, context=context)
                continue

            if import_type == 'delete':
                if line.po_line_id.state not in ('validated', 'validated_n'):
                    self.write(cr, uid, [line.id], {'type_change': 'ignore'}, context=context)
                    continue
                else:
                    self.write(cr, uid, [line.id], {'type_change': 'del'}, context=context)
                    continue

            # Delivery Confirmed Date
            dcd_value = values[11]
            if dcd_value and type(dcd_value) == type(DateTime.now()):
                write_vals['imp_dcd'] = dcd_value.strftime('%Y-%m-%d')
            elif dcd_value and isinstance(dcd_value, str):
                try:
                    time.strptime(dcd_value, '%Y-%m-%d')
                    write_vals['imp_dcd'] = dcd_value
                except ValueError:
                    err_msg = _('Incorrect date value for field \'Delivery Confirmed Date\'')
                    errors.append(err_msg)
                    write_vals['type_change'] = 'error'
            elif dcd_value:
                err_msg = _('Incorrect date value for field \'Delivery Confirmed Date\'')
                errors.append(err_msg)
                write_vals['type_change'] = 'error'

            if line.po_line_id.state == 'confirmed':
                if write_vals.get('imp_dcd') and write_vals.get('imp_dcd') != line.in_dcd:
                    if self.pool.get('stock.move').search_exists(cr ,uid, [('purchase_line_id', '=', line.po_line_id.id), ('type', '=', 'in'), ('state', '=', 'done')], context=context):
                        write_vals['type_change'] = 'warning'
                        warnings.append(_("IN for line %s has been partially processed, CDD can't be changed") % (line.in_line_number,))
                    else:
                        write_vals['type_change'] = 'cdd'
                if not write_vals.get('type_change'):
                    write_vals['type_change'] = 'ignore'
                self.write(cr, uid, [line.id], write_vals, context=context)
                continue

            if line.simu_id.order_id.state in ['confirmed', 'confirmed_p']:
                write_vals['type_change'] = 'ignore'
                self.write(cr, uid, [line.id], write_vals, context=context)
                continue

            # External Ref.
            write_vals['imp_external_ref'] = values[1] or False

            # Product
            partner_id = line.simu_id.order_id.partner_id.id
            if values[2] and values[2] == line.in_product_id.default_code:
                write_vals['imp_product_id'] = line.in_product_id and line.in_product_id.id or False
            else:
                if values[2]:
                    if not PRODUCT_CODE_ID.get(values[2]):
                        prod_ids = prod_obj.search(cr, uid, [('default_code', '=ilike', values[2])], context=context)
                        if prod_ids:
                            PRODUCT_CODE_ID[values[2]] = prod_ids[0]
                        else:
                            write_vals['type_change'] = 'error'
                            errors.append(_('Product %s not found in database') % values[2])

                    write_vals['imp_product_id'] = PRODUCT_CODE_ID.get(values[2])

            if write_vals.get('imp_product_id'):
                # Check constraints on products
                p_error, p_msg = prod_obj._test_restriction_error(cr, uid, [write_vals['imp_product_id']], vals={'partner_id': partner_id}, context=context)
                if p_error:
                    write_vals['type_change'] = 'error'
                    errors.append(p_msg)
                else:
                    if line.po_line_id and line.po_line_id.linked_sol_id and not line.po_line_id.linked_sol_id.procurement_request \
                            and line.po_line_id.po_order_type == 'regular' \
                            and prod_obj.browse(cr, uid, write_vals['imp_product_id'], fields_to_fetch=['type'], context=context).type == 'service_recep':
                        write_vals['type_change'] = 'error'
                        errors.append(_('You can not select the Service Product %s on a Regular PO if the line has been sourced from a FO') % values[2])
            else:
                write_vals['type_change'] = 'error'

            write_vals['ad_info'] = False
            if not write_vals.get('type_change') and len(values) > 20:
                existing_ad = line.po_line_id and line.po_line_id.analytic_distribution_id or line.simu_id.order_id.analytic_distribution_id
                if line.po_line_id.analytic_distribution_state != 'valid':
                    existing_ad = False
                errors_ad, ad_info = self.pool.get('wizard.import.po.simulation.screen').check_ad(cr, uid, values[20:], existing_ad, product_id=write_vals.get('imp_product_id'), po_type=line.simu_id.order_id.order_type,cc_cache=cc_cache, context=context)
                if errors_ad:
                    if not line.po_line_id.analytic_distribution_id or not existing_ad:
                        errors += errors_ad
                        write_vals['error_msg'] = _('Invalid AD in file')
                        write_vals['ad_error'] = 'ok'
                    else:
                        warnings += errors_ad
                elif ad_info:
                    write_vals['ad_info'] = ad_info

            # Qty
            if values[4]:
                if values[4] < max_qty:
                    write_vals['imp_qty'] = float(values[4])
                else:
                    errors.append(_('Quantity can not have more than 10 digits.'))
                    write_vals['type_change'] = 'error'
                    write_vals['imp_qty'] = 0.00
            else:
                write_vals['type_change'] = 'error'
                write_vals['imp_qty'] = 0.00

            # UoM
            uom_value = values[5]
            if tools.ustr(uom_value) == line.in_uom.name:
                write_vals['imp_uom'] = line.in_uom.id
            else:
                uom_id = UOM_NAME_ID.get(tools.ustr(uom_value))
                if not uom_id:
                    uom_ids = uom_obj.search(cr, uid, [('name', '=ilike', tools.ustr(uom_value))], context=context)
                    if uom_ids:
                        UOM_NAME_ID[tools.ustr(uom_value)] = uom_ids[0]
                        write_vals['imp_uom'] = uom_ids[0]
                    else:
                        errors.append(_('UoM not found in database.'))
                        write_vals['imp_uom'] = False
                        write_vals['type_change'] = 'error'
                else:
                    write_vals['imp_uom'] = uom_id

            if write_vals.get('imp_uom') and write_vals.get('imp_product_id') and \
                    (write_vals['imp_uom'] != line.in_uom.id or write_vals['imp_product_id'] != line.in_product_id.id):
                # Check if the UoM is compatible with the Product
                new_uom_categ = uom_obj.browse(cr, uid, write_vals['imp_uom'], context=context).category_id.id
                prod_uom_categ = prod_obj.browse(cr, uid, write_vals['imp_product_id'], context=context).uom_id.category_id.id
                if new_uom_categ != prod_uom_categ:
                    errors.append(_('The new UoM is not compatible with the product UoM.'))
                    write_vals['type_change'] = 'error'

            # Unit price
            err_msg = _('Incorrect float value for field \'Price Unit\'')
            try:
                unit_price = float(values[6])
                write_vals['imp_price'] = unit_price
            except Exception:
                errors.append(err_msg)
                write_vals['type_change'] = 'error'
                write_vals['imp_price'] = 0.00

            # Check unit price * quantity
            err_msg = _('The price subtotal must be greater than or equal to 0.01')
            if line.simu_id and line.simu_id.order_id and line.simu_id.order_id.order_type == 'regular' and write_vals['imp_price'] and write_vals['imp_qty']:
                if write_vals['imp_price'] * write_vals['imp_qty'] < 0.01:
                    errors.append(err_msg)
                    write_vals['type_change'] = 'error'
                if len(str(int(write_vals['imp_qty'] * write_vals['imp_price']))) > 25:
                    errors.append(_('The Total amount is more than 28 digits. Please check that the Qty and Unit price are correct, the current values are not allowed'))
                    write_vals.update({'imp_qty': 0.00, 'imp_price': 0.00, 'type_change': 'error'})

            # Currency
            currency_value = values[7].lower()
            if line.in_currency and tools.ustr(currency_value.lower()) == line.in_currency.name.lower():
                write_vals['imp_currency'] = line.in_currency.id
            elif line.in_currency.name:
                err_msg = _('The currency on the file is not the same as the currency of the PO line - You must have the same currency on both side - Currency of the initial line kept.')
                errors.append(err_msg)
                write_vals['type_change'] = 'error'

            # Origin
            full_origin = values[8]
            instance_sync_order_ref = False
            if full_origin and ':' in full_origin:
                origin = full_origin.split(':')[0]
                instance_sync_order_ref = full_origin.split(':')[-1]
            else:
                origin = full_origin

            if origin and import_type in ('match', 'split'):
                if origin != line.imp_origin:
                    info_msg.append(_('Origin in the imported file does not match the origin on the PO line. Imported Origin ignored'))
            elif origin:
                if line.simu_id.order_id.order_type not in ['loan', 'loan_return', 'donation_exp', 'donation_st', 'in_kind']:
                    so_ids = sale_obj.search(cr, uid, [('name', '=', origin), ('procurement_request', 'in', ['t', 'f'])],
                                             limit=1, context=context)
                    if so_ids:
                        so = sale_obj.browse(cr, uid, so_ids[0], fields_to_fetch=['state', 'order_type', 'procurement_request'], context=context)
                        if so.state not in ('done', 'cancel'):
                            if so.order_type == 'regular':
                                write_vals['imp_origin'] = origin
                            else:
                                err_msg = _('\'Origin\' Document must have the Regular Order Type')
                                errors.append(err_msg)
                                write_vals['type_change'] = 'error'
                        else:
                            err_msg = _('\'Origin\' Document can\'t be Closed or Cancelled')
                            errors.append(err_msg)
                            write_vals['type_change'] = 'error'
                        # To link the other instance's IR to the PO line
                        if line.type_change in ['new', 'split']:
                            if instance_sync_order_ref:
                                sync_order_label_ids = sync_order_obj.\
                                    search(cr, uid, [('name', '=', instance_sync_order_ref),
                                                     ('order_id.state', 'not in', ['done', 'cancel']),
                                                     ('order_id', '=', so.id)], context=context)
                                if sync_order_label_ids:
                                    write_vals['imp_sync_order_ref'] = sync_order_label_ids[0]
                                else:
                                    err_msg = _('No Order in sync. instance with an open FO was found with the data in \'Origin\'')
                                    errors.append(err_msg)
                                    write_vals['type_change'] = 'error'
                            if write_vals['imp_product_id'] and not so.procurement_request and line.simu_id.order_id.order_type == 'regular' \
                                    and prod_obj.browse(cr, uid, write_vals['imp_product_id'], fields_to_fetch=['type'], context=context).type == 'service_recep':
                                write_vals['type_change'] = 'error'
                                errors.append(_('The Service Product %s can not be linked to a FO (%s) on a Regular PO') % (values[2], origin))
                    else:
                        err_msg = _('The FO reference in \'Origin\' is not consistent with this PO')
                        errors.append(err_msg)
                        write_vals['type_change'] = 'error'
                else:
                    err_msg = _('A PO with a Loan, Donation before expiry, Standard donation or In Kind Donation Order Type can\'t have an Source Document in its lines')
                    errors.append(err_msg)
                    write_vals['type_change'] = 'error'
            elif line.simu_id.order_id.po_from_fo or line.simu_id.order_id.po_from_ir:
                if import_type == 'split':
                    info_msg.append(_('Missing mandatory Origin. Origin of same number split line has been used.'))
                elif import_type != 'match' or not line.imp_origin:
                    err_msg = _('The Origin is mandatory for a PO coming from an FO/IR')
                    errors.append(err_msg)
                    write_vals['type_change'] = 'error'

            # Stock Take Date
            if import_type in ('new', 'split'):
                stock_take_date = values[9]
                if stock_take_date and type(stock_take_date) == type(DateTime.now()):
                    if stock_take_date.strftime('%Y-%m-%d') <= line.simu_id.order_id.date_order:
                        write_vals['imp_stock_take_date'] = stock_take_date.strftime('%Y-%m-%d')
                    else:
                        err_msg = _('The  \'Stock Take Date\' is not consistent! It should not be later than %s\'s creation date') \
                            % (line.simu_id.order_id.name,)
                        errors.append(err_msg)
                        write_vals['type_change'] = 'error'
                elif stock_take_date and isinstance(stock_take_date, str):
                    try:
                        time.strptime(stock_take_date, '%Y-%m-%d')
                        if stock_take_date <= line.simu_id.order_id.date_order:
                            write_vals['imp_stock_take_date'] = stock_take_date
                        else:
                            err_msg = _('The  \'Stock Take Date\' is not consistent! It should not be later than %s\'s creation date') \
                                % (line.simu_id.order_id.name,)
                            errors.append(err_msg)
                            write_vals['type_change'] = 'error'
                    except ValueError:
                        err_msg = _('Incorrect date value for field \'Stock Take Date\'')
                        errors.append(err_msg)
                        write_vals['type_change'] = 'error'
                elif stock_take_date:
                    err_msg = _('Incorrect date value for field \'Stock Take Date\'')
                    errors.append(err_msg)
                    write_vals['type_change'] = 'error'
                elif not stock_take_date and import_type == 'new' and line.simu_id.order_id.partner_type == 'esc' \
                        and not line.simu_id.order_id.stock_take_date:
                    # If the partner is ESC and the PO has no STD, take the PO's creation date as STD for the line
                    write_vals['imp_stock_take_date'] = line.simu_id.order_id.date_order

            # Delivery Requested Date/Estimated Delivery Date
            rdd = False
            drd_value = values[10]
            if drd_value and type(drd_value) == type(DateTime.now()):
                rdd = drd_value.strftime('%Y-%m-%d')
            elif drd_value and isinstance(drd_value, str):
                try:
                    time.strptime(drd_value, '%Y-%m-%d')
                    rdd = drd_value
                except ValueError:
                    err_msg = _('Incorrect date value for field \'Delivery Requested Date\'')
                    errors.append(err_msg)
                    write_vals['type_change'] = 'error'
            elif drd_value:
                err_msg = _('Incorrect date value for field \'Delivery Requested Date\'')
                errors.append(err_msg)
                write_vals['type_change'] = 'error'
            # Update the Estimated Delivery Date if the Delivery Requested Date is changed
            if rdd and (line.type_change in ['new', 'split'] or rdd != line.po_line_id.date_planned):
                write_vals['imp_drd'] = rdd

            # ESC Confirmed
            if write_vals.get('imp_dcd') and line.simu_id.order_id.partner_type == 'esc':
                write_vals['esc_conf'] = True

            # Project Ref.
            write_vals['imp_project_ref'] = values[17]

            # Message ESC1
            write_vals['imp_esc1'] = values[18]
            # Message ESC2
            write_vals['imp_esc2'] = values[19]

            write_vals['info_msg'] = False
            if info_msg:
                write_vals['info_msg'] = ' -'.join(info_msg)
                warnings += info_msg
            if line.error_msg:
                write_vals['type_change'] = 'error'

            if write_vals.get('type_change') in ['warning', 'error']:
                err_msg = line.error_msg or ''
                for err in errors:
                    if err_msg:
                        err_msg += ' - '
                    err_msg += err
                if not err_msg and warnings:
                    err_msg = ' - '.join(warnings)
                write_vals['error_msg'] = err_msg
            else:
                write_vals['type_change'] = import_type


            self.write(cr, uid, [line.id], write_vals, context=context)

        return errors, warnings


    def update_po_line(self, cr, uid, ids, context=None):
        '''
        Update the corresponding PO lines with the imported values
        according to the change type
        '''
        line_obj = self.pool.get('purchase.order.line')
        simu_obj = self.pool.get('wizard.import.po.simulation.screen')
        wf_service = netsvc.LocalService("workflow")

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]
        nb_lines = float(len(ids))
        line_treated = 0.00
        percent_completed = 0.00
        lines_to_cancel = []
        for line in self.browse(cr, uid, ids, context=context):
            try:
                context['purchase_id'] = line.simu_id.order_id.id
                line_treated += 1
                percent_completed = int(float(line_treated) / float(nb_lines) * 100)
                if line.po_line_id and line.type_change != 'ignore' and not line.change_ok and not line.imp_external_ref and not line.imp_project_ref and not line.imp_origin:
                    continue

                if line.type_change in ('ignore', 'error', 'warning'):
                    if line.type_change in  ['warning', 'error']:
                        job_comment = context.get('job_comment', [])
                        job_comment.append({
                            'res_model': 'purchase.order',
                            'res_id': line.simu_id.order_id.id,
                            'msg': _('%s: %s on line %s %s') % (line.simu_id.order_id.name, line.type_change, line.in_line_number or line.imp_external_ref, line.error_msg),
                        })
                        context['job_comment'] = job_comment
                    continue
                elif line.info_msg:
                    # if we have a message that does not block the import of the line
                    context.setdefault('job_comment', []).append({
                        'res_model': 'purchase.order',
                        'res_id': line.simu_id.order_id.id,
                        'msg': _('%s: info on line %s %s') % (line.simu_id.order_id.name, line.in_line_number or line.imp_external_ref, line.info_msg),
                    })

                if line.type_change == 'del' and line.po_line_id:
                    lines_to_cancel.append(line.po_line_id.id)  # Delay the cancel to prevent the PO's cancellation
                    simu_obj.write(cr, uid, [line.simu_id.id], {'percent_completed': percent_completed}, context=context)
                    cr.commit()
                    continue

                if line.type_change == 'cdd':
                    line_obj.write(cr, uid, [line.po_line_id.id], {'confirmed_delivery_date': line.imp_dcd}, context=context)
                    in_ids = self.pool.get('stock.move').search(cr ,uid, [('purchase_line_id', '=', line.po_line_id.id), ('type', '=', 'in'), ('state', 'in', ['confirmed', 'assigned'])], context=context)
                    if in_ids:
                        self.pool.get('stock.move').write(cr, uid, in_ids, {'date_expected': line.imp_dcd}, context=context)

                    cr.commit()
                    continue
                line_vals = {
                    'product_id': line.imp_product_id.id,
                    'product_uom': line.imp_uom.id,
                    'price_unit': line.imp_price,
                    'product_qty': line.imp_qty,
                }

                has_delivery = False
                if line.imp_drd:
                    line_vals['esti_dd'] = line.imp_drd
                if line.imp_project_ref:
                    line_vals['project_ref'] = line.imp_project_ref
                if line.imp_origin:
                    line_vals['origin'] = line.imp_origin
                if line.imp_sync_order_ref:
                    line_vals.update({'instance_sync_order_ref': line.imp_sync_order_ref.id, 'display_sync_ref': True})
                if line.imp_external_ref:
                    line_vals['external_ref'] = line.imp_external_ref
                if line.imp_dcd:
                    has_delivery = True
                    line_vals['confirmed_delivery_date'] = line.imp_dcd
                if line.imp_stock_take_date:
                    line_vals['stock_take_date'] = line.imp_stock_take_date,

                if line.ad_info:
                    line_vals['analytic_distribution_id'] = simu_obj.create_ad(cr, uid, line.ad_info, line.simu_id.order_id.partner_id.partner_type, line.simu_id.order_id.currency_id.id, context)

                if line.type_change == 'split' and line.parent_line_id:
                    line_vals.update({
                        'is_line_split': True,
                        'order_id': line.simu_id.order_id.id,
                        'line_number': line.in_line_number,
                        'esc_confirmed': True if line.imp_dcd else False,
                        'original_line_id': line.parent_line_id.po_line_id.id,
                        'date_planned': line.imp_drd or line.in_drd or line.simu_id.order_id.delivery_requested_date,
                    })
                    if 'confirmed_delivery_date' not in line_vals:
                        line_vals['confirmed_delivery_date'] = False

                    if not line_vals.get('analytic_distribution_id') and line.parent_line_id.po_line_id.analytic_distribution_id:
                        line_vals.update({
                            'analytic_distribution_id': self.pool.get('analytic.distribution').copy(cr, uid, line.parent_line_id.po_line_id.analytic_distribution_id.id, {}, context=context),
                        })
                    if line.parent_line_id.po_line_id.stock_take_date:
                        line_vals['stock_take_date'] = line.parent_line_id.po_line_id.stock_take_date
                    split_line_id = line_obj.create(cr, uid, line_vals, context=context)
                    wf_service.trg_validate(uid, 'purchase.order.line', split_line_id, 'validated', cr)
                    if line.parent_line_id.po_line_id.linked_sol_id:
                        line_obj.update_fo_lines(cr, uid, line.parent_line_id.po_line_id.id, context=context)
                    if context.get('auto_import_confirm_pol') and has_delivery:
                        context['line_ids_to_confirm'] = context.get('line_ids_to_confirm', []) + [split_line_id]

                    job_comment = context.get('job_comment', [])
                    job_comment.append({
                        'res_model': 'purchase.order',
                        'res_id': line.simu_id.order_id.id,
                        'msg': _('%s: Line #%s has been split.') % (line.simu_id.order_id.name, line.parent_line_id.po_line_id.line_number),
                    })
                    context['job_comment'] = job_comment
                elif line.type_change == 'new':
                    line_vals.update({
                        'order_id': line.simu_id.order_id.id,
                        'set_as_validated_n': True,
                        'display_sync_ref': True,
                        'created_by_vi_import': True,
                        'date_planned': line.imp_drd,
                    })
                    if not line_vals.get('date_planned'):
                        line_vals['date_planned'] = line.simu_id.order_id.delivery_requested_date

                    if line.esc_conf:
                        line_vals['esc_confirmed'] = line.esc_conf
                    new_line_id = line_obj.create(cr, uid, line_vals, context=context)
                    new_line_numb = line_obj.read(cr, uid, new_line_id, ['line_number'], context=context)['line_number']
                    job_comment = context.get('job_comment', [])
                    job_comment.append({
                        'res_model': 'purchase.order',
                        'res_id': line.simu_id.order_id.id,
                        'msg': _('%s: New line #%s created.') % (line.simu_id.order_id.name, new_line_numb),
                    })
                    context['job_comment'] = job_comment
                    if context.get('auto_import_confirm_pol') and has_delivery:
                        context['line_ids_to_confirm'] = context.get('line_ids_to_confirm', []) + [new_line_id]
                elif line.po_line_id:
                    if line.esc_conf:
                        line_vals['esc_confirmed'] = line.esc_conf
                    if context.get('auto_import_ok') and not line.po_line_id.stock_take_date and line.simu_id.order_id.stock_take_date:
                        line_vals['stock_take_date'] = line.simu_id.order_id.stock_take_date

                    line_obj.write(cr, uid, [line.po_line_id.id], line_vals, context=context)
                    if context.get('auto_import_confirm_pol') and has_delivery:
                        context['line_ids_to_confirm'] = context.get('line_ids_to_confirm', []) + [line.po_line_id.id]
                simu_obj.write(cr, uid, [line.simu_id.id], {'percent_completed': percent_completed}, context=context)
                cr.commit()

            except Exception, e:
                cr.rollback()
                job_comment = context.get('job_comment', [])
                error_msg = hasattr(e, 'value') and e.value or e.message
                job_comment.append({
                    'res_model': 'purchase.order',
                    'res_id': line.simu_id.order_id.id,
                    'msg': _('%s: %s on line %s %s') % (line.simu_id.order_id.name, line.type_change, line.in_line_number or line.imp_external_ref, tools.ustr(error_msg)),
                })
                context['job_comment'] = job_comment

        # Cancel the lines at the end
        for line_id in lines_to_cancel:
            wf_service.trg_validate(uid, 'purchase.order.line', line_id, 'cancel', cr)

        if ids:
            return simu_obj.go_to_simulation(cr, uid, line.simu_id.id, context=context)

        return True


wizard_import_po_simulation_screen_line()
