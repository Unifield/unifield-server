# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO Consulting.
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
import threading
import pooler
from osv import osv, fields
from tools.translate import _
from mx import DateTime
import base64
from spreadsheet_xml.spreadsheet_xml import SpreadsheetXML
from spreadsheet_xml.spreadsheet_xml_write import SpreadsheetCreator
import time
from msf_supply_doc_import import check_line
from msf_supply_doc_import.wizard import PO_COLUMNS_FOR_INTEGRATION as columns_for_po_integration, PO_COLUMNS_HEADER_FOR_INTEGRATION


class purchase_line_import_xml_line(osv.osv_memory):
    """
    This class is usefull only for the import:
    - it helps using search function to find matching lines (between PO lines and file lines)
    - it helps updating or spliting the lines because we can directly use the fields in vals
    with a read.
    """
    _name = 'purchase.line.import.xml.line'
    
    
    _columns = {
        'line_ignored_ok': fields.boolean('Ignored?'),
        'file_line_number': fields.integer(string='File line numbers'),
        'line_number': fields.integer(string='Line number'),
        'product_id': fields.many2one('product.product', string='Product'),
        'product_uom': fields.many2one('product.uom', string='UoM'),
        'product_qty': fields.float(digits=(16,2), string='Quantity'),
        'price_unit':fields.float(digits=(16,2), string='Price'),
        'confirmed_delivery_date': fields.date('Confirmed Delivery Date'),
        'order_id': fields.many2one('purchase.order', string='Purchase Order'),
        'to_correct_ok': fields.boolean('To correct?'),
        'warning_list': fields.text('Warning'),
        'error_list': fields.text('Error'),
        'text_error': fields.text('Text Error'),
        'show_msg_ok': fields.boolean('To show?'),
        'comment': fields.text('Comment'),
    }
    _defaults = {
        'line_ignored_ok': False,
        }
    
purchase_line_import_xml_line()


