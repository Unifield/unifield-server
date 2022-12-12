# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF
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

import time

from report import report_sxw
from osv import fields, osv
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport
from tools.translate import _


class products_situation_report(osv.osv_memory):
    _name = 'products.situation.report'

    _columns = {
        'report_date': fields.datetime(string='Generated on', readonly=True),
        'instance_id': fields.many2one('msf.instance', string='Current Instance', readonly=True),
        'prod_ids': fields.text(string='Products', readonly=True),
        'p_code': fields.char('Code', size=36),
        'p_desc': fields.char('Description', size=256),
        'product_list_id': fields.many2one('product.list', string='Product List'),
        'nomen_manda_0': fields.many2one('product.nomenclature', 'Main Type'),
        'nomen_manda_1': fields.many2one('product.nomenclature', 'Group'),
        'nomen_manda_2': fields.many2one('product.nomenclature', 'Family'),
        'nomen_manda_3': fields.many2one('product.nomenclature', 'Root'),
        'heat_sensitive_item': fields.many2one('product.heat_sensitive', string='Temperature sensitive item'),
        'sterilized': fields.selection(string='Sterile', selection=[('yes', 'Yes'), ('no', 'No'), ('no_know', 'tbd')]),
        'single_use': fields.selection(string='Single Use', selection=[('yes', 'Yes'), ('no', 'No'), ('no_know', 'tbd')]),
        'controlled_substance': fields.selection(selection=[
            ('!', '! - Requires national export license'),
            ('N1', 'N1 - Narcotic 1'),
            ('N2', 'N2 - Narcotic 2'),
            ('P1', 'P1 - Psychotrop 1'),
            ('P2', 'P2 - Psychotrop 2'),
            ('P3', 'P3 - Psychotrop 3'),
            ('P4', 'P4 - Psychotrop 4'),
            ('DP', 'DP - Drug Precursor'),
            ('Y', 'Y - Kit or module with controlled substance'),
            ('True', 'CS / NP - Controlled Substance / Narcotic / Psychotropic')
        ], string='Controlled substance'),
        'dangerous_goods': fields.selection(string='Dangerous goods', selection=[('True', 'Yes'), ('False', 'No'), ('no_know', 'tbd')]),
        'perishable': fields.selection(string='Expiry Date Mandatory', selection=[('True', 'Yes'), ('False', 'No')]),
        'batch_management': fields.selection(string='Batch Number Mandatory', selection=[('True', 'Yes'), ('False', 'No')]),
        'location_id': fields.many2one('stock.location', 'Stock Location', select=True),
    }

    _defaults = {
        'report_date': lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
        'instance_id': lambda self, cr, uid, ids, c={}: self.pool.get('res.users').browse(cr, uid, uid).company_id.instance_id.id,
        'heat_sensitive_item': False,
    }

    def get_nomen(self, cr, uid, ids, field):
        return self.pool.get('product.nomenclature').get_nomen(cr, uid, self, ids, field, context={'withnum': 1})

    def onChangeSearchNomenclature(self, cr, uid, ids, position, type, nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, num=True, context=None):
        return self.pool.get('product.product').onChangeSearchNomenclature(cr, uid, 0, position, type, nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, False, context={'withnum': 1})

    def get_values(self, cr, uid, ids, context=None):
        '''
        Retrieve the data according to values in wizard
        and print the report in Excel format.
        '''
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        prod_obj = self.pool.get('product.product')

        for report in self.browse(cr, uid, ids, context=context):
            if not report.p_code and not report.p_desc and not report.product_list_id and not report.nomen_manda_0:
                raise osv.except_osv(
                    _('Error'),
                    _('You must use at least one of the following filters: Code, Description, Product List, Nomenclature'),
                )
            prod_domain = []

            if report.p_code:
                prod_domain.append(('default_code', 'ilike', report.p_code))

            if report.p_desc:
                prod_domain.append(('name', 'ilike', report.p_desc))

            if report.product_list_id:
                prod_ids = []
                for list_line in report.product_list_id.product_ids:
                    prod_ids.append(list_line.name.id)
                prod_domain.append(('id', 'in', prod_ids))

            if report.nomen_manda_0:
                prod_domain.append(('nomen_manda_0', '=', report.nomen_manda_0.id))
                if report.nomen_manda_1:
                    prod_domain.append(('nomen_manda_1', '=', report.nomen_manda_1.id))
                    if report.nomen_manda_2:
                        prod_domain.append(('nomen_manda_2', '=', report.nomen_manda_2.id))
                        if report.nomen_manda_3:
                            prod_domain.append(('nomen_manda_3', '=', report.nomen_manda_3.id))

            if report.heat_sensitive_item:
                prod_domain.append(('heat_sensitive_item', '=', report.heat_sensitive_item.id))

            if report.sterilized:
                prod_domain.append(('sterilized', '=', report.sterilized))

            if report.single_use:
                prod_domain.append(('single_use', '=', report.single_use))

            if report.controlled_substance:
                prod_domain.append(('controlled_substance', '=', report.controlled_substance))

            if report.dangerous_goods:
                prod_domain.append(('dangerous_goods', '=', report.dangerous_goods))

            if report.perishable:
                perishable = report.perishable == 'True' and True or report.perishable == 'False' and False or ''
                prod_domain.append(('perishable', '=', perishable))

            if report.batch_management:
                batch_management = report.batch_management == 'True' and True or report.batch_management == 'False' and False or ''
                prod_domain.append(('batch_management', '=', batch_management))

            prod_ids = prod_obj.search(cr, uid, prod_domain, order='default_code', context=context)

            if not prod_ids:
                raise osv.except_osv(
                    _('Error'),
                    _('No data found with these parameters'),
                )

            self.write(cr, uid, [report.id], {'prod_ids': prod_ids}, context=context)

        return True

    def print_excel(self, cr, uid, ids, context=None):
        '''
        Retrieve the data according to values in wizard
        and print the report in Excel format.
        '''
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        self.get_values(cr, uid, ids, context=context)

        background_id = self.pool.get('memory.background.report').create(cr, uid, {
            'file_name': _('Products Situation Report'),
            'report_name': 'products.situation.report_xls',
        }, context=context)
        context['background_id'] = background_id
        context['background_time'] = 3

        data = {'ids': ids, 'context': context}
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'products.situation.report_xls',
            'datas': data,
            'context': context,
        }


