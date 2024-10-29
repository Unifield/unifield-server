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
import time
import datetime
import tempfile
import os
from tools.translate import _
import base64
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetCreator
from msf_doc_import.wizard import PO_COLUMNS_HEADER_FOR_IMPORT as columns_header_for_po_line_import
from msf_doc_import.wizard import PO_LINE_COLUMNS_FOR_IMPORT as columns_for_po_line_import
from msf_doc_import.wizard import RFQ_COLUMNS_HEADER_FOR_IMPORT
from msf_doc_import.wizard import RFQ_LINE_COLUMNS_FOR_IMPORT
from msf_doc_import import GENERIC_MESSAGE
from spreadsheet_xml.spreadsheet_xml import SpreadsheetXML
import xml.etree.ElementTree as ET
from service.web_services import report_spool

class purchase_order_manual_export(osv.osv_memory):
    _name = 'purchase.order.manual.export'

    _columns = {
        'purchase_id': fields.many2one('purchase.order', 'Purchase Order'),

    }

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        result = {'fields': {}, 'model': 'purchase.order.manual.export', 'type': 'form'}

        msg = _('Manually run export of PO')

        if self.pool.get('purchase.order').search_exist(cr, uid, [('id', '=', context.get('purchase_order')), ('auto_exported_ok', '=', True)], context=context):
            msg = _('The PO was already exported, do you want to export it again ?')
        result['arch'] = '''<form string="%(title)s">
            <separator coslpan="4" string="%(msg)s" />
            <button special="cancel" string="%(cancel)s" icon="gtk-cancel" colspan="2"/>
            <button name="export_po" string="%(ok)s" icon="gtk-ok" colspan="2" type="object"/>
            </form>''' % {
            'title': msg,
            'msg': msg,
            'cancel': _('Cancel'),
            'ok': _('OK'),
        }
        return result

    def export_po(self, cr, uid, ids, context=None):
        wiz = self.browse(cr, uid, ids[0], context)
        auto_job_ids = self.pool.get('automated.export').search(cr, uid, [('function_id.method_to_call', '=', 'auto_export_validated_purchase_order'), ('active', '=', True), ('partner_id', '=', wiz.purchase_id.partner_id.id)], context=context)
        if not auto_job_ids:
            raise osv.except_osv(_('Warning'), _('The job to export PO is not active.'))

        auto_job = self.pool.get('automated.export').browse(cr, uid, auto_job_ids[0], context=context)


        processed, rejected, trash = self.pool.get('purchase.order').auto_export_validated_purchase_order(cr, uid, auto_job, [wiz.purchase_id.id], context=context)
        if not rejected:
            self.log(cr, uid, wiz.purchase_id.id, _('PO %s successfully exported') % wiz.purchase_id.name)
        else:
            self.log(cr, uid, wiz.purchase_id.id, _('PO %s %d lines rejected') %  (wiz.purchase_id.name, len(rejected)))

        return {'type': 'ir.actions.act_window_close'}

purchase_order_manual_export()

