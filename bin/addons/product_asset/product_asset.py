# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 MSF, TeMPO Consulting
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
import time


#----------------------------------------------------------
# Assets
#----------------------------------------------------------
class product_asset_type(osv.osv):
    _name = "product.asset.type"
    _description = "Specify the type of asset at product level"

    _columns = {
        'name': fields.char('Name', size=64, required=True),
    }

product_asset_type()



class product_asset(osv.osv):
    _name = "product.asset"
    _description = "A specific asset of a product"

    def _getRelatedProductFields(self, cr, uid, productId):
        '''
        get related fields from product
        '''
        result = {}
        # if no product, return empty dic
        if not productId:
            return result

        # fetch the product
        product = self.pool.get('product.product').browse(cr, uid, productId)

        result.update({
            'asset_type_id': product.asset_type_id.id,
            'prod_int_code': product.default_code,
            'prod_int_name': product.name,
            'nomenclature_description': product.nomenclature_description,
        })

        return result

    def copy(self, cr, uid, id, default=None, context=None):
        '''
        override copy to update the asset code which comes from a sequence
        '''
        if not default:
            default = {}
        default.update({
            'name': self.pool.get('ir.sequence').get(cr, uid, 'product.asset'),
            'partner_name': False,
        })
        # call to super
        return super(product_asset, self).copy(cr, uid, id, default, context=context)

    def copy_data(self, cr, uid, id, default=None, context=None):
        '''
        do not copy asset events
        '''
        if not default:
            default = {}
        default.update({
            'event_ids': [],
            'partner_name': False,
        })
        return super(product_asset, self).copy_data(cr, uid, id, default, context=context)

    def write(self, cr, user, ids, vals, context=None):
        '''
        override write method to force readonly fields to be saved to db
        on data update
        '''
        if not ids:
            return True
        # fetch the product
        if 'product_id' in vals:
            productId = vals['product_id']
            # add readonly fields to vals
            vals.update(self._getRelatedProductFields(cr, user, productId))

        # save the data to db
        return super(product_asset, self).write(cr, user, ids, vals, context)

    def create(self, cr, uid, vals, context=None):
        '''
        override create method to force readonly fields to be saved to db
        on data creation
        '''
        # fetch the product
        if 'product_id' in vals:
            productId = vals['product_id']
            # add readonly fields to vals
            vals.update(self._getRelatedProductFields(cr, uid, productId))

        # UF-1617: set the current instance into the new object if it has not been sent from the sync
        if 'partner_name' not in vals or not vals['partner_name']:
            company = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id
            if company and company.partner_id:
                vals['partner_name'] = company.partner_id.name

        # UF-2148: make the xmlid_name from the asset name for building xmlid if it is not given in the vals
        if 'xmlid_name' not in vals or not vals['xmlid_name']:
            vals['xmlid_name'] = vals['name']

        exist = self.search(cr, uid, [('xmlid_name', '=', vals['xmlid_name']),
                                      ('partner_name', '=', vals['partner_name']), ('product_id', '=',
                                                                                    vals['product_id'])], limit=1, order='NO_ORDER', context=context)
        if exist:
            # but if the value exist for xml_name, then just add a suffix to differentiate them, no constraint unique required here
            vals['xmlid_name'] = vals['xmlid_name'] + "_1"

        return super(product_asset, self).create(cr, uid, vals, context)

    def onChangeProductId(self, cr, uid, ids, productId):
        '''
        on change function when the product is changed
        '''
        result = {}

        # no product selected
        if not productId:
            return result

        result.update({'value': self._getRelatedProductFields(cr, uid, productId)
                       })

        return result


    def onChangeYear(self, cr, uid, ids, year):
        '''
        year must be 4 digit long and comprised between 1900 and 2100
        '''
        value = {}
        warning = {}
        result = {'value': value, 'warning': warning}

        if not year:
            return result

        # check that the year specified is a number
        try:
            intValue = int(year)
        except:
            intValue = False

        if not intValue:
            warning.update({
                'title':'The format of year is invalid.',
                'message':
                        'The format of the year must be 4 digits, e.g. 1983.'
            })
        elif len(year) != 4:
            warning.update({
                'title':'The length of year is invalid.',
                'message':
                        'The length of year must be 4 digits long, e.g. 1983.'
            })
        elif (intValue < 1900) or (intValue > 2100):
            warning.update({
                'title':'The year is invalid.',
                'message':
                        'The year must be between 1900 and 2100.'
            })

        # if a warning has been generated, clear the field
        if 'title' in warning:
            value.update({'year': ''})

        return result

    _columns = {
        # asset
        'name': fields.char('Asset Code', size=128, required=True),
        'asset_type_id': fields.many2one('product.asset.type', 'Asset Type', readonly=True), # from product
        'description': fields.char('Asset Description', size=128),
        'product_id': fields.many2one('product.product', 'Product', domain="[('subtype','=','asset')]", required=True, ondelete='cascade'),
        # msf codification
        'prod_int_code': fields.char('Product Code', size=128, readonly=True), # from product
        'prod_int_name': fields.char('Product Description', size=128, readonly=True), # from product
        'nomenclature_description': fields.char('Product Nomenclature', size=128, readonly=True), # from product when merged - to be added in _getRelatedProductFields and add dependency to module product_nomenclature
        'hq_ref': fields.char('HQ Reference', size=128),
        'local_ref': fields.char('Local Reference', size=128),
        # asset reference
        'serial_nb': fields.char('Serial Number', size=128, required=True),
        'brand': fields.char('Brand', size=128, required=True),
        'type': fields.char('Type', size=128, required=True),
        'model': fields.char('Model', size=128, required=True),
        'year': fields.char('Year', size=4),
        # remark
        'comment': fields.text('Comment'),
        # traceability
        'project_po': fields.char('Project PO', size=128),
        'orig_mission_code': fields.char('Original Mission Code', size=128, required=True),
        'international_po': fields.char('International PO', size=128, required=True),
        'arrival_date': fields.date('Arrival Date', required=True),
        'receipt_place': fields.char('Receipt Place', size=128, required=True),
        # Invoice
        'invo_num': fields.char('Invoice Number', size=128, required=True),
        'invo_date': fields.date('Invoice Date', required=True),
        'invo_value': fields.float('Value', required=True),
        #'invo_currency': fields.char('Currency', size=128, required=True),
        'invo_currency': fields.many2one('res.currency', 'Currency', required=True),
        'invo_supplier': fields.char('Supplier', size=128),
        'invo_donator_code': fields.char('Donator Code', size=128),
        'invo_certif_depreciation': fields.char('Certificate of Depreciation', size=128),
        # event history
        'event_ids': fields.one2many('product.asset.event', 'asset_id', 'Events'),
        # UF-1617: field only used for sync purpose
        'partner_id': fields.many2one('res.partner', string="Supplier", readonly=True, required=False),
        'partner_name': fields.char('Partner', size=128, required=True),
        'xmlid_name': fields.char('XML Code, hidden field', size=128, required=True),
    }

    _defaults = {
        'name': lambda obj, cr, uid, context: obj.pool.get('ir.sequence').get(cr, uid, 'product.asset'),
        'arrival_date': lambda *a: time.strftime('%Y-%m-%d'),
        'receipt_place': 'Country/Project/Activity',
    }
    # UF-2148: use this constraint with 3 attrs: name, prod and instance
    _sql_constraints = [('asset_name_uniq', 'unique(name, product_id, partner_name)', 'Asset Code must be unique per instance and per product!'),
                        ]
    _order = 'name desc'

