# -*- coding: utf-8 -*-

from osv import osv, fields
from tools.translate import _
import time
import base64
import tools
from io import BytesIO
from openpyxl import load_workbook
from tools import misc

class MyWizException(Exception):
    pass

class wizard_import_ad_line(osv.osv_memory):
    _name = 'wizard.import.ad.line'
    _description = 'Import AD Lines from Excel file'

    _columns = {
        'file': fields.binary(
            string='File to import',
            states={'draft': [('readonly', False)]}),
        'message': fields.text(string='Message', readonly=True),
        'purchase_id': fields.many2one(
            'purchase.order', required=True, string=u"Purchase Order"),
        'sale_id': fields.many2one(
            'sale.order', required=True, string=u"Field Order"),
        'state': fields.selection([
            ('draft', 'Draft'),
            ('in_progress', 'In Progress'),
            ('done', 'Done'),
            ('error', 'Error'),
        ], string=u"State", required=True, readonly=True),
    }

    def import_file(self, cr, uid, ids, context=None):
        aa_obj = self.pool.get('account.analytic.account')
        ana_obj = self.pool.get('analytic.distribution')
        cc_line_obj = self.pool.get('cost.center.distribution.line')
        fp_line_obj = self.pool.get('funding.pool.distribution.line')

        pf_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'analytic_distribution',
                                                                    'analytic_account_msf_private_funds')[1]

        wiz = self.browse(cr, uid, ids[0], context)

        if wiz.purchase_id:
            import_obj = self.pool.get('purchase.order.line')
            doc = wiz.purchase_id
            doc_name = _('PO')
        else:
            import_obj = self.pool.get('sale.order.line')
            doc = wiz.sale_id
            doc_name = _('FO')
        try:
            if doc.state != 'draft':
                raise MyWizException(_('Document is not in Draft state.'))


            wiz_file = wiz.file
            self.write(cr, uid, ids[0], {'file': False}, context=context)
            if not wiz_file:
                raise MyWizException(_('Please add a file to import.'))

            try:
                wb = load_workbook(filename=BytesIO(base64.decodestring(wiz_file)), read_only=True)
                ws = wb.active
            except:
                raise MyWizException(_('Unable to read file. Please check the file format.'))

            try:
                ref = next(ws.rows)
            except StopIteration:
                raise MyWizException(_('Empty file'))

            if len(ref) < 2 or not ref[1].value:
                raise MyWizException( _('%s Reference not found in file.') % doc_name)

            if doc.name.lower() != ref[1].value.strip().lower():
                raise MyWizException(_('%s Reference does not match.') % doc_name)

            current_line_add = {}
            cr.execute('''
                select ol.id, ol.line_number, coalesce(prod.default_code, ol.comment), ol.analytic_distribution_id, array_agg(LOWER(cc.code)), array_agg(LOWER(dest.code)), array_agg(cc_line.id),
                    (select array_agg(fp_line.id) from funding_pool_distribution_line fp_line where fp_line.distribution_id = ol.analytic_distribution_id) as fp_line_ids, array_agg(cc_line.percentage)
                from
                    ''' + import_obj._table + ''' ol
                    left join product_product prod on prod.id = ol.product_id
                    left join cost_center_distribution_line cc_line on cc_line.distribution_id = ol.analytic_distribution_id
                    left join account_analytic_account cc on cc.id = cc_line.analytic_id
                    left join account_analytic_account dest on dest.id = cc_line.destination_id
                where
                    ol.order_id = %s and
                    ol.state = 'draft'
                group by ol.id, ol.line_number, coalesce(prod.default_code, ol.comment), ol.analytic_distribution_id
            ''', (doc.id, ))  # not_a_user_entry

            for x in cr.fetchall():
                key = (x[1], x[2].lower())
                current_line_add.setdefault(key, []).append(x)


            partner_type = doc.partner_type
            currency_id = doc.pricelist_id.currency_id.id
            cc_cache = {}
            dest_cache = {}
            error = []

            no_change = 0
            l_no_change = []
            updated = 0
            l_updated = []
            delete_ad = 0
            split_line_ignored = 0
            percentage_col = 7
            cc = 8
            dest = 9

            seen = {}
            try:
                next(ws.rows) # skip header
                next(ws.rows) # skip header
            except StopIteration:
                raise MyWizException(_('Incomplete file.'))

            for row in ws.rows:
                if len(row) > percentage_col:
                    key = (row[0].value, row[1].value.lower())
                    if not row[0].value or not row[1].value:
                        # empty line
                        continue

                    if key not in current_line_add:
                        if key not in seen:
                            error.append(_('Line / product does not match %s: #%s %s') % (doc_name, row[0].value, row[1].value))
                        else:
                            split_line_ignored += 1
                        continue

                    seen[key] = True
                    if row[percentage_col].value:
                        percentage_vals = tools.ustr(row[percentage_col].value).strip().lower().split(';')
                        if len(percentage_vals) == 1 and percentage_vals[0] == '1':  # 100% in excel cell is converted to 1
                            percentage_vals = ['100']
                        try:
                            percentage_vals = [float(percentage_val.strip('%')) for percentage_val in percentage_vals]
                        except ValueError as e:
                            error.append(_('%s line %s %s: Percentage values must be numbers') % (doc_name, key[0], key[1]))

                        if sum(percentage_vals) == 100:
                            cc_values = False
                            dest_values = False
                            try:
                                if row[cc].value:
                                    cc_values = row[cc].value.strip().lower().split(';')
                                if row[dest].value:
                                    dest_values = row[dest].value.strip().lower().split(';')
                            except IndexError:
                                pass

                            if not cc_values and not dest_values:
                                to_del = [x[3] for x in current_line_add[key] if x[3]]
                                if to_del:
                                    delete_ad += len(to_del)
                                    ana_obj.unlink(cr, uid, to_del, context=context)
                                for x in current_line_add[key]:
                                    if not x[3]:
                                        if key not in l_no_change:
                                            l_no_change.append(key)
                                        no_change += 1
                            elif not cc_values or not dest_values:
                                error.append(_('%s line %s %s: please empty or set both Cost Center and Destination') % (doc_name, key[0], key[1]))
                            else:
                                if len(percentage_vals) == len(cc_values) == len(dest_values):
                                    for i, percent in enumerate(percentage_vals):
                                        cc_value = cc_values[i]
                                        dest_value = dest_values[i]
                                        for line in current_line_add[key]:
                                            if (i >= len(line[4]) and i >= len(line[5]) and i >= len(line[8])) \
                                                    or (line[4][i] != cc_value or line[5][i] != dest_value or line[8][i] != percent):
                                                if cc_value not in cc_cache:
                                                    cc_ids = aa_obj.search(cr, uid, [('category', '=', 'OC'), ('type','!=', 'view'), ('code', '=ilike', cc_value)], context=context)
                                                    cc_cache[cc_value] = cc_ids and cc_ids[0] or False
                                                if dest_value not in dest_cache:
                                                    dest_ids = aa_obj.search(cr, uid, [('category', '=', 'DEST'), ('type','!=', 'view'), ('code', '=ilike', dest_value)], context=context)
                                                    dest_cache[dest_value] = dest_ids and dest_ids[0] or False
                                                found = True
                                                if not cc_cache[cc_value]:
                                                    error.append(_('%s line %d: Cost Center %s not found') % (doc_name, row[0].value, cc_value))
                                                    found = False
                                                if not dest_cache[dest_value]:
                                                    error.append(_('%s line %d: Destination %s not found') % (doc_name, row[0].value, dest_value))
                                                    found = False

                                                if not found:
                                                    break

                                                if not error:
                                                    updated += 1
                                                    if line[0] not in l_updated:
                                                        l_updated.append(line[0])
                                                    cc_data = {
                                                        'partner_type': partner_type,
                                                        'destination_id': dest_cache[dest_value],
                                                        'analytic_id': cc_cache[cc_value],
                                                        'percentage': percent,
                                                        'currency_id': currency_id,
                                                    }
                                                    if line[3] and line[6]:
                                                        if i < len(line[6]):
                                                            # have cc_id(s) and distrib_id: update instead of delete/create
                                                            cc_line_obj.write(cr, uid, line[6][i], cc_data, context=context)
                                                            if len(line[6]) > len(percentage_vals):
                                                                delete_ad += (len(line[6]) - len(percentage_vals))
                                                                cc_line_obj.unlink(cr, uid, line[6][len(percentage_vals):], context=context)
                                                        else:
                                                            cc_data['distribution_id'] = line[3]
                                                            cc_line_obj.create(cr, uid, cc_data, context=context)

                                                        fp_data = {
                                                            'partner_type': partner_type,
                                                            'destination_id': dest_cache[dest_value],
                                                            'cost_center_id': cc_cache[cc_value],
                                                            'analytic_id': pf_id,
                                                            'percentage': percent,
                                                            'currency_id': currency_id,
                                                        }
                                                        if i < len(line[7]):
                                                            fp_line_obj.write(cr, uid, line[7][i], fp_data, context=context)
                                                            if len(line[7]) > len(percentage_vals):
                                                                fp_line_obj.unlink(cr, uid, line[7][len(percentage_vals):], context=context)
                                                        else:
                                                            fp_data['distribution_id'] = line[3]
                                                            fp_line_obj.create(cr, uid, fp_data, context=context)
                                                    else:
                                                        if line[3]:
                                                            # delete previous empty AD
                                                            ana_obj.unlink(cr, uid, line[3], context=context)
                                                        distrib_id = ana_obj.create(cr, uid, {'partner_type': partner_type, 'cost_center_lines': [(0, 0, cc_data)]}, context=context)
                                                        ana_obj.create_funding_pool_lines(cr, uid, [distrib_id], context=context)
                                                        if len(percentage_vals) > 1:
                                                            current_line_add[key] = [(line[0], line[1], line[2], distrib_id, [cc_cache[cc_value]], [dest_cache[dest_value]],
                                                                ana_obj.read(cr, uid, distrib_id, ['cost_center_lines'], context=context)['cost_center_lines'],
                                                                fp_line_obj.search(cr, uid, [('distribution_id', '=', distrib_id)], context=context),
                                                                [percent]
                                                            )]
                                                        import_obj.write(cr, uid, [line[0]], {'analytic_distribution_id': distrib_id}, context=context)
                                            else:
                                                if line[0] not in l_no_change:
                                                    l_no_change.append(line[0])
                                                no_change += 1
                                else:
                                    error.append(_('%s line %s %s: There must be the same number of Percentages, Cost Centers and Destinations') % (doc_name, key[0], key[1]))
                        else:
                            error.append(_('%s line %s %s: The sum of percentages must be equal to 100') % (doc_name, key[0], key[1]))
                    else:
                        error.append(_('%s line %s %s: Percentage is mandatory') % (doc_name, key[0], key[1]))

                    del current_line_add[key]

            for key in current_line_add:
                if key not in l_no_change:
                    l_no_change.append(key)
                no_change += len(current_line_add[key])

            if error:
                cr.rollback()
                self.write(cr, uid, wiz.id, {'state': 'error', 'message': _('Import stopped, please fix the error(s):\n  - %s') % ("\n  - ".join(error),)}, context=context)
            else:
                self.write(cr, uid, wiz.id, {
                    'state': 'done',
                    'message': _('''Import done.

                    # %(updated)s AD updated on %(l_updated)s %(doc_name)s lines
                    # %(delete_ad)s AD deleted on %(doc_name)s lines
                    # %(no_change)s AD not modified on %(l_no_change)s %(doc_name)s lines
                    # %(split_line_ignored)s Split lines ignored in file

                    ''') % {'delete_ad': delete_ad, 'updated': updated, 'l_updated': len(l_updated),
                            'no_change': no_change, 'l_no_change': len(l_no_change), 'split_line_ignored': split_line_ignored,
                            'doc_name': doc_name}}, context=context)
        except MyWizException as e:
            cr.rollback()
            self.write(cr, uid, wiz.id, {'state': 'error', 'message': _('Import stopped.\n%s') % (e.message,)}, context=context)

        except Exception as e:
            cr.rollback()
            self.write(cr, uid, wiz.id, {'state': 'error', 'message': _('Import stopped.\n%s') % (misc.get_traceback(e),)}, context=context)

        # cannot use return True, otherwise and 2nd import do not display the except_osv message on screen
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'wizard.import.ad.line',
            'res_id': ids[0],
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'context': context,
        }

    def export_ad_line(self, cr, uid, ids, context=None):
        wiz = self.browse(cr, uid, ids, fields_to_fetch=['purchase_id', 'sale_id'], context=context)[0]
        if wiz.purchase_id:
            obj = wiz.purchase_id
        else:
            obj = wiz.sale_id
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'export_po_fo_ad_line_xlsx',
            'context': context,
            'datas': {
                'ids': [wiz.id],
                'target_filename': 'AD-%s-%s' % (obj.name, time.strftime('%Y-%m-%d')),
                'keep_open': True,
            }
        }

    def close_import(self, cr, uid, ids, context=None):
        return {'type': 'ir.actions.act_window_close', 'o2m_refresh': 'order_line'}

wizard_import_ad_line()