class purchase_order(osv.osv):
    _inherit = 'purchase.order'


    def hook_rfq_sent_check_lines(self, cr, uid, ids, context=None):
        '''
        Please copy this to your module's method also.
        This hook belongs to the rfq_sent method from tender_flow>tender_flow.py
        - check lines after import
        '''
        res = super(purchase_order, self).hook_rfq_sent_check_lines(cr, uid, ids, context)
        if self.check_lines_to_fix(cr, uid, ids, context):
            res = False
        return res

    def _get_import_progress(self, cr, uid, ids, field_name, args, context=None):
        """
        Check if there are import wizard associated to POs
        """
        wiz_obj = self.pool.get('wizard.import.po.line')

        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        res = {}

        for po_id in ids:
            res[po_id] = wiz_obj.search(cr, 1, [
                ('po_id', '=', po_id),
                ('state', '=', 'in_progress'),
            ], limit=1, context=context) and True or False

        return res


    def _can_be_auto_exported(self, cr, uid, ids, field_name, args, context=None):
        ret = {}
        for id in ids:
            ret[id] = False

        if not ids:
            return {}

        cr.execute('''
            select o.id
                from
                    purchase_order o, automated_export exp, automated_export_function fnct
                where
                    o.id in %s and
                    o.partner_type = 'esc' and
                    o.state in ('validated', 'validated_p') and
                    o.partner_id = exp.partner_id and
                    exp.active = 't' and
                    exp.function_id = fnct.id and
                    fnct.method_to_call = 'auto_export_validated_purchase_order'
        ''', (tuple(ids), ))

        for x in cr.fetchall():
            ret[x[0]] = True

        return ret

    _columns = {
        'import_in_progress': fields.function(
            _get_import_progress,
            method=True,
            type='boolean',
            string='Import in progress',
            store=False,
        ),
        'import_filenames': fields.one2many('purchase.order.simu.import.file', 'order_id', string='Imported files', readonly=True),
        'auto_exported_ok': fields.boolean('PO exported to ESC'),
        'can_be_auto_exported': fields.function(_can_be_auto_exported, method=True, type='boolean', string='Can be auto exported ?'),
    }

    _defaults = {
        'import_in_progress': lambda *a: False,
    }

    def auto_export_manual(self, cr, uid, ids, context=None):
        wiz_id = self.pool.get('purchase.order.manual.export').create(cr, uid, {'purchase_id': ids[0]}, context=context)
        ctx = context.copy()
        ctx['purchase_order'] = ids[0]
        return {
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': wiz_id,
            'context': ctx,
            'type': 'ir.actions.act_window',
            'target': 'new',
            'res_model': 'purchase.order.manual.export',
        }

    def get_file_content(self, cr, uid, file_path, context=None):
        if context is None:
            context = {}
        res = ''
        with open(file_path) as fich:
            res = fich.read()
        return res


    def get_po_id_from_file(self, cr, uid, file_path, context=None):
        if context is None:
            context = {}

        filetype = self.pool.get('stock.picking').get_import_filetype(cr, uid, file_path, context)
        xmlstring = self.get_file_content(cr, uid, file_path, context=context)

        po_id = False
        po_name = False
        if filetype == 'excel':
            file_obj = SpreadsheetXML(xmlstring=xmlstring)
            po_name = False
            for index, row in enumerate(file_obj.getRows()):
                if row.cells[0].data == 'Order Reference*':
                    po_name = row.cells[1].data or ''
                    if isinstance(po_name, str):
                        po_name = po_name.strip()
                    if not po_name:
                        raise osv.except_osv(_('Error'), _('Field "Order Reference*" shouldn\'t be empty'))
                    break
            else:
                raise osv.except_osv(_('Error'), _('Header field "Order Reference*" not found in the given XLS file'))

        elif filetype == 'xml':
            root = ET.fromstring(xmlstring)
            orig = root.findall('.//record[@model="purchase.order"]/field[@name="name"]')
            if orig:
                po_name = orig[0].text or ''
                po_name = po_name.strip()
                if not po_name:
                    raise osv.except_osv(_('Error'), _('Field "Origin" shouldn\'t be empty'))
            else:
                raise osv.except_osv(_('Error'), _('No field with name "Origin" was found in the XML file'))

        if not po_name:
            raise osv.except_osv(_('Error'), _('No PO name found in the given import file'))

        po_id = self.search(cr, uid, [('name', '=', po_name), ('state', 'in', ['validated', 'validated_p', 'confirmed', 'confirmed_p'])], context=context)
        if not po_id:
            raise osv.except_osv(_('Error'), _('No available PO found with the name %s') % po_name)

        return po_id[0]


    def create_simu_screen_wizard(self, cr, uid, ids, file_content, filetype, file_path, context=None):
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        simu_id = self.pool.get('wizard.import.po.simulation.screen').create(cr, uid, {
            'order_id': ids[0],
            'file_to_import': base64.b64encode(bytes(file_content, 'utf8')),
            'filetype': filetype,
            'filename': os.path.basename(file_path),
        }, context=context)
        for line in self.pool.get('purchase.order').browse(cr, uid, ids[0], context=context).order_line:
            self.pool.get('wizard.import.po.simulation.screen.line').create(cr, uid, {
                'po_line_id': line.id,
                'in_line_number': line.line_number,
                'in_ext_ref': line.external_ref,
                'simu_id': simu_id,
            }, context=context)

        return simu_id


    def generate_simulation_screen_report(self, cr, uid, simu_id, context=None):
        '''
        generate a IN simulation screen report
        '''
        if context is None:
            context = {}

        # generate report:
        datas = {'ids': [simu_id]}
        rp_spool = report_spool()
        result = rp_spool.exp_report(cr.dbname, uid, 'po.simulation.screen.xls', [simu_id], datas, context=context)
        file_res = {'state': False}
        while not file_res.get('state'):
            file_res = rp_spool.exp_report_get(cr.dbname, uid, result)
            time.sleep(0.5)

        return file_res


    def get_processed_rejected_header(self, cr, uid, filetype, file_content, import_success, context=None):
        if context is None:
            context = {}

        processed, rejected, header = [], [], []

        if filetype == 'excel':
            values = self.pool.get('wizard.import.po.simulation.screen').get_values_from_excel(cr, uid, base64.b64encode(bytes(file_content,'utf8')), context=context)
            header = values.get(23)
            for key in sorted([k for k in list(values.keys()) if k > 23]):
                if import_success:
                    processed.append( (key, values[key]) )
                else:
                    rejected.append( (key, values[key]) )
        else:
            values = self.pool.get('wizard.import.po.simulation.screen').get_values_from_xml(cr, uid, base64.b64encode(bytes(file_content, 'utf8')), context=context)
            header = [x.replace('_', ' ').title() for x in values.get(23)]
            for key in sorted([k for k in list(values.keys()) if k > 23]):
                if import_success:
                    processed.append( (key, values[key]) )
                else:
                    rejected.append( (key, values[key]) )

        return processed, rejected, header


    def auto_import_purchase_order(self, cr, uid, file_path, context=None):
        '''
        method called by obj automated.import
        '''
        if context is None:
            context = {}

        import_success = False
        # Reset part of the context updated in the PO import
        context.update({'line_ids_to_confirm': [], 'job_comment': []})
        simu_obj = self.pool.get('wizard.import.po.simulation.screen')
        try:
            # get filetype
            filetype = self.pool.get('stock.picking').get_import_filetype(cr, uid, file_path, context=context)
            file_content = self.get_file_content(cr, uid, file_path, context=context)

            # get po_id from file
            po_id = self.get_po_id_from_file(cr, uid, file_path, context=context)
            context['po_id'] = po_id
            po = self.read(cr, uid, po_id, ['name', 'locked_by_signature'], context=context)
            if po['locked_by_signature']:
                raise osv.except_osv(_('Error'), _('%s: The automated import can not be used on a locked PO') % (po['name']))
            # create wizard.import.po.simulation.screen
            simu_id = self.create_simu_screen_wizard(cr, uid, po_id, file_content, filetype, file_path, context=context)
            # launch simulate
            simu_obj.launch_simulate(cr, uid, simu_id, context=context, thread=False)

            # get simulation report
            file_res = self.generate_simulation_screen_report(cr, uid, simu_id, context=context)
            simu_result = simu_obj.read(cr, uid, simu_id, ['state', 'message'], context=context)
            if simu_result['state'] == 'error':
                raise osv.except_osv(_('Error'), simu_result['message'])

            # import lines
            simu_obj.launch_import(cr, uid, simu_id, context=context, thread=False)
            # attach simulation report
            self.pool.get('ir.attachment').create(cr, uid, {
                'name': 'simulation_screen_%s.xls' % time.strftime('%Y_%m_%d_%H_%M'),
                'datas_fname': 'simulation_screen_%s.xls' % time.strftime('%Y_%m_%d_%H_%M'),
                'description': 'PO simulation screen',
                'res_model': 'purchase.order',
                'res_id': po_id,
                'datas': file_res.get('result'),
            })
            import_success = True
        except Exception as e:
            raise e

        return self.get_processed_rejected_header(cr, uid, filetype, file_content, import_success, context=context)


    def auto_import_confirmed_purchase_order(self, cr, uid, file_path, context=None):
        '''
        Method called by obj automated.export
        '''
        if context is None:
            context = {}

        context.update({'auto_import_confirm_pol': True})
        # Reset part of the context updated in the PO import
        context.update({'line_ids_to_confirm': [], 'job_comment': []})
        res = self.auto_import_purchase_order(cr, uid, file_path, context=context)
        context['rejected_confirmation'] = 0

        pol_obj = self.pool.get('purchase.order.line')
        if context.get('po_id'):
            pol_ids_to_confirm = pol_obj.search(cr, uid, [('order_id', '=', context['po_id']), ('id', 'in', context['line_ids_to_confirm']), ('state', 'not in', ['confirmed', 'done', 'cancel', 'cancel_r'])], context=context)
            nb_pol_confirmed = 0
            nb_pol_total = 0
            po_name = ''
            for pol in pol_obj.browse(cr, uid, pol_ids_to_confirm, fields_to_fetch=['order_id', 'line_number'], context=context):
                nb_pol_total += 1
                try:
                    self.pool.get('purchase.order.line').button_confirmed_no_mml_check(cr, uid, [pol.id], context=context)
                    cr.commit()
                    nb_pol_confirmed += 1
                    po_name = pol.order_id.name
                except:
                    context['rejected_confirmation'] += 1
                    cr.rollback()
                    self.infolog(cr, uid, _('%s :: not able to confirm line #%s') % (pol.order_id.name, pol.line_number))
                    job_comment = context.get('job_comment', [])
                    job_comment.append({
                        'res_model': 'purchase.order',
                        'res_id': pol.order_id.id,
                        'msg': _('%s line #%s cannot be confirmed') % (pol.order_id.name, pol.line_number),
                    })
                    context['job_comment'] = job_comment

            if nb_pol_confirmed:
                self.log(cr, uid, context['po_id'], _('%s: %s out of %s lines have been confirmed') % (po_name, nb_pol_confirmed, nb_pol_total))

        return res


    def auto_export_validated_purchase_order(self, cr, uid, export_wiz, po_ids=False, context=None):
        '''
        Method called by obj automated.export
        '''
        if context is None:
            context = {}

        # any change in domain must also be changed in _can_be_auto_exported
        if not po_ids:
            po_ids = self.search(cr, uid, [
                ('partner_type', '=', 'esc'),
                ('state', 'in', ['validated', 'validated_p']),
                ('auto_exported_ok', '=', False),
                ('partner_id', '=', export_wiz.partner_id.id),
            ], context=context)

        if not po_ids:
            msg = _('No PO to export !')
            self.infolog(cr, uid, msg)
            context.update({'po_not_found': True})
            return [], [], ['PO id', 'PO name'], []

        processed, rejected, filenames = [], [], []
        cr.execute('select id from purchase_order where id in %s for update skip locked', (tuple(po_ids),))
        index = 0
        for po_id, in cr.fetchall():
            # generate report:
            report_name = 'validated.purchase.order_xls' if export_wiz.export_format == 'excel' else 'validated.purchase.order_xml'
            datas = {'ids': [po_id]}
            rp_spool = report_spool()
            result = rp_spool.exp_report(cr.dbname, uid, report_name, [po_id], datas, context=context)
            file_res = {'state': False}
            while not file_res.get('state'):
                file_res = rp_spool.exp_report_get(cr.dbname, uid, result)
                time.sleep(0.5)

            po_name = self.read(cr, uid, po_id, ['name'], context=context)['name']
            filename = 'POV_%s_%s.%s' % (
                po_name.replace('/', '_'),
                datetime.datetime.now().strftime('%Y_%m_%d'),
                'xls' if export_wiz.export_format == 'excel' else 'xml',
            )
            path_to_file = os.path.join(export_wiz.dest_path, filename)
            filenames.append(filename)
            if export_wiz.ftp_ok and export_wiz.ftp_dest_ok and export_wiz.ftp_protocol == 'ftp':
                ftp_connec = None
                context.update({'no_raise_if_ok': True})
                ftp_connec = self.pool.get('automated.export').ftp_test_connection(cr, uid, export_wiz.id, context=context)
                context.pop('no_raise_if_ok')

                # write export on FTP server
                tmp_file = tempfile.NamedTemporaryFile(mode='w', delete=False)
                tmp_file.write(base64.b64decode(file_res['result']))
                tmp_file.close()
                rep = ''
                with open(tmp_file.name, 'rb') as fich:
                    rep = ftp_connec.storbinary('STOR %s' % path_to_file, fich)
                os.remove(tmp_file.name)
                if not rep.startswith('2'):
                    raise osv.except_osv(_('Error'), ('Unable to move local file to destination location on FTP server'))
            elif export_wiz.ftp_ok and export_wiz.ftp_dest_ok and export_wiz.ftp_protocol == 'sftp':
                sftp = None
                context.update({'no_raise_if_ok': True})
                sftp = self.pool.get('automated.export').sftp_test_connection(cr, uid, export_wiz.id, context=context)
                context.pop('no_raise_if_ok')

                # create tmp file
                tmp_file = tempfile.NamedTemporaryFile(mode='w', delete=False)
                tmp_file.write(str(base64.b64decode(file_res['result']), 'utf8'))
                tmpname = tmp_file.name
                tmp_file.close()

                # transfer tmp file on SFTP server
                try:
                    with sftp.cd(export_wiz.dest_path):
                        sftp.put(tmpname, filename, preserve_mtime=True)
                except:
                    raise osv.except_osv(_('Error'), _('Unable to write on SFTP server at location %s') % export_wiz.dest_path)

                # now we can remove tmp file
                os.remove(tmpname)
            else:
                # write export in local file
                with open(path_to_file, 'wb') as fich:
                    fich.write(base64.b64decode(bytes(file_res['result'], 'utf8')))

            self.write(cr, uid, [po_id], {'auto_exported_ok': True}, context=context)
            processed.append((index, [po_id, po_name]))
            self.infolog(cr, uid, _('%s successfully exported') % po_name)
            index += 1

        return processed, rejected, ['PO id', 'PO name'], filenames

    def copy(self, cr, uid, id, defaults=None, context=None):
        '''
        Remove the import_in_progress flag
        '''
        if not defaults:
            defaults = {}

        if 'import_in_progress' not in defaults:
            defaults.update({'import_in_progress': False})
        if 'auto_exported_ok' not in defaults:
            defaults.update({'auto_exported_ok': False})
        if 'import_filenames' not in defaults:
            defaults['import_filenames'] = False

        return super(purchase_order, self).copy(cr, uid, id, defaults, context=context)

    def wizard_import_file(self, cr, uid, ids, context=None):
        '''
        Launches the wizard to import lines from a file
        '''
        export_obj = self.pool.get('wizard.import.po.simulation.screen')

        if context is None:
            context = {}

        context.update({'active_id': ids[0]})
        export_ids = export_obj.search(cr, uid, [('order_id', '=', ids[0])], context=context)
        export_obj.unlink(cr, uid, export_ids, context=context)
        export_id = export_obj.create(cr, uid, {
            'order_id': ids[0]}, context)

        return {'type': 'ir.actions.act_window',
                'res_model': 'wizard.import.po.simulation.screen',
                'res_id': export_id,
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'same',
                'context': context,
                }

    def export_po_integration(self, cr, uid, ids, context=None):
        '''
        Call the wizard to choose the export file format
        '''
        wiz_obj = self.pool.get('wizard.export.po.validated')

        if isinstance(ids, int):
            ids = [ids]

        wiz_id = wiz_obj.create(cr, uid, {'order_id': ids[0]}, context=context)

        return {'type': 'ir.actions.act_window',
                'res_model': wiz_obj._name,
                'res_id': wiz_id,
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'context': context}

    def export_get_file_name(self, cr, uid, ids, prefix='PO', context=None):
        """
        UFTP-56: get export file name
        :param prefix: prefix of the file (POV for PO Validated, etc)
        :return POV_14_OC_MW101_PO00060_YYYY_MM_DD.xls or POV_14_OC_MW101_PO00060_YYYY_MM_DD.xml
        """
        if isinstance(ids, int):
            ids = [ids]
        if len(ids) != 1:
            return False
        po_r = self.read(cr, uid, ids[0], ['name'], context=context)
        if not po_r or not po_r['name']:
            return False
        dt_now = datetime.datetime.now()
        po_name = "%s_%s_%d_%02d_%02d" % (prefix,
                                          po_r['name'].replace('/', '_'),
                                          dt_now.year, dt_now.month, dt_now.day)
        return po_name

    def export_xml_po_integration(self, cr, uid, ids, context=None):
        '''
        Call the Pure XML report of validated PO
        '''
        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        datas = {
            'ids': ids,
            'need_ad': context.get('need_ad', True),
        }
        file_name = self.export_get_file_name(cr, uid, ids, prefix='POV',
                                              context=context)
        if file_name:
            datas['target_filename'] = file_name
        report_name = 'validated.purchase.order_xml'

        return {
            'type': 'ir.actions.report.xml',
            'report_name': report_name,
            'datas': datas,
            'context': context,
        }

    def export_excel_po_integration(self, cr, uid, ids, context=None):
        '''
        Call the Excel report of validated PO
        '''
        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        datas = {
            'ids': ids,
            'need_ad': context.get('need_ad', True),
        }
        file_name = self.export_get_file_name(cr, uid, ids, prefix='POV',
                                              context=context)
        if file_name:
            datas['target_filename'] = file_name
        report_name = 'validated.purchase.order_xls'

        return {
            'type': 'ir.actions.report.xml',
            'report_name': report_name,
            'datas': datas,
            'context': context,
        }

    def wizard_import_po_line(self, cr, uid, ids, context=None):
        '''
        Launches the wizard to import lines from a file
        '''
        if context is None:
            context = {}
        if isinstance(ids, int):
            ids = [ids]
        context.update({'active_id': ids[0]})

        # Check if we are in the case of update of sent RfQ
        po = self.browse(cr, uid, [ids[0]], context=context)[0]
        columns = columns_for_po_line_import
        columns_header = [(_(f[0]), f[1]) for f in columns_header_for_po_line_import]

        if po.rfq_ok:
            columns = RFQ_LINE_COLUMNS_FOR_IMPORT
            columns_header = [(_(f[0]), f[1]) for f in RFQ_COLUMNS_HEADER_FOR_IMPORT]

        # if PO is not a RfQ, then we doesn't take in account the first column (Line Number):
        if not po.rfq_ok:
            columns = columns_for_po_line_import[1:]
            columns_header = columns_header[1:]

        default_template = SpreadsheetCreator('Template of import', columns_header, [])
        file = base64.b64encode(default_template.get_xml(default_filters=['decode.utf8']))
        export_id = self.pool.get('wizard.import.po.line').create(cr, uid, {'file': file,
                                                                            'filename_template': 'template.xls',
                                                                            'filename': 'Lines_Not_Imported.xls',
                                                                            'po_id': ids[0],
                                                                            'message': """%s %s""" % (_(GENERIC_MESSAGE), ', '.join([_(f) for f in columns]),),
                                                                            'state': 'draft', },
                                                                  context)
        return {'type': 'ir.actions.act_window',
                'res_model': 'wizard.import.po.line',
                'res_id': export_id,
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'same',
                'context': context,
                }

    def wizard_import_ad(self, cr, uid, ids, context=None):
        if isinstance(ids, int):
            ids = [ids]
        if not self.search_exists(cr, uid, [('id', 'in', ids), ('state', '=', 'draft')], context=context):
            raise osv.except_osv(_('Warning !'), _('The PO must be in Draft state.'))
        if not self.pool.get('purchase.order.line').search_exists(cr, uid, [('order_id', 'in', ids), ('state', '=', 'draft')], context=context):
            raise osv.except_osv(_('Warning !'), _('The PO has no draft line.'))

        export_id = self.pool.get('wizard.import.ad.line').create(cr, uid, {'purchase_id': ids[0], 'state': 'draft'}, context=context)
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'wizard.import.ad.line',
            'res_id': export_id,
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'context': context,
        }

    def check_lines_to_fix(self, cr, uid, ids, context=None):
        """
        Check both the lines that need to be corrected and also that the supplier or the address is not 'To be defined'
        """
        if isinstance(ids, int):
            ids = [ids]
        message = ''
        plural = ''

        for var in self.browse(cr, uid, ids, context=context):
            # we check the lines that need to be fixed
            if var.order_line:
                for var in var.order_line:
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

    def check_condition(self, cr, uid, ids, context=None):
        if isinstance(ids, int):
            ids = [ids]
        for var in self.browse(cr, uid, ids, context=context):
            if not var.from_sync and var.partner_type not in ('external', 'esc'):
                raise osv.except_osv(_('Warning !'), _("""You can\'t cancel the PO because it may have already been synchronized,
                the cancellation should then come from the supplier instance (and synchronize down to the requestor instance)."""))
        return True

