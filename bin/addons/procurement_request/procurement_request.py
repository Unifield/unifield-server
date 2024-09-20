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
from tools.translate import _
import datetime
import decimal_precision as dp
import netsvc

from msf_order_date.order_dates import compute_rts


class procurement_request(osv.osv):
    _name = 'sale.order'
    _inherit = 'sale.order'

    def _ir_amount_all(self, cr, uid, ids, field_name, arg, context=None):
        cur_obj = self.pool.get('res.currency')
        res = {}
        for ir in self.browse(cr, uid, ids, context=context):
            res[ir.id] = 0.0
            val = 0.0
            if ir.procurement_request:
                curr_browse = self.pool.get('res.users').browse(cr, uid, [uid], context)[0].company_id.currency_id
                for line in ir.order_line:
                    if line.state not in ('cancel', 'cancel_r'):
                        val += line.price_subtotal
                res[ir.id] = cur_obj.round(cr, uid, curr_browse.rounding, val)
        return res

    def _amount_by_type(self, cr, uid, ids, field_name, arg, context=None):
        '''
        Compute the amount of line by type of procurement
        '''
        line_obj = self.pool.get('sale.order.line')

        res = {}

        for id in ids:
            res[id] = {'purchase_amount': 0.00, 'stock_amount': 0.00, 'proc_amount': 0.00}

        line_ids = line_obj.search(cr, uid, [('order_id', 'in', ids)], context=context)

        for line_data in line_obj.read(cr, uid, line_ids, ['price_subtotal', 'order_id', 'type', 'state'], context=context):
            if line_data['state'] not in ('cancel', 'cancel_r'):
                order_id = line_data['order_id'][0]
                line_amount = line_data['price_subtotal'] or 0
                res[order_id]['proc_amount'] += line_amount
                if line_data['type'] == 'make_to_stock':
                    res[order_id]['stock_amount'] += line_amount
                else:
                    res[order_id]['purchase_amount'] += line_amount

        return res

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        '''
        Returns the procurement request search view instead of default sale order search view
        '''
        if not context:
            context = {}
        obj_data = self.pool.get('ir.model.data')
        if view_type == 'search' and context.get('procurement_request') and not view_id:
            view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'procurement_request', 'procurement_request_search_view')[1]

        elif view_type == 'form' and context.get('procurement_request'):
            view_id = obj_data.get_object_reference(cr, uid, 'procurement_request', 'procurement_request_form_view')[1]

        return super(procurement_request, self).fields_view_get(cr, uid, view_id=view_id, view_type=view_type, context=context, toolbar=toolbar, submenu=submenu)

    _columns = {
        'date_order': fields.date('Ordered Date', required=True, readonly=False, select=True, states={}),
        'location_requestor_id': fields.many2one('stock.location', string='Location Requestor', ondelete="cascade",
                                                 domain=[('location_category', '!=', 'transition'), '|', ('usage', '=', 'internal'), '&', ('usage', '=', 'customer'), ('location_category', '=', 'consumption_unit')], help='The location where the products will be delivered to'),
        'requestor': fields.char(size=128, string='Requestor', states={'draft': [('readonly', False)]}, readonly=True),
        'procurement_request': fields.boolean(string='Internal Request', readonly=True),
        'warehouse_id': fields.many2one('stock.warehouse', string='Warehouse'),
        'origin': fields.char(size=512, string='Origin', readonly=True),
        'notes': fields.text(string='Notes'),
        'order_ids': fields.one2many(
            'procurement.request.sourcing.document',
            'order_id',
            string='Sourcing document',
            readonly=True,
        ),
        'ir_total_amount': fields.function(_ir_amount_all, method=True, digits_compute=dp.get_precision('Sale Price'), string='Indicative Total Value'),
        'purchase_amount': fields.function(_amount_by_type, method=True, digits_compute=dp.get_precision('Sale Price'), string='Purchase Total', help="The amount of lines sourced on order", multi='by_type'),
        'stock_amount': fields.function(_amount_by_type, method=True, digits_compute=dp.get_precision('Sale Price'), string='Stock Total', help="The amount of lines sourced from stock", multi='by_type'),
        'proc_amount': fields.function(_amount_by_type, method=True, digits_compute=dp.get_precision('Sale Price'), string='Stock Total', help="The amount of lines sourced from stock", multi='by_type'),
        'name': fields.char('Order Reference', size=64, required=True, readonly=True, select=True, sort_column='id'),
        'is_ir_from_po_cancel': fields.boolean('Is IR from a PO cancelled', invisible=True),  # UFTP-82: flagging we are in an IR and its PO is cancelled
    }

    _defaults = {
        'name': lambda *a: False,
        'procurement_request': lambda obj, cr, uid, context: context.get('procurement_request', False),
        'state': 'draft',
        'warehouse_id': lambda obj, cr, uid, context: len(obj.pool.get('stock.warehouse').search(cr, uid, [])) and obj.pool.get('stock.warehouse').search(cr, uid, [])[0],
        'is_ir_from_po_cancel': False,  # UFTP-82
    }

    def create(self, cr, uid, vals, context=None):
        if not context:
            context = {}

        pricelist_obj = self.pool.get('product.pricelist')

        if context.get('procurement_request') or vals.get('procurement_request', False):
            # Get the ISR number
            if not vals.get('name', False):
                vals.update({'name': self.pool.get('ir.sequence').get(cr, uid, 'procurement.request')})

            company = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id
            if company.partner_id.address:
                address_id = company.partner_id.address[0].id
            else:
                address_id = self.pool.get('res.partner.address').search(cr, uid, [], limit=1)[0]
            vals['partner_id'] = company.partner_id.id
            vals['partner_order_id'] = address_id
            vals['partner_invoice_id'] = address_id
            vals['partner_shipping_id'] = address_id
            pl = pricelist_obj.search(cr, uid, [('type', '=', 'sale'),
                                                ('currency_id', '=', company.currency_id.id)], limit=1)[0]
            vals['pricelist_id'] = pl
            if vals.get('delivery_requested_date'):
                vals['ready_to_ship_date'] = compute_rts(self, cr, uid, vals['delivery_requested_date'], 0, 'so', context=context)
        elif not vals.get('name', False):
            vals.update({'name': self.pool.get('ir.sequence').get(cr, uid, 'sale.order')})

        return super(procurement_request, self).create(cr, uid, vals, context)

    def write(self, cr, uid, ids, vals, context=None):
        '''
        Update date_planned of lines
        '''
        if not ids:
            return True

        if isinstance(ids, int):
            ids = [ids]

        for req in self.browse(cr, uid, ids, context=context):
            # Only in case of Internal request
            if req.procurement_request and vals.get('delivery_requested_date'):
                rts = compute_rts(self, cr, uid, vals['delivery_requested_date'], 0, 'so', context=context)
                vals['ready_to_ship_date'] = rts
                for line in req.order_line:
                    self.pool.get('sale.order.line').write(cr, uid, line.id, {'date_planned': vals['delivery_requested_date']}, context=context)

        return super(procurement_request, self).write(cr, uid, ids, vals, context=context)

    def unlink(self, cr, uid, ids, context=None):
        '''
        Changes the state of the order to allow the deletion
        '''
        del_ids = []
        normal_ids = []

        for request in self.browse(cr, uid, ids, context=context):
            if request.procurement_request and request.state in ['draft', 'cancel']:
                del_ids.append(request.id)
            elif not request.procurement_request:
                normal_ids.append(request.id)
            else:
                raise osv.except_osv(_('Invalid action !'), _('Cannot delete Internal Request(s) which are already validated !'))

        if del_ids:
            osv.osv.unlink(self, cr, uid, del_ids, context=context)

        return super(procurement_request, self).unlink(cr, uid, normal_ids, context=context)

    def search(self, cr, uid, args=None, offset=0, limit=None, order=None, context=None, count=False):
        '''
        Adds automatically a domain to search only True sale orders if no procurement_request in context
        '''
        test = True
        if args is None:
            args = []
        if context is None:
            context = {}
        for a in args:
            if a[0] == 'procurement_request':
                test = False

        if not context.get('procurement_request', False) and test:
            args.append(('procurement_request', '=', False))

        return super(procurement_request, self).search(cr, uid, args, offset,
                                                       limit, order, context, count)

    def _hook_copy_default(self, cr, uid, *args, **kwargs):
        id = kwargs['id']
        default = kwargs['default']
        context = kwargs['context']

        if not default:
            default = {}
        order = self.browse(cr, uid, id)
        proc = order.procurement_request or context.get('procurement_request', False)
        default.update({
            'shipped': False,
            'invoice_ids': [],
            'picking_ids': [],
            'date_confirm': False,
            'procurement_request': proc,
        })
        # UFTP-322: Remove the block of code to calculate 'name' as the creation could be blocked by the user right to make a wrong increase of sequence
        # moved this block of code to analytic_distribution_supply/sale.py method copy_data()
        return default

    def copy(self, cr, uid, id, default, context=None):
        if not default:
            default = {}

        if not default.get('order_ids'):
            default['order_ids'] = None

        obj = self.browse(cr, uid, id, fields_to_fetch=['location_requestor_id'], context=context)
        if obj.location_requestor_id and not obj.location_requestor_id.active:
            default['location_requestor_id'] = False
        # bypass name sequence
        new_id = super(procurement_request, self).copy(cr, uid, id, default, context=context)
        if new_id:
            new_order = self.read(cr, uid, new_id, ['delivery_requested_date', 'order_line'])
            if new_order['delivery_requested_date'] and new_order['order_line']:
                self.pool.get('sale.order.line').write(cr, uid, new_order['order_line'], {'date_planned': new_order['delivery_requested_date']})
        return new_id


    def wkf_action_cancel(self, cr, uid, ids, context=None):
        '''
        Cancel the procurement request and all lines
        '''
        line_ids = []
        for req in self.browse(cr, uid, ids, context=context):
            for line in req.order_line:
                if line.id not in line_ids:
                    line_ids.append(line.id)

        self.write(cr, uid, ids, {'state': 'cancel'}, context=context)
        self.pool.get('sale.order.line').write(cr, uid, line_ids, {'state': 'cancel'}, context=context)

        for ir in self.read(cr, uid, ids, ['name'], context=context):
            self.infolog(cr, uid, "The IR id:%s (%s) has been canceled" % (
                ir['id'], ir['name'],
            ))

        return True

    def validate_procurement(self, cr, uid, ids, context=None):
        '''
        Validate the request (which is a the same object as a SO)
        It is the action called on the activity of the workflow.
        '''
        obj_data = self.pool.get('ir.model.data')
        line_obj = self.pool.get('sale.order.line')
        nomen_manda_0 = obj_data.get_object_reference(cr, uid, 'msf_doc_import', 'nomen_tbd0')[1]
        nomen_manda_1 = obj_data.get_object_reference(cr, uid, 'msf_doc_import', 'nomen_tbd1')[1]
        nomen_manda_2 = obj_data.get_object_reference(cr, uid, 'msf_doc_import', 'nomen_tbd2')[1]
        nomen_manda_3 = obj_data.get_object_reference(cr, uid, 'msf_doc_import', 'nomen_tbd3')[1]
        uom_tbd = obj_data.get_object_reference(cr, uid, 'msf_doc_import', 'uom_tbd')[1]
        nb_lines = 0
        line_ids = []
        reset_soq = []
        for req in self.browse(cr, uid, ids, context=context):
            if len(req.order_line) <= 0:
                raise osv.except_osv(_('Error'), _('You cannot validate an Internal request with no lines !'))
            for line in req.order_line:
                line_ids.append(line.id)

                if line.soq_updated:
                    reset_soq.append(line.id)

                if line.nomen_manda_0.id == nomen_manda_0 \
                        or line.nomen_manda_1.id == nomen_manda_1 \
                        or line.nomen_manda_2.id == nomen_manda_2 \
                        or line.nomen_manda_3.id == nomen_manda_3 \
                        or line.product_uom.id == uom_tbd:
                    nb_lines += 1
                if line.product_uom_qty <= 0.00:
                    raise osv.except_osv(_('Error'), _('A line must a have a quantity larger than 0.00'))

                if not line.stock_take_date:
                    line_obj.write(cr, uid, [line.id], {'stock_take_date': req.stock_take_date, }, context=context)

                # 5/ Check if there is a temporary product in the sale order :
                temp_prod_ids = self.pool.get('product.product').search(cr, uid, [('international_status', '=', 5)], context=context)
                line_with_temp_ids = line_obj.search(cr, uid, [('order_id', '=', req.id), ('product_id', 'in', temp_prod_ids)], context=context)
                line_err = ' / '.join([str(line.line_number) for l in line_obj.browse(cr, uid, line_with_temp_ids, context=context)])
                if line_with_temp_ids:
                    raise osv.except_osv(
                        _("Warning"),
                        _("You can not confirm internal request containing temporary product (line: %s)") % line_err,
                    )
            if nb_lines:
                raise osv.except_osv(_('Error'), _('Please check the lines : you cannot have "To Be confirmed" for Nomenclature Level". You have %s lines to correct !') % nb_lines)
            self.log(cr, uid, req.id, _("The internal request '%s' has been validated (nb lines: %s).") % (req.name, len(req.order_line)), context=context)
            self.infolog(cr, uid, "The internal request id:%s (%s) has been validated." % (
                req.id, req.name,
            ))
        line_obj.update_supplier_on_line(cr, uid, line_ids, context=context)
        line_obj.write(cr, uid, reset_soq, {'soq_updated': False,}, context=context)
        self.write(cr, uid, ids, {'state': 'validated'}, context=context)

        self.ssl_products_in_line(cr, uid, ids, context=context)

        return True

    def procurement_done(self, cr, uid, ids, context=None):
        '''
        Creates all procurement orders according to lines
        '''
        self.write(cr, uid, ids, {'state': 'done'})
        return True

    def pricelist_id_change(self, cr, uid, ids, pricelist_id):
        '''
        Display a warning message on pricelist change
        '''
        res = {}

        if pricelist_id and ids:
            order = self.browse(cr, uid, ids[0])
            if pricelist_id != order.pricelist_id.id and order.order_line:
                res.update({'warning': {'title': 'Currency change',
                                        'message': 'You have changed the currency of the order. \
                                         Please note that all order lines in the old currency will be changed to the new currency without conversion !'}})

        return res

    def stock_take_data(self, cr, uid, ids, context=None):
        '''
        data for confirmed for change line wizard
        '''
        if context is None:
            context = {}
        return {'name': _('Do you want to update the Date of Stock Take of all/selected Order lines ?'), }

    def update_date(self, cr, uid, ids, context=None):
        '''
        open the update lines wizard
        '''
        # we need the context
        if context is None:
            context = {}
        # field name
        field_name = context.get('field_name', False)
        assert field_name, 'The button is not correctly set.'
        # data
        data = getattr(self, field_name + '_data')(cr, uid, ids, context=context)
        name = data['name']
        model = 'update.lines'
        wiz_obj = self.pool.get('wizard')
        # open the selected wizard
        return wiz_obj.open_wizard(cr, uid, ids, name=name, model=model, context=context)

    def ir_import_by_order_to_create(self, cr, uid, ids, context=None):
        '''
        Launches the wizard to import lines from a file
        '''
        import_obj = self.pool.get('internal.request.import')

        if context is None:
            context = {}

        import_id = import_obj.create(cr, uid, {}, context)
        context.update({'active_id': [], 'ir_import_id': import_id})

        return {'type': 'ir.actions.act_window',
                'res_model': 'internal.request.import',
                'res_id': import_id,
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'same',
                'context': context,
                }

    def ir_import_by_order_to_update(self, cr, uid, ids, context=None):
        '''
        Launches the wizard to import lines from a file
        '''
        import_obj = self.pool.get('internal.request.import')

        if context is None:
            context = {}

        context.update({'active_id': ids[0], 'to_update_ir': True})
        ir = self.browse(cr, uid, ids[0], fields_to_fetch=['order_line', 'state'], context=context)
        if ir.state != 'draft':
            raise osv.except_osv(_('Warning'), _('Importing from IR Excel template is only allowed on an IR which is in Draft state'))
        import_ids = import_obj.search(cr, uid, [('order_id', '=', ids[0])], context=context)
        import_obj.unlink(cr, uid, import_ids, context=context)
        new_import_vals = {
            'order_id': ids[0],
            'imp_line_ids': [(0, 0, {
                'ir_line_id': l.id,
                'ir_line_number': l.line_number,
            }) for l in ir.order_line],
        }
        import_id = import_obj.create(cr, uid, new_import_vals, context)
        context.update({'ir_import_id': import_id})

        return {'type': 'ir.actions.act_window',
                'res_model': 'internal.request.import',
                'res_id': import_id,
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'same',
                'context': context,
                }

    def ir_export_get_file_name(self, cr, uid, ids, prefix='IR', context=None):
        """
        get export file name
        :return IR_14_OC_MW101_IR00060_YYYY_MM_DD.xls
        """
        if isinstance(ids, int):
            ids = [ids]
        if len(ids) != 1:
            return False
        ir_r = self.read(cr, uid, ids[0], ['name'], context=context)
        if not ir_r or not ir_r['name']:
            return False
        dt_now = datetime.datetime.now()
        ir_name = "%s_%s_%d_%02d_%02d" % (prefix, ir_r['name'].replace('/', '_'),
                                          dt_now.year, dt_now.month, dt_now.day)
        return ir_name

    def export_excel_ir(self, cr, uid, ids, context=None):
        '''
        Call the Excel report of IR
        '''
        if context is None:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        data = {'ids': ids}
        file_name = self.ir_export_get_file_name(cr, uid, ids, prefix='IR', context=context)
        if file_name:
            data['target_filename'] = file_name

        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'internal_request_export',
            'datas': data,
            'context': context,
        }

    def ir_product_list_import_call_wizard(self, cr, uid, ids, context=None):
        '''
        Launches the wizard to import lines from a file
        '''
        if not ids:
            return False
        if context is None:
            context = {}

        if self.read(cr, uid, ids[0], ['state'], context=context)['state'] != 'draft':
            raise osv.except_osv(_('Warning'),
                                 _('This import can not be used as IR must be in Draft with header information already filled'))
        import_id = self.pool.get('ir.product.list.import.wizard').create(cr, uid, {'sale_id': ids[0]}, context)
        context.update({'ir_plist_import_id': import_id})

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'ir.product.list.import.wizard',
            'res_id': import_id,
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'same',
            'context': context,
        }


