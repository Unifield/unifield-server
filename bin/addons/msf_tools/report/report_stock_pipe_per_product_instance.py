# -*- coding: utf-8 -*-

import time
import threading
import pooler
from osv import fields
from osv import osv
from report import report_sxw
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport
from service.web_services import report_spool
from tools.translate import _


class stock_pipe_per_product_instance(osv.osv):

    _name = 'stock.pipe.per.product.instance'
    _order = 'name desc'

    _columns = {
        'name': fields.datetime(string='Generated On', readonly=True),
        'state': fields.selection([('draft', 'Draft'), ('in_progress', 'In Progress'), ('ready', 'Ready')], string='State', readonly=True),
        'product_id': fields.many2one('product.product', string='Product'),
        'product_list_id': fields.many2one('product.list', string='Product List'),
        'stock_pipe_per_product_instance_prod_lines_ids': fields.one2many('stock.pipe.per.product.instance.prod.lines', 'stock_pipe_per_product_instance_id', string='Stock & Pipe for the selected Product'),
    }

    _defaults = {
        'state': lambda *a: 'draft',
    }

    def generate_report(self, cr, uid, ids, context=None):
        '''
        Generate a report of stopped products
        Method is called by button on XML view (form)
        '''
        data_obj = self.pool.get('ir.model.data')

        res = {}
        for report in self.browse(cr, uid, ids, context=context):
            # get ids of all products :
            if report.product_list_id:
                product_ids = [pll.name.id for pll in report.product_list_id.product_ids]
            elif report.product_id:
                product_ids = [report.product_id.id]
            else:
                cr.execute("""SELECT id FROM product_product""")
                product_ids = [p[0] for p in cr.fetchall()]
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
            new_thread.join(timeout=5.0) # join = wait until new_thread is finished but if it last more then timeout value, you can continue to work

            res = {
                'type': 'ir.actions.act_window',
                'res_model': self._name,
                'view_type': 'form',
                'view_mode': 'form,tree',
                'res_id': report.id,
                'context': context,
                'target': 'same',
            }

            if new_thread.is_alive():
                view_id = data_obj.get_object_reference(cr, uid, 'msf_tools', 'stock_pipe_per_product_instance_info_view')[1]
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

        if isinstance(report_ids, int):
            report_ids = [report_ids]

        new_cr = pooler.get_db(cr.dbname).cursor()

        # export datas :
        report_name = "stock.pipe.per.product.instance.xls"
        attachment_name = "stock_pipe_per_product_instance_report_%s.xls" % time.strftime('%Y%m%d_%H%M')
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
            'res_model': 'stock.pipe.per.product.instance',
            'res_id': report_ids[0],
            'datas': file_res.get('result'),
        }, context=context)

        # state is now 'ready' :
        self.write(new_cr, uid, report_ids, {'state': 'ready'}, context= context)

        new_cr.commit()
        new_cr.close(True)

        return True


stock_pipe_per_product_instance()


class stock_pipe_per_product_instance_prod_lines(osv.osv):

    _name = 'stock.pipe.per.product.instance.prod.lines'

    _columns = {
        'stock_pipe_per_product_instance_id': fields.many2one('stock.pipe.per.product.instance', string='Report Stock & Pipe per Product and per Instance'),
        'product_id': fields.many2one('product.product', string='Product'),
        'uom_id': fields.related('product_id', 'uom_id', type='many2one', relation='product.uom', store=True, string='UoM', write_relate=False),
        'instance_id': fields.many2one('msf.instance', 'Instance/Mission'),
        'uf_state': fields.related('product_id', 'state', type='many2one', relation='product.status', store=True, string='HQ UniField Status', write_relate=False),
        'ud_state': fields.related('product_id', 'state_ud', type='selection', selection=[('valid', 'Valid'), ('outdated', 'Outdated'), ('discontinued', 'Discontinued'), ('phase_out', 'Phase Out'), ('stopped', 'Stopped'), ('archived', 'Archived'), ('forbidden', 'Forbidden')], store=True, write_relate=False, string='HQ UniData Status'),
        'instance_stock': fields.float('Instance stock', related_uom='uom_id'),
        'pipe_qty': fields.float('Pipeline Qty', related_uom='uom_id'),
        'product_creator': fields.char(size=64, string='Product Creator'),
        'standard_ok': fields.selection(selection=[('standard', 'Standard'), ('non_standard', 'Non-standard'), ('non_standard_local', 'Non-standard Local')], size=32, string='Standardization Level'),
        'inst_uf_state': fields.selection(selection=[('valid', 'Valid'), ('phase_out', 'Phase Out'), ('forbidden', 'Forbidden'), ('archived', 'Archived')], string='Instance UniField Status'),
    }


