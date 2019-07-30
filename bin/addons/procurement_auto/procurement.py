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

from osv import osv, fields

import time
from tools.translate import _

class stock_warehouse_automatic_supply(osv.osv):
    _name = 'stock.warehouse.automatic.supply'
    _description = 'Automatic Supply'
    _order = 'name, id'

    def _get_next_date_from_frequence(self, cr, uid, ids, name, args, context=None):
        '''
        Returns the next date of the frequency
        '''
        res = {}

        for proc in self.browse(cr, uid, ids):
            if proc.frequence_id and proc.frequence_id.next_date:
                res[proc.id] = proc.frequence_id.next_date
            else:
                res[proc.id] = False

        return res

    def _get_frequence_change(self, cr, uid, ids, context=None):
        '''
        Returns Auto. Sup. ids when frequence change
        '''
        result = {}
        for frequence in self.pool.get('stock.frequence').browse(cr, uid, ids, context=context):
            for sup_id in frequence.auto_sup_ids:
                result[sup_id.id] = True

        return result.keys()

    def _get_frequence_name(self, cr, uid, ids, field_name, arg, context=None):
        '''
        Returns the name_get value of the frequence
        '''
        res = {}
        for proc in self.browse(cr, uid, ids):
            if proc.frequence_id:
                res[proc.id] = self.pool.get('stock.frequence').name_get(cr, uid, [proc.frequence_id.id], context=context)[0][1]

        return res

    def _get_product_ids(self, cr, uid, ids, field_name, arg, context=None):
        '''
        Returns a list of products for the rule
        '''
        res = {}

        for rule in self.browse(cr, uid, ids, context=context):
            res[rule.id] = []
            for line in rule.line_ids:
                res[rule.id].append(line.product_id.id)

        return res

    def _src_product_ids(self, cr, uid, obj, name, args, context=None):
        if not context:
            context = {}

        res = []

        for arg in args:
            if arg[0] == 'product_ids':
                rule_ids = []
                line_ids = self.pool.get('stock.warehouse.automatic.supply.line').search(cr, uid, [('product_id', arg[1], arg[2])])
                for l in self.pool.get('stock.warehouse.automatic.supply.line').browse(cr, uid, line_ids):
                    if l.supply_id.id not in rule_ids:
                        rule_ids.append(l.supply_id.id)
                res.append(('id', 'in', rule_ids))

        return res

    _columns = {
        'sequence': fields.integer(string='Order', required=False, help='A higher order value means a low priority'),
        'name': fields.char(size=64, string='Reference', required=True),
        'category_id': fields.many2one('product.category', string='Category'),
        'product_id': fields.many2one('product.product', string='Specific product'),
        'product_uom_id': fields.many2one('product.uom', string='Product UoM'),
        'product_qty': fields.float(digits=(16,2), string='Qty', related_uom='product_uom_id'),
        'warehouse_id': fields.many2one('stock.warehouse', string='Warehouse', required=True),
        'location_id': fields.many2one('stock.location', 'Location', ondelete="cascade", required=True,
                                       domain="[('is_replenishment', '=', warehouse_id)]",
                                       help='Location where the computation is made.'),
        'frequence_name': fields.function(_get_frequence_name, method=True, string='Frequency', type='char',
                                          help='Define the time between two replenishments'),
        'frequence_id': fields.many2one('stock.frequence', string='Frequency', help='It\'s the time between two replenishments'),
        'line_ids': fields.one2many('stock.warehouse.automatic.supply.line', 'supply_id', string="Products",
                                    help='Define the quantity to order for each products'),
        'company_id': fields.many2one('res.company','Company',required=True),
        'active': fields.boolean('Active', help="If the active field is set to False, it will allow you to hide the automatic supply without removing it."),
        'procurement_id': fields.many2one('procurement.order', string='Last procurement', readonly=True,
                                          help='Reference of the last procurement generated by this rule'),
        'next_date': fields.function(_get_next_date_from_frequence, method=True, string='Next scheduled date', type='date',
                                     help='As this date is not in the past, no new replenishment will be run',
                                     store={'stock.warehouse.automatic.supply': (lambda self, cr, uid, ids, c=None: ids, ['frequence_id'],20),
                                            'stock.frequence': (_get_frequence_change, None, 20)}),
        'product_ids': fields.function(_get_product_ids, fnct_search=_src_product_ids,
                                       type='many2many', relation='product.product', method=True, string='Products'),
        'sublist_id': fields.many2one('product.list', string='List/Sublist', ondelete='set null'),
        'nomen_manda_0': fields.many2one('product.nomenclature', 'Main Type', ondelete='set null'),
        'nomen_manda_1': fields.many2one('product.nomenclature', 'Group', ondelete='set null'),
        'nomen_manda_2': fields.many2one('product.nomenclature', 'Family', ondelete='set null'),
        'nomen_manda_3': fields.many2one('product.nomenclature', 'Root', ondelete='set null'),
    }

    _defaults = {
        'active': lambda *a: 1,
        'name': lambda x,y,z,c: x.pool.get('ir.sequence').get(y,z,'stock.automatic.supply') or '',
    }

    def default_get(self, cr, uid, fields, context=None):
        '''
        Get the default values for the replenishment rule
        '''
        res = super(stock_warehouse_automatic_supply, self).default_get(cr, uid, fields, context=context)

        company_id = res.get('company_id')
        warehouse_id = res.get('warehouse_id')

        if not 'company_id' in res:
            company_id = self.pool.get('res.company')._company_default_get(cr, uid, 'stock.warehouse.automatic.supply', context=context)
            res.update({'company_id': company_id})

        if not 'warehouse_id' in res:
            warehouse_id = self.pool.get('stock.warehouse').search(cr, uid, [('company_id', '=', company_id)], context=context)[0]
            res.update({'warehouse_id': warehouse_id})

        if not 'location_id' in res:
            location_id = self.pool.get('stock.warehouse').browse(cr, uid, warehouse_id, context=context).lot_stock_id.id
            res.update({'location_id': location_id})

        return res

    def choose_change_frequence(self, cr, uid, ids, context=None):
        '''
        Open a wizard to define a frequency for the automatic supply
        or open a wizard to modify the frequency if frequency already exists
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
        if context is None:
            context = {}

        frequence_id = False
        res_id = False
        res_ok = False

        for proc in self.browse(cr, uid, ids):
            res_id = proc.id
            if proc.frequence_id and proc.frequence_id.id:
                frequence_id = proc.frequence_id.id
                res_ok = True
            else:
                frequence_data = {'name': 'monthly',
                                  'monthly_choose_freq': 1,
                                  'monthly_choose_day': 'monday',
                                  'monthly_frequency': 1,
                                  'monthly_one_day': True,
                                  'no_end_date': True,
                                  'start_date': time.strftime('%Y-%m-%d'),}
                frequence_id = self.pool.get('stock.frequence').create(cr, uid, frequence_data, context=context)
                self.write(cr, uid, proc.id, {'frequence_id': frequence_id}, context=context)
                res_ok = True

        context.update({'active_id': res_id,
                        'active_model': 'stock.warehouse.automatic.supply',
                        'res_ok': res_ok})

        return {'type': 'ir.actions.act_window',
                'target': 'new',
                'res_model': 'stock.frequence',
                'view_type': 'form',
                'view_model': 'form',
                'context': context,
                'res_id': frequence_id}

    def onchange_warehouse_id(self, cr, uid, ids, warehouse_id, context=None):
        """ Finds location id for changed warehouse.
        @param warehouse_id: Changed id of warehouse.
        @return: Dictionary of values.
        """
        if warehouse_id:
            w = self.pool.get('stock.warehouse').browse(cr, uid, warehouse_id, context=context)
            v = {'location_id': w.lot_stock_id.id}
            return {'value': v}
        return {}

    def onchange_product_id(self, cr, uid, ids, product_id, context=None):
        """ Finds uom for changed product.
        @param product_id: Changed id of product.
        @return: Dictionary of values.
        """
        if product_id:
            w = self.pool.get('product.product').browse(cr, uid, product_id, context=context)
            v = {'product_uom_id': w.uom_id.id}
            return {'value': v}
        return {}

    def unlink(self, cr, uid, ids, context):
        '''
        When delete an automatic supply rule, also remove the frequency
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
        freq_ids = []
        for auto in self.read(cr, uid, ids, ['frequence_id']):
            if auto['frequence_id']:
                freq_ids.append(auto['frequence_id'][0])
        if freq_ids:
            self.pool.get('stock.frequence').unlink(cr, uid, freq_ids, context)
        return super(stock_warehouse_automatic_supply, self).unlink(cr, uid, ids, context=context)

    def copy(self, cr, uid, id, default=None, context=None):
        '''
        When duplicate an automatic supply rule, also duplicate the frequency 
        '''
        if not default:
            default = {}
        obj = self.read(cr, uid, id, ['frequence_id'])
        if obj['frequence_id']:
            default['frequence_id'] = int(self.pool.get('stock.frequence').copy(cr, uid, obj['frequence_id'][0], context=context))
        default.update({
            'name': self.pool.get('ir.sequence').get(cr, uid, 'stock.automatic.supply') or '',
            'procurement_id': False,
        })
        return super(stock_warehouse_automatic_supply, self).copy(cr, uid, id, default, context=context)

    def _check_frequency(self, cr, uid, ids, context=None):
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        if context.get('button') == 'choose_change_frequence':
            return True

        for auto in self.read(cr, uid, ids, ['frequence_id']):
            if not auto['frequence_id']:
                raise osv.except_osv(_('Error !'), _('Frequency is mandatory, please add one by clicking on the "Change/Choose Frequency" button.'))
        return True

    def create(self, cr, uid, vals, context=None):
        id = super(stock_warehouse_automatic_supply, self).create(cr, uid, vals, context=context)
        self._check_frequency(cr, uid, [id], context)
        return id

    def write(self, cr, uid, ids, vals, context=None):
        if not ids:
            return True
        if vals.get('sublist_id', False):
            vals.update({'nomen_manda_0': False, 'nomen_manda_1': False, 'nomen_manda_2': False, 'nomen_manda_3': False})
        if vals.get('nomen_manda_0', False):
            vals.update({'sublist_id': False})
        ret = super(stock_warehouse_automatic_supply, self).write(cr, uid, ids, vals, context=context)
        self._check_frequency(cr, uid, ids, context)
        return ret

    def onChangeSearchNomenclature(self, cr, uid, id, position, type, nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, num=True, context=None):
        return self.pool.get('product.product').onChangeSearchNomenclature(cr, uid, 0, position, type, nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, False, context={'withnum': 1})

    def fill_lines(self, cr, uid, ids, context=None):
        '''
        Fill all lines according to defined nomenclature level and sublist
        '''
        if context is None:
            context = {}
        for report in self.browse(cr, uid, ids, context=context):
            product_ids = []
            products = []
            nom = False
            field = False
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
                    self.pool.get('stock.warehouse.automatic.supply.line').unlink(cr, uid, line.id, context=context)

            for product in self.pool.get('product.product').browse(cr, uid, product_ids, context=context):
                # Check if the product is not already on the report
                if product.type not in ('consu', 'service', 'service_recep') and product.id not in products:
                    self.pool.get('stock.warehouse.automatic.supply.line').create(cr, uid, {'product_id': product.id,
                                                                                            'product_uom_id': product.uom_id.id,
                                                                                            'product_qty': 1.00,
                                                                                            'supply_id': report.id})
        return {'type': 'ir.actions.act_window',
                'res_model': 'stock.warehouse.automatic.supply',
                'view_type': 'form',
                'view_mode': 'form',
                'res_id': ids[0],
                'target': 'dummy',
                'context': context}

    def get_nomen(self, cr, uid, id, field):
        return self.pool.get('product.nomenclature').get_nomen(cr, uid, self, id, field, context={'withnum': 1})