product_asset()


class product_asset_event(osv.osv):
    _name = "product.asset.event"
    _rec_name = 'asset_id'
    _description = "Event for asset follow up"

    stateSelection = [('blank', ' '),
                      ('inUse', 'In Use'),
                      ('stock', 'Stock'),
                      ('repair', 'Repair'),
                      ]

    eventTypeSelection = [('reception', 'Reception'),
                          ('startUse', 'Start Use'),
                          ('repairing', 'Repairing'),
                          ('endUse', 'End Use'),
                          ('obsolete', 'Obsolete'),
                          ('loaning', 'Loaning'),
                          ('transfer', 'Transfer (internal)'),
                          ('donation', 'Donation (external)'),
                          ('other', 'Other'),
                          ]

    def name_get(self, cr, uid, ids, context=None):
        '''
        override because no name field is defined
        '''
        result = []
        for e in self.read(cr, uid, ids, ['asset_id', 'date'], context):
            # e = dict: {'asset_id': (68, 'AF/00045'), 'date': '2011-05-05', 'id': 75}
            result.append((e['id'], '%s - %s'%(e['asset_id'][1], e['date'])))

        return result

    def _getRelatedAssetFields(self, cr, uid, assetId):
        '''
        get related fields from product
        '''
        result = {}
        # if no asset, return empty dic
        if not assetId:
            return result

        # newly selected asset object
        asset = self.pool.get('product.asset').browse(cr, uid, assetId)

        result.update({
            'product_id': asset.product_id.id,
            'asset_type_id': asset.asset_type_id.id,
            'serial_nb': asset.serial_nb,
            'brand': asset.brand,
            'model': asset.model,
        })

        return result

    def write(self, cr, user, ids, vals, context=None):
        '''
        override write method to force readonly fields to be saved to db
        on data update
        '''
        if not ids:
            return True
        # fetch the asset
        if 'asset_id' in vals:
            assetId = vals['asset_id']
            # add readonly fields to vals
            vals.update(self._getRelatedAssetFields(cr, user, assetId))

        # save the data to db
        return super(product_asset_event, self).write(cr, user, ids, vals, context)

    def create(self, cr, user, vals, context=None):
        '''
        override create method to force readonly fields to be saved to db
        on data creation
        '''
        # fetch the asset
        if 'asset_id' in vals:
            assetId = vals['asset_id']
            # add readonly fields to vals
            vals.update(self._getRelatedAssetFields(cr, user, assetId))

        # save the data to db
        return super(product_asset_event, self).create(cr, user, vals, context)

    def onChangeAssetId(self, cr, uid, ids, assetId):

        result = {}

        # no asset selected
        if not assetId:
            return result

        result.update({'value': self._getRelatedAssetFields(cr, uid, assetId)})

        return result

    _columns = {
        # event information
        'date': fields.date('Date', required=True),
        'location': fields.char('Location', size=128, required=True),
        'proj_code': fields.char('Project Code', size=128, required=True),
        'event_type': fields.selection(eventTypeSelection, 'Event Type', required=True),
        'state': fields.selection(stateSelection, 'Current Status'),
        # selection
        'asset_id': fields.many2one('product.asset', 'Asset Code', required=True, ondelete='cascade'),
        'product_id': fields.many2one('product.product', 'Product', readonly=True, ondelete='cascade'),
        'serial_nb': fields.char('Serial Number', size=128, readonly=True),
        'brand': fields.char('Brand', size=128, readonly=True), # from asset
        'model': fields.char('Model', size=128, readonly=True), # from asset
        'comment': fields.text('Comment'),

        'asset_type_id': fields.many2one('product.asset.type', 'Asset Type', readonly=True), # from asset
    }

    _defaults = {
        'date': lambda *a: time.strftime('%Y-%m-%d'),
        'state': 'blank',
    }

