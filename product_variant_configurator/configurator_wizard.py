# -*- encoding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution    
#    Copyright (C) 2009 Smile.fr. All Rights Reserved
#    authors: Raphaël Valyi, Xavier Fernandez
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
from osv import fields, osv
import sale_product_multistep_configurator


class product_variant_configurator_line(osv.osv_memory):
    _name = "product_variant_configurator.line"

    _columns = {
                "dimension_type_id": fields.many2one('product.variant.dimension.type', "Dimension Type"), # , domain="[('product_tmpl_id','=',product_tmpl_id)]"
                "dimension_type_value_id": fields.many2one('product.variant.dimension.value',"Dimension Value", domain="[('dimension_id','=',dimension_type_id)]"),
                "dimension_custom_value": fields.char('Custom Value', size=64),
                "configurator_id": fields.many2one('product_variant_configurator.configurator', 'product_variant_configurator Test'),
                "allow_custom_value": fields.boolean('Allow custom values ?'),
    }
    
    def onchange_dimension_type_id(self, cr, uid, ids, dimension_type_id):
        dim_allow=self.pool.get('product.variant.dimension.type').read(cr, uid, dimension_type_id, ['allow_custom_value'])
        print dim_allow
        if dim_allow:
            allow_custom=dim_allow['allow_custom_value']
        
        return {'value':{'dimension_type_id':dimension_type_id, 'allow_custom_value': allow_custom}}
    
    def onchange_dimension_type_value_id(self, cr, uid, ids, dimension_type_value_id):
        return {'value':{'dimension_type_value_id':dimension_type_value_id}}
    
    def onchange_dimension_custom_value(self, cr, uid, ids, dimension_custom_value, allow_custom_value):
        #FIX: this shouldn't be necessary if attrs="{'readonly':[('allow_custom_value','=',False)]}"
        # was working in tree view
        if allow_custom_value:
            return {'value':{'dimension_custom_value':dimension_custom_value}}
        else:
            return {'value':{'dimension_custom_value':False}}

product_variant_configurator_line()


class product_variant_configurator_configurator(osv.osv_memory):
    _name = "product_variant_configurator.configurator"

    _columns = {
              "product_tmpl_id": fields.many2one('product.template', "Product Template"),
              "dimension_configuration_line_ids": fields.one2many('product_variant_configurator.line', 'configurator_id', 'Configurator Lines'),
              "product_variant_id": fields.many2one('product.product', "Product Variant", domain="[('product_tmpl_id','=',product_tmpl_id)]"),
    }
    
    def create(self, cr, uid, vals, context=None):
        id = super(osv.osv_memory, self).create(cr, uid, vals, context)
        line_ids=[i[1] for i in vals['dimension_configuration_line_ids']]
        if line_ids:
            self.pool.get('product_variant_configurator.line').write(cr, uid, line_ids, {'configurator_id':id})
        return id

    #TODO load the product of the sale order line in the wizard in case of modification
    def default_get(self, cr, uid, fields_list, context=None):
        sol_id = context.get('active_id', False)
        if (context.get('active_id_object_type', False)=='sale.order.line' and sol_id):
            res_sol = self.pool.get('sale.order.line').read(cr, uid, sol_id, ['product_id','dimension_custom_value_ids'])
            
            if res_sol:
                res_product = self.pool.get('product.product').read(cr, uid, res_sol['product_id'][0], ['product_tmpl_id','dimension_value_ids'])

