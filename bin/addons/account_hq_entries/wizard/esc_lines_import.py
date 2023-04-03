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
import re


class esc_line_import_wizard(osv.osv_memory):
    _name = 'esc.line.import'
    _description = 'Import International Invoices Lines'

    _columns = {
        'file': fields.binary(string="File", required=True),
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
    }
    def open_wizard(self, cr, uid, ids, context=None):
        """
            on click on menutim: display the running hq import
        """
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

    def button_validate(self, cr, uid, ids, context=None):
        """
        Take a CSV file and fetch some informations for HQ Entries
        """
        # Do verifications
        if not context:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]


        threading.Thread(target=self.load_bg, args=(cr.dbname, uid, ids[0], context)).start()
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


    def load_bg(self, dbname, uid, wiz_id, context=None):
        def manage_error(line_index, msg):
            errors.append(_('Line %s, %s') % (line_index, _(msg)))

        errors = []
        curr_cache = {}
        product_cache = {}
        cost_center = {}

        created = 0
        processed = 0

        try:
            cr = pooler.get_db(dbname).cursor()

            target_cc_ids = self.pool.get('account.target.costcenter').search(cr, uid, [('instance_id.state', '!=', 'inactive'), ('is_po_fo_cost_center', '=', True)], context=context)
            for target in self.pool.get('account.target.costcenter').browse(cr, uid, target_cc_ids, fields_to_fetch=['cost_center_id'], context=context):
                cost_center[target.cost_center_id.code.lower()] = target.cost_center_id.id

            wiz = self.browse(cr, uid, wiz_id, context=None)
            file_data = SpreadsheetXML(xmlstring=base64.decodestring(wiz.file))
            nb_lines = file_data.getRows()

            line = 0
            for row in file_data.getRows():
                line += 1
                if line == 1:
                    # header
                    continue
                if not len(row.cells):
                    # empty line
                    continue
                if len(row.cells) < 8:
                    manage_error(line, _('A row must have 8 columns'))
                    continue

                if not row.cells[0].data:
                    manage_error(line, _('Order ref is mandatory'))
                    continue

                po_ref = row.cells[0].data.strip()
                if not re.match('^[0-9]{2}/[^/]+/\w+/PO\d+$', po_ref):
                    manage_error(line, _('Order ref %s does not match the PO pattern') % po_ref)
                    continue

                if not row.cells[1].data:
                    manage_error(line, _('Requestor Cost Center is mandatory'))
                    continue

                cc = row.cells[1].data.strip().lower()
                if cc not in cost_center:
                    manage_error(line, _('Requestor Cost Center %s not found or does not match any active instance.') % row.cells[1].data)
                    continue
                cc_id = cost_center[cc]

                consignee_id = False
                if row.cells[2].data:
                    cc = row.cells[2].data.strip().lower()
                    if cc not in cost_center:
                        manage_error(line, _('Requestor Cost Center %s not found or does not match any active instance.') % row.cells[2].data)
                        continue
                    consignee_id = cost_center[cc]

                if not row.cells[3].data:
                    manage_error(line, _('Product Code is mandatory.'))
                    continue
                p_code = row.cells[3].data.strip().lower()
                if p_code not in product_cache:
                    p_ids = self.pool.get('product.product').search(cr, uid, [('default_code', '=ilike', p_code)], context=context)
                    product_cache[p_code] = p_ids[0] if p_ids else False
                if not product_cache[p_code]:
                    manage_error(line, _('Product Code %s not found.') % (row.cells[3].data,))
                    continue

                if not row.cells[4].data:
                    manage_error(line, _('Product quantity is mandatory.'))
                    continue
                try:
                    qty = float(row.cells[4].data)
                except:
                    manage_error(line, _('Product Quantity %s is not a number.') % (row.cells[4].data, ))
                    continue

                if not row.cells[5].data:
                    manage_error(line, _('Unit Price is mandatory.'))
                    continue
                try:
                    unit_price = float(row.cells[5].data)
                except:
                    manage_error(line, _('Unit Price %s is not a number.') % (row.cells[5].data, ))
                    continue

                if not row.cells[6].data:
                    manage_error(line, _('Currency is mandatory.'))
                    continue
                curr_code = row.cells[6].data.strip().lower()
                if curr_code not in curr_cache:
                    curr_ids = self.pool.get('res.currency').search(cr, uid, [('name', '=ilike', curr_code)], context=context)
                    curr_cache[curr_code] = curr_ids[0] if curr_ids else False
                if not curr_cache[curr_code]:
                    manage_error(line, _('Currency %s not found.') % (row.cells[6].data,))
                    continue

                mapping = ''
                if row.cells[7].data:
                    mapping = row.cells[7].data.strip()

                processed += 1
                try:
                    self.pool.get('esc.invoice.line').create(cr, uid, {
                        'po_name': po_ref,
                        'requestor_cc_id': cc_id,
                        'consignee_cc_id': consignee_id,
                        'product_id': product_cache[p_code],
                        'price_unit': unit_price,
                        'product_qty': qty,
                        'currency_id': curr_cache[curr_code],
                        'shipment_ref': mapping,
                    }, context=context)
                    created += 1
                except osv.except_osv, e:
                    manage_error(line, e.value)

                if processed%10 == 0:
                    self.write(cr, uid, wiz_id, {'progress': int(processed/float(nb_lines)*100), 'created': created, 'nberrors': len(errors), 'error': "\n".join(errors)}, context=context)

            state = 'done'
            if errors:
                cr.rollback()
                state = 'error'
                msg = "\n".join(errors)
            else:
                msg = _("International Invoices Lines import successful")

            self.write(cr, uid, wiz_id, {'progress': 100, 'state': state, 'created': created, 'total': processed, 'error': msg, 'nberrors': len(errors), 'end_date': time.strftime('%Y-%m-%d %H:%M:%S')}, context=context)

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

    def done(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state': 'ack'}, context=context)
        d = self.pool.get('ir.actions.act_window').open_view_from_xmlid(cr, uid, 'account_hq_entries.esc_invoice_line_action', context=context)
        return d

    def ack(self, cr, uid, ids, context=None):
        self.write(cr, uid, ids, {'state': 'ack'}, context=context)
        return {'type': 'ir.actions.act_window_close'}

esc_line_import_wizard()