products_situation_report()


class products_situation_report_parser(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        super(products_situation_report_parser, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'parseDateXls': self._parse_date_xls,
            'getLines': self.get_lines,
        })

        self._order_iterator = 0
        self._nb_orders = 0
        if context.get('background_id'):
            self.back_browse = self.pool.get('memory.background.report').browse(self.cr, self.uid, context['background_id'])
        else:
            self.back_browse = None

    def _parse_date_xls(self, dt_str, is_datetime=True):
        if not dt_str or dt_str == 'False':
            return ''
        if is_datetime:
            dt_str = dt_str[0:10] if len(dt_str) >= 10 else ''
        if dt_str:
            dt_str += 'T00:00:00.000'
        return dt_str

    def get_lines(self, report):
        prod_obj = self.pool.get('product.product')
        lines = []

        self._nb_orders = len(report.prod_ids)
        rep_context = self.localcontext.copy()
        rep_context.update({
            'states': ['done'],
            'what': ['in', 'out'],
        })
        if report.location_id:
            rep_context.update({
                'location': report.location_id.id,
                'location_id': report.location_id.id,
            })
        ftf = ['default_code', 'name', 'uom_id', 'standard_price', 'international_status', 'uf_create_date',
               'uf_write_date', 'qty_available', 'virtual_available', 'qty_allocable']
        for prod in prod_obj.browse(self.cr, self.uid, report.prod_ids, fields_to_fetch=ftf, context=rep_context):
            amc = 0
            fmc = 0
            self.cr.execute("""
                SELECT l.product_amc, l.product_consumption FROM stock_mission_report_line l, stock_mission_report r
                WHERE l.mission_report_id = r.id AND r.instance_id = %s AND l.product_id = %s AND r.full_view = 'f' 
                LIMIT 1
            """, (report.instance_id.id, prod.id))
            for srml in self.cr.fetchall():
                amc = srml[0] or 0
                fmc = srml[1] or 0

            # Do not show the line if Real Stock, Virtual Stock, Available Stock, AMC and FMC = 0
            if prod.qty_available != 0 or prod.virtual_available != 0 or prod.qty_allocable != 0 or amc != 0 or fmc != 0:
                lines.append({
                    'code': prod.default_code,
                    'name': prod.name,
                    'uom': prod.uom_id and prod.uom_id.name or '',
                    'cost_price': prod.standard_price,
                    'creator': prod.international_status and prod.international_status.name or '',
                    'create_date': prod.uf_create_date,
                    'write_date': prod.uf_write_date,
                    'real_stock': prod.qty_available,
                    'virtual_stock': prod.virtual_available,
                    'available_stock': prod.qty_allocable,
                    'amc': amc,
                    'fmc': fmc,
                })

            self._order_iterator += 1
            if self.back_browse:
                percent = float(self._order_iterator) / float(self._nb_orders)
                self.pool.get('memory.background.report').update_percent(self.cr, self.uid, [self.back_browse.id], percent)

        return lines


SpreadsheetReport(
    'report.products.situation.report_xls',
    'products.situation.report',
    'stock/report/products_situation_report_xls.mako',
    parser=products_situation_report_parser
)
