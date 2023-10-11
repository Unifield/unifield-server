#!/usr/bin/env python
# -*- coding: utf-8 -*-
from osv import osv
from osv import fields
from spreadsheet_xml.spreadsheet_xml import SpreadsheetXML
import threading
import pooler
import tools
from tools.translate import _
import time
import base64
import os
import re
from psycopg2 import IntegrityError


class esc_line_import_rejected(osv.osv):
    _name = 'esc.line.import.rejected'
    _description = 'Rejected Lines'
    _rec_name = 'wiz_id'
    _order = 'wiz_id desc, id asc'

    _columns = {
        'wiz_id': fields.many2one('esc.line.import', 'Import', required=1),
        'error': fields.text('Reason'),
        'xls_row': fields.text('Row'),
    }

esc_line_import_rejected()

class esc_line_import_wizard(osv.osv):
    _name = 'esc.line.import'
    _description = 'Import International Invoices Lines'
    _rec_name = 'start_date'

    _columns = {
        'file': fields.binary(string="File"),
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
        'start_date': lambda *x: fields.datetime.now()
    }

    def __init__(self, pool, cr):
        super(esc_line_import_wizard, self).__init__(pool, cr)
        if cr.column_exists('esc_line_import', 'state'):
            cr.execute("update esc_line_import set state='error', created=0, error='Server restarted, import cancelled.', nberrors=0, total=0 where state='inprogress'")
        if cr.column_exists('esc_line_import', 'file'):
            cr.execute("update esc_line_import set file=null where file is not null")

    def write(self, cr, uid, ids, vals, context=None):
        if context is None:
            context = {}
        # remove concurrency warning on refresh
        if self.CONCURRENCY_CHECK_FIELD in context:
            del context[self.CONCURRENCY_CHECK_FIELD]
        return super(esc_line_import_wizard, self).write(cr, uid, ids, vals, context)

    def open_wizard(self, cr, uid, ids, context=None):
        """
            on click on menutim: display the running hq import
        """
        if self.pool.get('res.company')._get_instance_level(cr, uid) != 'section':
            raise osv.except_osv(_('Warning'), ('This object can only be imported at HQ level'))

        ids = self.search(cr, uid, [('state', 'in', ['inprogress', 'error', 'done'])], context=context)
        if ids:
            res_id = ids[0]
            view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'account_hq_entries', 'esc_line_import_progress_wizard')[1]
        else:
            res_id = False
            view_id = False
        return {
            'name': _('Import International Invoices Lines'),
            'type': 'ir.actions.act_window',
            'res_model': 'esc.line.import',
            'view_mode': 'form',
            'view_type': 'form',
            'view_id': [view_id],
            'res_id': res_id,
            'target': 'new',
            'context': context,
        }

    def get_template_file(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'esc_line_import_template',
            'datas': {'target_filename': _('International Invoices Lines Template'), 'keep_open': 1},
            'context': context,
        }

    def get_error_file(self, cr, uid, ids, context=None):
        if context is None:
            context = {}

        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'esc_line_import_rejected',
            'datas': {'target_filename': _('International Invoices Rejected Lines'), 'keep_open': 1, 'active_id': ids[0]},
            'context': context,
        }

    def button_validate(self, cr, uid, ids, context=None):
        """
        Take a CSV file and fetch some informations for HQ Entries
        """
        # Do verifications
        if not context:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        if not self.browse(cr, uid, ids[0], context=context).file:
            raise osv.except_osv(_('Warning'), _('No file to import'))

        threading.Thread(target=self.load_bg, args=(cr.dbname, uid, ids[0], False, context)).start()
        self.write(cr, uid, ids[0], {'state': 'inprogress', 'progress': 0}, context=context)

        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'account_hq_entries', 'esc_line_import_progress_wizard')[1]
        return {
            'name': _('Import International Invoices Lines'),
            'type': 'ir.actions.act_window',
            'res_model': 'esc.line.import',
            'view_mode': 'form',
            'view_type': 'form',
            'view_id': [view_id],
            'res_id': ids[0],
            'target': 'new',
            'context': context,
        }

    def auto_import(self, cr, uid, file_to_import, context=None):

        import_id = self.create(cr, uid, {
            'file': base64.encodestring(open(file_to_import, 'r').read()),
            'filename': os.path.split(file_to_import)[1],
            'state': 'inprogress',
        })
        cr.commit()
        self.load_bg(cr.dbname, uid, import_id, auto_import=True, context=context)
        curr_state = self.browse(cr, uid, import_id, fields_to_fetch=['state'], context=context).state
        self.write(cr, uid, import_id, {'state': 'ack'}, context=context)
        return import_id, curr_state


    def load_bg(self, dbname, uid, wiz_id, auto_import=False, context=None):
        def manage_error(line_index, msg, row):
            errors.append(_('Line %s, %s') % (line_index, _(msg)))
            line_data = []
            len_cell = len(row.cells)
            for x in range(0, min(len_cell, 8)):
                line_data.append({'type': row.cells[x].type, 'data': row.cells[x].data})
            self.pool.get('esc.line.import.rejected').create(cr, uid, {'wiz_id': wiz_id, 'error': msg, 'xls_row': tools.ustr(line_data)}, context=context)

        errors = []
        curr_cache = {}
        product_cache = {}
        cost_center = {}

        created = 0
        processed = 0

        created_ids = {}
        consignee_instances = {}

        try:
            cr = pooler.get_db(dbname).cursor()
            cr2 = pooler.get_db(dbname).cursor()

            target_cc_ids = self.pool.get('account.target.costcenter').search(cr, uid, [('instance_id.state', '!=', 'inactive'), ('is_po_fo_cost_center', '=', True)], context=context)
            for target in self.pool.get('account.target.costcenter').browse(cr, uid, target_cc_ids, fields_to_fetch=['cost_center_id', 'instance_id'], context=context):
                if target.cost_center_id and target.instance_id.instance:
                    cost_center[target.cost_center_id.code.lower()] = target.cost_center_id.id
                    consignee_instances[target.instance_id.instance.lower()] = target.cost_center_id.id

            wiz = self.browse(cr, uid, wiz_id, context=None)
            file_data = SpreadsheetXML(xmlstring=base64.decodestring(wiz.file))
            nb_lines = file_data.getNbRows()

            line = 0
            for row in file_data.getRows():
                line += 1
                if line == 1:
                    # header
                    continue
                if not len(row.cells):
                    # empty line
                    continue
                processed += 1
                if len(row.cells) < 7:
                    manage_error(line, _('a row must have 8 columns'), row)
                    continue

                if not row.cells[0].data:
                    manage_error(line, _('Order ref is mandatory'), row)
                    continue

                po_ref = row.cells[0].data.strip()
                if not re.match('^[0-9]{2}/[^/]+/\w+/PO\d+$', po_ref):
                    manage_error(line, _('Order ref %s does not match the PO pattern') % po_ref, row)
                    continue

                if not row.cells[1].data:
                    manage_error(line, _('Requestor Cost Center is mandatory'), row)
                    continue

                cc = row.cells[1].data.strip().lower()
                if cc not in cost_center:
                    manage_error(line, _('Requestor Cost Center %s not found or does not match any active instance.') % row.cells[1].data, row)
                    continue
                cc_id = cost_center[cc]

                consignee_id = False
                consignee_instance_txt = False
                if row.cells[2].data:
                    cc = row.cells[2].data.strip().lower()

                    if cc in cost_center:
                        consignee_id = cost_center[cc]
                        consignee_instance_txt = ''
                    elif cc in consignee_instances:
                        consignee_id= consignee_instances[cc]
                        consignee_instance_txt = row.cells[2].data.strip()
                    else:
                        manage_error(line, _('Consignee Cost Center/Instance %s not found or does not match any active instance.') % row.cells[2].data, row)
                        continue


                if not row.cells[3].data:
                    manage_error(line, _('Product Code is mandatory.'), row)
                    continue
                p_code = row.cells[3].data.strip().lower()
                if p_code not in product_cache:
                    p_ids = self.pool.get('product.product').search(cr, uid, [('default_code', '=ilike', p_code)], context=context)
                    product_cache[p_code] = p_ids[0] if p_ids else False
                if not product_cache[p_code]:
                    manage_error(line, _('Product Code %s not found.') % (row.cells[3].data,), row)
                    continue

                if not row.cells[4].data:
                    manage_error(line, _('Product quantity is mandatory.'), row)
                    continue
                try:
                    qty = float(row.cells[4].data)
                except:
                    manage_error(line, _('Product Quantity %s is not a number.') % (row.cells[4].data, ), row)
                    continue

                if qty <= 0:
                    manage_error(line, _('Product Quantity %s cannot be 0 or negative') % (row.cells[4].data, ), row)
                    continue

                if not row.cells[5].data:
                    manage_error(line, _('Unit Price is mandatory.'), row)
                    continue
                try:
                    unit_price = float(row.cells[5].data)
                except:
                    manage_error(line, _('Unit Price %s is not a number.') % (row.cells[5].data, ), row)
                    continue

                if not row.cells[6].data:
                    manage_error(line, _('Currency is mandatory.'), row)
                    continue
                curr_code = row.cells[6].data.strip().lower()
                if curr_code not in curr_cache:
                    curr_ids = self.pool.get('res.currency').search(cr, uid, [('name', '=ilike', curr_code)], context=context)
                    curr_cache[curr_code] = curr_ids[0] if curr_ids else False
                if not curr_cache[curr_code]:
                    manage_error(line, _('Currency %s not found.') % (row.cells[6].data,), row)
                    continue

                mapping = ''
                if len(row.cells) > 7 and row.cells[7].data:
                    if row.cells[7].type == 'str':
                        mapping = row.cells[7].data.strip()
                    else:
                        mapping = '%s' % row.cells[7].data

                cr.execute("SAVEPOINT esc_line")
                try:
                    new_line = self.pool.get('esc.invoice.line').create(cr, uid, {
                        'po_name': po_ref,
                        'requestor_cc_id': cc_id,
                        'consignee_cc_id': consignee_id,
                        'imported_consignee_instance': consignee_instance_txt,
                        'product_id': product_cache[p_code],
                        'price_unit': unit_price,
                        'product_qty': qty,
                        'currency_id': curr_cache[curr_code],
                        'shipment_ref': mapping,
                    }, context=context)
                    created_ids[new_line] = line
                    created += 1
                    cr.execute("RELEASE SAVEPOINT esc_line")
                except osv.except_osv, e:
                    cr.execute("ROLLBACK TO SAVEPOINT esc_line")
                    manage_error(line, e.value, row)
                except IntegrityError:
                    cr.execute("ROLLBACK TO SAVEPOINT esc_line")
                    line_id = False

                    if created_ids:
                        line_id = self.pool.get('esc.invoice.line').search(cr, uid, [
                            ('id', 'in', created_ids.keys()),
                            ('po_name', '=', po_ref),
                            ('requestor_cc_id', '=', cc_id),
                            ('consignee_cc_id', '=', consignee_id),
                            ('product_id', '=', product_cache[p_code]),
                            ('price_unit', '=', unit_price),
                            ('product_qty', '=', qty),
                            ('currency_id', '=', curr_cache[curr_code]),
                            ('shipment_ref', '=', mapping)
                        ], context=context)
                        if line_id:
                            manage_error(line, _('duplicates line %d') % created_ids[line_id[0]], row)
                    if not line_id:
                        manage_error(line, _('Line duplicated in the system'), row)

                if processed%10 == 0:
                    self.write(cr2, uid, wiz_id, {'progress': int(processed/float(nb_lines)*100), 'created': created, 'nberrors': len(errors), 'error': "\n".join(errors)}, context=context)
                    cr2.commit()

            state = 'done'
            if errors:
                state = 'error'
                nb_errors = len(errors)
                errors.insert(0, _('Imported with error(s)'))
                msg = "\n".join(errors)
            else:
                msg = _("International Invoices Lines import successful")
                nb_errors = 0

            self.write(cr, uid, wiz_id, {'progress': 100, 'state': state, 'created': created, 'total': processed, 'error': msg, 'nberrors': nb_errors, 'end_date': time.strftime('%Y-%m-%d %H:%M:%S'), 'file': False}, context=context)

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
            cr.close(True)
            cr2.commit()
            cr2.close(True)

    def done(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state': 'ack'}, context=context)
        d = self.pool.get('ir.actions.act_window').open_view_from_xmlid(cr, uid, 'account_hq_entries.esc_invoice_line_action', context=context)
        return d

    def ack(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state': 'ack'}, context=context)
        return {'type': 'ir.actions.act_window_close'}

esc_line_import_wizard()

