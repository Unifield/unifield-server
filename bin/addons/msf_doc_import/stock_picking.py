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

import base64
import time
import re
from os import path

from osv import fields
from osv import osv
from tools.translate import _
import netsvc

from msf_doc_import import GENERIC_MESSAGE, PPL_IMPORT_FOR_UPDATE_MESSAGE
from msf_doc_import.wizard import INT_COLUMNS_HEADER_FOR_IMPORT as columns_header_for_internal_import
from msf_doc_import.wizard import IN_COLUMNS_HEADER_FOR_IMPORT as columns_header_for_incoming_import
from msf_doc_import.wizard import IN_LINE_COLUMNS_FOR_IMPORT as columns_for_incoming_import
from msf_doc_import.wizard import OUT_COLUMNS_HEADER_FOR_IMPORT as columns_header_for_delivery_import
from msf_doc_import.wizard import OUT_LINE_COLUMNS_FOR_IMPORT as columns_for_delivery_import
from msf_doc_import.wizard import PPL_COLUMNS_LINES_FOR_IMPORT as ppl_columns_lines_for_import
from msf_doc_import.wizard.wizard_in_simulation_screen import LINES_COLUMNS as IN_LINES_COLUMNS
from msf_doc_import.wizard.wizard_in_simulation_screen import HEADER_COLUMNS
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetCreator
from spreadsheet_xml.spreadsheet_xml import SpreadsheetXML
from service.web_services import report_spool
import xml.etree.ElementTree as ET