class wizard_import_po(osv.osv_memory):
    """
    This class helps importing the PO for the vertical integration.
    """
    _name = 'wizard.import.po'
    _description = 'Import PO from Excel sheet'

    def get_bool_values(self, cr, uid, ids, fields, arg, context=None):
        res = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        for obj in self.browse(cr, uid, ids, context=context):
            res[obj.id] = False
            if obj.message:
                res[obj.id] = True
        return res

    _columns = {
        'file': fields.binary(string='File to import', required=True, readonly=True, states={'draft': [('readonly', False)]}),
        'message': fields.text(string='Message', readonly=True),
        'po_id': fields.many2one('purchase.order', string='Purchase Order', required=True),
        'data': fields.binary('Lines with errors'),
        'filename_template': fields.char('Templates', size=256),
        'filename': fields.char('Lines with errors', size=256),
        'import_error_ok': fields.function(get_bool_values, method=True, readonly=True, type="boolean", string="Error at import", store=False),
        'percent_completed': fields.integer('% completed', readonly=True),
        'state': fields.selection([('draft', 'Draft'), ('in_progress', 'In Progress'), ('done', 'Done')],
                                  string="State", required=True, readonly=True),
    }
    
    _defaults = {
        'message': lambda *a : """
        IMPORTANT : The first line will be ignored by the system.
        The file should be in XML 2003 format.

The columns should be in this values:
%s
""" % (', \n'.join(columns_for_po_integration), ),
        'state': lambda *a: 'draft',
    }

    def export_file_with_error(self, cr, uid, ids, *args, **kwargs):
        lines_not_imported = kwargs.get('line_with_error') # list of list
        header_index = kwargs.get('header_index')
        data = header_index.items()
        columns_header = []
        for k,v in sorted(data, key=lambda tup: tup[1]):
            columns_header.append((k, type(k)))
        files_with_error = SpreadsheetCreator('Lines with errors', columns_header, lines_not_imported)
        vals = {'data': base64.encodestring(files_with_error.get_xml()), 'filename': 'Lines_Not_Imported.xls'}
        return vals

    def default_get(self, cr, uid, fields, context=None):
        '''
        Set po_id with the active_id value in context
        '''
        if not context or not context.get('active_id'):
            raise osv.except_osv(_('Error !'), _('No Purchase Order found !'))
        else:
            po_id = context.get('active_id')
            res = super(wizard_import_po, self).default_get(cr, uid, fields, context=context)
            res['po_id'] = po_id
        columns_header = PO_COLUMNS_HEADER_FOR_INTEGRATION
        default_template = SpreadsheetCreator('Template of import', columns_header, [])
        res.update({'file': base64.encodestring(default_template.get_xml()), 'filename': 'template.xls'})
        return res

    def get_line_values(self, cr, uid, ids, row, cell_nb, error_list, line_num, context=None):
        list_of_values = []
        for cell_nb in range(len(row)):
            cell_data = row.cells and row.cells[cell_nb] and row.cells[cell_nb].data
            list_of_values.append(cell_data)
        return list_of_values

    def get_header_index(self, cr, uid, ids, row, error_list, line_num, context):
        """
        Return dict with {'header_name0': header_index0, 'header_name1': header_index1...}
        """
        header_dict = {}
        for cell_nb in range(len(row.cells)):
            header_dict.update({row.cells and row.cells[cell_nb] and row.cells[cell_nb].data: cell_nb})
        return header_dict

    def check_header_values(self, cr, uid, ids, context, header_index):
        """
        Check that the columns in the header will be taken into account.
        """
        for k,v in header_index.items():
            if k not in columns_for_po_integration:
                vals = {'message': 'The column "%s" is not taken into account. Please remove it. The list of columns accepted is: \n %s' 
                                                   % (k, ', \n'.join(columns_for_po_integration))}
                return self.write(cr, uid, ids, vals, context), False
        return True, True

    def get_po_row_values(self, cr, uid, ids, row, po_browse, header_index, context=None):
        product_obj = self.pool.get('product.product')
        uom_obj = self.pool.get('product.uom')
        purchase_obj = self.pool.get('purchase.order')
        to_write = {
            'error_list': [],
            'warning_list': [],
            'to_correct_ok': False,
            'show_msg_ok': False,
            'comment': '',
            'confirmed_delivery_date': False,
        }
        
        # Order Reference*
        cell_nb = header_index['Order Reference*']
        order_name = row.cells and row.cells[cell_nb] and row.cells[cell_nb].data
        order_ids = purchase_obj.search(cr, uid, [('name', '=', order_name)])
        if not order_ids:
            to_write['error_list'].append(_('The Purchase Order %s was not found in the DataBase.' % order_name))
            to_write.update({'error_list': to_write['error_list'], 'to_correct_ok': True})
        elif order_ids[0] != po_browse.id:
            to_write['error_list'].append(_('The Purchase Order %s does not correspond to the current one (%s).' % (order_name, po_browse.name)))
            to_write.update({'error_list': to_write['error_list'], 'to_correct_ok': True})
        elif order_ids[0] == po_browse.id:
            to_write.update({'order_id': order_ids[0]})
        
        # Line
        cell_nb = header_index['Line*']
        line_number = int(row.cells and row.cells[cell_nb] and row.cells[cell_nb].data)
        to_write.update({'line_number': line_number})

        # Quantity
        cell_nb = header_index['Quantity*']
        product_qty = float(row.cells and row.cells[cell_nb] and row.cells[cell_nb].data)
        to_write.update({'product_qty': product_qty})
    
        # Product Code
        cell_nb = header_index['Product Code*']
        product_code = row.cells and row.cells[cell_nb] and row.cells[cell_nb].data
        p_ids = product_obj.search(cr, uid, [('default_code', '=', product_code)])
        if not p_ids:
            to_write['error_list'].append("The Product\'s Code %s is not found in the database."% (product_code))
            to_write.update({'error_list': to_write['error_list'], 'to_correct_ok': True})
        else:
            default_code = p_ids[0]
            to_write.update({'product_id': default_code})

        # UOM
        cell_nb = header_index['UoM*']
        cell_data = row.cells and row.cells[cell_nb] and row.cells[cell_nb].data
        product_uom = uom_obj.search(cr, uid, [('name', '=', cell_data)])
        if product_uom:
            to_write.update({'product_uom': product_uom[0]})
        else:
            to_write['error_list'].append(_('The UOM %s was not found in the DataBase.' % cell_data))
            to_write.update({'error_list': to_write['error_list'], 'to_correct_ok': True})

        # Price
        cell_nb = header_index['Price*']
        price_unit = int(row.cells and row.cells[cell_nb] and row.cells[cell_nb].data)
        to_write.update({'price_unit': price_unit})

        # Delivery Confirmed Date
        cell_nb = header_index['Delivery Confirmed Date*']
        confirmed_delivery_date = row.cells and row.cells[cell_nb] and row.cells[cell_nb].data
        if confirmed_delivery_date:
            confirmed_delivery_date = DateTime.strptime(confirmed_delivery_date,'%d/%m/%Y')
        to_write.update({'confirmed_delivery_date': confirmed_delivery_date})

        #  Comment
        c_value = {}
        cell_nb = header_index['Comment']
        c_value = check_line.comment_value(row=row, cell_nb=cell_nb, to_write=to_write, context=context)
        to_write.update({'comment': c_value['comment'], 'warning_list': c_value['warning_list']})
        to_write.update({
            'text_error': '\n'.join(to_write['error_list'] + to_write['warning_list']),
        })
        return to_write

    def get_file_values(self, cr, uid, ids, rows, header_index, error_list, line_num, context=None):
        """
        Catch the file values on the form [{values of the 1st line}, {values of the 2nd line}...]
        """
        file_values = []
        for row in rows:
            line_values = {}
            for cell in enumerate(self.get_line_values(cr, uid, ids, row, cell_nb=False, error_list=error_list, line_num=line_num, context=context)):
                line_values.update({cell[0]: cell[1]})
            file_values.append(line_values)
        return file_values

    def _import(self, dbname, uid, ids, context=None):
        '''
        Import file
        '''
        cr = pooler.get_db(dbname).cursor()
        
        if context is None:
            context = {}
        pol_obj = self.pool.get('purchase.order.line')
        import_obj = self.pool.get('purchase.line.import.xml.line')
        context.update({'import_in_progress': True})
        start_time = time.time()
        wiz_browse = self.browse(cr, uid, ids, context)[0]
        po_browse = wiz_browse.po_id
        po_id = po_browse.id
        header_index = context['header_index']

        ignore_lines, complete_lines, lines_to_correct = 0, 0, 0
        line_with_error, error_list, notif_list = [], [], []
        error_log, notif_log = '', ''
        
        fileobj = SpreadsheetXML(xmlstring=base64.decodestring(wiz_browse.file))
        rows = fileobj.getRows()
        # take all the lines of the file in a list of dict
        file_values = self.get_file_values(cr, uid, ids, rows, header_index, error_list=[], line_num=False, context=context)
        
        rows = fileobj.getRows()
        rows.next()
        file_line_number = 0
        total_line_num = len([row for row in file_obj.getRows()])
        for row in rows:
            file_line_number += 1
            try:
                to_write = self.get_po_row_values(cr, uid, ids, row, po_browse, header_index, context)
                if to_write['error_list']:
                    import_obj.create(cr, uid, {'file_line_number': file_line_number, 'line_ignored_ok': True, 'line_number': False, 'order_id': False, 'product_id': False})
                    error_log += 'Line %s in the Excel file was added to the file of the lines with errors: %s \n' % (file_line_number, ' '.join(to_write['error_list']))
                    line_with_error.append(self.get_line_values(cr, uid, ids, row, cell_nb=False, error_list=to_write['error_list'], line_num=False, context=context))
                    ignore_lines += 1
                else:
                    # we check consistency on the model of on_change functions to call for updating values
                    context.update({'po_integration': True})
                    pol_obj.check_line_consistency(cr, uid, po_browse.id, to_write=to_write, context=context)
                    line_number = to_write['line_number']
                    # We ignore the lines with a line number that does not correspond to any line number of the PO line
                    if not pol_obj.search(cr, uid, [('order_id', '=', po_id), ('line_number', '=', line_number)]):
                        import_obj.create(cr, uid, {'file_line_number': file_line_number, 'line_ignored_ok': True, 'line_number': False, 'order_id': False, 'product_id': False})
                        error_log += 'Line %s in the Excel file was added to the file of the lines with errors: the line number %s does not exist for %s \n' % (file_line_number, line_number, po_browse.name)
                        line_with_error.append(self.get_line_values(cr, uid, ids, row, cell_nb=False, error_list=to_write['error_list'], line_num=False, context=context))
                        ignore_lines += 1
                    else:
                        to_write.update({'file_line_number': file_line_number})
                        import_obj.create(cr, uid, to_write)
            except osv.except_osv as osv_error:
                import_obj.create(cr, uid, {'file_line_number': file_line_number, 'line_ignored_ok': True, 'line_number': False, 'order_id': False, 'product_id': False})
                osv_value = osv_error.value
                osv_name = osv_error.name
                error_log += "Line %s in the Excel file was added to the file of the lines with errors: %s: %s\n" % (file_line_number, osv_name, osv_value)
                line_with_error.append(self.get_line_values(cr, uid, ids, row, cell_nb=False, error_list=error_list, line_num=file_line_number, context=context))
                ignore_lines += 1
                continue
        try:
            # start importing lines
            sql_line_number = """
            select distinct line_number
            from purchase_order_line
            where order_id = %s
            """
            cr.execute(sql_line_number, (po_id,))
            list_line_number = cr.fetchall()
            for line_number in list_line_number:
                line_number = line_number[0]
                same_file_line_nb = import_obj.search(cr, uid, [('line_ignored_ok', '=', False), ('line_number', '=', line_number), ('order_id', '=', po_id)])
                same_pol_line_nb = pol_obj.search(cr, uid, [('line_number', '=', line_number), ('order_id', '=', po_id)])
                count_same_file_line_nb = len(same_file_line_nb)
                count_same_pol_line_nb = len(same_pol_line_nb)
                # we deal with 3 cases
                if same_file_line_nb:
                    # 1st CASE
                    if count_same_file_line_nb == count_same_pol_line_nb:
                        # 'We update all the lines.'
                        for pol_line, file_line in zip(pol_obj.browse(cr, uid, same_pol_line_nb, context), import_obj.read(cr, uid, same_file_line_nb)):
                            vals = file_line
                            file_line_number = vals['file_line_number']
                            pol_obj.write(cr, uid, pol_line.id, vals)
                            notif_list.append("Line %s of the Excel file updated the PO line %s."
                                              % (file_line_number, pol_line.line_number))
                            complete_lines += 1
                    # 2nd CASE
                    elif count_same_file_line_nb < count_same_pol_line_nb:
                        # if the product is the same: we update the corresponding line
                        file_line_proceed = []
                        for pol_line in pol_obj.browse(cr, uid, same_pol_line_nb, context):
                            # is a product similar between the file line and obj line?
                            overlapping_lines = import_obj.search(cr, uid, [('id', 'in', same_file_line_nb), ('product_id', '=', pol_line.product_id.id)])
                            if overlapping_lines and len(overlapping_lines) == 1 and overlapping_lines[0] not in file_line_proceed:
                                import_values = import_obj.read(cr, uid, overlapping_lines)[0]
                                file_line_number = import_values['file_line_number']
                                pol_obj.write(cr, uid, pol_line.id, import_values)
                                notif_list.append("Line %s of the Excel file updated the line %s with the product %s in common."
                                                  % (file_line_number, pol_line.line_number, pol_line.product_id.default_code))
                                file_line_proceed.append(overlapping_lines[0])
                                complete_lines += 1
                        #we ignore the file lines with this line number because we can't know which lines to update or not.
                        for line in import_obj.read(cr, uid, same_file_line_nb):
                            if not line['line_ignored_ok'] and line['id'] not in file_line_proceed:
                                # the file_line_number is equal to the index of the line in file_values
                                error_log += "Line %s in the Excel file was added to the file of the lines with errors\n" % (import_values['file_line_number'])
                                data = file_values[line['file_line_number']].items()
                                line_with_error.append([v for k,v in sorted(data, key=lambda tup: tup[0])])
                                ignore_lines += 1
                    # 3rd CASE
                    elif count_same_file_line_nb > count_same_pol_line_nb:
                        if count_same_pol_line_nb == 1:
                            #"We split the only line with this line number"
                            product_qty = 0.0
                            file_line_read = import_obj.read(cr, uid, same_file_line_nb)
                            for file_line in file_line_read:
                                product_qty += file_line['product_qty']
                            import_values = file_line_read[0]
                            lines = [str(import_values['file_line_number'])]
                            import_values.update({'product_qty': product_qty})
                            pol_obj.write(cr, uid, same_pol_line_nb, import_values)
                            complete_lines += 1
                            for file_line in import_obj.browse(cr, uid, same_file_line_nb[1:len(same_file_line_nb)]):
                                wizard_values = pol_obj.open_split_wizard(cr, uid, same_pol_line_nb, context)
                                wiz_context = wizard_values.get('context')
                                self.pool.get(wizard_values['res_model']).write(cr, uid, [wizard_values['res_id']],
                                                                                {'new_line_qty': file_line.product_qty}, context=wiz_context)
                                self.pool.get(wizard_values['res_model']).split_line(cr, uid, [wizard_values['res_id']], context=wiz_context)
                                lines.append(str(file_line.file_line_number))
                                po_line_ids = pol_obj.search(cr, uid, [('product_qty', '=', file_line.product_qty),
                                                                       ('line_number', '=', line_number),
                                                                       ('order_id', '=', po_id)])
                                new_po_line = po_line_ids[-1]
                                pol_obj.write(cr, uid, [new_po_line], {'product_qty': file_line.product_qty,
                                                                        'product_uom': file_line.product_uom.id,
                                                                        'product_id': file_line.product_id.id,
                                                                        'confirmed_delivery_date': file_line.confirmed_delivery_date})
                                complete_lines += 1
                            lines = ','.join(lines)
                            error_list.append(_("Lines %s of the Excel file produced a split for the line %s.") % (lines, line_number))
                        else:
                            # if the product is the same: we update the corresponding line
                            file_line_proceed = []
                            for pol_line in pol_obj.browse(cr, uid, same_pol_line_nb, context):
                                # is a product similar between the file line and obj line?
                                overlapping_lines = import_obj.search(cr, uid, [('id', 'in', same_file_line_nb), ('product_id', '=', pol_line.product_id.id)])
                                if overlapping_lines and len(overlapping_lines) == 1 and overlapping_lines[0] not in file_line_proceed:
                                    import_values = import_obj.read(cr, uid, overlapping_lines)[0]
                                    file_line_number = import_values['file_line_number']
                                    pol_obj.write(cr, uid, pol_line.id, import_values)
                                    notif_list.append("Line %s of the Excel file updated the line %s with the product %s in common."
                                                      % (file_line_number, pol_line.line_number, pol_line.product_id.default_code))
                                    file_line_proceed.append(overlapping_lines[0])
                                    complete_lines += 1
                            # we ignore the file lines that doesn't correspond to any PO line for this product and this line_number
                            for line in import_obj.read(cr, uid, same_file_line_nb):
                                if not line['line_ignored_ok'] and line['id'] not in file_line_proceed:
                                    # the file_line_number is equal to the index of the line in file_values
                                    error_log += "Line %s in the Excel file was added to the file of the lines with errors\n" % (import_values['file_line_number'])
                                    data = file_values[line['file_line_number']].items()
                                    line_with_error.append([v for k,v in sorted(data, key=lambda tup: tup[0])])
                                    ignore_lines += 1
            error_log += '\n'.join(error_list)
            notif_log += '\n'.join(notif_list)
            if error_log:
                error_log = " ---------------------------------\n Reported errors for ignored lines : \n" + error_log
            if notif_log:
                notif_log = "--------------------------------- \n The following lines were modified: \n" + notif_log
            end_time = time.time()
            total_time = str(round(end_time-start_time)) + ' second(s)'
            message = ''' Importation completed in %s!
# of imported lines : %s
# of ignored lines: %s
%s

%s
    ''' % (total_time ,complete_lines, ignore_lines, error_log, notif_log)
            wizard_vals = {'message': message, 'state': 'done'}
            if line_with_error:
                file_to_export = self.export_file_with_error(cr, uid, ids, line_with_error=line_with_error, header_index=header_index)
                wizard_vals.update(file_to_export)
            self.write(cr, uid, ids, wizard_vals, context=context)
        except Exception, e:
            error_exception = ('%s' % e)
            self.write(cr, uid, ids, {'message': error_exception, 'state': 'draft'}, context=context)
        finally:
            cr.commit()
            cr.close()

    def import_file(self, cr, uid, ids, context=None):
        """
        Launch a thread for importing lines.
        """
        for wiz_read in self.read(cr, uid, ids, ['po_id', 'file']):
            po_id = wiz_read['po_id']
            if not wiz_read['file']:
                return self.write(cr, uid, ids, {'message': "Nothing to import"})
            try:
                fileobj = SpreadsheetXML(xmlstring=base64.decodestring(wiz_read['file']))
                # iterator on rows
                reader = fileobj.getRows()
                reader_iterator = iter(reader)
                # get first line
                first_row = next(reader_iterator)
                header_index = self.get_header_index(cr, uid, ids, first_row, error_list=[], line_num=0, context=context)
                context.update({'po_id': po_id, 'header_index': header_index})
                (res, res1) = self.check_header_values(cr, uid, ids, context, header_index)
                if not res1:
                    return False
            except osv.except_osv as osv_error:
                osv_value = osv_error.value
                osv_name = osv_error.name
                message = "%s: %s\n" % (osv_name, osv_value)
                return self.write(cr, uid, ids, {'message': message})
        thread = threading.Thread(target=self._import, args=(cr.dbname, uid, ids, context))
        thread.start()
        msg_to_return = _("""
Important, please do not update the Purchase Order %s
Import in progress, please leave this window open and press the button 'Update' when you think that the import is done.
Otherwise, you can continue to use Unifield.""" % self.pool.get('purchase.order').read(cr, uid, po_id, ['name'])['name'])
        return self.write(cr, uid, ids, {'message': msg_to_return, 'state': 'in_progress'}, context=context)

    def dummy(self, cr, uid, ids, context=None):
        """
        This button is only for updating the view.
        """
        if isinstance(ids, (int, long)):
            ids = [ids]
        purchase_obj = self.pool.get('purchase.order')
        for wiz_read in self.read(cr, uid, ids, ['po_id', 'state', 'file']):
            po_id = wiz_read['po_id']
            po_name = purchase_obj.read(cr, uid, po_id, ['name'])['name']
            if wiz_read['state'] != 'done':
                self.write(cr, uid, ids, {'message': ' Import in progress... \n Please wait that the import is finished before editing %s.' % po_name})
        return False

    def cancel(self, cr, uid, ids, context=None):
        '''
        Return to the initial view. I don't use the special cancel because when I open the wizard with target: crush, and I click on cancel (the special),
        I come back on the home page. Here, I come back on the PO on which I opened the wizard.
        '''
        if isinstance(ids, (int, long)):
            ids=[ids]
        for wiz_obj in self.read(cr, uid, ids, ['po_id']):
            po_id = wiz_obj['po_id']
        return {'type': 'ir.actions.act_window',
                'res_model': 'purchase.order',
                'view_type': 'form',
                'view_mode': 'form, tree',
                'target': 'crush',
                'res_id': po_id,
                'context': context,
                }

    def close_import(self, cr, uid, ids, context=None):
        '''
        Return to the initial view
        '''
        if isinstance(ids, (int, long)):
            ids=[ids]
        for wiz_obj in self.read(cr, uid, ids, ['po_id']):
            po_id = wiz_obj['po_id']
        return {'type': 'ir.actions.act_window',
                'res_model': 'purchase.order',
                'view_type': 'form',
                'view_mode': 'form, tree',
                'target': 'crush',
                'res_id': po_id,
                'context': context,
                }
    
wizard_import_po()


class wizard_export_po(osv.osv_memory):
    _name = 'wizard.export.po'
    _description = 'Export PO for integration'
    
    _columns = {
        'po_id': fields.many2one('purchase.order', string='PO'),
        'file': fields.binary(string='File to export', required=True, readonly=True),
        'filename': fields.char(size=128, string='Filename', required=True),
        'message': fields.char(size=256, string='Message', readonly=True),
    }
    
    def close_window(self, cr, uid, ids, context=None):
        '''
        Return to the initial view
        '''
        res_id = self.browse(cr, uid, ids[0], context=context).po_id.id
        
        return {'type': 'ir.actions.act_window',
                'res_model': 'purchase.order',
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'crush',
                'res_id': res_id}   
        
wizard_export_po()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