#                dim_val_obj = self.pool.get('product.variant.dimension.value')
#                dim_values = res_product['dimension_value_ids']
#                dim_types = []
#                for val in res_product['dimension_value_ids']:
#                    dim_types.append(dim_val_obj.read(cr, uid, val, ['dimension_id'])['dimension_id'][0])
#
#                
#                dim_customs = []
#                for dim_type in dim_types:
#                    for custom_val in res_sol['dimension_custom_value_ids']:
#                        pass
#                        
#                line_ids = []
                vals = {'product_variant_id': res_sol['product_id'],
                      'product_tmpl_id': res_product['product_tmpl_id'],}
                return vals
    
        return super(osv.osv_memory, self).default_get(cr, uid, fields_list, context)
    
    def onchange_product_tmpl_id(self, cr, uid, ids, product_tmpl_id=False):
        print "onchange_product_tmpl_id"
        result = {}
        if not product_tmpl_id:
            return result

        product_template = self.pool.get('product.template').browse(cr, uid, product_tmpl_id)
        dim_ids = product_template.dimension_type_ids
        
        line_ids = []
        for dim in dim_ids:
            #TODO that would be much better if the client could interpret a hash of lines to create (later on) 
            #instead of creating those lines now while not being able yet to link them to the current configurator object
            dim_allow=self.pool.get('product.variant.dimension.type').read(cr, uid, dim.id, ['allow_custom_value'])
            if dim_allow:
                allow_custom=dim_allow['allow_custom_value']
            vals = {'dimension_type_id':dim.id, 'dimension_type_value_id':None, 'allow_custom_value': allow_custom}
            line_ids.append(self.pool.get('product_variant_configurator.line').create(cr, uid, vals))

        result['value'] = {'dimension_configuration_line_ids': line_ids}
        return result
    
    def onchange_product_variant_id(self, cr, uid, ids, product_variant_id=False, dimension_configuration_line_ids=False):
        print "onchange_product_variant_id"
        result = {}
        if not product_variant_id:
            return result
        
        line_obj = self.pool.get('product_variant_configurator.line')
        
        dim_value_ids = self.pool.get('product.product').read(cr,uid,product_variant_id)['dimension_value_ids']
        dim_couple= [(dim_id,self.pool.get('product.variant.dimension.value').read(cr,uid,dim_id)['dimension_id']) for dim_id in dim_value_ids]
        print "dimension_configuration_line_ids",dimension_configuration_line_ids
        for line in dimension_configuration_line_ids:
            for couple in dim_couple:
                if line[2] and line[2]['dimension_type_id'] == couple[1][0]:
                    vals={'dimension_type_value_id':couple[0], 'dimension_custom_value':line[2]['dimension_custom_value']}
                    line_obj.write(cr, uid, [line[1]], vals)

        line_ids = [line[1] for line in dimension_configuration_line_ids]

        result['value'] = {'dimension_configuration_line_ids': line_ids}
        return result
    
    def configure_line(self, cr, uid, ids, context={}):
        active_id_object_type = context.get('active_id_object_type', False)
        res_obj = self.pool.get('sale.order.line')
        line_obj = self.pool.get('product_variant_configurator.line')
        sol_id = False
        
        if active_id_object_type == 'sale.order':
            print "Creating Line"
            
            order_id = context.get('active_id', False)
            
            for res in self.read(cr,uid,ids):
                if res['product_tmpl_id']:
                    tmpl_obj=self.pool.get('product.template')
                    tmpl_infos=tmpl_obj.read(cr,uid,res['product_tmpl_id'],['name','uom_id'])
                    default_uom_id=tmpl_infos['uom_id'][0]
                    tmpl_name=tmpl_infos['name']

                    if res['product_variant_id']:
                        prod_name=self.pool.get('product.product').read(cr,uid,res['product_variant_id'])['variants']
                        vals = {'order_id':order_id,
                              'product_id':res['product_variant_id'],
                              'delay':0.0,
                              'name': tmpl_name + " - " + prod_name,
                              'type':'make_to_order',
                              'state':'draft',
                              'price_unit':0.0,
                              'product_uom_qty':1.0,
                              'product_uom':default_uom_id,}
                        
                        sol_id = res_obj.create(cr, uid, vals, context=context)
                        
                        cust_lines_obj = self.pool.get('sale.order.line.dimension_custom_values')
                        for line_id in line_obj.read(cr, uid, res['dimension_configuration_line_ids']):
                            if line_id['dimension_custom_value']:
                                cust_vals={'dimension_type_id': line_id['dimension_type_id'],
                                           'custom_value': line_id['dimension_custom_value'],
                                           'sale_order_line_id':sol_id,
                                           }
                                cust_lines_obj.create(cr, uid, cust_vals, context=context)
        
        elif active_id_object_type == 'sale.order.line':
            print "Modifying Line"
            
            sol_id = context.get('active_id', False)
            
            for res in self.read(cr,uid,ids):
                if res['product_tmpl_id']:
                    default_uom_id = self.pool.get('product.template').read(cr,uid,res['product_tmpl_id'])['uom_id'][0]
                    if res['product_variant_id']:
                        tmpl_obj = self.pool.get('product.template')
                        tmpl_name = tmpl_obj.read(cr,uid,res['product_tmpl_id'],['name'])['name']
                        prod_name = self.pool.get('product.product').read(cr,uid,res['product_variant_id'])['variants']
                        name = tmpl_name
                        if prod_name: name = tmpl_name + " - " + prod_name
                        vals = {'product_id':res['product_variant_id'], 'name':name,}
                        if res['product_variant_id']: res_obj.write(cr, uid, [sol_id], vals)
            
            cust_lines_obj = self.pool.get('sale.order.line.dimension_custom_values')
            for line_id in line_obj.read(cr, uid, res['dimension_configuration_line_ids']):
                if line_id['dimension_custom_value']:
                    cust_vals={'dimension_type_id': line_id['dimension_type_id'],
                               'custom_value': line_id['dimension_custom_value'],
                               'sale_order_line_id':sol_id,
                               }
                    cl_id=cust_lines_obj.search(cr, uid, [('dimension_type_id','=',line_id['dimension_type_id']),
                                                          ('sale_order_line_id','=',sol_id)])
                    if cl_id:
                        cust_lines_obj.write(cr, uid, cl_id, cust_vals, context=context)
                    else:
                        cust_lines_obj.create(cr, uid, cust_vals, context=context)
        
        if sol_id :
            context.update({'sol_id': sol_id})

            return sale_product_multistep_configurator.sale_product_multistep_configurator.next_step(context)
            
        else:
            return True
        
product_variant_configurator_configurator()