procurement_request()


class procurement_request_line(osv.osv):
    _name = 'sale.order.line'
    _inherit = 'sale.order.line'

    def create(self, cr, uid, vals, context=None):
        '''
        Adds the date_planned value.
        Check if product or comment exist and set the the fields required accordingly.
        '''
        if context is None:
            context = {}
        if vals.get('product_id', False):
            vals.update({'comment_ok': True})
        if vals.get('comment', False):
            vals.update({'product_ok': True})

        if not 'date_planned' in vals and context.get('procurement_request'):
            if 'date_planned' in context:
                vals.update({'date_planned': context.get('date_planned')})
            else:
                date_planned = self.pool.get('sale.order').browse(cr, uid, vals.get('order_id'), context=context).delivery_requested_date
                vals.update({'date_planned': date_planned})

        if vals.get('price_unit') and not vals.get('original_price'):
            vals.update({'original_price': vals['price_unit'] or 0.00})

        # Compute the rounding of the product qty
        if vals.get('product_uom') and vals.get('product_uom_qty'):
            vals['product_uom_qty'] = self.pool.get('product.uom')._compute_round_up_qty(cr, uid, vals.get('product_uom'), vals.get('product_uom_qty'), context=context)

        return super(procurement_request_line, self).create(cr, uid, vals, context=context)

    def write(self, cr, uid, ids, vals, context=None):
        '''
        Compute the UoM qty according to UoM rounding value
        '''
        if not ids:
            return True
        res = True

        if 'product_uom_qty' in vals or 'product_uom' in vals:
            for req in self.read(cr, uid, ids, ['product_uom_qty', 'product_uom'], context=context):
                # Compute the rounding of the product qty
                uom_id = vals.get('product_uom', req['product_uom'][0])
                uom_qty = vals.get('product_uom_qty', req['product_uom_qty'])
                vals['product_uom_qty'] = self.pool.get('product.uom')._compute_round_up_qty(cr, uid, uom_id, uom_qty, context=context)
                res = res and super(procurement_request_line, self).write(cr, uid, [req['id']], vals, context=context)
        else:
            res = res and super(procurement_request_line, self).write(cr, uid, ids, vals, context=context)

        return res

    def _get_fake_state(self, cr, uid, ids, field_name, args, context=None):
        if isinstance(ids, int):
            ids = [ids]
        ret = {}
        for pol in self.read(cr, uid, ids, ['state']):
            ret[pol['id']] = pol['state']
        return ret

    def _get_product_id_ok(self, cr, uid, ids, field_name, args, context=None):
        if isinstance(ids, int):
            ids = [ids]
        res = {}
        for pol in self.read(cr, uid, ids, ['product_id']):
            if pol['product_id']:
                res[pol['id']] = True
            else:
                res[pol['id']] = False
        return res

    def button_view_changed(self, cr, uid, ids, context=None):
        """
        Launch wizard to display line information
        """
        if not context:
            context = {}
        if isinstance(ids, int):
            ids = [ids]

        wiz_obj = self.pool.get('procurement.request.line.wizard')
        cols = ['product_id', 'original_product', 'product_uom_qty', 'original_qty', 'price_unit',
                'original_price', 'product_uom', 'original_uom', 'modification_comment']
        sol = self.read(cr, uid, ids[0], cols, context=context)
        wiz_id = wiz_obj.create(cr, uid, sol, context=context)

        context.update({
            'active_id': ids[0],
            'active_ids': ids,
        })

        return {
            'name': _('Original Data Internal Request Line'),
            'type': 'ir.actions.act_window',
            'res_model': 'procurement.request.line.wizard',
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'res_id': [wiz_id],
            'context': context,
        }

    _columns = {
        'cost_price': fields.float(string='Cost price', digits_compute=dp.get_precision('Sale Price Computation')),
        'procurement_request': fields.boolean(string='Internal Request', readonly=True),
        'latest': fields.char(size=64, string='Latest documents', readonly=True),
        'my_company_id': fields.many2one('res.company', 'Company', select=1),
        'supplier': fields.many2one('res.partner', 'Supplier', domain="[('id', '!=', my_company_id)]"),
        # openerp bug: eval invisible in p.o use the po line state and not the po state !
        'fake_state': fields.function(_get_fake_state, type='char', method=True, string='State', help='for internal use only'),
        'stock_take_date': fields.date('Date of Stock Take', required=False),
        'product_id_ok': fields.function(_get_product_id_ok, type="boolean", method=True, string='Product defined?', help='for if true the button "configurator" is hidden'),
        'product_ok': fields.boolean('Product selected'),
        'comment_ok': fields.boolean('Comment written'),
    }

    def _get_planned_date(self, cr, uid, c=None):
        if c is None:
            c = {}
        if 'procurement_request' in c:
            return c.get('date_planned', False)

        return super(procurement_request_line, self)._get_planned_date(cr, uid, c)

    def _get_stock_take_date(self, cr, uid, context=None):
        '''
            Returns stock take date
        '''
        if context is None:
            context = {}
        if 'procurement_request' in context:
            return context.get('stock_take_date', False)

        return super(procurement_request_line, self)._get_stock_take_date(cr, uid, context)

    _defaults = {
        'procurement_request': lambda self, cr, uid, c: c.get('procurement_request', False),
        'date_planned': _get_planned_date,
        'my_company_id': lambda obj, cr, uid, context: obj.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.id,
        'product_ok': False,
        'comment_ok': True,
        'fake_state': 'draft',
    }

    def update_supplier_on_line(self, cr, uid, ids, context=None):
        return True


    def requested_product_id_change(self, cr, uid, ids, product_id, comment=False, categ=False, context=None):
        '''
        Fills automatically the product_uom_id field and the name on the line when the
        product is changed.
        Add a domain on the product_uom when a product is selected.
        Check consistency of product according to the selected order category
        '''
        if context is None:
            context = {}
        product_obj = self.pool.get('product.product')
        uom_obj = self.pool.get('product.uom')

        vals = {}
        vals.setdefault('value', {})
        vals.setdefault('domain', {})
        if not product_id:
            vals['value'] = {'product_uom': False, 'supplier': False, 'name': '', 'type':'make_to_order', 'comment_ok': False, 'cost_price': False, 'price_subtotal': False, 'product_uom_qty': 0.00, 'product_uos_qty': 0.00}
            vals['domain'] = {'product_uom':[], 'supplier': [('partner_type', 'in', ['internal', 'section', 'intermission'])]}
        elif product_id:
            product = product_obj.browse(cr, uid, product_id)
            # Test the compatibility of the product with a consumption report
            res, test = product_obj._on_change_restriction_error(cr, uid, product_id, field_name='product_id', values={'value': vals['value']}, vals={'constraints': 'consumption'}, context=context)
            if test:
                return res
            vals['value'] = {
                'product_uom': product.uom_id.id,
                'name': '[%s] %s' % (product.default_code, product.name),
                'type': product.procure_method,
                'comment_ok': True,
                'cost_price': product.standard_price,
                'price_unit': product.list_price,
            }
            if vals['value']['type'] != 'make_to_stock':
                vals['value'].update({'supplier': product.seller_ids and product.seller_ids[0].name.id})
            uom_val = uom_obj.read(cr, uid, [product.uom_id.id], ['category_id'])
            vals['domain'] = {'product_uom':[('category_id', '=', uom_val[0]['category_id'][0])]}

        # Check consistency of product according to the selected order category:
        if categ and product_id:
            consistency_message = product_obj.check_consistency(cr, uid, product_id, categ, context=context)
            if consistency_message:
                vals.setdefault('warning', {})
                vals['warning'].setdefault('title', _('Warning'))
                vals['warning'].setdefault('message', '')
                vals['warning']['message'] = '%s \n %s' % (vals.get('warning', {}).get('message', ''), consistency_message)

        return vals


    def requested_type_change(self, cr, uid, ids, product_id, type, context=None):
        """
        If there is a product, we check its type (procure_method) and update eventually the supplier.
        """
        if context is None:
            context = {}
        v = {}
        m = {}
        product_obj = self.pool.get('product.product')
        if product_id and type != 'make_to_stock':
            product = product_obj.browse(cr, uid, product_id, context=context)
            if product.seller_ids and (product.seller_ids[0].name.supplier or product.seller_ids[0].name.manufacturer or
                                       product.seller_ids[0].name.transporter):
                v.update({'supplier': product.seller_ids[0].name.id})
            else:
                v.update({'supplier': False})
        elif product_id and type == 'make_to_stock':
            v.update({'supplier': False})
            product = product_obj.browse(cr, uid, product_id, context=context)
            if product.type in ('consu', 'service', 'service_recep'):
                v.update({'type': 'make_to_order'})
                m.update({'title': _('Warning'),
                          'message': _('You can\'t source a line \'from stock\' if line contains a non-stockable or service product.')})
        return {'value': v, 'warning': m}

    def comment_change(self, cr, uid, ids, comment, product_id, nomen_manda_0, context=None):
        '''
        Fill the level of nomenclatures with tag "to be defined" if you have only comment
        '''
        if context is None:
            context = {}
        value = {'comment': comment}
        domain = {}

        if comment and not product_id:
            value.update({'name': 'To be defined',
                          'supplier': False,
                          'product_ok': True})
            domain = {'product_uom':[], 'supplier': [('partner_type', 'in', ['internal', 'section', 'intermission'])]}
        if not comment:
            value.update({'product_ok': True})
            domain = {'product_uom':[], 'supplier': []}
        return {'value': value, 'domain': domain}

    def validated_ir(self, cr, uid, ids, context=None):
        netsvc.LocalService("workflow").trg_validate(uid, 'sale.order.line', ids, 'validated', cr)
        return True

procurement_request_line()

class procurement_request_sourcing_document(osv.osv):
    """ Backward compatibility: do not change object's sdref """

    _name = 'procurement.request.sourcing.document'
    _table = 'procurement_request_sourcing_document2'
    _auto = False
    _columns = {
        'order_id': fields.many2one('sale.order', string='Internal request'),
    }

procurement_request_sourcing_document()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