stock_warehouse_automatic_supply()

class stock_warehouse_automatic_supply_line(osv.osv):
    _name = 'stock.warehouse.automatic.supply.line'
    _description = 'Automatic Supply Line'
    _rec_name = 'product_id'

    _columns = {
        'product_id': fields.many2one('product.product', string='Product', required=True),
        'product_uom_id': fields.many2one('product.uom', string='Product UoM', required=True),
        'product_qty': fields.float(digit=(16,2), string='Quantity to order', required=True, related_uom='product_uom_id'),
        'supply_id': fields.many2one('stock.warehouse.automatic.supply', string='Supply', ondelete='cascade', required=True)
    }

    _defaults = {
        'product_qty': lambda *a: 1.00,
    }

    def _check_product_qty(self, cr, uid, ids, context=None):
        '''
        Check if the quantity is larger than 0.00
        '''
        context = context is None and {} or context

        if isinstance(ids, (int, long)):
            ids = [ids]

        if not context.get('noraise'):
            for line in self.read(cr, uid, ids, ['product_qty'], context=context):
                if line['product_qty'] <= 0.00:
                    raise osv.except_osv(_('Error'), _('Lines must have a quantity larger than 0.00'))
                    return False

        return True

    def create(self, cr, uid, vals, context=None):
        res = super(stock_warehouse_automatic_supply_line, self).create(cr, uid, vals, context=context)
        self._check_product_qty(cr, uid, res, context=context)
        return res

    def write(self, cr, uid, ids, vals, context=None):
        if not ids:
            return True
        res = super(stock_warehouse_automatic_supply_line, self).write(cr, uid, ids, vals, context=context)
        self._check_product_qty(cr, uid, ids, context=context)
        return res

    def _check_uniqueness(self, cr, uid, ids, context=None):
        '''
        Check if the product is not already in the current rule
        '''
        for line in self.browse(cr, uid, ids, context=context):
            lines = self.search(cr, uid, [('id', '!=', line.id),
                                          ('product_id', '=', line.product_id.id),
                                          ('supply_id', '=', line.supply_id.id)], context=context)
            if lines:
                return False

        return True

    _constraints = [
        (_check_uniqueness, 'You cannot have two times the same product on the same automatic supply rule', ['product_id'])
    ]

    def onchange_product_id(self, cr, uid, ids, product_id, uom_id, product_qty, context=None):
        """ Finds UoM for changed product.
        @param product_id: Changed id of product.
        @return: Dictionary of values.
        """
        res = {}

        if product_id:
            prod = self.pool.get('product.product').browse(cr, uid, product_id, context=context)
            v = {'product_uom_id': prod.uom_id.id}
            res.update({'value': v})

        if product_qty:
            uom_id = res.get('value', {}).get('product_uom_id', uom_id)
            res = self.pool.get('product.uom')._change_round_up_qty(cr, uid, uom_id, product_qty, 'product_qty', result=res)

        return res

    def onchange_uom_qty(self, cr, uid, ids, uom_id, product_qty, context=None):
        '''
        Check the round of qty according to UoM
        '''
        res = {}

        if product_qty:
            res = self.pool.get('product.uom')._change_round_up_qty(cr, uid, uom_id, product_qty, 'product_qty', result=res)

        return res

stock_warehouse_automatic_supply_line()

class stock_frequence(osv.osv):
    _name = 'stock.frequence'
    _inherit = 'stock.frequence'

    _columns = {
        'auto_sup_ids': fields.one2many('stock.warehouse.automatic.supply', 'frequence_id', string='Auto. Sup.'),
    }

    def choose_frequency(self, cr, uid, ids, context=None):
        '''
        Adds the support of automatic supply on choose frequency method
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
        if context is None:
            context = {}

        if not context.get('res_ok', False) and 'active_id' in context and 'active_model' in context and \
                context.get('active_model') == 'stock.warehouse.automatic.supply':
            self.pool.get('stock.warehouse.automatic.supply').write(cr, uid, [context.get('active_id')], {'frequence_id': ids[0]})

        return super(stock_frequence, self).choose_frequency(cr, uid, ids, context=context)

    def copy(self, cr, uid, id, default=None, context=None):
        if not default:
            default = {}
        default['auto_sup_ids'] = False
        return super(stock_frequence, self).copy(cr, uid, id, default, context)

stock_frequence()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
