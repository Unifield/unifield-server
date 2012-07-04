# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 TeMPO Consulting, MSF 
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
from mx.DateTime import *

from tools.translate import _

import time
import base64
import netsvc

import csv
from tempfile import TemporaryFile


class real_average_consumption(osv.osv):
    _name = 'real.average.consumption'
    _description = 'Real Average Consumption'
    
    def _get_nb_lines(self, cr, uid, ids, field_name, args, context=None):
        '''
        Returns the # of lines on the real average consumption
        '''
        res = {}
        
        for mrc in self.browse(cr, uid, ids, context=context):
            res[mrc.id] = len(mrc.line_ids)
            
        return res


    def unlink(self, cr, uid, ids, context=None):
        '''
        Display a message to the user if the report has been confirmed
        and stock moves has been generated
        '''
        for report in self.browse(cr, uid, ids, context=context):
            if report.created_ok and report.picking_id:
                if report.picking_id.state != 'cancel':
                    raise osv.except_osv(_('Error'), _('You cannot delete this report because stock moves has been generated and validated from this report !'))
                else:
                    for move in report.picking_id.move_lines:
                        if move.state != 'cancel':
                            raise osv.except_osv(_('Error'), _('You cannot delete this report because stock moves has been generated and validated from this report !'))

        return super(real_average_consumption, self).unlink(cr, uid, ids, context=context)

    def copy(self, cr, uid, ids, default=None, context=None):
        '''
        Unvalidate all lines of the duplicate report
        '''
        # Change default values
        if default is None:
            default = {}
        if context is None:
            context = {}
        if not 'picking_id' in default:
            default['picking_id'] = False
        if not 'valid_ok' in default:
            default['valid_ok'] = False

        default['name'] = self.pool.get('ir.sequence').get(cr, uid, 'consumption.report')

        # Copy the report
        res = super(real_average_consumption, self).copy(cr, uid, ids, default, context=context)

        # Unvalidate all lines of the report
        for report in self.browse(cr, uid, [res], context=context):
            lines = []
            for line in report.line_ids:
                lines.append(line.id)
            if lines:
                self.pool.get('real.average.consumption.line').write(cr, uid, lines, {'move_id': False}, context=context)

        # update created_ok at this end to disable _check qty on line
        self.write(cr, uid, res, {'created_ok': False})
        self.button_update_stock(cr, uid, res)
        return res

    
    _columns = {
        'name': fields.char(size=64, string='Reference'),
        'creation_date': fields.datetime(string='Creation date', required=1),
        'cons_location_id': fields.many2one('stock.location', string='Consumer location', domain=[('usage', '=', 'internal')], required=True),
        'activity_id': fields.many2one('stock.location', string='Activity', domain=[('usage', '=', 'customer')], required=1),
        'period_from': fields.date(string='Period from', required=True),
        'period_to': fields.date(string='Period to', required=True),
        'sublist_id': fields.many2one('product.list', string='List/Sublist'),
        'line_ids': fields.one2many('real.average.consumption.line', 'rac_id', string='Lines'),
        'picking_id': fields.many2one('stock.picking', string='Picking', readonly=True),
        'valid_ok': fields.boolean(string='Create and process out moves'),
        'created_ok': fields.boolean(string='Out moves created'),
        'nb_lines': fields.function(_get_nb_lines, method=True, type='integer', string='# lines', readonly=True,),
        'nomen_manda_0': fields.many2one('product.nomenclature', 'Main Type'),
        'nomen_manda_1': fields.many2one('product.nomenclature', 'Group'),
        'nomen_manda_2': fields.many2one('product.nomenclature', 'Family'),
        'nomen_manda_3': fields.many2one('product.nomenclature', 'Root'),
    }
    
    _defaults = {
        'name': lambda obj, cr, uid, context: obj.pool.get('ir.sequence').get(cr, uid, 'consumption.report'),
        'creation_date': lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
        'activity_id': lambda obj, cr, uid, context: obj.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock', 'stock_location_internal_customers')[1],
        'period_to': lambda *a: time.strftime('%Y-%m-%d'),
        'valid_ok': lambda *a: True,
    }

    _sql_constraints = [
        ('date_coherence', "check (period_from <= period_to)", '"Period from" must be less than or equal to "Period to"'),
    ]

    def button_update_stock(self, cr, uid, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        to_update = []
        for line in self.read(cr, uid, ids, ['created_ok','line_ids']):
            if line['created_ok']:
                continue
            to_update += line['line_ids']

        if to_update:
            self.pool.get('real.average.consumption.line')._check_qty(cr, uid, to_update, {'noraise': True})
        return True
    
    def save_and_process(self, cr, uid, ids, context=None):
        '''
        Returns the wizard to confirm the process of all lines
        '''
        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'consumption_calculation', 'real_average_consumption_confirmation_view')[1],
        
        return {'type': 'ir.actions.act_window',
                'res_model': 'real.average.consumption',
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'view_id': [view_id],
                'res_id': ids[0],
                }
        
    def process_moves(self, cr, uid, ids, context=None):
        '''
        Creates all stock moves according to the report lines
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
        if context is None:
            context = {}
        
        move_obj = self.pool.get('stock.move')
        line_obj = self.pool.get('real.average.consumption.line')
        wf_service = netsvc.LocalService("workflow")
        
        reason_type_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_consumption_report')[1]

        move_ids = []
       
        # check and update lines
        for rac in self.browse(cr, uid, ids, context=context):
            if not rac.valid_ok:
                raise osv.except_osv(_('Error'), _('Please check the last checkbox before processing the lines'))
            if DateFrom(rac.period_to) > now():
                raise osv.except_osv(_('Error'), _('"Period to" can\'t be in the future.'))

            if rac.created_ok:
                return {'type': 'ir.actions.close_window'}
            line_obj._check_qty(cr, uid, [x.id for x in rac.line_ids])

        partner_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.partner_id.id
        addresses = self.pool.get('res.partner').address_get(cr, uid, partner_id, ['delivery', 'default'])
        address_id = addresses.get('delivery') or addresses.get('default')

        for rac in self.browse(cr, uid, ids, context=context):
            date = '%s %s'%(rac.period_to, time.strftime('%H:%M:%S'))
            picking_id = self.pool.get('stock.picking').create(cr, uid, {'name': 'OUT-%s' % rac.name,
                                                                         'origin': rac.name,
                                                                         'partner_id': partner_id,
                                                                         'address_id': address_id,
                                                                         'type': 'out',
                                                                         'subtype': 'standard',
                                                                         'state': 'auto',
                                                                         'move_type': 'one',
                                                                         'invoice_state': 'none',
                                                                         'date': date,
                                                                         'reason_type_id': reason_type_id}, context=context)
            
            self.write(cr, uid, [rac.id], {'created_ok': True}, context=context)
            for line in rac.line_ids:
                move_id = move_obj.create(cr, uid, {'name': '%s/%s' % (rac.name, line.product_id.name),
                                                    'picking_id': picking_id,
                                                    'product_uom': line.uom_id.id,
                                                    'product_id': line.product_id.id,
                                                    'date_expected': date,
                                                    'date': date,
                                                    'product_qty': line.consumed_qty,
                                                    'prodlot_id': line.prodlot_id.id,
                                                    'expiry_date': line.expiry_date,
                                                    'location_id': rac.cons_location_id.id,
                                                    'location_dest_id': rac.activity_id.id,
                                                    'state': 'done',
                                                    'reason_type_id': reason_type_id})
                move_ids.append(move_id)
                line_obj.write(cr, uid, [line.id], {'move_id': move_id})

            self.write(cr, uid, [rac.id], {'picking_id': picking_id}, context=context)

            # Confirm the picking
            wf_service.trg_validate(uid, 'stock.picking', picking_id, 'button_confirm', cr)

            # Confirm all moves
            move_obj.action_done(cr, uid, move_ids, context=context)
            #move_obj.write(cr, uid, move_ids, {'date': rac.period_to}, context=context)
            
        
        return {'type': 'ir.actions.act_window',
                'res_model': 'real.average.consumption',
                'view_type': 'form',
                'view_mode': 'form,tree',
                'target': 'dummy',
                'res_id': ids[0],
                }
        
    def import_rac(self, cr, uid, ids, context=None):
        '''
        Launches the wizard to import lines from a file
        '''
        if context is None:
            context = {}
        context.update({'active_id': ids[0]})
        
        return {'type': 'ir.actions.act_window',
                'res_model': 'wizard.import.rac',
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'context': context,
                }
        
    def export_rac(self, cr, uid, ids, context=None):
        '''
        Creates a CSV file and launches the wizard to save it
        '''
        if context is None:
            context = {}
        rac = self.browse(cr, uid, ids[0], context=context)
        
        outfile = TemporaryFile('w+')
        writer = csv.writer(outfile, quotechar='"', delimiter=',')
        writer.writerow(['Product reference', 'Product name', 'Product UoM', 'Batch Number', 'Expiry Date', 'Consumed Qty', 'Remark'])
        
        for line in rac.line_ids:
            writer.writerow([line.product_id.default_code and line.product_id.default_code.encode('utf-8'), line.product_id.name and line.product_id.name.encode('utf-8'), line.uom_id.name and line.uom_id.name.encode('utf-8'), line.prodlot_id and line.prodlot_id.name.encode('utf-8') or '', line.expiry_date and strptime(line.expiry_date,'%Y-%m-%d').strftime('%d/%m/%Y') or '',line.consumed_qty, line.remark and line.remark.encode('utf-8') or ''])
        outfile.seek(0)    
        file = base64.encodestring(outfile.read())
        outfile.close()
        
        export_id = self.pool.get('wizard.export.rac').create(cr, uid, {'rac_id': ids[0], 'file': file, 
                                                                        'filename': 'rac_%s.csv' % (rac.cons_location_id.name.replace(' ', '_')), 
                                                                        'message': 'The RAC lines has been exported. Please click on Save As button to download the file'})
        
        return {'type': 'ir.actions.act_window',
                'res_model': 'wizard.export.rac',
                'res_id': export_id,
                'view_mode': 'form',
                'view_type': 'form',
                'target': 'new',
                }
        
    def fill_lines(self, cr, uid, ids, context=None):
        '''
        Fill all lines according to defined nomenclature level and sublist
        '''
        if context is None:
            context = {}
        self.write(cr, uid, ids, {'created_ok': True})    
        for report in self.browse(cr, uid, ids, context=context):
            product_ids = []
            products = []

            nom = False
            # Get all products for the defined nomenclature
            if report.nomen_manda_3:
                nom = report.nomen_manda_3.id
                field = 'nomen_manda_3'
            elif report.nomen_manda_2:
                nom = report.nomen_manda_2.id
                field = 'nomen_manda_2'
            elif report.nomen_manda_1:
                nom = report.nomen_manda_1.id
                field = 'nomen_manda_1'
            elif report.nomen_manda_0:
                nom = report.nomen_manda_0.id
                field = 'nomen_manda_0'
            if nom:
                product_ids.extend(self.pool.get('product.product').search(cr, uid, [(field, '=', nom)], context=context))

            # Get all products for the defined list
            if report.sublist_id:
                for line in report.sublist_id.product_ids:
                    product_ids.append(line.name.id)

            # Check if products in already existing lines are in domain
            products = []
            for line in report.line_ids:
                if line.product_id.id in product_ids:
                    products.append(line.product_id.id)
                else:
                    self.pool.get('real.average.consumption.line').unlink(cr, uid, line.id, context=context)

            for product in self.pool.get('product.product').browse(cr, uid, product_ids, context=context):
                # Check if the product is not already on the report
                if product.id not in products:
                    batch_mandatory = product.batch_management or product.perishable
                    date_mandatory = not product.batch_management and product.perishable
                    values = {'product_id': product.id,
                              'uom_id': product.uom_id.id,
                              'consumed_qty': 0.00,
                              'batch_mandatory': batch_mandatory,
                              'date_mandatory': date_mandatory,
                              'rac_id': report.id,}
                    v = self.pool.get('real.average.consumption.line').product_onchange(cr, uid, [], product.id, report.cons_location_id.id,
                                                                                        product.uom_id.id, False, context=context)['value']
                    values.update(v)
                    if batch_mandatory or date_mandatory:
                        values.update({'remark': 'You must assign a batch number'})
                    self.pool.get('real.average.consumption.line').create(cr, uid, values)
        
        self.write(cr, uid, ids, {'created_ok': False})    
        return {'type': 'ir.actions.act_window',
                'res_model': 'real.average.consumption',
                'view_type': 'form',
                'view_mode': 'form',
                'res_id': ids[0],
                'target': 'dummy',
                'context': context}
        
    def get_nomen(self, cr, uid, id, field):
        return self.pool.get('product.nomenclature').get_nomen(cr, uid, self, id, field, context={'withnum': 1})

    def onChangeSearchNomenclature(self, cr, uid, id, position, type, nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, num=True, context=None):
        return self.pool.get('product.product').onChangeSearchNomenclature(cr, uid, 0, position, type, nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, False, context={'withnum': 1})
    
    def write(self, cr, uid, ids, vals, context=None):
        if vals.get('sublist_id',False):
            vals.update({'nomen_manda_0':False,'nomen_manda_1':False,'nomen_manda_2':False,'nomen_manda_3':False})
        if vals.get('nomen_manda_0',False):
            vals.update({'sublist_id':False})
        ret = super(real_average_consumption, self).write(cr, uid, ids, vals, context=context)
        return ret
    
real_average_consumption()


class real_average_consumption_line(osv.osv):
    _name = 'real.average.consumption.line'
    _description = 'Real average consumption line'
    _rec_name = 'product_id'
    _order = 'id desc'

    def _get_checks_all(self, cr, uid, ids, name, arg, context=None):
        result = {}
        for id in ids:
            result[id] = {'batch_number_check': False, 'expiry_date_check': False, 'type_check': False}
            
        for out in self.browse(cr, uid, ids, context=context):
            if out.product_id:
                result[out.id]['batch_number_check'] = out.product_id.batch_management
                result[out.id]['expiry_date_check'] = out.product_id.perishable
            
        return result

    def _get_qty(self, cr, uid, product, lot, location, uom):
        if not product and not lot:
            return False
        context = {'location_id': location, 'location': location, 'uom': uom, 'compute_child': False}
        if not lot:
            return self.pool.get('product.product').read(cr, uid, product, ['qty_available'], context=context)['qty_available']
            
        return self.pool.get('stock.production.lot').read(cr, uid, lot, ['stock_available'], context=context)['stock_available']

    def _check_qty(self, cr, uid, ids, context=None):
       
        if context is None:
            context = {}
        for obj in self.browse(cr, uid, ids):
            if obj.rac_id.created_ok:
                continue

            location = obj.rac_id.cons_location_id.id
            prodlot_id = None
            expiry_date = None

            batch_mandatory = obj.product_id.batch_management or obj.product_id.perishable
            date_mandatory = not obj.product_id.batch_management and obj.product_id.perishable
        
            if batch_mandatory:
                if not obj.prodlot_id:
                    raise osv.except_osv(_('Error'), 
                        _("Product: %s, You must assign a Batch Number")%(obj.product_id.name,))

                prodlot_id = obj.prodlot_id.id
                expiry_date = obj.prodlot_id.life_date

#            if date_mandatory:
#                prod_ids = self.pool.get('stock.production.lot').search(cr, uid, [('life_date', '=', obj.expiry_date),
#                                                    ('type', '=', 'internal'),
#                                                    ('product_id', '=', obj.product_id.id)])
#                expiry_date = obj.expiry_date
#                if not prod_ids:
#                    raise osv.except_osv(_('Error'), 
#                        _("Product: %s, no internal batch found for expiry (%s)")%(obj.product_id.name, obj.expiry_date))
#                prodlot_id = prod_ids[0]

            product_qty = self._get_qty(cr, uid, obj.product_id.id, prodlot_id, location, obj.uom_id and obj.uom_id.id)

            if prodlot_id and obj.consumed_qty > product_qty and not context.get('noraise'):
                raise osv.except_osv(_('Error'), 
                    _("Product: %s, Qty Consumed (%s) can't be greater than the Indicative Stock (%s)")%(obj.product_id.name, obj.consumed_qty, product_qty))
            
            #recursion: can't use write
            cr.execute('UPDATE '+self._table+' SET product_qty=%s, batch_mandatory=%s, date_mandatory=%s, prodlot_id=%s, expiry_date=%s  where id=%s', (product_qty, batch_mandatory, date_mandatory, prodlot_id, expiry_date, obj.id))

        return True

    _columns = {
        'product_id': fields.many2one('product.product', string='Product', required=True),
        'uom_id': fields.many2one('product.uom', string='UoM', required=True),
        'product_qty': fields.float(digits=(16,2), string='Indicative stock', readonly=True),
        'consumed_qty': fields.float(digits=(16,2), string='Qty consumed', required=True),
        'batch_number_check': fields.function(_get_checks_all, method=True, string='Batch Number Check', type='boolean', readonly=True, multi="m"),
        'expiry_date_check': fields.function(_get_checks_all, method=True, string='Expiry Date Check', type='boolean', readonly=True, multi="m"),
        'prodlot_id': fields.many2one('stock.production.lot', string='Batch number'),
        'batch_mandatory': fields.boolean(string='BM'),
        'expiry_date': fields.date(string='Expiry date'),
        'date_mandatory': fields.boolean(string='DM'),
        'remark': fields.char(size=256, string='Remark'),
        'move_id': fields.many2one('stock.move', string='Move'),
        'rac_id': fields.many2one('real.average.consumption', string='RAC', ondelete='cascade'),
    }

    _constraints = [
        (_check_qty, "The Qty Consumed can't be greater than the Indicative Stock", ['consumed_qty']),
    ]

    _sql_constraints = [
        ('unique_lot_poduct', "unique(product_id, prodlot_id, rac_id)", 'The couple product, batch number has to be unique'),
    ]


    def change_expiry(self, cr, uid, id, expiry_date, product_id, location_id, uom, remark=False, context=None):
        '''
        expiry date changes, find the corresponding internal prod lot
        '''
        if context is None:
            context = {}
        prodlot_obj = self.pool.get('stock.production.lot')
        result = {'value':{}}
        context.update({'location': location_id})
       
        if expiry_date and product_id:
            if remark and remark == 'You must assign a batch number':
                result['value']['remark'] = ''
            prod_ids = prodlot_obj.search(cr, uid, [('life_date', '=', expiry_date),
                                                    ('type', '=', 'internal'),
                                                    ('product_id', '=', product_id)], context=context)
            if not prod_ids:
                # display warning
                result['warning'] = {'title': _('Error'),
                                     'message': _('The selected Expiry Date does not exist in the system.')}
                # clear date
                result['value'].update(expiry_date=False, prodlot_id=False)
            else:
                # return first prodlot
                result = self.change_prodlot(cr, uid, id, product_id, prod_ids[0], expiry_date, location_id, uom, context={})
                result.setdefault('value',{}).update(prodlot_id=prod_ids[0])
                if remark and remark == 'You must assign a batch number':
                    result['value']['remark'] = ''
                return result
                
        else:
            # clear expiry date, we clear production lot
            result['value'].update(prodlot_id=False)
   
        context.update(uom=uom)
        context.update({'compute_child': False})
        product = self.pool.get('product.product').browse(cr, uid, product_id, context=context)
        result['value'].update({'product_qty': product.qty_available})
        
        return result

    def change_qty(self, cr, uid, ids, qty, product_id, prodlot_id, location, uom, context=None):
        if context is None:
            context = {}
        stock_qty = self._get_qty(cr, uid, product_id, prodlot_id, location, uom)
        warn_msg = {'title': _('Error'), 'message': _("The Qty Consumed is greater than the Indicative Stock")}
        if uom:
            new_qty = self.pool.get('product.uom')._compute_qty(cr, uid, uom, qty, uom)
            if new_qty != qty:
                warn_msg = {
                    'title': _('Error'), 
                    'message': _("The Qty Consumed %s and rounding uom qty %s are not equal !")%(qty, new_qty)
                }
                return {'warning': warn_msg, 'value': {'consumed_qty': 0}}

        if prodlot_id and qty > stock_qty:
            return {'warning': warn_msg, 'value': {'consumed_qty': 0}}
        if qty > stock_qty:
            return {'warning': warn_msg}
        return {}

    def change_prodlot(self, cr, uid, ids, product_id, prodlot_id, expiry_date, location_id, uom, remark=False, context=None):
        '''
        Set the expiry date according to the prodlot
        '''
        if context is None:
            context = {}
        res = {'value': {}}
        context.update({'location': location_id, 'uom': uom})
        if prodlot_id and not expiry_date:
            if remark and remark == 'You must assign a batch number':
                res['value']['remark'] = ''
            res['value'].update({'expiry_date': self.pool.get('stock.production.lot').browse(cr, uid, prodlot_id, context=context).life_date})
        elif not prodlot_id and expiry_date:
            res['value'].update({'expiry_date': False})

        if not prodlot_id:
            context.update({'compute_child': False})
            product_qty = self.pool.get('product.product').browse(cr, uid, product_id, context=context).qty_available
        else:
            if remark and remark == 'You must assign a batch number':
                res['value']['remark'] = ''
            context.update({'location_id': location_id})
            product_qty = self.pool.get('stock.production.lot').browse(cr, uid, prodlot_id, context=context).stock_available
        res['value'].update({'product_qty': product_qty})

        return res
   
    def uom_onchange(self, cr, uid, ids, product_id, location_id=False, uom=False, lot=False, context=None):
        if context is None:
            context = {}
        qty_available = 0
        d = {}
        if uom and product_id:
            qty_available = self._get_qty(cr, uid, product_id, lot, location_id, uom)

        if not uom and product_id:
            product = self.pool.get('product.product').browse(cr, uid, product_id, context=context)
            d['uom_id'] = [('category_id', '=', product.uom_id.category_id.id)]

        return {'value': {'product_qty': qty_available}, 'domain': d}

    def product_onchange(self, cr, uid, ids, product_id, location_id=False, uom=False, lot=False, context=None):
        '''
        Set the product uom when the product change
        '''
        if context is None:
            context = {}
        v = {'batch_mandatory': False, 'date_mandatory': False}
        d = {'uom_id': []} 
        if product_id:
            if location_id:
                context.update({'location': location_id, 'uom': uom})

            context.update({'compute_child': False})
            product = self.pool.get('product.product').browse(cr, uid, product_id, context=context)
            qty_available = product.qty_available
                
            if product.batch_management or product.perishable:
                v.update({'batch_mandatory': True})
            if not product.batch_management and product.perishable:
                v.update({'date_mandatory': True})

            uom = product.uom_id.id
            v.update({'uom_id': uom})
            d['uom_id'] = [('category_id', '=', product.uom_id.category_id.id)]
            if location_id:
                v.update({'product_qty': qty_available})
        else:
            v.update({'uom_id': False, 'product_qty': 0.00, 'prodlot_id': False, 'expiry_date': False, 'consumed_qty': 0.00})
        
        return {'value': v, 'domain': d}
    
real_average_consumption_line()


class monthly_review_consumption(osv.osv):
    _name = 'monthly.review.consumption'
    _description = 'Monthly review consumption'
    _rec_name = 'creation_date'
    
    def _get_nb_lines(self, cr, uid, ids, field_name, args, context=None):
        '''
        Returns the # of lines on the monthly review consumption
        '''
        res = {}
        
        for mrc in self.browse(cr, uid, ids, context=context):
            res[mrc.id] = len(mrc.line_ids)
            
        return res
    
    _columns = {
        'creation_date': fields.date(string='Creation date'),
        'cons_location_id': fields.char(size=256, string='Location', readonly=True),
        'period_from': fields.date(string='Period from', required=True),
        'period_to': fields.date(string='Period to', required=True),
        'sublist_id': fields.many2one('product.list', string='List/Sublist'),
        'nomen_id': fields.many2one('product.nomenclature', string='Products\' nomenclature level'),
        'line_ids': fields.one2many('monthly.review.consumption.line', 'mrc_id', string='Lines'),
        'nb_lines': fields.function(_get_nb_lines, method=True, type='integer', string='# lines', readonly=True,),
        'nomen_manda_0': fields.many2one('product.nomenclature', 'Main Type'),
        'nomen_manda_1': fields.many2one('product.nomenclature', 'Group'),
        'nomen_manda_2': fields.many2one('product.nomenclature', 'Family'),
        'nomen_manda_3': fields.many2one('product.nomenclature', 'Root'),
    }
    
    _defaults = {
        'period_to': lambda *a: (DateFrom(time.strftime('%Y-%m-%d')) + RelativeDateTime(months=1, day=1, days=-1)).strftime('%Y-%m-%d'),
        'creation_date': lambda *a: time.strftime('%Y-%m-%d'),
        'cons_location_id': lambda *a: 'MSF Instance',
    }

    def period_change(self, cr, uid, ids, period_from, period_to, context=None):
        '''
        Get the first day of month and the last day
        '''
        res = {}

        if period_from:
            res.update({'period_from': (DateFrom(period_from) + RelativeDateTime(day=1)).strftime('%Y-%m-%d')})
        if period_to:
            res.update({'period_to': (DateFrom(period_to) + RelativeDateTime(months=1, day=1, days=-1)).strftime('%Y-%m-%d')})

        return {'value': res}
    
    def import_fmc(self, cr, uid, ids, context=None):
        '''
        Launches the wizard to import lines from a file
        '''
        if context is None:
            context = {}
        context.update({'active_id': ids[0]})
        
        return {'type': 'ir.actions.act_window',
                'res_model': 'wizard.import.fmc',
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'context': context,
                }
        
    def export_fmc(self, cr, uid, ids, context=None):
        '''
        Creates a CSV file and launches the wizard to save it
        '''
        if context is None:
            context = {}
        fmc = self.browse(cr, uid, ids[0], context=context)
        
        outfile = TemporaryFile('w+')
        writer = csv.writer(outfile, quotechar='"', delimiter=',')
        writer.writerow(['Product reference', 'Product name', 'AMC', 'FMC', 'Valid until'])
        
        for line in fmc.line_ids:
            writer.writerow([line.name.default_code and line.name.default_code.encode('utf-8'), line.name.name and line.name.name.encode('utf-8'), line.amc, line.fmc, line.valid_until or ''])
        outfile.seek(0)    
        file = base64.encodestring(outfile.read())
        outfile.close()
        
        export_id = self.pool.get('wizard.export.fmc').create(cr, uid, {'fmc_id': ids[0], 'file': file, 
                                                                        'filename': 'fmc_%s.csv' % (time.strftime('%Y_%m_%d')), 
                                                                        'message': 'The FMC lines has been exported. Please click on Save As button to download the file'})
        
        return {'type': 'ir.actions.act_window',
                'res_model': 'wizard.export.fmc',
                'res_id': export_id,
                'view_mode': 'form',
                'view_type': 'form',
                'target': 'new',
                }
        
    def fill_lines(self, cr, uid, ids, context=None):
        '''
        Fill all lines according to defined nomenclature level and sublist
        '''
        if context is None:
            context = {}
        line_obj = self.pool.get('monthly.review.consumption.line')
        for report in self.browse(cr, uid, ids, context=context):
            product_ids = []
            products = []
            # Get all products for the defined nomenclature
            nom = False
            field = False
            if report.nomen_manda_3:
                nom = report.nomen_manda_3.id
                field = 'nomen_manda_3'
            elif report.nomen_manda_2:
                nom = report.nomen_manda_2.id
                field = 'nomen_manda_2'
            elif report.nomen_manda_1:
                nom = report.nomen_manda_1.id
                field = 'nomen_manda_1'
            elif report.nomen_manda_0:
                nom = report.nomen_manda_0.id
                field = 'nomen_manda_0'
            if nom:
                product_ids.extend(self.pool.get('product.product').search(cr, uid, [(field, '=', nom)], context=context))
            
            # Get all products for the defined list
            if report.sublist_id:
                for line in report.sublist_id.product_ids:
                    product_ids.append(line.name.id)
                    
            # Check if products in already existing lines are in domain
            products = []
            for line in report.line_ids:
                if line.name.id in product_ids:
                    products.append(line.name.id)
                else:
                    self.pool.get('monthly.review.consumption.line').unlink(cr, uid, line.id, context=context)

            amc_context = context.copy()
            if amc_context.get('from_date', False):
                from_date = (DateFrom(amc_context.get('from_date')) + RelativeDateTime(day=1)).strftime('%Y-%m-%d')
                amc_context.update({'from_date': from_date})
                                               
            if amc_context.get('to_date', False):
                to_date = (DateFrom(amc_context.get('to_date')) + RelativeDateTime(months=1, day=1, days=-1)).strftime('%Y-%m-%d')
                amc_context.update({'to_date': to_date})
                    
            for product in self.pool.get('product.product').browse(cr, uid, product_ids, context=context):
                # Check if the product is not already on the report
                if product.id not in products:
                    products.append(product.id)
                    amc = self.pool.get('product.product').compute_amc(cr, uid, product.id, context=amc_context)
                    last_fmc_reviewed = False
                    line_ids = line_obj.search(cr, uid, [('name', '=', product.id), ('valid_ok', '=', True)], order='valid_until desc, id desc', context=context)
                    if line_ids:
                        for line in line_obj.browse(cr, uid, [line_ids[0]], context=context):
                            last_fmc_reviewed = line.mrc_id.creation_date
                    self.pool.get('monthly.review.consumption.line').create(cr, uid, {'name': product.id,
                                                                                      'amc': amc,
                                                                                      'fmc': amc,
                                                                                      'fmc2': amc,
                                                                                      'last_reviewed': last_fmc_reviewed,
                                                                                      'last_reviewed2': last_fmc_reviewed,
                                                                                      'mrc_id': report.id})
        
        return {'type': 'ir.actions.act_window',
                'res_model': 'monthly.review.consumption',
                'view_type': 'form',
                'view_mode': 'form',
                'res_id': ids[0],
                'target': 'dummy',
                'context': context}


    def valid_multiple_lines(self, cr, uid, ids, context=None):
        '''
        Validate multiple lines
        '''
        if context is None:
            context = {}
        for report in self.browse(cr, uid, ids, context=context):
            for line in report.line_ids:
                if not line.valid_ok:
                    self.pool.get('monthly.review.consumption.line').valid_line(cr, uid, line.id, context=context)

        return {'type': 'ir.actions.act_window',
                'res_model': 'monthly.review.consumption',
                'view_type': 'form',
                'view_mode': 'form',
                'res_id': ids[0],
                'target': 'dummy',
                'context': context}
    
    def write(self, cr, uid, ids, vals, context=None):
        if vals.get('sublist_id',False):
            vals.update({'nomen_manda_0':False,'nomen_manda_1':False,'nomen_manda_2':False,'nomen_manda_3':False})
        if vals.get('nomen_manda_0',False):
            vals.update({'sublist_id':False})
        ret = super(monthly_review_consumption, self).write(cr, uid, ids, vals, context=context)
        return ret
    
    def onChangeSearchNomenclature(self, cr, uid, id, position, type, nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, num=True, context=None):
        return self.pool.get('product.product').onChangeSearchNomenclature(cr, uid, 0, position, type, nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, False, context={'withnum': 1})
    
    def get_nomen(self, cr, uid, id, field):
        return self.pool.get('product.nomenclature').get_nomen(cr, uid, self, id, field, context={'withnum': 1})
    
monthly_review_consumption()


class monthly_review_consumption_line(osv.osv):
    _name = 'monthly.review.consumption.line'
    _description = 'Monthly review consumption line'
    
    def _get_amc(self, cr, uid, ids, field_name, arg, ctx=None):
        '''
        Calculate the product AMC for the period
        '''
        if ctx is None:
            ctx = {}
        context = ctx.copy()
        res = {}
        
        for line in self.browse(cr, uid, ids, context=context):
            context.update({'from_date': line.mrc_id.period_from, 'to_date': line.mrc_id.period_to})
            if context.get('from_date', False):
                from_date = (DateFrom(context.get('from_date')) + RelativeDateTime(day=1)).strftime('%Y-%m-%d')
                context.update({'from_date': from_date})
                                               
            if context.get('to_date', False):
                to_date = (DateFrom(context.get('to_date')) + RelativeDateTime(months=1, day=1, days=-1)).strftime('%Y-%m-%d')
                context.update({'to_date': to_date})
                    
            res[line.id] = self.pool.get('product.product').compute_amc(cr, uid, line.name.id, context=context)
            
        return res
    
    def _get_last_fmc(self, cr, uid, ids, field_name, args, context=None):
        '''
        Returns the last fmc date
        '''
        if context is None:
            context = {}
        res = {}
        
        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = self.product_onchange(cr, uid, line.id, line.name.id, line.mrc_id.id, context=context).get('value', {}).get('last_reviewed', None)
            
        return res

    def create(self, cr, uid, vals, context=None):
        if context is None:
            context = {}
        if 'fmc2' in vals:
            vals.update({'fmc': vals.get('fmc2')})
        if 'last_reviewed2' in vals:
            vals.update({'last_reviewed': vals.get('last_reviewed2')})

        if vals.get('valid_ok') and not vals.get('last_reviewed'):
            vals.update({'last_reviewed': time.strftime('%Y-%m-%d'),
                         'last_reviewed2': time.strftime('%Y-%m-%d')})

        return super(monthly_review_consumption_line, self).create(cr, uid, vals, context=context)

    def write(self, cr, uid, ids, vals, context=None):
        if context is None:
            context = {}
        if 'fmc2' in vals:
            vals.update({'fmc': vals.get('fmc2')})
        if 'last_reviewed2' in vals:
            vals.update({'last_reviewed': vals.get('last_reviewed2')})

        if vals.get('valid_ok') and not vals.get('last_reviewed'):
            vals.update({'last_reviewed': time.strftime('%Y-%m-%d'),
                         'last_reviewed2': time.strftime('%Y-%m-%d')})

        return super(monthly_review_consumption_line, self).write(cr, uid, ids, vals, context=context)
    
    _columns = {
        'name': fields.many2one('product.product', string='Product', required=True),
        'amc': fields.function(_get_amc, string='AMC', method=True, readonly=True, store=True),
        'fmc': fields.float(digits=(16,2), string='FMC'),
        'fmc2': fields.float(digits=(16,2), string='FMC (hidden)'),
        #'last_reviewed': fields.function(_get_last_fmc, method=True, type='date', string='Last reviewed on', readonly=True, store=True),
        'last_reviewed': fields.date(string='Last reviewed on', readonly=True),
        'last_reviewed2': fields.date(string='Last reviewed on (hidden)'),
        'valid_until': fields.date(string='Valid until'),
        'valid_ok': fields.boolean(string='Validated', readonly=False),
        'mrc_id': fields.many2one('monthly.review.consumption', string='MRC', required=True, ondelete='cascade'),
        'mrc_creation_date': fields.related('mrc_id', 'creation_date', type='date', store=True),
    }
    
    def valid_line(self, cr, uid, ids, context=None):
        '''
        Valid the line and enter data in product form
        '''
        if not context:
            context = {}
            
        if isinstance(ids, (int, long)):
            ids = [ids]
                
        for line in self.browse(cr, uid, ids, context=context):
            if line.valid_ok:
                raise osv.except_osv(_('Error'), _('The line is already validated !'))
            
            self.write(cr, uid, [line.id], {'valid_ok': True, 
                                            'last_reviewed': time.strftime('%Y-%m-%d'),
                                            'last_reviewed2': time.strftime('%Y-%m-%d')}, context=context)
            
        return
    
    def display_graph(self, cr, uid, ids, context=None):
        '''
        Display the graph view of the line
        '''
        raise osv.except_osv('Error !', 'Not implemented yet !')

    def fmc_change(self, cr, uid, ids, amc, fmc, product_id, context=None):
        '''
        Valid the line if the FMC is manually changed
        '''
        if context is None:
            context = {}
        res = {}

        if fmc != amc:
            res.update({'valid_ok': True, 'last_reviewed': time.strftime('%Y-%m-%d'), 'fmc2': fmc, 'last_reviewed2': time.strftime('%Y-%m-%d')})
        else:
            last_fmc_reviewed = False
            domain = [('name', '=', product_id), ('valid_ok', '=', True)]
            line_ids = self.search(cr, uid, domain, order='valid_until desc, mrc_creation_date desc', context=context)
            
            if line_ids:
                for line in self.browse(cr, uid, [line_ids[0]], context=context):
                    last_fmc_reviewed = line.mrc_id.creation_date

            res.update({'last_reviewed': last_fmc_reviewed, 'last_reviewed2': last_fmc_reviewed, 'fmc2': fmc})

        return {'value': res}
    
    def product_onchange(self, cr, uid, ids, product_id, mrc_id=False, from_date=False, to_date=False, context=None):
        '''
        Fill data in the line
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]

        if not context:
            context = {}

        # Compute the AMC on the period of the consumption report
        context.update({'from_date': from_date, 'to_date': to_date})
        
        product_obj = self.pool.get('product.product')
        line_obj = self.pool.get('monthly.review.consumption.line')
        
        last_fmc_reviewed = False
        
        if not product_id:
            return {'value': {'amc': 0.00,
                              'fmc': 0.00,
                              'fmc2': 0.00,
                              'last_reviewed2': 0.00,
                              'last_reviewed': None,
                              'valid_until': False,
                              'valid_ok': False}}
        
        domain = [('name', '=', product_id), ('valid_ok', '=', True)]
        
        line_ids = line_obj.search(cr, uid, domain, order='valid_until desc, mrc_creation_date desc', context=context)
            
        if line_ids:
            for line in self.browse(cr, uid, [line_ids[0]], context=context):
                last_fmc_reviewed = line.mrc_id.creation_date

        if context.get('from_date', False):
            from_date = (DateFrom(context.get('from_date')) + RelativeDateTime(day=1)).strftime('%Y-%m-%d')
            context.update({'from_date': from_date})
                                               
        if context.get('to_date', False):
            to_date = (DateFrom(context.get('to_date')) + RelativeDateTime(months=1, day=1, days=-1)).strftime('%Y-%m-%d')
            context.update({'to_date': to_date})
                
        amc = product_obj.compute_amc(cr, uid, product_id, context=context)
        return {'value': {'amc': amc,
                          'fmc': amc,
                          'fmc2': amc,
                          'last_reviewed': last_fmc_reviewed,
                          'last_reviewed2': last_fmc_reviewed,
                          'valid_until': False,
                          'valid_ok': False}}
        
    
