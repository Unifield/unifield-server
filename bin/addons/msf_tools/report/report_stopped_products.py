# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
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
import threading
from osv import fields
from osv import osv
from report import report_sxw
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport
from service.web_services import report_spool
from tools.translate import _



class export_report_stopped_products(osv.osv):

    _name = 'export.report.stopped.products'
    _order = 'name desc'

    _columns = {
        'name': fields.datetime(string='Generated On', readonly=True),
        'state': fields.selection(
            [('draft', 'Draft'),
             ('in_progress', 'In Progress'),
             ('ready', 'Ready')],
            string='State',
            readonly=True,
        ),
    }

    _defaults = {
        'state': lambda *a: 'draft',
    }


    def generate_report(self, cr, uid, ids, context=None):
        '''
        Generate a report of stopped products
        Method is called by button on XML view (form)
        '''
        prod_obj = self.pool.get('product.product')
        data_obj = self.pool.get('ir.model.data')

        res = {}
        for report in self.browse(cr, uid, ids, context=context):
            # get ids of all non-local products :
            status_local_id = data_obj.get_object_reference(cr, uid, 'product_attributes', 'int_4')[1]
            product_ids = prod_obj.search(cr, uid, [('international_status', '!=', status_local_id)], context=context)
            if not product_ids:
                continue

            # state of report is in progress :
            self.write(cr, uid, [report.id], {
                'name': time.strftime('%Y-%m-%d %H:%M:%S'), 
                'state': 'in_progress'
            }, context=context)

            datas = {
                'ids': [report.id],
                'lines': product_ids,
            }

            cr.commit()
            new_thread = threading.Thread(target=self.generate_report_bkg, args=(cr, uid, report.id, datas, context))
            new_thread.start()
            new_thread.join(timeout=30.0) # join = wait until new_thread is finished but if it last more then timeout value, you can continue to work

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
                view_id = data_obj.get_object_reference(
                    cr, uid,
                    'msf_tools',
                    'report_stopped_products_info_view')[1]
                res['view_id'] = [view_id]

        if not res:
            raise osv.except_osv(
                _('Error'),
                _("Nothing to generate")
            )

        return res


    def generate_report_bkg(self, cr, uid, report_ids, datas, context=None):
        '''
        Generate the report in background (thread)
        '''
        attachment_obj = self.pool.get('ir.attachment')

        if context is None:
            context ={}

        if isinstance(report_ids, (int, long)):
            report_ids = [report_ids]

        import pooler
        new_cr = pooler.get_db(cr.dbname).cursor()

        # export datas :
        report_name = "stopped.products.xls"
        attachment_name = "stopped_products_report_%s.xls" % time.strftime('%d-%m-%Y_%Hh%M')
        rp_spool = report_spool()
        res_export = rp_spool.exp_report(cr.dbname, uid, report_name, report_ids, datas, context)
        file_res = {'state': False}
        while not file_res.get('state'):
            file_res = rp_spool.exp_report_get(new_cr.dbname, uid, res_export)
            time.sleep(0.5)

        # attach report to the right panel :
        attachment_obj.create(new_cr, uid, {
            'name': attachment_name,
            'datas_fname': attachment_name,
            'description': "Stopped products",
            'res_model': 'export.report.stopped.products',
            'res_id': report_ids[0],
            'datas': file_res.get('result'),
        }, context=context)

        # state is now 'ready' :
        self.write(new_cr, uid, report_ids, {'state': 'ready'}, context= context)

        new_cr.commit()
        new_cr.close(True)

        return True


export_report_stopped_products()


