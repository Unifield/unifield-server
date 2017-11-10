# -*- coding: utf-8 -*-

import time

from osv import fields, osv
from tools.translate import _
import decimal_precision as dp


PHYSICAL_INVENTORIES_STATES = (
    ('draft', _('Draft')),
    ('counting', _('Counting')),
    ('counted', _('Counted')),
    ('validated', _('Validated')),
    ('confirmed', _('Confirmed')),
    ('closed', _('Closed')),
    ('cancelled', _('Cancelled'))
)


class PhysicalInventory(osv.osv):
    _name = 'physical.inventory'
    _description = 'Physical Inventory'

    _columns = {
        'ref': fields.char('Reference', size=64, required=True),
        'name': fields.char('Name', size=64, required=True),
        'date': fields.datetime('Creation Date', readonly=True, required=True),
        'responsible': fields.char('Responsible', size=128, required=False),
        'date_done': fields.datetime('Date done', readonly=True),
        'product_ids': fields.many2many('product.product', 'physical_inventory_product_rel',
                                        'product_id', 'inventory_id', string="Product selection"),
        'line_ids': fields.one2many('physical.inventory.line', 'inventory_id', 'Inventories',
                                    states={'closed': [('readonly', True)]}),
        'counting_line_ids': fields.one2many('physical.inventory.counting', 'inventory_id', 'Counting lines',
                                    states={'closed': [('readonly', True)]}),
        'location_id': fields.many2one('stock.location', 'Location', required=True),
        'move_ids': fields.many2many('stock.move', 'physical_inventory_move_rel', 'inventory_id', 'move_id',
                                     'Created Moves'),
        'state': fields.selection(PHYSICAL_INVENTORIES_STATES, 'State', readonly=True, select=True),
        'company_id': fields.many2one('res.company', 'Company', readonly=True, select=True, required=True,
                                      states={'draft': [('readonly', False)]}),
        'full_inventory': fields.boolean('Full inventory', readonly=True, states={'draft': [('readonly', False)]}),
    }

    _defaults = {
        'ref': lambda obj, cr, uid, context: obj.pool.get('ir.sequence').get(cr, uid, 'physical.inventory'),
        'date': lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
        'state': 'draft',
        'company_id': lambda self, cr, uid,
                             c: self.pool.get('res.company')._company_default_get(cr, uid, 'stock.inventory', context=c)
    }

    def perm_write(self, cr, user, ids, fields, context=None):
        pass

    def action_select_products(self, cr, uid, ids, context=None):
        """
        Trigerred when clicking on the button "Products Select"

        Open the wizard to select the products according to specific filters..
        """
        context = context is None and {} or context

        # Prepare values to feed the wizard with
        assert len(ids) == 1
        inventory_id = ids[0]
        full_inventory = self.read(cr, uid, ids, ['full_inventory'], context)[0]["full_inventory"]
        vals = {"inventory_id": inventory_id,
                "full_inventory": full_inventory
                }

        # Create the wizard
        wiz_id = self.pool.get('physical.inventory.select.products').create(cr, uid, vals, context=context)
        context['wizard_id'] = wiz_id

        # Get the view reference
        data_obj = self.pool.get('ir.model.data')
        view_id = data_obj.get_object_reference(cr, uid, 'stock', 'physical_inventory_select_products')[1]

        # Return a description of the wizard view
        return {'type': 'ir.actions.act_window',
                'res_model': 'physical.inventory.select.products',
                'res_id': wiz_id,
                'view_id': [view_id],
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'context': context}

    def generate_counting_sheet(self, cr, user, ids, context=None):
        pass

    def export_xls_counting_sheet(self, cr, uid, ids, context=None):
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'physical_inventory_counting_sheet_xls',
            'datas': {'ids': ids},
            'nodestroy': True,
            'context': context,
        }

    def export_pdf_counting_sheet(self, cr, uid, ids, context=None):
        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'physical_inventory_counting_sheet_pdf',
            'datas': {'ids': ids},
            'nodestroy': True,
            'context': context,
        }

    def import_counting_sheet(self, cr, uid, ids, context=None):
        pass


PhysicalInventory()


class PhysicalInventoryCounting(osv.osv):
    _name = 'physical.inventory.counting'
    _description = 'Physical Inventory Counting Line'

    _columns = {
        'inventory_id': fields.many2one('stock.inventory', _('Inventory'), ondelete='cascade', select=True),
        'line_no': fields.integer(string=_('Line #'), readonly=True),
        'product_id': fields.many2one('product.product', _('Product'), required=True, select=True,
                                      domain=[('type', '<>', 'service')]),
        'product_uom_id': fields.many2one('product.uom', _('Product UOM'), required=True),
        'batch_number': fields.char(_('Batch number'), size=30),
        'expiry_date': fields.date(string=_('Expiry date')),
        'quantity': fields.char(_('Quantity'), size=15),
        'is_bn': fields.related('product_id', 'batch_management', string='BN', type='boolean', readonly=True),
        'is_ed': fields.related('product_id', 'perishable', string='ED', type='boolean', readonly=True),
        'is_kc': fields.related('product_id', 'is_kc', string='KC', type='boolean', readonly=True),
        'is_dg': fields.related('product_id', 'is_dg', string='DG', type='boolean', readonly=True),
        'is_cs': fields.related('product_id', 'is_cs', string='CS', type='boolean', readonly=True),
    }

    def create(self, cr, user, vals, context=None):
        # Compute line number
        if not vals.get('line_no'):
            cr.execute("""SELECT MAX(line_no) FROM physical_inventory_counting WHERE inventory_id=%s""",
                       (vals.get('inventory_id'),))
            vals['line_no'] = (cr.fetchone()[0] or 0) + 1  # Last line number + 1

        return super(PhysicalInventoryCounting, self).create(cr, user, vals, context)

    @staticmethod
    def quantity_validate(cr, quantity):
        """Return a valide quantity or raise ValueError exception"""
        if quantity:
            float_width, float_prec = dp.get_precision('Product UoM')(cr)
            quantity = float(quantity)
            if quantity < 0:
                raise ValueError()
            quantity = '%.*f' % (float_prec, quantity)
        return quantity

    def on_change_quantity(self, cr, uid, ids, quantity):
        """Check and format quantity."""
        if quantity:
            try:
                quantity = self.quantity_validate(cr, quantity)
            except ValueError:
                return {'value': {'physical_qty': False}, 'warning': {'title': 'warning', 'message': 'Enter a valid quantity.'}}
        return {'value': {'physical_qty': quantity}}

    def on_change_product_id(self, cr, uid, ids, product_id, uom=False):
        """Changes UoM and quantity if product_id changes."""
        if product_id and not uom:
            product_rec = self.pool.get('product.product').browse(cr, uid, product_id)
            uom = product_rec.uom_id and product_rec.uom_id.id
        return {'value': {'quantity': False, 'product_uom_id': product_id and uom}}

    def perm_write(self, cr, user, ids, fields, context=None):
        pass


PhysicalInventoryCounting()


class PhysicalInventoryLine(osv.osv):
    _name = 'physical.inventory.line'
    _description = 'Physical Inventory Line'

    _columns = {
        'inventory_id': fields.many2one('stock.inventory', 'Inventory', ondelete='cascade', select=True),
        'product_id': fields.many2one('product.product', 'Product', required=True, select=True),
        'product_uom_id': fields.many2one('product.uom', 'Product UOM', required=True),
        'count_qty': fields.float('Quantity', digits_compute=dp.get_precision('Product UoM')),
        'initial_qty': fields.float('Quantity', digits_compute=dp.get_precision('Product UoM')),
        'company_id': fields.related('inventory_id', 'company_id', type='many2one', relation='res.company',
                                     string='Company', store=True, select=True, readonly=True),
        'prod_lot_id': fields.many2one('stock.production.lot', 'Production Lot',
                                       domain="[('product_id','=',product_id)]"),
        'state': fields.related('inventory_id', 'state', type='char', string='State', readonly=True),
    }

    def perm_write(self, cr, user, ids, fields, context=None):
        pass


PhysicalInventoryLine()
