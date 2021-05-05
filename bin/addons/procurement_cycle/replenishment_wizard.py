# -*- coding: utf-8 -*-


from osv import osv, fields
from tools.translate import _
from spreadsheet_xml.spreadsheet_xml import SpreadsheetXML
import base64


class replenishment_consolidated_oc_import(osv.osv_memory):
    _name = 'replenishment.consolidated_oc.import'

    _columns = {
        'file_to_import': fields.binary(string='File to import', required=1),
        'state': fields.selection([('draft', 'Draft'), ('done', 'Done'), ('partial', 'Partially Imported'), ('error', 'Error')], 'State', readonly=1),
        'error': fields.text('Error', readonly=1),
    }

    def import_oc_lines(self, cr, uid, ids, context=None):
        wiz = self.browse(cr, uid, ids, context=context)[0]

        if not wiz.file_to_import:
            raise osv.except_osv(_('Error'), _('Nothing to import.'))
        file_data = SpreadsheetXML(xmlstring=base64.b64decode(wiz.file_to_import))


        cal_obj = self.pool.get('replenishment.order_calc')
        cal_line_obj = self.pool.get('replenishment.order_calc.line')

        oc_ref_col = 4
        qty_col = 24
        comment_col = 27
        header = 5
        error = []
        updated = 0

        nb_cells = 29

        idx = 0

        oc_by_ref = {}
        oc_updated = {}
        for row in file_data.getRows():
            idx += 1
            if idx < header:
                continue
            if idx == header:
                if len(row.cells) != nb_cells:
                    add = ""
                    if len(row.cells) == 30:
                        add = _('tips: to import the "Consolidated all status" file, remove the "Order Calc Status" column"')
                    self.write(cr, uid, ids, {'error':_('Wrong format: expected %d cells, found %s %s') % (nb_cells, len(row.cells), add), 'state': 'error'}, context=context)
                    return True
                continue

            oc_ref = row.cells[oc_ref_col].data
            if not oc_ref:
                error.append(_('Line %d: OC Ref not found.') % (idx+1,))
                continue
            oc_ref = oc_ref.strip()
            if oc_ref not in oc_by_ref:
                cal_ids = cal_obj.search(cr, uid, [('state', '=', 'draft'), ('name', '=', oc_ref)], context=context, limit=1)
                oc_by_ref[oc_ref] = cal_ids and cal_ids[0]

            if not oc_by_ref[oc_ref]:
                error.append(_('Line %d: no draft %s found.') % (idx+1, oc_ref))
                continue

            prod_code = row.cells[0].data
            if not prod_code:
                continue
            prod_code = prod_code.strip()
            cal_line_ids = cal_line_obj.search(cr, uid, [('product_id.default_code', '=', prod_code), ('order_calc_id', '=', oc_by_ref[oc_ref])], limit=1, context=context)
            if not cal_line_ids:
                error.append(_('Line %d: product %s not found in %s') % (idx+1, prod_code, oc_by_ref[oc_ref]))
                continue

            if row.cells[qty_col].data and not isinstance(row.cells[qty_col].data, (int, float)):
                error.append(_('Line %d: product %s %s : Agreed Order Qty  must be a number, found %s') % (idx+1, prod_code, oc_by_ref[oc_ref], row.cells[qty_col].data))
                continue

            cal_line_obj.write(cr, uid, cal_line_ids, {
                'agreed_order_qty': row.cells[qty_col].data,
                'order_qty_comment': row.cells[comment_col].data or '',
            }, context=context)
            oc_updated[oc_ref] = oc_updated.setdefault(oc_ref, 0) + 1
            updated += 1



        if not error:
            state = 'done'
        elif updated:
            state = 'partial'
        else:
            state = 'error'

        msg = []
        if updated:
            msg.append(_('%d lines updated in %d OC, %d error%s') % (updated, len(oc_updated), len(error), len(error)>1 and 's' or ''))
            for oc_ref in oc_updated:
                msg.append(_('  - %s : %d products') % (oc_ref, oc_updated[oc_ref]))
            msg.append('')


        self.write(cr, uid, ids, {'error':"\n".join(msg+error), 'state': state}, context=context)

        return True

    _defaults = {
        'state': 'draft',
    }
replenishment_consolidated_oc_import()
