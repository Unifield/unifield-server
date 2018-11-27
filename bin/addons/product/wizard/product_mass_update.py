# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
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
import time


class product_mass_update(osv.osv):
    _name = 'product.mass.update'
    _description = 'Product Mass Update'

    _order = 'id desc'

    def _get_expected_prod_creator(self, cr, uid, ids, field_names, arg, context=None):
        if context is None:
            context = {}

        obj_data = self.pool.get('ir.model.data')
        instance_level = self.pool.get('res.users').browse(cr, uid, uid).company_id.instance_id.level
        res = {}
        for p_mass_upd in self.browse(cr, uid, ids, fields_to_fetch=[], context=context):
            if instance_level == 'section':
                res[p_mass_upd.id] = obj_data.get_object_reference(cr, uid, 'product_attributes', 'int_3')[1]
            elif instance_level == 'coordo':
                res[p_mass_upd.id] = obj_data.get_object_reference(cr, uid, 'product_attributes', 'int_4')[1]
            else:
                res[p_mass_upd.id] = False

        return res

    def _expected_prod_creator_search(self, cr, uid, obj, name, args, context=None):
        '''
        Returns all documents according to the product creator
        '''
        if context is None:
            context = {}

        obj_data = self.pool.get('ir.model.data')
        instance_level = self.pool.get('res.users').browse(cr, uid, uid).company_id.instance_id.level
        prod_creator_id = False
        for arg in args:
            if arg[0] == 'expected_prod_creator':
                if instance_level == 'section':
                    prod_creator_id = obj_data.get_object_reference(cr, uid, 'product_attributes', 'int_3')[1]
                elif instance_level == 'coordo':
                    prod_creator_id = obj_data.get_object_reference(cr, uid, 'product_attributes', 'int_4')[1]

        return [('international_status', '=', prod_creator_id)]

    _columns = {
        'state': fields.selection(selection=[('draft', 'Draft'), ('done', 'Done')], string='Status', readonly=True),
        'date_done': fields.datetime(string='Date of the update'),
        'log': fields.char(string='Information', size=128, readonly=True),
        'import_in_progress': fields.boolean(string='Import in progress'),
        'expected_prod_creator': fields.function(_get_expected_prod_creator, method=True, type='many2one', relation='product.international.status',
                                                 fnct_search=_expected_prod_creator_search, readonly=True, string='Expected Product Creator'),
        'product_ids': fields.many2many('product.product', 'prod_mass_update_product_rel', 'product_id',
                                        'prod_cluster_import_id', string="Product selection", order_by="default_code",
                                        domain=[('international_status', '=', 'expected_prod_creator')]),
        # Fields
        'active_product': fields.selection(selection=[('', ''), ('no', 'No'), ('yes', 'Yes')], string='Active', help="If the active field is set to False, it allows to hide the nomenclature without removing it."),
        'dangerous_goods': fields.selection(selection=[('', ''), ('False', 'No'), ('True', 'Yes'), ('no_know', 'tbd')], string='Dangerous goods'),
        'heat_sensitive_item': fields.selection(selection=[('', ''), ('False', 'No'), ('True', 'Yes'), ('no_know', 'tbd')], string='Temperature sensitive item'),
        'single_use': fields.selection(selection=[('', ''), ('yes', 'Yes'), ('no', 'No'), ('no_know', 'tbd')], string='Single Use'),
        'short_shelf_life': fields.selection(selection=[('', ''), ('False', 'No'), ('True', 'Yes'), ('no_know', 'tbd')], string='Short Shelf Life'),
        'alert_time': fields.char(string='Product Alert Time', size=32, help="The number of days after which an alert should be notified about the production lot."),
        'life_time': fields.char('Product Life Time', size=32, help='The number of months before a production lot may become dangerous and should not be consumed.'),
        'use_time': fields.char('Product Use Time', size=32, help='The number of months before a production lot starts deteriorating without becoming dangerous.'),
        'procure_delay': fields.char(string='Procurement Lead Time', size=32,
                                     help='It\'s the default time to procure this product. This lead time will be used on the Order cycle procurement computation'),
        'procure_method': fields.selection([('', ''), ('make_to_stock', 'from stock'), ('make_to_order', 'on order')], 'Procurement Method',
                                           help="If you encode manually a Procurement, you probably want to use a make to order method."),
        'product_state': fields.selection([('', ''), ('valid', 'Valid'), ('phase_out', 'Phase Out'), ('stopped', 'Stopped'), ('archived', 'Archived'), ('status1', 'Status 1'), ('status2', 'Status 2'), ], 'Status', help="Tells the user if he can use the product or not."),
        'sterilized': fields.selection(selection=[('', ''), ('yes', 'Yes'), ('no', 'No'), ('no_know', 'tbd')], string='Sterile'),
        'supply_method': fields.selection([('', ''), ('produce', 'Produce'), ('buy', 'Buy')], 'Supply method',
                                          help="Produce will generate production order or tasks, according to the product type. Purchase will trigger purchase orders when requested."),
        'seller_id': fields.many2one('res.partner', 'Default Partner'),
        'property_account_income': fields.many2one('account.account', string='Income Account',
                                                   help='This account will be used for invoices instead of the default one to value sales for the current product'),
        'property_account_expense': fields.many2one('account.account', string='Expense Account',
                                                    help='This account will be used for invoices instead of the default one to value expenses for the current product'),
    }

    _defaults = {
        'state': 'draft',
        'active_product': '',
        'dangerous_goods': '',
        'heat_sensitive_item': '',
        'single_use': '',
        'short_shelf_life': '',
        'procure_method': '',
        'sterilized': '',
        'supply_method': '',
    }

    def cancel_update(self, cr, uid, ids, context=None):
        '''
        Delete the current Product Mass Update
        '''
        if context is None:
            context = {}

        self.unlink(cr, uid, ids, context=context)

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'product.mass.update',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'target': 'crush',
        }

    def apply_update(self, cr, uid, ids, context=None):
        '''
        Apply the current Product Mass Update
        '''
        if context is None:
            context = {}

        if not ids:
            return True

        prod_obj = self.pool.get('product.product')
        heat_obj = self.pool.get('product.heat_sensitive')
        p_state_obj = self.pool.get('product.status')
        p_suppinfo_obj = self.pool.get('product.supplierinfo')

        p_mass_upd = self.browse(cr, uid, ids[0], context=context)
        if not p_mass_upd.product_ids:
            raise osv.except_osv(_('Error'), _('You cannot apply an update on no products.'))

        vals = {}
        if p_mass_upd.dangerous_goods:
            vals.update({'dangerous_goods': p_mass_upd.dangerous_goods})
        if p_mass_upd.heat_sensitive_item:
            heat_ids = heat_obj.search(cr, uid, [('code', '=', p_mass_upd.heat_sensitive_item)], context=context)
            if heat_ids:
                vals.update({'heat_sensitive_item': heat_ids[0]})
        if p_mass_upd.short_shelf_life:
            vals.update({'short_shelf_life': p_mass_upd.short_shelf_life})
        if p_mass_upd.alert_time:
            try:
                alert_time = int(p_mass_upd.alert_time)
                vals.update({'alert_time': alert_time})
            except ValueError:
                raise osv.except_osv(_('Error'), _('Alert Time must be an integer.'))
        if p_mass_upd.life_time:
            try:
                life_time = int(p_mass_upd.life_time)
                vals.update({'life_time': life_time})
            except ValueError:
                raise osv.except_osv(_('Error'), _('Life Time must be an integer.'))
        if p_mass_upd.use_time:
            try:
                use_time = int(p_mass_upd.use_time)
                vals.update({'use_time': use_time})
            except ValueError:
                raise osv.except_osv(_('Error'), _('Use Time must be an integer.'))
        if p_mass_upd.procure_delay:
            try:
                procure_delay = float(p_mass_upd.procure_delay)
                vals.update({'procure_delay': procure_delay})
            except ValueError:
                raise osv.except_osv(_('Error'), _('Procurement Lead Time must be a float.'))
        if p_mass_upd.procure_method:
            vals.update({'procure_method': p_mass_upd.procure_method})
        if p_mass_upd.single_use:
            vals.update({'single_use': p_mass_upd.single_use})
        if p_mass_upd.product_state:
            p_state_ids = p_state_obj.search(cr, uid, [('code', '=', p_mass_upd.product_state)], context=context)
            if p_state_ids:
                vals.update({'state': p_state_ids[0]})
        if p_mass_upd.sterilized:
            vals.update({'sterilized': p_mass_upd.sterilized})
        if p_mass_upd.supply_method:
            vals.update({'supply_method': p_mass_upd.supply_method})
        if p_mass_upd.property_account_income:
            vals.update({'property_account_income': p_mass_upd.property_account_income.id})
        if p_mass_upd.property_account_expense:
            vals.update({'property_account_expense': p_mass_upd.property_account_expense.id})

        for prod in p_mass_upd.product_ids:
            if p_mass_upd.seller_id and not p_suppinfo_obj.search(cr, uid, [('product_id', '=', prod.id), ('name', '=', p_mass_upd.seller_id.id)], context=context):
                p_suppinfo_obj.create(cr, uid, {'product_id': prod.id, 'name': p_mass_upd.seller_id.id, 'sequence': 1}, context=context)
            prod_obj.write(cr, uid, prod.id, vals, context=context)
            if p_mass_upd.active_product:
                if not prod.active and p_mass_upd.active_product == 'yes':
                    prod_obj.reactivate_product(cr, uid, [prod.id], context=context)
                elif prod.active and p_mass_upd.active_product == 'no':
                    prod_obj.deactivate_product(cr, uid, [prod.id], context=context)

        user = self.pool.get('res.users').browse(cr, uid, uid, context=context).name
        log = _('Modification of %s product(s) the %s done by %s') % \
              (len(p_mass_upd.product_ids), time.strftime('%d/%m/%Y'), user)
        self.write(cr, uid, ids[0], {'date_done': time.strftime('%Y-%m-%d %H:%M'), 'log': log, 'state': 'done'}, context=context)

        return True


product_mass_update()