class parser_report_stopped_products_xls(report_sxw.rml_parse):
    '''
    To parse our mako template for stopped products
    '''
    def __init__(self, cr, uid, name, context=None):
        super(parser_report_stopped_products_xls, self).__init__(cr, uid, name, context=context)

        # localcontext allows you to call methods inside mako file :
        self.localcontext.update({
            'time': time,
            'get_uf_stopped_products': self.get_uf_stopped_products,
            'get_stock_mission_report_lines': self.get_stock_mission_report_lines,
            'get_uf_status': self.get_uf_status,
        })

        self.status_buffer = {}

    def get_uf_stopped_products(self):
        '''
        Return browse record list that contains stopped products
        taking in account non-local/temp products stopped in the current instance,
        and products in stock mission if they have qty in stock or in pipe
        '''
        prod_obj = self.pool.get('product.product')
        data_obj = self.pool.get('ir.model.data')
        smrl_obj = self.pool.get('stock.mission.report.line')

        stopped_state_id = data_obj.get_object_reference(self.cr, self.uid, 'product_attributes', 'status_3')[1]
        status_local_id = data_obj.get_object_reference(self.cr, self.uid, 'product_attributes', 'int_4')[1]
        temporary_status_id = data_obj.get_object_reference(self.cr, self.uid, 'product_attributes', 'int_5')[1]

        hq_stopped_ids = prod_obj.search(self.cr, self.uid, [
            ('state', '=', stopped_state_id), 
            ('international_status', '!=', status_local_id),
            ('international_status', '!=', temporary_status_id)],
            context=self.localcontext)

        smrl_ids = smrl_obj.search(self.cr, self.uid, [
            ('full_view', '=', False),
            ('product_state', '=', 'stopped'),
            '|', ('internal_qty', '!=', 0),
            ('in_pipe_qty', '!=', 0)
        ], context=self.localcontext)

        sm_stopped_ids = smrl_obj.read(self.cr, self.uid, smrl_ids, ['product_id'], context=self.localcontext)
        sm_stopped_ids = [x.get('product_id')[0] for x in sm_stopped_ids]

        # build a list of stopped products with unique ids and sorted by default_code:
        stopped_ids = list(set(hq_stopped_ids + sm_stopped_ids))
        ls = []
        for prod in prod_obj.browse(self.cr, self.uid, stopped_ids, context=self.localcontext):
            ls.append( (prod.id, prod.default_code) )
        sorted_stopped_ids = [x[0] for x in sorted(ls, key=lambda tup: tup[1])]

        return prod_obj.browse(self.cr, self.uid, sorted_stopped_ids, context=self.localcontext)

    def get_stock_mission_report_lines(self, product):
        '''
        Return browse record list of stock_mission_report_line with given product_id
        '''
        data_obj = self.pool.get('ir.model.data')
        smrl_obj = self.pool.get('stock.mission.report.line')
        smrl_ids = smrl_obj.search(self.cr, self.uid, [('product_id', '=', product.id)], context=self.localcontext)

        stopped_state_id = data_obj.get_object_reference(self.cr, self.uid, 'product_attributes', 'status_3')[1]

        res = [smrl for smrl in smrl_obj.browse(self.cr, self.uid, smrl_ids, context=self.localcontext) if \
               not smrl.full_view and (smrl.product_state == 'stopped' or product.state.id == stopped_state_id) and
               (smrl.internal_qty != 0 or smrl.in_pipe_qty != 0) and smrl.mission_report_id.instance_id.state != 'inactive']

        return res

    def get_uf_status(self, code):
        '''
        Return the name of the unifield status with the given code
        '''
        if code in self.status_buffer:
            return self.status_buffer[code]

        status_obj = self.pool.get('product.status')
        code_ids = status_obj.search(self.cr, self.uid, [('code', '=', code)], context=self.localcontext)
        res = ""
        if code_ids:
            res = status_obj.read(self.cr, self.uid, code_ids, ['name'])[0]['name']

        self.status_buffer[code] = res

        return res


class report_stopped_products_xls(SpreadsheetReport):

    def __init(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        super(report_stopped_products_xls, self).__init__(
            name,
            table,
            rml=rml,
            parser=parser,
            header=header,
            store=store
        )

    def create(self, cr, uid, ids, data, context=None):
        a = super(report_stopped_products_xls, self).create(cr, uid, ids, data, context=context)
        return (a[0], 'xls')


report_stopped_products_xls(
    'report.stopped.products.xls',
    'export.report.stopped.products',
    'addons/msf_tools/report/report_stopped_products_xls.mako',
    parser=parser_report_stopped_products_xls,
    header='internal',
)