class stock_picking(osv.osv):
    """
    We override the class for import of Internal moves
    """
    _inherit = 'stock.picking'

    _columns = {
        'filetype': fields.selection([('excel', 'Excel file'),
                                      ('xml', 'XML file')], string='Type of file',),
        'last_imported_filename': fields.char(size=128, string='Filename'),
    }

    def get_import_filetype(self, cr, uid, file_path, context=None):
        if context is None:
            context = {}

        if '.' not in file_path:
            raise osv.except_osv(_('Error'), _('Wrong extension for given import file')  )

        if file_path.endswith('.xml'):
            return 'xml'
        elif file_path.endswith('.xls'):
            return 'excel'
        else:
            raise osv.except_osv(_('Error'), _('Import file extension should end with .xml or .xls'))


    def get_available_incoming_from_po_name(self, cr, uid, po_name, context=None):
        if context is None:
            context = {}

        if po_name.find(':') != -1:
            for part in po_name.split(':'):
                re_res = re.findall(r'PO[0-9]+$', part, re.I)
                if re_res:
                    po_name = part
                    break

        po_id = self.pool.get('purchase.order').search(cr, uid, [('name', '=ilike', po_name)], context=context)
        if not po_id:
            raise osv.except_osv(_('Error'), _('PO with name %s not found') % po_name)
        in_id = self.pool.get('stock.picking').search(cr, uid, [
            ('purchase_id', '=', po_id[0]),
            ('type', '=', 'in'),
            ('state', 'in', ['assigned', 'shipped']),
            ('claim', '=', False),
        ], context=context)
        if not in_id:
            raise osv.except_osv(_('Error'), _('No available IN found for the given PO %s') % po_name)

        return in_id[0]


    def get_incoming_id_from_file(self, cr, uid, file_path, context=None):
        if context is None:
            context = {}

        filetype = self.get_import_filetype(cr, uid, file_path, context)
        xmlstring = open(file_path).read()

        incoming_id = False
        if filetype == 'excel':
            file_obj = SpreadsheetXML(xmlstring=xmlstring)
            po_name = False
            for index, row in enumerate(file_obj.getRows()):
                if (row.cells[0].data or '').lower() == 'origin':
                    po_name = row.cells[1].data or ''
                    if isinstance(po_name, str):
                        po_name = po_name.strip().lower()
                    if not po_name:
                        raise osv.except_osv(_('Error'), _('Field "Origin" shouldn\'t be empty'))
                    break
            else:
                raise osv.except_osv(_('Error'), _('Header field "Origin" not found in the given XLS file'))
            incoming_id = self.get_available_incoming_from_po_name(cr, uid, po_name, context=context)

        elif filetype == 'xml':
            root = ET.fromstring(xmlstring)
            orig = root.findall('.//field[@name="origin"]')
            if orig:
                po_name = orig[0].text or ''
                po_name = po_name.strip().lower()
                if not po_name:
                    raise osv.except_osv(_('Error'), _('Field "Origin" shouldn\'t be empty'))
            else:
                raise osv.except_osv(_('Error'), _('No field with name "Origin" was found in the XML file'))
            incoming_id = self.get_available_incoming_from_po_name(cr, uid, po_name, context=context)

        return incoming_id


    def get_file_content(self, cr, uid, file_path, context=None):
        if context is None:
            context = {}
        res = ''
        with open(file_path) as fich:
            res = fich.read()
        return res


    def generate_simulation_screen_report(self, cr, uid, simu_id, context=None):
        '''
        generate a IN simulation screen report
        '''
        if context is None:
            context = {}

        # generate report:
        datas = {'ids': [simu_id]}
        rp_spool = report_spool()
        result = rp_spool.exp_report(cr.dbname, uid, 'in.simulation.screen.xls', [simu_id], datas, context=context)
        file_res = {'state': False}
        while not file_res.get('state'):
            file_res = rp_spool.exp_report_get(cr.dbname, uid, result)
            time.sleep(0.5)

        return file_res


    def get_processed_rejected_header(self, cr, uid, filetype, file_content, import_success, context=None):
        if context is None:
            context = {}
        processed, rejected = [], []

        context.update({'xml_is_string': True})
        if filetype == 'excel':
            values, nb_file_lines, file_parse_errors = self.pool.get('wizard.import.in.simulation.screen').get_values_from_excel(cr, uid, file_content, context=context)
        else:
            values, nb_file_lines, file_parse_errors = self.pool.get('wizard.import.in.simulation.screen').get_values_from_xml(cr, uid, file_content, context=context)
        context.pop('xml_is_string')

        tech_header = [x[1] for x in IN_LINES_COLUMNS]
        line_start = len(HEADER_COLUMNS) + 4
        for index in range(line_start, len(values)+1):
            if not isinstance(values[index], dict):
                continue
            elif not values[index].get('line_number'):
                continue
            line_data = [values[index].get(x) for x in tech_header]
            if all([x is None for x in line_data]):
                continue
            if import_success:
                processed.append( (index, line_data) )
            else:
                rejected.append( (index, line_data) )

        return processed, rejected, [x[0] for x in IN_LINES_COLUMNS]


    def xml_has_pack_info(self, cr, uid, file_content, context=None):
        '''
        if given XML has pack info filled return True
        '''
        if context is None:
            context = {}
        if not file_content:
            return False

        root = ET.fromstring(file_content)
        parcel_from = root.findall('.//field[@name="parcel_from"]')
        parcel_to = root.findall('.//field[@name="parcel_to"]')
        if parcel_from:
            parcel_from = parcel_from[0].text or ''
            parcel_from = parcel_from.strip()
        if parcel_to:
            parcel_to = parcel_to[0].text or ''
            parcel_to = parcel_to.strip()

        return parcel_from and parcel_to and True or False


    def auto_import_incoming_shipment(self, cr, uid, file_path, context=None):
        '''
        Method called by automated.imports feature
        '''
        if context is None:
            context = {}
        wf_service = netsvc.LocalService("workflow")

        import_success = False
        try:
            filetype = self.get_import_filetype(cr, uid, file_path, context=context)
            file_content = self.get_file_content(cr, uid, file_path, context=context)

            # get ID of the IN:
            in_id = self.get_incoming_id_from_file(cr, uid, file_path, context)

            # create stock.incoming.processor and its stock.move.in.processor:
            in_processor = self.pool.get('stock.incoming.processor').create(cr, uid, {'picking_id': in_id}, context=context)
            self.pool.get('stock.incoming.processor').create_lines(cr, uid, in_processor, context=context) # import all lines and set qty to zero
            if filetype == 'xml' and not self.xml_has_pack_info(cr, uid, file_content, context=context):
                self.pool.get('stock.incoming.processor').launch_simulation(cr, uid, in_processor, context=context)
            else:
                self.pool.get('stock.incoming.processor').launch_simulation_pack(cr, uid, in_processor, context=context)

            simu_id = context.get('simu_id')

            # create simulation screen to get the simulation report:
            self.pool.get('wizard.import.in.simulation.screen').write(cr, uid, [simu_id], {
                'filetype': filetype,
                'file_to_import': base64.b64encode(bytes(file_content, 'utf8')),
            }, context=context)

            context.update({'do_not_process_incoming': True, 'do_not_import_with_thread': True, 'simulation_bypass_missing_lot': True, 'auto_import_ok': True})
            self.pool.get('wizard.import.in.simulation.screen').launch_simulate(cr, uid, [simu_id], context=context)

            with_pack = self.pool.get('wizard.import.in.simulation.screen').read(cr, uid, simu_id, ['pack_found'], context=context)['pack_found']
            if with_pack:
                info_wiz = self.pool.get('wizard.import.in.simulation.screen').read(cr,uid, [simu_id], ['state', 'message'])[0]
                if info_wiz['state'] == 'error':
                    errors = []
                    if info_wiz['message']:
                        for error in info_wiz['message'].split("\n"):
                            if not error:
                                continue
                            errors.append(('', [], error))

                    return ([], errors, [])

            file_res = self.generate_simulation_screen_report(cr, uid, simu_id, context=context)
            self.pool.get('wizard.import.in.simulation.screen').launch_import(cr, uid, [simu_id], context=context)
            context.pop('do_not_process_incoming'); context.pop('do_not_import_with_thread'); context.pop('simulation_bypass_missing_lot'); context.pop('auto_import_ok')

            if context.get('new_picking') and context['new_picking'] != in_id:
                wf_service.trg_validate(uid, 'stock.picking', context.get('new_picking', in_id), 'button_confirm', cr)
            wf_service.trg_validate(uid, 'stock.picking', context.get('new_picking', in_id), 'updated', cr)

            # attach simulation report to new IN:
            self.pool.get('ir.attachment').create(cr, uid, {
                'name': 'simulation_screen_%s.xls' % time.strftime('%Y_%m_%d_%H_%M'),
                'datas_fname': 'simulation_screen_%s.xls' % time.strftime('%Y_%m_%d_%H_%M'),
                'description': 'IN simulation screen',
                'res_model': 'stock.picking',
                'res_id': context.get('new_picking', in_id),
                'datas': file_res.get('result'),
            })
            # attach import file to new IN (usefull to import & process auto PICK/PACK):
            fname = path.basename(file_path) if path.basename(file_path).startswith('SHPM_') else 'SHPM_%s' % path.basename(file_path)
            self.pool.get('ir.attachment').create(cr, uid, {
                'name': fname,
                'datas_fname': fname,
                'description': 'IN import file',
                'res_model': 'stock.picking',
                'res_id': context.get('new_picking', in_id),
                'datas': base64.b64encode(bytes(file_content, 'utf8')),
            })
            import_success = True

            self.create_update_ito(cr, uid, [context.get('new_picking', in_id)], context=context)
        except Exception as e:
            raise e


        return self.get_processed_rejected_header(cr, uid, filetype, file_content, import_success, context=context)



    def export_template_file(self, cr, uid, ids, context=None):
        '''
        Export the template file in Excel or Pure XML format
        '''
        if isinstance(ids, int):
            ids = [ids]

        pick = self.browse(cr, uid, ids[0], context=context)
        if not pick.filetype:
            raise osv.except_osv(_('Error'), _('You must select a file type'))

        report_name = pick.filetype == 'excel' and 'incoming.shipment.xls' or 'incoming.shipment.xml'

        datas = {'ids': ids}

        return {'type': 'ir.actions.report.xml',
                'report_name': report_name,
                'datas': datas,
                'context': context,
                }

    def wizard_import_pick_line(self, cr, uid, ids, context=None):
        '''
        Launches the wizard to import lines from a file
        '''
        # Objects
        wiz_obj = self.pool.get('wizard.import.pick.line')

        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        context.update({'active_id': ids[0]})

        picking = self.browse(cr, uid, ids[0], context=context)
        if picking.type == 'in':
            header_cols = columns_header_for_incoming_import
            cols = columns_for_incoming_import
        elif picking.type == 'out' and picking.subtype == 'standard':
            header_cols = columns_header_for_delivery_import
            cols = columns_for_delivery_import
        else:
            header_cols = columns_header_for_internal_import
            cols = columns_for_incoming_import

        columns_header = [(_(f[0]), f[1]) for f in header_cols]
        default_template = SpreadsheetCreator(_('Template of import'), columns_header, [])
        file = base64.b64encode(default_template.get_xml(default_filters=['decode.utf8']))
        export_id = wiz_obj.create(cr, uid, {'file': file,
                                             'filename_template': 'template.xls',
                                             'filename': 'Lines_Not_Imported.xls',
                                             'message': """%s %s""" % (_(GENERIC_MESSAGE), ', '.join([_(f) for f in cols])),
                                             'picking_id': ids[0],
                                             'state': 'draft',}, context=context)

        return {'type': 'ir.actions.act_window',
                'res_model': 'wizard.import.pick.line',
                'res_id': export_id,
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'crush',
                'context': context,
                }

    def export_ppl(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        if isinstance(ids,int):
            ids = [ids]

        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'pre.packing.excel.export',
            'datas': {'ids': ids},
            'context': context,
        }

    def wizard_update_ppl_to_create_ship(self, cr, uid, ids, context=None):
        '''
        Launches the wizard to update lines from a file
        '''
        # Objects
        wiz_obj = self.pool.get('wizard.import.ppl.to.create.ship')

        context = context is None and {} or context

        if isinstance(ids, int):
            ids = [ids]

        context.update({'active_id': ids[0]})

        # header_cols = ppl_columns_lines_headers_for_import
        cols = ppl_columns_lines_for_import

        # TODO: Create a specific template for this case (US-2269)
        # columns_header = [(_(f[0]), f[1]) for f in header_cols]
        # default_template = SpreadsheetCreator(_('Template of import'), columns_header, [])
        # file = base64.b64encode(default_template.get_xml(default_filters=['decode.utf8']))
        export_id = wiz_obj.create(cr, uid, {'file': False,
                                             'filename_template': 'template.xls',
                                             'filename': 'Lines_Not_Imported.xls',
                                             'message': """%s %s"""
                                                        % (_(PPL_IMPORT_FOR_UPDATE_MESSAGE), ', '.join([_(f) for f in cols])),
                                             'picking_id': ids[0],
                                             'state': 'draft',}, context=context)

        return {'type': 'ir.actions.act_window',
                'res_model': 'wizard.import.ppl.to.create.ship',
                'res_id': export_id,
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'crush',
                'context': context,
                }

    def check_lines_to_fix(self, cr, uid, ids, context=None):
        if isinstance(ids, int):
            ids = [ids]

        message = ''
        plural = ''

        for var in self.browse(cr, uid, ids, context=context):
            if var.move_lines:
                for var in var.move_lines:
                    if var.to_correct_ok:
                        line_num = var.line_number
                        if message:
                            message += ', '
                        message += str(line_num)
                        if len(message.split(',')) > 1:
                            plural = 's'
        if message:
            raise osv.except_osv(_('Warning !'), _('You need to correct the following line%s: %s') % (plural, message))
        return True

    def wizard_import_return_from_unit(self, cr, uid, ids, context=None):
        wiz_obj = self.pool.get('wizard.return.from.unit.import')
        return_reason_type_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves',
                                                                                    'reason_type_return_from_unit')[1]

        ftf = ['reason_type_id', 'ext_cu', 'purchase_id', 'move_lines']
        picking = self.browse(cr, uid, ids[0], fields_to_fetch=ftf, context=context)
        if picking.reason_type_id.id != return_reason_type_id:
            raise osv.except_osv(_('Error'), _('The reason type does not correspond to the expected “Return from Unit”, please check this'))
        if not picking.ext_cu:
            raise osv.except_osv(_('Error'), _('The header field “Ext. CU” must be filled for this import, please check this'))
        if picking.purchase_id:
            raise osv.except_osv(_('Error'), _('This type of import is only available for INs from scratch'))
        if picking.move_lines:
            raise osv.except_osv(_('Error'), _('Lines already exist for this IN, this import is not possible'))

        wiz_id = wiz_obj.create(cr, uid, {'picking_id': ids[0], 'state': 'draft'}, context=context)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'wizard.return.from.unit.import',
            'res_id': wiz_id,
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'same',
            'context': context,
        }

    def create_update_ito(self, cr, uid, ids, context=None):
        '''
        Create or update the Inbound Transport Object with the Available Updated IN as new line using the Ship Reference
        '''
        if context is None:
            context = {}

        ito_obj = self.pool.get('transport.order.in')
        partner_obj = self.pool.get('res.partner')

        for upd_in_id in ids:
            cr.execute('''
                select pick.details,
                    bool_or(is_kc),
                    bool_or(dangerous_goods = 'True'),
                    bool_or(cs_txt = 'X'),
                    sum(m.price_unit * m.product_qty / rate.rate),
                    sum(m.price_unit * m.product_qty),
                    count(distinct (m.price_currency_id)),
                    min(m.price_currency_id),
                    pick.partner_id,
                    pick.order_category,
                    pick.shipment_ref
                from stock_picking pick
                    left join stock_move m on m.picking_id = pick.id
                    left join product_product p on p.id = m.product_id
                    left join lateral (
                        select rate.rate, rate.name as fx_date
                        from res_currency_rate rate
                        where rate.name <= coalesce(pick.physical_reception_date, pick.min_date)
                            and rate.currency_id = m.price_currency_id
                        order by rate.name desc, id desc
                           limit 1
                        ) rate
                       on true
                where
                   pick.id = %s
                group by pick.id
            ''', (upd_in_id,))
            x = cr.fetchone()
            in_partner_id = x[8]
            in_order_category = x[9]
            in_shipment_ref = x[10]
            ito_line_data = {
                'description': x[0],
                'kc': x[1],
                'dg': x[2],
                'cs': x[3],
            }
            if x[6] and x[6] > 1:
                ito_line_data['amount'] = x[4]
                ito_line_data['currency_id'] = self.pool.get('res.users').get_company_currency_id(cr, uid)
            else:
                ito_line_data['amount'] = x[5]
                ito_line_data['currency_id'] = x[7]

            cr.execute('''
                select sum(parcel_to - parcel_from + 1),
                    sum(total_weight * (parcel_to - parcel_from + 1)),
                    sum(total_height * total_length * total_width * (parcel_to - parcel_from + 1))
                from wizard_import_in_pack_simulation_screen pa
                where pa.id in (select m.pack_info_id from stock_move m where m.picking_id = %s)
               ''', (upd_in_id,))
            x = cr.fetchone()
            if x[0]:
                ito_line_data.update({
                    'parcels_nb': x[0],
                    'weight': x[1] and round(x[1], 2) or 0,
                    'volume': x[2] and round(x[2] / 1000, 2) or 0
                })

            if in_partner_id:
                ito_ids = ito_obj.search(cr, uid, [('state', '=', 'planned'), ('supplier_partner_id', '=', in_partner_id),
                              ('ship_ref', '=', in_shipment_ref)], context=context)
                ito_categ = in_order_category == 'medical' and '' or in_order_category == 'log' and '' or 'mixed'
                if not ito_ids:
                    company_partner_id = self.pool.get('res.users').get_current_company_partner_id(cr, uid)[0]
                    company_address = partner_obj.address_get(cr, uid, company_partner_id, [])
                    supplier_address = partner_obj.address_get(cr, uid, in_partner_id, [])
                    ito_data = {
                        'supplier_partner_id': in_partner_id,
                        'ship_ref': in_shipment_ref,
                        'zone_type': company_address and company_address.country_id and supplier_address and supplier_address.country_id and
                             company_address.country_id.id == supplier_address.country_id.id and 'regional' or 'int',
                        'cargo_category': ito_categ,
                    }
                    ito_id = ito_obj.create(cr, uid, ito_data, context=context)
                else:
                    ito_id = ito_ids[0]
                    if ito_obj.read(cr, uid, ito_id, ['cargo_category'], context=context)['cargo_category'] != ito_categ:
                        ito_obj.write(cr, uid, ito_id, {'cargo_category': 'mixed'}, context=context)

                ito_line_data.update({'transport_id': ito_id, 'incoming_id': upd_in_id})
                self.pool.get('transport.order.in.line').create(cr, uid, ito_line_data, context=context)

        return True


stock_picking()
