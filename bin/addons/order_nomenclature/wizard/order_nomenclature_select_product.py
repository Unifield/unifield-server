#!/usr/bin/env python
# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO consulting
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

from osv import osv, fields
from tools.translate import _

class order_nomenclature_select_product(osv.osv_memory):
    _name = 'order.nomenclature.select.product'
    _description = 'Select Product'
    
    # EXACT SAME CODE AS IN PRODUCT NOMENCLATURE TAB - product_nomenclature.py
    _columns = {
                # mandatory nomenclature levels
                'nomen_manda_0': fields.many2one('product.nomenclature', 'Main Type', required=True),
                'nomen_manda_1': fields.many2one('product.nomenclature', 'Group', required=True),
                'nomen_manda_2': fields.many2one('product.nomenclature', 'Family', required=True),
                'nomen_manda_3': fields.many2one('product.nomenclature', 'Root', required=True),
                # optional nomenclature levels
                'nomen_sub_0': fields.many2one('product.nomenclature', 'Sub Class 1'),
                'nomen_sub_1': fields.many2one('product.nomenclature', 'Sub Class 2'),
                'nomen_sub_2': fields.many2one('product.nomenclature', 'Sub Class 3'),
                'nomen_sub_3': fields.many2one('product.nomenclature', 'Sub Class 4'),
                'nomen_sub_4': fields.many2one('product.nomenclature', 'Sub Class 5'),
                'nomen_sub_5': fields.many2one('product.nomenclature', 'Sub Class 6'),
                
                'test': fields.char('TEST', size=128),
    }

    _defaults = {
    }
    # END OF COPIED CODE FROM PRODUCT NOMENCLATURE TAB - product_nomenclature.py

    def view_init(self, cr , uid , fields_list, context=None):
        '''
        http://doc.openerp.com/v6.0/developer/2_5_Objects_Fields_Methods/methods.html#osv.osv.osv.view_init
        
        Override this method to do specific things when a view on the object is opened.
        '''
        print 'view_init'
        
        
        if False:
            obj_inv = self.pool.get('account.invoice')
            if context is None:
                context = {}
            if context.get('active_id',False):
                if obj_inv.browse(cr, uid, context['active_id']).state != 'draft':
                    raise osv.except_osv(_('Error'), _('You can only change currency for Draft Invoice !'))
                pass

    def selectNomenclature(self, cr, uid, ids, context=None):
        print 'selectNomenclature'
#        obj_inv = self.pool.get('account.invoice')
#        obj_inv_line = self.pool.get('account.invoice.line')
#        obj_currency = self.pool.get('res.currency')
#        if context is None:
#            context = {}
#        data = self.read(cr, uid, ids)[0]
#        new_currency = data['currency_id']
#
#        invoice = obj_inv.browse(cr, uid, context['active_id'], context=context)
#        if invoice.currency_id.id == new_currency:
#            return {}
#        rate = obj_currency.browse(cr, uid, new_currency, context=context).rate
#        for line in invoice.invoice_line:
#            new_price = 0
#            if invoice.company_id.currency_id.id == invoice.currency_id.id:
#                new_price = line.price_unit * rate
#                if new_price <= 0:
#                    raise osv.except_osv(_('Error'), _('New currency is not confirured properly !'))
#
#            if invoice.company_id.currency_id.id != invoice.currency_id.id and invoice.company_id.currency_id.id == new_currency:
#                old_rate = invoice.currency_id.rate
#                if old_rate <= 0:
#                    raise osv.except_osv(_('Error'), _('Currnt currency is not confirured properly !'))
#                new_price = line.price_unit / old_rate
#
#            if invoice.company_id.currency_id.id != invoice.currency_id.id and invoice.company_id.currency_id.id != new_currency:
#                old_rate = invoice.currency_id.rate
#                if old_rate <= 0:
#                    raise osv.except_osv(_('Error'), _('Current currency is not confirured properly !'))
#                new_price = (line.price_unit / old_rate ) * rate
#            obj_inv_line.write(cr, uid, [line.id], {'price_unit': new_price})
#        obj_inv.write(cr, uid, [invoice.id], {'currency_id': new_currency}, context=context)
        #return {'type': 'ir.actions.act_window_close'}
        return {'test':'voila le test'}
    
    def selectProduct(self, cr, uid, ids, context=None):
        print 'selectProduct'
        pass

order_nomenclature_select_product()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: