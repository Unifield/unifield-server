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

from osv import fields, osv

class stock_production_lot(osv.osv):
    _inherit = 'stock.production.lot'


    # UF-1617: Handle the instance in the batch number object
    def copy(self, cr, uid, id, default=None, context=None):
        if not default:
            default = {}
        default.update({
            'partner_name': False,
        })
        return super(stock_production_lot, self).copy(cr, uid, id, default, context=context)

    # UF-1617: Handle the instance in the batch number object
    def copy_data(self, cr, uid, id, default=None, context=None):
        '''
        do not copy asset events
        '''
        if not default:
            default = {}
        default.update({
            'partner_name': False,
        })
        return super(stock_production_lot, self).copy_data(cr, uid, id, default, context=context)

    # UF-1617: Handle the instance in the batch number object
    # US-838: this method is removed in integration, because the 2 fields are no more used, xmlid_name and partner name



    # US-838: This method got moved from addons/msf_outgoing/wizard/incoming_shipment_processor.py
    def _get_prodlot_from_expiry_date(self, cr, uid, expiry_date, product_id, comment, context=None):
        """
        Search if an internal batch exists in the system with this expiry date.
        If no, create the batch.
        """
        # Objects
        seq_obj = self.pool.get('ir.sequence')

        # Double check to find the corresponding batch
        lot_ids = self.search(cr, uid, [
            ('life_date', '=', expiry_date),
            ('type', '=', 'internal'),
            ('product_id', '=', product_id),
        ], context=context)

        # No batch found, create a new one
        if not lot_ids:
            seq_ed = seq_obj.get(cr, uid, 'stock.lot.serial')
            vals = {
                'product_id': product_id,
                'life_date': expiry_date,
                'name': seq_ed,
                'type': 'internal',
                'comment': comment,  # Add comment through synchro
            }
            lot_id = self.create(cr, uid, vals, context)
        else:
            lot_id = lot_ids[0]
            # Add comment through synchro
            self.write(cr, uid, lot_id, {'comment': comment}, context=context)

        return lot_id

    _columns = {
        # UF-1617: field only used for sync purpose
        'partner_id': fields.many2one('res.partner', string="Supplier", readonly=True, required=False),
        'partner_name': fields.char('Partner', size=128),
        'xmlid_name': fields.char('XML Code, hidden field', size=128), # UF-2148, this field is used only for xml_id
    }


    # UF-2148: Removed the name unique constraint in specific_rules and use only this constraint with 3 attrs: name, prod and instance
    _sql_constraints = [('batch_name_uniq', 'unique(name, product_id, life_date)', 'Batch name must be unique per product and expiry date!'),]

stock_production_lot()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