product_asset_event()

#----------------------------------------------------------
# Products
#----------------------------------------------------------
class product_template(osv.osv):

    _inherit = "product.template"
    _description = "Product Template"

    PRODUCT_SUBTYPE = [('single','Single Item'),('kit', 'Kit/Module'),('asset','Asset')]

    _columns = {
        'subtype': fields.selection(PRODUCT_SUBTYPE, 'Product SubType', required=True, help="Will change the way procurements are processed."),
        'asset_type_id': fields.many2one('product.asset.type', 'Asset Type'),
    }

    _defaults = {
        'subtype': lambda *a: 'single',
    }

product_template()

class product_product(osv.osv):

    _inherit = "product.product"
    _description = "Product"

    def write(self, cr, uid, ids, vals, context=None):
        '''
        if a product is not of type product, it is set to single subtype
        '''
        if not ids:
            return True
        if context is None:
            context={}
        # fetch the product
        if 'type' in vals and vals['type'] != 'product':
            vals.update(subtype='single')

        #UF-2170: remove the standard price value from the list if the value comes from the sync
        #US-803: If the price comes from rw_sync, then take it
        # US-3254: update standard_pricde during initial sync (i.e if msf.instance is not set)
        if 'standard_price' in vals and context.get('sync_update_execution', False) and not context.get('rw_sync', False) and not context.get('keep_standard_price'):
            msf_instance = self.pool.get('res.users').browse(cr, uid, uid).company_id.instance_id
            if msf_instance:
                del vals['standard_price']
            elif not vals['standard_price']:
                vals['standard_price'] = 1

        return super(product_product, self).write(cr, uid, ids, vals, context=context)

    def create(self, cr, uid, vals, context=None):
        if context is None:
            context = {}

        if context.get('sync_update_execution', False) and 'standard_price' in vals and not vals['standard_price']:
            vals['standard_price'] = 1

        return super(product_product, self).create(cr, uid, vals, context)


    def _constaints_product_consu(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        for obj in self.read(cr, uid, ids, ['type', 'procure_method'], context=context):
            if obj['type'] == 'consu' and obj['procure_method'] != 'make_to_order':
                return False
        return True


    _columns = {
        'asset_ids': fields.one2many('product.asset', 'product_id', 'Assets')
    }

    _constraints = [
        (_constaints_product_consu, 'If you select "Non-stockable" as product type then you have to select "Make to order" as procurement method', []),
    ]

product_product()

#----------------------------------------------------------
# Stock moves
#----------------------------------------------------------
class stock_move(osv.osv):

    _inherit = "stock.move"
    _description = "Stock Move"

    def _do_partial_hook(self, cr, uid, ids, context, *args, **kwargs):
        '''
        hook to update defaults data
        '''
        # variable parameters
        move = kwargs.get('move')
        assert move, 'missing move'
        partial_datas = kwargs.get('partial_datas')
        assert partial_datas, 'missing partial_datas'

        # calling super method
        defaults = super(stock_move, self)._do_partial_hook(cr, uid, ids, context, *args, **kwargs)
        assert defaults is not None

        assetId = partial_datas.get('move%s'%(move.id), False).get('asset_id')
        if assetId:
            defaults.update({'asset_id': assetId})

        return defaults

stock_move()


class stock_picking(osv.osv):
    '''

    '''
    _inherit = 'stock.picking'
    _description = 'Stock Picking with hook'

    def _do_partial_hook(self, cr, uid, ids, context, *args, **kwargs):
        '''
        hook to update defaults data
        '''
        # variable parameters
        move = kwargs.get('move')
        assert move, 'missing move'
        partial_datas = kwargs.get('partial_datas')
        assert partial_datas, 'missing partial_datas'

        # calling super method
        defaults = super(stock_picking, self)._do_partial_hook(cr, uid, ids, context, *args, **kwargs)
        assetId = partial_datas.get('move%s'%(move.id), {}).get('asset_id')
        if assetId:
            defaults.update({'asset_id': assetId})

        return defaults

stock_picking()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
