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



class export_report_inconsistencies(osv.osv):

    _name = 'export.report.inconsistencies'
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
            new_thread = threading.Thread(target=self.generate_report_bkg, args=(cr, uid, report.id, datas, context))
            new_thread.start()
            new_thread.join(timeout=25.0) # join = wait until new_thread is finished but if it last more then timeout value, you can continue to work

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
        report_name = "inconsistencies.xls"
        attachment_name = "inconsistencies_report_%s.xls" % time.strftime('%d-%m-%Y_%Hh%M')
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
            'description': "Inconsistencies with HQ",
            'res_model': 'export.report.inconsistencies',
            'res_id': report_ids[0],
            'datas': file_res.get('result'),
        }, context=context)

        # state is now 'ready' :
        self.write(new_cr, uid, report_ids, {'state': 'ready'}, context= context)

        new_cr.commit()
        new_cr.close(True)

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
        smrl_obj = self.pool.get('stock.mission.report.line')
        inconsistent_id_list = []
        if not self.inconsistent:
            prod_obj = self.pool.get('product.product')
            prod_status_obj = self.pool.get('product.status')

            smrl_ids = smrl_obj.search(self.cr, self.uid, [('full_view', '=', False)], order='NO_ORDER', context=self.localcontext)

            # check stock mission report line for inconsistencies with HQ (our instance):
            self.inconsistent = {}
            read_smrl_result = smrl_obj.read(self.cr, self.uid, smrl_ids,
                    ['product_id', 'product_state', 'state_ud',
                    'product_active', 'mission_report_id', 'default_code',
                    'international_status_code'],
                    context=self.localcontext)

            read_smrl_result_dict = {}
            all_product_ids = []
            for read_smrl in read_smrl_result:
                read_smrl_result_dict[read_smrl['id']] = read_smrl
                all_product_ids.append(read_smrl['product_id'][0])
            del read_smrl_result

            # read all product informations
            product_result = prod_obj.read(self.cr, self.uid, all_product_ids,
                    ['state', 'state_ud', 'active', 'name_template',
                     'international_status', 'default_code'],
                     context=self.localcontext)
            product_dict = dict((x['id'], x) for x in product_result)

            # get all product_status
            prod_status_ids = prod_status_obj.search(self.cr, self.uid, [], context=self.localcontext)
            prod_status_result = prod_status_obj.read(self.cr, self.uid, prod_status_ids, ['code'], context=self.localcontext)
            prod_status_dict = dict((x['id'], x['code']) for x in prod_status_result)

            # get all instance id and build a level dict
            instance_obj = self.pool.get('msf.instance')
            instance_ids = instance_obj.search(self.cr, self.uid, [])
            instance_read_result = instance_obj.read(self.cr, self.uid, instance_ids,
                    ['level', 'name'], context=self.localcontext)
            instance_level_dict = dict((x['id'], x) for x in
                    instance_read_result)

            # get all report id and build a instance dict
            smr_obj = self.pool.get('stock.mission.report')
            smr_ids = smr_obj.search(self.cr, self.uid, [])
            smr_read_result = smr_obj.read(self.cr, self.uid, smr_ids,
                    ['instance_id'], context=self.localcontext)
            smr_instance_dict = dict((x['id'], x) for x in
                    smr_read_result)

            # get all uf_status codes
            uf_status_obj = self.pool.get('product.status')
            uf_status_code_ids = uf_status_obj.search(self.cr, self.uid, [], context=self.localcontext)
            uf_status_code_read_result = uf_status_obj.read(self.cr, self.uid,
                    uf_status_code_ids, ['code', 'name'], context=self.localcontext)
            uf_status_code_dict = dict((x['code'], x) for x in
                    uf_status_code_read_result)

            product_result_dict = {}
            state_ud_dict = {}
            for product in product_result:
                inconsistent_id_list = []
                # get the lines matching this product
                smrl_ids = smrl_obj.search(self.cr, self.uid,
                        [('full_view', '=', False),
                         ('product_id', '=', product['id'])],
                         order='NO_ORDER', context=self.localcontext)

                # get the inconsistent related lines
                for smrl_id in smrl_ids:
                    smrl = read_smrl_result_dict[smrl_id] 
                    product = product_dict[smrl['product_id'][0]]
                    # in product_product state is False when empty
                    # in smrl product_state is '' when empty:
                    if not product['state'] and not smrl['product_state']:
                        pass
                    elif not product['state'] and smrl['product_state']:
                        inconsistent_id_list.append(smrl['id'])
                        continue
                    elif product['state'] and not smrl['product_state']:
                        inconsistent_id_list.append(smrl['id'])
                        continue
                    elif product['state'] and product['state'] in prod_status_dict:
                        state_code = prod_status_dict[product['state'][0]]
                        if state_code != smrl['product_state']:
                            inconsistent_id_list.append(smrl['id'])
                            continue

                    if not product['state_ud'] and not smrl['state_ud']:
                        pass
                    elif product['state_ud'] != smrl['state_ud']:
                        inconsistent_id_list.append(smrl['id'])
                        continue

                    if product['active'] != smrl['product_active']: # if null in DB smrl.product_active = False ....
                        inconsistent_id_list.append(smrl['id'])
                        continue

                if inconsistent_id_list:
                    product_result_dict[product['id']] = {}
                    current_prod = product_result_dict[product['id']]
                    current_prod['smrl_list'] = []
                    prod_state_ud = ''
                    if product['state_ud']:
                        if product['state_ud'] not in state_ud_dict:
                            product_browse_obj = prod_obj.browse(self.cr, self.uid, product['id'], context=self.localcontext)
                            state_ud_name = self.pool.get('ir.model.fields').get_browse_selection(self.cr, self.uid, product_browse_obj, 'state_ud', self.localcontext)
                            state_ud_dict[product['state_ud']] = state_ud_name
                        prod_state_ud = state_ud_dict[product['state_ud']] 
                    current_prod.update({
                        'prod_default_code': product['default_code'],
                        'prod_name_template': product['name_template'],
                        'prod_international_status': product['international_status'] and product['international_status'][1] or '',
                        'prod_state': product['state'] and product['state'][1] or '',
                        'prod_state_ud': prod_state_ud,
                        'prod_active': product['active'],
                    })

                    # build the result list dict
                    for smrl_id in inconsistent_id_list:
                        smrl = read_smrl_result_dict[smrl_id]
                        instance_id = smr_instance_dict[smrl['mission_report_id'][0]]['instance_id'][0]
                        
                        smrl_dict = {
                            'instance_name': instance_level_dict[instance_id]['name'],
                            'smrl_default_code': smrl['default_code'],
                            'smrl_name_template': product['name_template'],
                            'internationnal_status_code_name': smrl['international_status_code'] and smrl['international_status_code'][1] or '',
                            'uf_status_code': smrl['product_state'] and uf_status_code_dict[smrl['product_state']]['name'] or '',
                            'ud_status_code': self.get_ud_status(smrl['state_ud']),
                            'active': smrl['product_active'],
                            'instance_level': instance_level_dict[instance_id]['level'],
                        }
                        product_result_dict[product['id']]['smrl_list'].append(smrl_dict)
                    product_result_dict[product['id']]['smrl_list'].sort(key=lambda smrl: smrl['instance_level']) 
                    self.inconsistent[product['id']] = product_result_dict[product['id']]

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