purchase_order()


class purchase_order_line(osv.osv):
    '''
    override of purchase_order_line class
    '''
    _inherit = 'purchase.order.line'
    _description = 'Purchase Order Line'


    def _get_inactive_product(self, cr, uid, ids, field_name, args, context=None):
        '''
        Fill the error message if the product of the line is inactive
        '''
        res = {}
        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = {'inactive_product': False,
                            'inactive_error': ''}
            if line.text_error:
                res[line.id] = {'inactive_error': line.comment}
            if line.order_id and line.order_id.state not in ('cancel', 'done') and line.product_id and not line.product_id.active:
                res[line.id] = {'inactive_product': True,
                                'inactive_error': _('The product in line is inactive !')}

        return res

    _columns = {
        'to_correct_ok': fields.boolean('To correct'),
        'show_msg_ok': fields.boolean('Info on importation of lines'),
        'text_error': fields.text('Errors when trying to import file'),
        'no_prod_nr_error': fields.text(string="Error when a line has been created by a NR because the product wasn't found"),
        'inactive_product': fields.function(_get_inactive_product, method=True, type='boolean', string='Product is inactive', store=False, multi='inactive'),
        'inactive_error': fields.function(_get_inactive_product, method=True, type='char', string='Comment', store=False, multi='inactive'),
    }

    _defaults = {
        'no_prod_nr_error': '',
        'inactive_product': False,
        'inactive_error': lambda *a: '',
    }

    def _check_active_product(self, cr, uid, ids, context=None):
        '''
        Check if the Purchase order line has an inactive product
        '''

        if not ids:
            return True
        cr.execute('''select pol.id from
            purchase_order_line pol, product_product p
            where
                pol.product_id = p.id and
                pol.state not in ('draft', 'cancel', 'cancel_r', 'done') and
                p.active = 'f' and
                pol.id in %s
        ''', (tuple(ids),))
        inactive_lines = cr.rowcount
        if inactive_lines:
            if inactive_lines == 1:
                line_id = cr.fetchone()[0]
                line = self.browse(cr, uid, line_id, fields_to_fetch=['product_id'], context=context)
                raise osv.except_osv(_('Error'), _('%s has been inactivated. Please correct the line containing the inactive product.') % (line.product_id.default_code, ))

            plural = _('Some products have')
            l_plural = _('lines')
            raise osv.except_osv(_('Error'), _('%s been inactivated. If you want to validate this line you have to remove/correct the line containing the inactive product (see red %s of the document)') % (plural, l_plural))
        return True

    _constraints = [
        (_check_active_product, "You cannot validate this purchase order line because it has an inactive product", ['id', 'state'])
    ]

    def check_line_consistency(self, cr, uid, ids, *args, **kwargs):
        """
        After having taken the value in the to_write variable we are going to check them.
        This function routes the value to check in dedicated methods (one for checking UoM, an other for Price Unit...).
        """
        context = kwargs['context']
        if context is None:
            context = {}
        obj_data = self.pool.get('ir.model.data')
        to_write = kwargs['to_write']
        order_id = to_write.get('order_id', False)
        if order_id:
            text_error = to_write['text_error']
            price_unit_defined = to_write['price_unit_defined']
            po_obj = self.pool.get('purchase.order')
            po = po_obj.browse(cr, uid, order_id, context=context)
            # on_change functions to call for updating values
            pricelist = po.pricelist_id.id or False
            partner_id = po.partner_id.id or False
            date_order = po.date_order or False
            fiscal_position = po.fiscal_position or False
            state = po.state or False
            product = to_write.get('product_id', False)
            if product:
                qty = to_write.get('product_qty')
                price_unit = to_write.get('price_unit')
                uom = to_write.get('product_uom')
                if product and qty and not price_unit_defined:
                    try:
                        res = self.product_id_on_change(cr, uid, False, pricelist, product, qty, uom,
                                                        partner_id, date_order, fiscal_position, date_planned=False,
                                                        name=False, price_unit=price_unit, notes=False, state=state, old_price_unit=False,
                                                        nomen_manda_0=False, comment=False, context=context)
                        if not context.get('po_integration'):
                            price_unit = res.get('value', {}).get('price_unit', False)
                            text_error += _('\n We use the price mechanism to compute the Price Unit.')
                        uom = res.get('value', {}).get('product_uom', False)
                        warning_msg = res.get('warning', {}).get('message', '')
                        text_error += '\n %s' % warning_msg
                    except osv.except_osv as osv_error:
                        if not context.get('po_integration'):
                            osv_value = osv_error.value
                            osv_name = osv_error.name
                            text_error += '%s. %s\n' % (osv_value, osv_name)
                    to_write.update({'price_unit': price_unit, 'product_uom': uom, 'text_error': text_error})
                if uom:
                    self.check_data_for_uom(cr, uid, False, to_write=to_write, context=context)
                else:
                    if not context.get('po_integration'):
                        uom = obj_data.get_object_reference(cr, uid, 'msf_doc_import', 'uom_tbd')[1]
                        text_error += _('\n It wasn\'t possible to update the UoM with the product\'s one because the former wasn\'t either defined.')
                        to_write.update({'product_uom': uom, 'text_error': text_error})

                # Check product line restrictions
                if product and po.partner_id:
                    self.pool.get('product.product')._get_restriction_error(cr, uid, [product], {'partner_id': po.partner_id.id}, context=dict(context, noraise=False))

        return to_write

    def check_data_for_uom(self, cr, uid, ids, *args, **kwargs):
        context = kwargs['context']
        if context is None:
            context = {}
        obj_data = self.pool.get('ir.model.data')
        # we take the values that we are going to write in PO line in "to_write"
        to_write = kwargs['to_write']
        text_error = to_write['text_error']
        product_id = to_write['product_id']
        uom_id = to_write['product_uom']
        if uom_id and product_id:
            if not self.pool.get('uom.tools').check_uom(cr, uid, product_id, uom_id, context):
                text_error += _("""\n You have to select a product UOM in the same category than the UOM of the product.""")
                return to_write.update({'text_error': text_error,
                                        'to_correct_ok': True})
        elif (not uom_id or uom_id == obj_data.get_object_reference(cr, uid, 'msf_doc_import', 'uom_tbd')[1]) and product_id:
            # we take the default uom of the product
            product = self.pool.get('product.product').browse(cr, uid, product_id)
            product_uom = product.uom_id.id
            return to_write.update({'product_uom': product_uom})
        elif not uom_id or uom_id == obj_data.get_object_reference(cr, uid, 'msf_doc_import', 'uom_tbd')[1]:
            # this is inspired by the on_change in purchase>purchase.py: product_uom_change
            text_error += _("\n The UoM was not defined so we set the price unit to 0.0.")
            return to_write.update({'text_error': text_error,
                                    'to_correct_ok': True,
                                    'price_unit': 0.0, })

    def write(self, cr, uid, ids, vals, context=None):
        if not ids:
            return True
        if isinstance(ids, int):
            ids = [ids]
        if context is None:
            context = {}
        obj_data = self.pool.get('ir.model.data')
        tbd_uom = obj_data.get_object_reference(cr, uid, 'msf_doc_import', 'uom_tbd')[1]
        message = ''
        if not context.get('import_in_progress') and not context.get('button'):
            if vals.get('product_uom') or vals.get('nomen_manda_0') or vals.get('nomen_manda_1') or vals.get('nomen_manda_2'):
                if vals.get('product_uom'):
                    if vals.get('product_uom') == tbd_uom:
                        message += _('You have to define a valid UOM, i.e. not "To be defined".')
                if vals.get('nomen_manda_0'):
                    if vals.get('nomen_manda_0') == obj_data.get_object_reference(cr, uid, 'msf_doc_import', 'nomen_tbd0')[1]:
                        message += _('You have to define a valid Main Type (in tab "Nomenclature Selection"), i.e. not "To be defined".')
                if vals.get('nomen_manda_1'):
                    if vals.get('nomen_manda_1') == obj_data.get_object_reference(cr, uid, 'msf_doc_import', 'nomen_tbd1')[1]:
                        message += _('You have to define a valid Group (in tab "Nomenclature Selection"), i.e. not "To be defined".')
                if vals.get('nomen_manda_2'):
                    if vals.get('nomen_manda_2') == obj_data.get_object_reference(cr, uid, 'msf_doc_import', 'nomen_tbd2')[1]:
                        message += _('You have to define a valid Family (in tab "Nomenclature Selection"), i.e. not "To be defined".')
                # the 3rd level is not mandatory
                if message:
                    raise osv.except_osv(_('Warning !'), _(message))
                else:
                    vals['show_msg_ok'] = False
                    vals['to_correct_ok'] = False
                    vals['text_error'] = False

        return super(purchase_order_line, self).write(cr, uid, ids, vals, context=context)

