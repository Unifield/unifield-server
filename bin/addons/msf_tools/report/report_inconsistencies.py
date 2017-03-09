# -*- coding: utf-8 -*-

import time
import threading
from osv import fields
from osv import osv
from report import report_sxw
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetReport
from service.web_services import report_spool
from tools.translate import _
import logging
import pooler


class export_report_inconsistencies(osv.osv):

    _name = 'export.report.inconsistencies'
    _order = 'name desc'

    _columns = {
        'name': fields.datetime(string='Generated On', readonly=True),
        'state': fields.selection(
            [('draft', 'Draft'),
             ('in_progress', 'In Progress'),
             ('error', 'Error'),
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
        Generate a report
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

            new_thread = threading.Thread(target=self.generate_new_report_bkg_newthread, args=(cr, uid, report.id, datas, context))
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

            if new_thread.isAlive():
                view_id = data_obj.get_object_reference(
                    cr, uid,
                    'msf_tools',
                    'report_inconsistencies_info_view')[1]
                res['view_id'] = [view_id]

        if not res:
            raise osv.except_osv(
                _('Error'),
                _("Nothing to generate")
            )

        return res

    def generate_new_report_bkg_newthread(self, cr, uid, report_ids, datas, context=None):
        '''
        run the thread protected with a try except
        '''
        if isinstance(report_ids, (int, long)):
            report_ids = [report_ids]
        logger = logging.getLogger('Product Status inconsistencies report')
        new_cr = pooler.get_db(cr.dbname).cursor()
        try:
            self.generate_report_bkg(new_cr, uid, report_ids, datas, context=context)
        except Exception as e:
            logger.error('Error while running the Product Status inconsistencies report: %s' % str(e))
            new_cr2 = pooler.get_db(cr.dbname).cursor()
            self.write(new_cr2, uid, report_ids, {
                'state': 'error'
            }, context=context)
            new_cr2.commit()
            new_cr2.close(True)
        finally:
            new_cr.close(True)

    def generate_report_bkg(self, cr, uid, report_ids, datas, context=None):
        '''
        Generate the report in background (thread)
        '''
        if context is None:
            context ={}
        attachment_obj = self.pool.get('ir.attachment')

        if isinstance(report_ids, (int, long)):
            report_ids = [report_ids]

        # export datas :
        report_name = "inconsistencies.xls"
        attachment_name = "inconsistencies_report_%s.xls" % time.strftime('%d-%m-%Y_%Hh%M')
        rp_spool = report_spool()
        res_export = rp_spool.exp_report(cr.dbname, uid, report_name, report_ids, datas, context)
        file_res = {'state': False}
        while not file_res.get('state'):
            file_res = rp_spool.exp_report_get(cr.dbname, uid, res_export)
            time.sleep(0.5)

        # attach report to the right panel :
        attachment_obj.create(cr, uid, {
            'name': attachment_name,
            'datas_fname': attachment_name,
            'description': "Inconsistencies with HQ",
            'res_model': 'export.report.inconsistencies',
            'res_id': report_ids[0],
            'datas': file_res.get('result'),
        }, context=context)

        # state is now 'ready' :
        self.write(cr, uid, report_ids, {'state': 'ready'}, context= context)
        cr.commit()
        return True


export_report_inconsistencies()



class parser_report_inconsistencies_xls(report_sxw.rml_parse):
    '''
    To parse our mako template for inconsistencies
    '''
    def __init__(self, cr, uid, name, context=None):
        super(parser_report_inconsistencies_xls, self).__init__(cr, uid, name, context=context)

        # localcontext allows you to call methods inside mako file :
        self.localcontext.update({
            'time': time,
            'get_uf_status': self.get_uf_status,
            'get_ud_status': self.get_ud_status,
            'get_inconsistent_lines': self.get_inconsistent_lines,
            'get_products_with_inconsistencies': self.get_products_with_inconsistencies,
            'get_product_creator_name_from_code': self.get_product_creator_name_from_code,
        })

        # cached data
        self.uf_status_cache = {}
        self.prod_creator_cache = {}
        self.inconsistent = {}


    def get_inconsistent_lines(self, prod_id=None):
        '''
        Return stock mission report lines that are inconsistent with HQ
        Based on the fields: product_active, state_ud and international_status_code

        prod_id: You can get only SMRL with product_id, if you don't give this information you
        will get all inconsistents SMRL
        '''
        product_creator_obj = self.pool.get('product.international.status')

        intl_status_code_name = {}
        intl_status_ids = product_creator_obj.search(self.cr, self.uid, [])
        for intl_status in product_creator_obj.read(self.cr, self.uid,
                intl_status_ids, ['code', 'name']):
            intl_status_code_name.setdefault(intl_status['code'],
            intl_status['name'])

        if not self.inconsistent:
            prod_obj = self.pool.get('product.product')
            self.inconsistent = {}

            request = '''
                SELECT
                    smr.name,
                    pp.default_code,
                    pp.name_template,
                    smrl.international_status_code,
                    smrl.product_state,
                    smrl.state_ud,
                    smrl.product_active,
                    instance.level,
                    pp.id,
                    pp.international_status,
                    pt.state,
                    pp.state_ud,
                    pp.active
                FROM
                    stock_mission_report_line AS smrl
                    INNER JOIN product_product AS pp ON pp.id = smrl.product_id
                    INNER JOIN product_template AS pt ON pp.product_tmpl_id = pt.id
                    LEFT JOIN product_status AS ps ON pt.state = ps.id
                    INNER JOIN stock_mission_report AS smr ON smr.id = smrl.mission_report_id
                    INNER JOIN msf_instance AS instance ON smr.instance_id = instance.id
                    JOIN (VALUES ('section',1), ('coordo',2), ('project',3)) AS il(id, ordering) ON instance.level = il.id
                WHERE
                    smrl.full_view='f' AND
                    instance.state='active' AND
                    (coalesce(ps.code, '') != coalesce(smrl.product_state, '') OR
                    pp.state_ud != smrl.state_ud OR pp.active != smrl.product_active)

                ORDER BY
                    pp.default_code, il.ordering, smr.name
            '''
            self.cr.execute(request)
            smrl_results = self.cr.fetchall()  # this object is 3.3 MB in RAM
                                               # with 340 000 lines of result

            # get all uf_status codes
            uf_status_obj = self.pool.get('product.status')
            uf_status_code_ids = uf_status_obj.search(self.cr, self.uid, [], context=self.localcontext)
            uf_status_code_read_result = uf_status_obj.read(self.cr, self.uid,
                    uf_status_code_ids, ['code', 'name'], context=self.localcontext)
            uf_status_code_dict = dict((x['code'], x['name']) for x in
                                       uf_status_code_read_result)

            # build a dict of state_ud
            state_ud_dict = dict(prod_obj._columns['state_ud'].selection)

            # build a dict of product internationnal_status
            int_status_obj = self.pool.get('product.international.status')
            ids = int_status_obj.search(self.cr, self.uid, [], context=self.localcontext)
            read_result = int_status_obj.read(self.cr, self.uid, ids,
                    ['code', 'name'], context=self.localcontext)
            status_code_dict = dict((x['id'], x['name']) for x in read_result)

            # build a dict of product status
            status_obj = self.pool.get('product.status')
            ids = status_obj.search(self.cr, self.uid, [], context=self.localcontext)
            read_result = status_obj.read(self.cr, self.uid, ids,
                    ['code', 'name'], context=self.localcontext)
            state_code_dict = dict((x['id'], x['name']) for x in read_result)

            keys = (
                'instance_name',
                'smrl_default_code',
                'smrl_name_template',
                'internationnal_status_code_name',
                'uf_status_code',
                'ud_status_code',
                'active',
                'instance_level',
                'product_id',
                'product_international_status',
                'product_state',
                'prod_state_ud',
                'prod_active',
            )

            for smrl_line in smrl_results:
                smrl = dict(zip(keys, smrl_line))
                product_id = smrl.pop('product_id')
                prod_state_ud = smrl.pop('prod_state_ud')
                prod_active = smrl.pop('prod_active')
                if product_id not in self.inconsistent:
                    prod_default_code = smrl['smrl_default_code']
                    prod_name_template = smrl['smrl_name_template']
                    prod_state_ud = prod_state_ud in state_ud_dict and state_ud_dict[prod_state_ud] or ''
                    prod_state = smrl['product_state']
                    prod_state = prod_state in state_code_dict and state_code_dict[prod_state] or ''
                    prod_int_status = smrl['product_international_status']
                    prod_int_status = prod_int_status in status_code_dict and status_code_dict[prod_int_status] or ''
                    product = {
                        'prod_default_code': prod_default_code,
                        'prod_name_template': prod_name_template,
                        'prod_international_status': prod_int_status,
                        'prod_state': prod_state,
                        'prod_state_ud': prod_state_ud,
                        'prod_active': prod_active,
                    }
                    self.inconsistent[product_id] = product
                    self.inconsistent[product_id]['smrl_list'] = []

                # tweak results to display string instead of codes
                smrl['uf_status_code'] = smrl['uf_status_code'] and uf_status_code_dict[smrl['uf_status_code']] or ''
                smrl['ud_status_code'] = smrl['ud_status_code'] and self.get_ud_status(smrl['ud_status_code']) or ''
                smrl['internationnal_status_code_name'] = smrl['internationnal_status_code_name'] and intl_status_code_name[smrl['internationnal_status_code_name']] or ''

                smrl_list = self.inconsistent[product_id]['smrl_list']
                smrl_list.append(smrl)

        if prod_id:
            return self.inconsistent[prod_id]
        else:
            return self.inconsistent

    def get_products_with_inconsistencies(self):
        '''
        return a browse record list of inconsistent product_product
        '''
        if not self.inconsistent:
            self.inconsistent = self.get_inconsistent_lines()

        prod_ids = self.inconsistent.keys()

        # order product id by default code
        prod_obj = self.pool.get('product.product')
        prod_result = prod_obj.read(self.cr, self.uid, prod_ids, ['default_code'], self.localcontext)
        prod_result.sort(key=lambda prod: prod['default_code'])
        ordered_ids = [x['id'] for x in prod_result]

        # order self.inconsistent according with this ids
        final_result = [self.inconsistent[x] for x in ordered_ids] 
        return final_result


    def get_uf_status(self, code):
        '''
        Return the name of the unifield status with the given code
        '''
        if code in self.uf_status_cache:
            return self.uf_status_cache[code]

        status_obj = self.pool.get('product.status')
        code_ids = status_obj.search(self.cr, self.uid, [('code', '=', code)], context=self.localcontext)
        res = ""
        if code_ids:
            res = status_obj.read(self.cr, self.uid, code_ids, ['name'])[0]['name']

        self.uf_status_cache[code] = res

        return res


    def get_ud_status(self, code):
        '''
        Return the name of the unidata status with the given code
        '''
        if not code or not isinstance(code, (str, unicode)):
            return ''
        return code.capitalize().replace('_', ' ')


    def get_product_creator_name_from_code(self, code):
        '''
        return the name of the product creator with the given code
        '''
        if code in self.prod_creator_cache:
            return self.prod_creator_cache[code]

        prodstat_obj = self.pool.get('product.international.status')
        prodstat_ids = prodstat_obj.search(self.cr, self.uid, [('code', '=', code)], context=self.localcontext)
        if not prodstat_ids:
            return code

        name = prodstat_obj.read(self.cr, self.uid, prodstat_ids, ['name'], context=self.localcontext)[0]['name']
        self.prod_creator_cache[code] = name

        return name



class report_inconsistencies_xls(SpreadsheetReport):

    def __init(self, name, table, rml=False, parser=report_sxw.rml_parse, header='external', store=False):
        super(report_inconsistencies_xls, self).__init__(
            name,
            table,
            rml=rml,
            parser=parser,
            header=header,
            store=store
        )

    def create(self, cr, uid, ids, data, context=None):
        a = super(report_inconsistencies_xls, self).create(cr, uid, ids, data, context=context)
        return (a[0], 'xls')



report_inconsistencies_xls(
    'report.inconsistencies.xls',
    'export.report.inconsistencies',
    'addons/msf_tools/report/report_inconsistencies_xls.mako',
    parser=parser_report_inconsistencies_xls,
    header='internal',
)
