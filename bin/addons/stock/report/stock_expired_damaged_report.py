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

import tools
import time
import threading

from report import report_sxw
from osv import fields, osv
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport
from tools.translate import _
from service.web_services import report_spool
from datetime import datetime


class stock_expired_damaged_report(osv.osv):
    _name = 'stock.expired.damaged.report'

    _columns = {
        'name': fields.datetime(string='Generated on', readonly=True),
        'state': fields.selection(selection=[('draft', 'Draft'), ('in_progress', 'In Progress'), ('ready', 'Ready')], string='State'),
        'company_id': fields.many2one('res.company', string='DB/Instance name', readonly=True),
        'date_from': fields.date(string='From'),
        'date_to': fields.date(string='To'),
        'location_id': fields.many2one('stock.location', 'Specific Source Location', select=True),
        'location_dest_id': fields.many2one('stock.location', 'Specific Destination Location', select=True),
        'nomen_manda_0': fields.many2one('product.nomenclature', 'Product Main Type'),
        'loss_ok': fields.boolean(string='12 Loss'),
        'loss_scrap_ok': fields.boolean(string='12.1 Loss / Scrap'),
        'loss_sample_ok': fields.boolean(string='12.2 Loss / Sample'),
        'loss_expiry_ok': fields.boolean(string='12.3 Loss / Expiry'),
        'loss_damage_ok': fields.boolean(string='12.4 Loss / Damage'),
    }

    _defaults = {
        'state': 'draft',
        'company_id': lambda self, cr, uid, ids, c={}: self.pool.get('res.users').browse(cr, uid, uid).company_id.id,
        'loss_ok': True,
        'loss_scrap_ok': True,
        'loss_sample_ok': True,
        'loss_expiry_ok': True,
        'loss_damage_ok': True,
    }

    def update(self, cr, uid, ids, context=None):
        return {}

    def _get_reason_types(self, cr, uid, report):
        '''
        Return a list of Reason Type ids
        '''
        obj_data = self.pool.get('ir.model.data')
        reason_type_ids = []

        if report.loss_ok:
            reason_type_ids.append(obj_data.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_loss')[1])

        if report.loss_scrap_ok:
            reason_type_ids.append(obj_data.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_scrap')[1])

        if report.loss_sample_ok:
            reason_type_ids.append(obj_data.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_sample')[1])

        if report.loss_expiry_ok:
            reason_type_ids.append(obj_data.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_expiry')[1])

        if report.loss_damage_ok:
            reason_type_ids.append(obj_data.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_damage')[1])

        return reason_type_ids

    def generate_report(self, cr, uid, ids, context=None):
        '''
        Retrieve the data according to values in wizard
        and print the report in Excel format.
        '''
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        move_obj = self.pool.get('stock.move')
        data_obj = self.pool.get('ir.model.data')

        for report in self.browse(cr, uid, ids, context=context):
            move_domain = [
                ('type', '=', 'internal'),
                ('picking_id.state', '=', 'done'),
            ]

            if report.date_from:
                move_domain.append(('date', '>=', report.date_from))

            if report.date_to:
                move_domain.append(('date', '<=', report.date_to))

            if report.location_id:
                move_domain.append(('location_id', '=', report.location_id.id))
            else:
                move_domain.append(('location_id.usage', '=', 'internal'))

            if report.location_dest_id:
                move_domain.append(('location_dest_id', '=', report.location_dest_id.id))
            else:
                move_domain.extend(['|', ('location_dest_id.quarantine_location', '=', True),
                                    ('location_dest_id.destruction_location', '=', True)])

            if report.nomen_manda_0:
                move_domain.append(('product_id.nomen_manda_0', '=', report.nomen_manda_0.id))

            reason_types_ids = self._get_reason_types(cr, uid, report)
            if reason_types_ids:
                move_domain.append(('reason_type_id', 'in', reason_types_ids))

            move_ids = move_obj.search(cr, uid, move_domain, order='picking_id, line_number', context=context)

            if not move_ids:
                raise osv.except_osv(
                    _('Error'),
                    _('No data found with these parameters'),
                )

            datas = {
                'ids': [report.id],
                'moves_ids': move_ids,
                'reason_types_ids': reason_types_ids,
            }
            self.write(cr, uid, [report.id], {'name': time.strftime('%Y-%m-%d %H:%M:%S'), 'state': 'in_progress'}, context=context)

            cr.commit()
            # Start generating the file in the background
            new_thread = threading.Thread(
                target=self.generate_report_bkg,
                args=(cr, uid, report.id, datas, context)
            )
            new_thread.start()
            new_thread.join(30.0)

            res = {
                'type': 'ir.actions.act_window',
                'res_model': self._name,
                'view_type': 'form',
                'view_mode': 'form,tree',
                'res_id': report.id,
                'context': context,
                'target': 'same',
            }
            if new_thread.isAlive():
                view_id = data_obj.get_object_reference(cr, uid, 'stock', 'stock_expired_damaged_report_info_view')[1]
                res['view_id'] = [view_id]

            return res

        raise osv.except_osv(
            _('Error'),
            _('No data found with these parameters'),
        )

    def generate_report_bkg(self, cr, uid, ids, datas, context=None):
        """
        Generate the report in background
        """
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        import pooler
        new_cr = pooler.get_db(cr.dbname).cursor()

        rp_spool = report_spool()
        result = rp_spool.exp_report(cr.dbname, uid, 'stock.expired.damaged.report_xls', ids, datas, context)
        file_res = {'state': False}
        while not file_res.get('state'):
            file_res = rp_spool.exp_report_get(cr.dbname, uid, result)
            time.sleep(0.5)
        attachment = self.pool.get('ir.attachment')
        attachment.create(new_cr, uid, {
            'name': 'expired_damaged_products_%s.xls' % time.strftime('%Y_%m_%d_%H_%M'),
            'datas_fname': 'expired_damaged_products_%s.xls' % time.strftime('%Y_%m_%d_%H_%M'),
            'description': _('Expired-Damaged Products Report'),
            'res_model': 'stock.expired.damaged.report',
            'res_id': ids[0],
            'datas': file_res.get('result'),
        })
        self.write(new_cr, uid, ids, {'state': 'ready'}, context=context)

        new_cr.commit()
        new_cr.close(True)

        return True


stock_expired_damaged_report()


class stock_expired_damaged_parser(report_sxw.rml_parse):
    def __init__(self, cr, uid, name, context):
        super(stock_expired_damaged_parser, self).__init__(cr, uid, name, context=context)
        self.localcontext.update({
            'parseDateXls': self._parse_date_xls,
            'getReasonTypesText': self.reason_types_text,
            'getMoves': self.get_moves,
        })

    def _parse_date_xls(self, dt_str, is_datetime=True):
        if not dt_str or dt_str == 'False':
            return ''
        if is_datetime:
            dt_str = dt_str[0:10] if len(dt_str) >= 10 else ''
        if dt_str:
            dt_str += 'T00:00:00.000'
        return dt_str

    def reason_types_text(self):
        rt_obj = self.pool.get('stock.reason.type')

        rts_text = []
        for rt in rt_obj.browse(self.cr, self.uid, self.datas['reason_types_ids'], context=self.localcontext):
            if rt.parent_id:
                rts_text.append(str(rt.parent_id.id) + '.' + str(rt.code))
            else:
                rts_text.append(str(rt.code))

        return rts_text and ', '.join(rts_text) or ''

    def get_moves(self):
        move_obj = self.pool.get('stock.move')
        res = []

        for move in move_obj.browse(self.cr, self.uid, self.datas['moves_ids'], context=self.localcontext):
            price_at_date = False
            self.cr.execute("""SELECT distinct on (product_id) product_id, new_standard_price
            FROM standard_price_track_changes
            WHERE product_id = %s AND change_date <= %s
            ORDER BY product_id, change_date desc
            """, (move.product_id.id, move.date))
            for x in self.cr.fetchall():
                price_at_date = x[1]
            res.append({
                'ref': move.picking_id.name,
                'reason_type': move.reason_type_id and move.reason_type_id.name or '',
                'main_type': move.product_id and move.product_id.nomen_manda_0 and move.product_id.nomen_manda_0.name or '',
                'product_code': move.product_id and move.product_id.default_code or '',
                'product_desc': move.product_id and move.product_id.name or '',
                'uom': move.product_uom and move.product_uom.name or '',
                'qty': move.product_qty,
                'batch': move.prodlot_id and move.prodlot_id.name or '',
                'exp_date': move.expired_date,
                'unit_price': price_at_date or move.price_unit,
                'currency': move.price_currency_id and move.price_currency_id.name or
                            move.product_id.currency_id and move.product_id.currency_id.name or '',
                'total_price': price_at_date and move.product_qty * price_at_date or
                               move.product_qty * move.price_unit,
                'src_loc': move.location_id and move.location_id.name or '',
                'dest_loc': move.location_dest_id and move.location_dest_id.name or '',
                'crea_date': move.picking_id.date,
                'move_date': move.date,
            })

        return res


SpreadsheetReport(
    'report.stock.expired.damaged.report_xls',
    'stock.expired.damaged.report',
    'stock/report/stock_expired_damaged_report_xls.mako',
    parser=stock_expired_damaged_parser
)