purchase_order_line()


class wizard_export_po_validated(osv.osv_memory):
    _name = 'wizard.export.po.validated'

    _columns = {
        'order_id': fields.many2one('purchase.order', string='Purchase Order', required=True),
        'need_ad': fields.selection(
            selection=[
                ('yes', 'Yes'),
                ('no', 'No'),
            ],
            string='Export AD',
            required=True,
        ),
        'file_type': fields.selection([('excel', 'Excel file'),
                                       ('xml', 'XML file')], string='File type', required=True),
    }

    _defaults = {
        'need_ad': 'yes',
    }

    def export_file(self, cr, uid, ids, context=None):
        '''
        Launch the good method to download the good file
        '''
        order_obj = self.pool.get('purchase.order')

        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        wiz = self.browse(cr, uid, ids[0], context=context)

        context['need_ad'] = wiz.need_ad == 'yes'

        if wiz.file_type == 'xml':
            return order_obj.export_xml_po_integration(cr, uid, wiz.order_id.id, context=context)
        else:
            return order_obj.export_excel_po_integration(cr, uid, wiz.order_id.id, context=context)

wizard_export_po_validated()


class purchase_order_simu_import_file(osv.osv):
    _name = 'purchase.order.simu.import.file'
    _order = 'timestamp'
    _rec_name = 'order_id'

    _columns = {
        'order_id': fields.many2one('purchase.order', string='Order', required=True),
        'filename': fields.char(size=256, string='Filename', required=True),
        'timestamp': fields.datetime(string='Date', required=True),
    }

    _defaults = {
        'timestamp': lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
    }

purchase_order_simu_import_file()