monthly_review_consumption_line()


class product_product(osv.osv):
    _name = 'product.product'
    _inherit = 'product.product'
    
    def _compute_fmc(self, cr, uid, ids, field_name, args, context=None):
        '''
        Returns the last value of the FMC
        '''
        if not context:
            context = {}
            
        res = {}
        #fmc_obj = self.pool.get('monthly.review.consumption')
        fmc_line_obj = self.pool.get('monthly.review.consumption.line')
            
        # Search all Review report for locations
        #fmc_ids = fmc_obj.search(cr, uid, [], order='period_to desc, creation_date desc', limit=1, context=context)
        
        for product in ids:
            res[product] = 0.00
            
            # Search all validated lines with the product
            #line_ids = fmc_line_obj.search(cr, uid, [('name', '=', product), ('valid_ok', '=', True), ('mrc_id', 'in', fmc_ids)], context=context)
            line_ids = fmc_line_obj.search(cr, uid, [('name', '=', product), ('valid_ok', '=', True)], order='last_reviewed desc, mrc_id desc', limit=1, context=context)
            
            # Get the last created line
            for line in fmc_line_obj.browse(cr, uid, line_ids, context=context):
                res[product] = line.fmc
        
        return res
    
    def compute_mac(self, cr, uid, ids, field_name, args, context=None):
        '''
        Compute the Real Average Consumption
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
        if context is None:
            context = {}
        
        uom_obj = self.pool.get('product.uom')
        
        rac_domain = [('created_ok', '=', True)]
        res = {}
        
        from_date = False
        to_date = False

        location_ids = []
        
        # Read if a interval is defined
        if context.get('from_date', False):
            from_date = context.get('from_date')
            rac_domain.append(('period_to', '>=', from_date))
        
        if context.get('to_date', False):
            to_date = context.get('to_date')
            rac_domain.append(('period_to', '<=', to_date))
        
        # Filter for one or some locations    
        if context.get('location_id', False):
            if type(context['location_id']) == type(1):
                location_ids = [context['location_id']]
            elif type(context['location_id']) in (type(''), type(u'')):
                location_ids = self.pool.get('stock.location').search(cr, uid, [('name','ilike',context['location'])], context=context)
            else:
                location_ids = context.get('location_id', [])
       
        for id in ids:
            res[id] = 0.00
            if from_date and to_date:
                rcr_domain = ['&', '&', ('product_id', 'in', ids), ('rac_id.cons_location_id', 'in', location_ids),
                              # All lines with a report started out the period and finished in the period 
                              '|', '&', ('rac_id.period_to', '>=', from_date), ('rac_id.period_to', '<=', to_date),
                              # All lines with a report started in the period and finished out the period 
                              '|', '&', ('rac_id.period_from', '<=', to_date), ('rac_id.period_from', '>=', from_date),
                              # All lines with a report started before the period  and finished after the period
                              '&', ('rac_id.period_from', '<=', from_date), ('rac_id.period_to', '>=', to_date)]
            
                rcr_line_ids = self.pool.get('real.average.consumption.line').search(cr, uid, rcr_domain, context=context)
                for line in self.pool.get('real.average.consumption.line').browse(cr, uid, rcr_line_ids, context=context):
                    cons = self._get_period_consumption(cr, uid, line, from_date, to_date, context=context)
                    res[id] += uom_obj._compute_qty(cr, uid, line.uom_id.id, cons, line.product_id.uom_id.id)

                # We want the average for the entire period
                if to_date < from_date:
                    raise osv.except_osv(_('Error'), _('You cannot have a \'To Date\' younger than \'From Date\'.'))
                # Calculate the # of months in the period
                try:
                    to_date_str = strptime(to_date, '%Y-%m-%d')
                except ValueError:
                    to_date_str = strptime(to_date, '%Y-%m-%d %H:%M:%S')
                
                try:
                    from_date_str = strptime(from_date, '%Y-%m-%d')
                except ValueError:
                    from_date_str = strptime(from_date, '%Y-%m-%d %H:%M:%S')
        
                nb_months = self._get_date_diff(from_date_str, to_date_str)
                
                if not nb_months: nb_months = 1

                uom_id = self.browse(cr, uid, ids[0], context=context).uom_id.id
                res[id] = res[id]/nb_months
                res[id] = round(self.pool.get('product.uom')._compute_qty(cr, uid, uom_id, res[id], uom_id), 2)
            
        return res
    
    def compute_amc(self, cr, uid, ids, context=None):
        '''
        Compute the Average Monthly Consumption with this formula :
            AMC = (sum(OUTGOING (except reason types Loan, Donation, Loss, Discrepancy))
                  -
                  sum(INCOMING with reason type Return from unit)) / Number of period's months
            The AMC is the addition of all done stock moves for a product within a period.
            For stock moves generated from a real consumption report, the qty of product is computed
            according to the average of consumption for the time of the period.
        '''
        if not context:
            context = {}
        
        if isinstance(ids, (int, long)):
            ids = [ids]
        
        move_obj = self.pool.get('stock.move')
        uom_obj = self.pool.get('product.uom')
        
        res = 0.00
        
        from_date = False
        to_date = False
        
        # Read if a interval is defined
        if context.get('from_date', False):
            from_date = context.get('from_date')
        
        if context.get('to_date', False):
            to_date = context.get('to_date')
            
        # Get all reason types
        loan_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_loan')[1]
        donation_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_donation')[1]
        donation_exp_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_donation_expiry')[1]
        loss_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_loss')[1]
        discrepancy_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_discrepancy')[1]
        return_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_return_from_unit')[1]

        # Update the domain
        domain = [('state', '=', 'done'), ('reason_type_id', 'not in', (loan_id, donation_id, donation_exp_id, loss_id, discrepancy_id)), ('product_id', 'in', ids)]
        if to_date:
            domain.append(('date', '<=', to_date))
        if from_date:
            domain.append(('date', '>=', from_date))
        
        locations = self.pool.get('stock.location').search(cr, uid, [('usage', 'in', ('internal', 'customer'))], context=context)
        # Add locations filters in domain if locations are passed in context
        domain.append(('location_id', 'in', locations))
        domain.append(('location_dest_id', 'in', locations))
        
        # Search all real consumption line included in the period
        # If no period found, take all stock moves
        if from_date and to_date:
            rcr_domain = ['&', ('product_id', 'in', ids),
                          # All lines with a report started out the period and finished in the period 
                          '|', '&', ('rac_id.period_to', '>=', from_date), ('rac_id.period_to', '<=', to_date),
                          # All lines with a report started in the period and finished out the period 
                          '|', '&', ('rac_id.period_from', '<=', to_date), ('rac_id.period_from', '>=', from_date),
                          # All lines with a report started before the period  and finished after the period
                          '&', ('rac_id.period_from', '<=', from_date), ('rac_id.period_to', '>=', to_date)]
        
            rcr_line_ids = self.pool.get('real.average.consumption.line').search(cr, uid, rcr_domain, context=context)
            report_move_ids = []
            for line in self.pool.get('real.average.consumption.line').browse(cr, uid, rcr_line_ids, context=context):
                report_move_ids.append(line.move_id.id)
                res += self._get_period_consumption(cr, uid, line, from_date, to_date, context=context)
            
            if report_move_ids:
                domain.append(('id', 'not in', report_move_ids))
        
        out_move_ids = move_obj.search(cr, uid, domain, context=context)
        
        for move in move_obj.browse(cr, uid, out_move_ids, context=context):
            if move.reason_type_id.id == return_id and move.location_id.usage == 'customer':
                res -= uom_obj._compute_qty(cr, uid, move.product_uom.id, move.product_qty, move.product_id.uom_id.id)
            elif move.location_dest_id.usage == 'customer':
                res += uom_obj._compute_qty(cr, uid, move.product_uom.id, move.product_qty, move.product_id.uom_id.id)
            
            # Update the limit in time
            if not context.get('from_date') and (not from_date or move.date < from_date):
                from_date = move.date
            if not context.get('to_date') and (not to_date or move.date > to_date):
                to_date = move.date
                
        if not to_date or not from_date:
            return 0.00
            
        # We want the average for the entire period
        if to_date < from_date:
            raise osv.except_osv(_('Error'), _('You cannot have a \'To Date\' younger than \'From Date\'.'))
        # Calculate the # of months in the period
        try:
            to_date_str = strptime(to_date, '%Y-%m-%d')
        except ValueError:
            to_date_str = strptime(to_date, '%Y-%m-%d %H:%M:%S')
        
        try:
            from_date_str = strptime(from_date, '%Y-%m-%d')
        except ValueError:
            from_date_str = strptime(from_date, '%Y-%m-%d %H:%M:%S')

        nb_months = self._get_date_diff(from_date_str, to_date_str)
        
        if not nb_months: nb_months = 1
        
        uom_id = self.browse(cr, uid, ids[0], context=context).uom_id.id
        res = res/nb_months
        res = self.pool.get('product.uom')._compute_qty(cr, uid, uom_id, res, uom_id)
            
        return res
    
    def _get_date_diff(self, from_date, to_date):
        '''
        Returns the number of months between to dates according to the number
        of days in the month.
        '''
        diff_date = Age(to_date, from_date)
        res = 0.0
        
        def days_in_month(month, year):
            '''
            Returns the # of days in the month
            '''
            res = 30
            if month == 2 and year%4 == 0:
                res = 29
            elif month == 2 and year%4 != 0:
                res = 28
            elif month in (1, 3, 5, 7, 8, 10, 12):
                res = 31
            return res
        
        while from_date <= to_date:
            # Add 12 months by years between the two dates
            if diff_date.years:
                res += diff_date.years*12
                from_date += RelativeDate(years=diff_date.years)
                diff_date = Age(to_date, from_date)
            else:
                # If two dates are in the same month
                if from_date.month == to_date.month:
                    nb_days_in_month = days_in_month(from_date.month, from_date.year)
                    # We divided the # of days between the two dates by the # of days in month
                    # to have a percentage of the number of month
                    res += round((to_date.day-from_date.day+1)/nb_days_in_month, 2)
                    break
                elif to_date.month - from_date.month > 1 or to_date.year - from_date.year > 0:
                    res += 1
                    from_date += RelativeDate(months=1)
                else:
                    # Number of month till the end of from month
                    fr_nb_days_in_month = days_in_month(from_date.month, from_date.year)
                    nb_days = fr_nb_days_in_month - from_date.day + 1
                    res += round(nb_days/fr_nb_days_in_month, 2)
                    # Number of month till the end of from month
                    to_nb_days_in_month = days_in_month(to_date.month, to_date.year)  
                    res += round(to_date.day/to_nb_days_in_month, 2)
                    break
                    
        return res
                     
            

    def _compute_product_amc(self, cr, uid, ids, field_name, args, ctx=None):
        if ctx is None:
            ctx = {}
        context = ctx.copy()
        res = {}
        from_date = (DateFrom(time.strftime('%Y-%m-%d')) + RelativeDateTime(months=-3, day=1)).strftime('%Y-%m-%d')
        to_date = (DateFrom(time.strftime('%Y-%m-%d')) + RelativeDateTime(day=1, days=-1)).strftime('%Y-%m-%d')

        if context.get('from_date', False):
            from_date = (DateFrom(context.get('from_date')) + RelativeDateTime(day=1)).strftime('%Y-%m-%d')
                                               
        if context.get('to_date', False):
            to_date = (DateFrom(context.get('to_date')) + RelativeDateTime(months=1, day=1, days=-1)).strftime('%Y-%m-%d')

        context.update({'from_date': from_date})
        context.update({'to_date': to_date})

        for product in ids:
            res[product] = self.compute_amc(cr, uid, product, context=context)

        return res
    
    def _get_period_consumption(self, cr, uid, line, from_date, to_date, context=None):
        '''
        Returns the average quantity of product in the period
        '''        
        # Compute the # of days in the report period
        if context is None:
            context = {}
        from datetime import datetime
        report_from = datetime.strptime(line.rac_id.period_from, '%Y-%m-%d')
        report_to = datetime.strptime(line.rac_id.period_to, '%Y-%m-%d')
        dt_from_date = datetime.strptime(from_date, '%Y-%m-%d')
        dt_to_date = datetime.strptime(to_date, '%Y-%m-%d')
        delta = report_to - report_from

        # Add 1 to include the last day of report to        
        report_nb_days = delta.days + 1
        days_incl = 0
        
        # Case where the report is totally included in the period
        if line.rac_id.period_from >= from_date and line.rac_id.period_to <= to_date:
            return line.consumed_qty
        # Case where the report started before the period and done after the period
        elif line.rac_id.period_from <= from_date and line.rac_id.period_to >= to_date:
            # Compute the # of days of the period
            delta2 = dt_to_date - dt_from_date
            days_incl = delta2.days +1
        # Case where the report started before the period and done in the period
        elif line.rac_id.period_from <= from_date and line.rac_id.period_to <= to_date and line.rac_id.period_to >= from_date:
            # Compute the # of days of the report included in the period
            # Add 1 to include the last day of report to
            delta2 = report_to - dt_from_date
            days_incl = delta2.days +1
        # Case where the report started in the period and done after the period
        elif line.rac_id.period_from >= from_date and line.rac_id.period_to >= to_date and line.rac_id.period_from <= to_date:
            # Compute the # of days of the report included in the period
            # Add 1 to include the last day of to_date
            delta2 = dt_to_date - report_from
            days_incl = delta2.days +1
        
        # Compute the quantity consumed in the period for this line
        consumed_qty = (line.consumed_qty/report_nb_days)*days_incl
        return self.pool.get('product.uom')._compute_qty(cr, uid, line.uom_id.id, consumed_qty, line.uom_id.id)
    
    _columns = {
        'procure_delay': fields.float(digits=(16,2), string='Procurement Lead Time', 
                                        help='It\'s the default time to procure this product. This lead time will be used on the Order cycle procurement computation'),
        'monthly_consumption': fields.function(compute_mac, method=True, type='float', string='Real Consumption', readonly=True),
        'product_amc': fields.function(_compute_product_amc, method=True, type='float', string='Monthly consupmiton', readonly=True),
        'reviewed_consumption': fields.function(_compute_fmc, method=True, type='float', string='Forecasted Monthly Consumption', readonly=True),
    }
    
    _defaults = {
        'procure_delay': lambda *a: 60,
    }

    
product_product()


class stock_picking(osv.osv):
    _inherit = 'stock.picking'
    _name = 'stock.picking'

    def _hook_log_picking_modify_message(self, cr, uid, ids, context=None, message='', pick=False):
        '''
        Possibility to change the message
        '''
        report_ids = self.pool.get('real.average.consumption').search(cr, uid, [('picking_id', '=', pick.id)], context=context)
        if report_ids:
            name = self.pool.get('real.average.consumption').browse(cr, uid, report_ids[0], context=context).picking_id.name
            return 'Delivery Order %s generated from the consumption report is closed.' % name
        else:
            return super(stock_picking, self)._hook_log_picking_modify_message(cr, uid, ids, context=context, message=message, pick=pick)

stock_picking()

class stock_location(osv.osv):
    _inherit = 'stock.location'

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        if context is None:
            context = {}
        if context.get('no3buttons') and view_type == 'search':
            view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'consumption_calculation', 'view_stock_location_without_buttons')
        return super(stock_location, self).fields_view_get(cr, uid, view_id, view_type, context=context, toolbar=toolbar, submenu=submenu)
stock_location()
