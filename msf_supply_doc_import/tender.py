# -*- coding: utf-8 -*-

from osv import osv
from osv import fields
from tools.translate import _
import base64
from spreadsheet_xml.spreadsheet_xml import SpreadsheetXML


class tender(osv.osv):
    _inherit = 'tender'

    _columns = {
        'file_to_import': fields.binary(string='File to import', filters='*.xml', help='You can use the template of the export for the format that you need to use'),
    }

    def button_remove_lines(self, cr, uid, ids, context=None):
        '''
        Remove lines
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        vals = {}
        vals['tender_line_ids'] = []
        for line in self.browse(cr, uid, ids, context=context):
            line_browse_list = line.tender_line_ids
            for var in line_browse_list:
                vals['tender_line_ids'].append((2, var.id))
            self.write(cr, uid, ids, vals, context=context)
        return True

    def import_file(self, cr, uid, ids, context=None):
        '''
        Import lines from file
        '''
        if not context:
            context = {}

        product_obj = self.pool.get('product.product')
        uom_obj = self.pool.get('product.uom')
        obj_data = self.pool.get('ir.model.data')

        vals = {}
        vals['tender_line_ids'] = []
        text_error = ''

        obj = self.browse(cr, uid, ids, context=context)[0]
        if not obj.file_to_import:
            raise osv.except_osv(_('Error'), _('Nothing to import.'))

        fileobj = SpreadsheetXML(xmlstring=base64.decodestring(obj.file_to_import))
        
        # iterator on rows
        reader = fileobj.getRows()
        
        # ignore the first row
        line_num = 0
        reader.next()
        for row in reader:
            line_num += 1
            error_list = []
            to_correct_ok = False
            default_code = obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import','product_tbd')[1]
            
            product_code = row.cells[0].data
            if not product_code:
                to_correct_ok = True
                error_list.append('No Product Name')
            else:
                code_ids = product_obj.search(cr, uid, [('default_code', '=', product_code.strip())])
                if not code_ids or code_ids[0] == default_code:
                    to_correct_ok = True
                    error_list.append('The Product was not found in the list of the products.')
                else:
                    default_code = code_ids[0]
            
            product_qty = str(row.cells[2].data)
            if not product_qty:
                product_qty = 1
                to_correct_ok = True
                error_list.append('The Product Quantity was not set, we set it to 1 by default.')
            else:
                try:
                    float(product_qty)
                except ValueError:
                     error_list.append('The Product Quantity was not a number, we set it to 1 by default.')
                     to_correct_ok = True
                     product_qty = 1
            
            p_uom = row.cells[3].data
            if not p_uom:
                uom_id = obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import','uom_tbd')[1]
                to_correct_ok = True
                error_list.append('No product UoM was defined.')
            else:
                uom_ids = uom_obj.search(cr, uid, [('name', '=', p_uom.strip())], context=context)
                if not uom_ids:
                    uom_id = obj_data.get_object_reference(cr, uid, 'msf_supply_doc_import','uom_tbd')[1]
                    to_correct_ok = True
                    error_list.append('The UOM was not found.')
                else:
                    uom_id = uom_ids[0]
                    
            price_unit = str(row.cells[4].data)
            if not price_unit:
                price_unit = 1
                to_correct_ok = True
                error_list.append('The Price Unit was not set, we set it to 1 by default.')
            else:
                try:
                    float(price_unit)
                except ValueError:
                     error_list.append('The Price Unit was not a number, we set it to 1 by default.')
                     to_correct_ok = True
                     price_unit = 1
                
            to_write = {
                'line_number': line_num,
                'to_correct_ok': to_correct_ok, # the lines with to_correct_ok=True will be red
                'tender_id': obj.id,
                'product_id': default_code,
                'product_uom': uom_id,
                'qty': product_qty,
                'price_unit': price_unit,
            }
            
            vals['tender_line_ids'].append((0, 0, to_write))
            if error_list:
                text_error += 'Line '+str(line_num)+':'+ '\n'.join(error_list)
            
        # write tender line on tender
        self.write(cr, uid, ids, vals, context=context)
        
        view_id = obj_data.get_object_reference(cr, uid, 'tender_flow','tender_form')[1]
        
        if text_error:
            msg_to_return = _("The import of lines had errors, please correct the red lines below: %s")%text_error
        else:
            msg_to_return = _("All lines successfully imported")

        
        return self.log(cr, uid, obj.id, msg_to_return, context={'view_id': view_id,})
        
    def check_lines_to_fix(self, cr, uid, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        message = ''
        plural= ''
            
        for var in self.browse(cr, uid, ids, context=context):
            if var.tender_line_ids:
                for var in var.tender_line_ids:
                    if var.to_correct_ok:
                        line_num = var.line_number
                        if message:
                            message += ', '
                        message += str(line_num)
                        if len(message.split(',')) > 1:
                            plural = 's'
        if message:
            raise osv.except_osv(_('Warning !'), _('You need to correct the following line%s : %s')% (plural, message))
        else:
            self.log(cr, uid, var.id, _("There isn't error in import"), context=context)
        return True
        
tender()

class tender_line(osv.osv):
    '''
    override of tender_line class
    '''
    _inherit = 'tender.line'
    _description = 'Tender Line'
    _columns = {
        'to_correct_ok': fields.boolean('To correct'),
        'line_number': fields.integer('Line Number'),
    }

tender_line()