stock_pipe_per_product_instance_prod_lines()


class parser_report_stock_pipe_per_product_instance_xls(report_sxw.rml_parse):
    '''
    To parse our mako template for stopped products
    '''
    def __init__(self, cr, uid, name, context=None):
        super(parser_report_stock_pipe_per_product_instance_xls, self).__init__(cr, uid, name, context=context)

        # localcontext allows you to call methods inside mako file :
        self.localcontext.update({
            'time': time,
            'parseDateXls': self._parse_date_xls,
            'get_products': self.get_products,
            'get_product_state': self.get_product_state,
            'get_stock_mission_report_lines': self.get_stock_mission_report_lines,
        })

        self.status_buffer = {}

    def _parse_date_xls(self, dt_str, is_datetime=True):
        if not dt_str or dt_str == 'False':
            return ''
        if is_datetime:
            dt_str = dt_str[0:10] if len(dt_str) >= 10 else ''
        if dt_str:
            dt_str += 'T00:00:00.000'
        return dt_str

    def get_products(self):
        '''
        Return data of products which have qty in the stock mission report
        '''
        self.cr.execute("""
            SELECT p.id, p.default_code, p.name_template, pis.name, p.standard_ok, p.state_ud
            FROM product_product p
            LEFT JOIN product_international_status pis on p.international_status = pis.id
            WHERE p.id IN (SELECT DISTINCT(product_id) FROM stock_mission_report_line WHERE full_view = 'f' 
                AND product_id IN %s AND (internal_qty != 0 OR in_pipe_qty != 0))
        """, (tuple(self.datas['lines']),))

        return self.cr.fetchall()

    def get_product_state(self, product_state):
        sel = {'valid': _('Valid'), 'phase_out': _('Phase Out'), 'forbidden': _('Forbidden'), 'archived': _('Archived')}
        return sel.get(product_state, '')

    def get_stock_mission_report_lines(self, report, product):
        '''
        Return browse record list of stock_mission_report_line with given product_id
        '''
        self.cr.execute("""
            SELECT m.instance_id, m.name, l.product_id, l.product_state, l.internal_qty, l.in_pipe_qty, l.product_state, 
                p.standard_ok, p.state_ud, ps.code
            FROM stock_mission_report_line l 
            LEFT JOIN stock_mission_report m ON l.mission_report_id = m.id 
            LEFT JOIN msf_instance i ON m.instance_id = i.id AND i.state != 'inactive' 
            LEFT JOIN product_product p ON l.product_id = p.id
            LEFT JOIN product_template pt ON p.product_tmpl_id = pt.id
            LEFT JOIN product_status ps ON pt.state = ps.id
            WHERE l.full_view = 'f' AND l.product_id = %s AND (l.internal_qty != 0 OR l.in_pipe_qty != 0)
        """, (product[0],))

        prod_infos = self.cr.fetchall()
        if report.product_id:  # Create lines to display only if one product has been selected
            for prod in prod_infos:
                info = {
                    'stock_pipe_per_product_instance_id': report.id,
                    'product_id': prod[2],
                    'instance_id': prod[0],
                    'instance_stock': prod[4],
                    'pipe_qty': prod[5],
                    'product_creator': product[3],
                    'standard_ok': prod[7],
                    'inst_uf_state': prod[6],
                }
                self.pool.get('stock.pipe.per.product.instance.prod.lines').create(self.cr, self.uid, info, context=self.localcontext)

        return prod_infos


class report_stock_pipe_per_product_instance_xls(SpreadsheetReport):

    def __init(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        super(report_stock_pipe_per_product_instance_xls, self).__init__(name, table, rml=rml, parser=parser, header=header, store=store)

    def create(self, cr, uid, ids, data, context=None):
        a = super(report_stock_pipe_per_product_instance_xls, self).create(cr, uid, ids, data, context=context)
        return (a[0], 'xls')


report_stock_pipe_per_product_instance_xls(
    'report.stock.pipe.per.product.instance.xls',
    'stock.pipe.per.product.instance',
    'addons/msf_tools/report/report_stock_pipe_per_product_instance_xls.mako',
    parser=parser_report_stock_pipe_per_product_instance_xls,
    header='internal',
)
