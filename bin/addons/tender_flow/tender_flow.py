# -*- coding: utf-8 -*-
##############################################################################
#
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

from datetime import datetime
from order_types import ORDER_PRIORITY, ORDER_CATEGORY
from osv import osv, fields
from tools.translate import _
from lxml import etree

import decimal_precision as dp
import netsvc
import time

from purchase import PURCHASE_ORDER_STATE_SELECTION

class tender(osv.osv):
    '''
    tender class
    '''
    _name = 'tender'
    _description = 'Tender'

    def copy(self, cr, uid, id, default=None, context=None, done_list=[], local=False):
        if not default:
            default = {}
        default['internal_state'] = 'draft'  # UF-733: Reset the internal_state
        if not 'sale_order_id' in default:
            default['sale_order_id'] = False
        return super(osv.osv, self).copy(cr, uid, id, default, context=context)

    def unlink(self, cr, uid, ids, context=None):
        '''
        cannot delete tender not draft
        '''
        # Objects
        t_line_obj = self.pool.get('tender.line')

        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        for obj in self.browse(cr, uid, ids, context=context):
            if obj.state != 'draft':
                raise osv.except_osv(_('Warning !'), _("Cannot delete Tenders not in 'draft' state."))

            if obj.sale_order_id:
                obj_name = obj.sale_order_id.procurement_request and _('an Internal Request') or _('a Field Order')
                raise osv.except_osv(_('Warning !'), _("This tender is linked to %s, so you cannot delete it. Please cancel it instead.") % obj_name)

            for line in obj.tender_line_ids:
                t_line_obj.fake_unlink(cr, uid, [line.id], context=context)

        return super(tender, self).unlink(cr, uid, ids, context=context)

    def _vals_get(self, cr, uid, ids, fields, arg, context=None):
        '''
        return function values
        '''
        result = {}
        for obj in self.browse(cr, uid, ids, context=context):
            result[obj.id] = {'rfq_name_list': '',
                              }
            rfq_names = []
            for rfq in obj.rfq_ids:
                rfq_names.append(rfq.name)
            # generate string
            rfq_names.sort()
            result[obj.id]['rfq_name_list'] = ','.join(rfq_names)

        return result

    def _is_tender_from_fo(self, cr, uid, ids, field_name, args, context=None):
        res = {}
        for tender in self.browse(cr, uid, ids, context=context):
            retour = False
            ids_proc = self.pool.get('procurement.order').search(cr, uid, [('tender_id', '=', tender.id)])
            ids_sol = self.pool.get('sale.order.line').search(cr, uid, [('procurement_id', 'in', ids_proc), ('order_id.procurement_request', '=', False)])
            if ids_sol:
                retour = True
            res[tender.id] = retour
        return res

    _columns = {'name': fields.char('Tender Reference', size=64, required=True, select=True, readonly=True),
                'sale_order_id': fields.many2one('sale.order', string="Sale Order", readonly=True),
                'state': fields.selection([('draft', 'Draft'), ('comparison', 'Comparison'), ('done', 'Closed'), ('cancel', 'Cancelled'), ], string="State", readonly=True),
                'supplier_ids': fields.many2many('res.partner', 'tender_supplier_rel', 'tender_id', 'supplier_id', string="Suppliers", domain="[('id', '!=', company_id)]",
                                                 states={'draft': [('readonly', False)]}, readonly=True,
                                                 context={'search_default_supplier': 1, }),
                'location_id': fields.many2one('stock.location', 'Location', required=True, states={'draft': [('readonly', False)]}, readonly=True, domain=[('usage', '=', 'internal')]),
                'company_id': fields.many2one('res.company', 'Company', required=True, states={'draft': [('readonly', False)]}, readonly=True),
                'rfq_ids': fields.one2many('purchase.order', 'tender_id', string="RfQs", readonly=True),
                'priority': fields.selection(ORDER_PRIORITY, string='Tender Priority', states={'draft': [('readonly', False)], }, readonly=True,),
                'categ': fields.selection(ORDER_CATEGORY, string='Tender Category', required=True, states={'draft': [('readonly', False)], }, readonly=True),
                'creator': fields.many2one('res.users', string="Creator", readonly=True, required=True,),
                'warehouse_id': fields.many2one('stock.warehouse', string="Warehouse", required=True, states={'draft': [('readonly', False)], }, readonly=True),
                'creation_date': fields.date(string="Creation Date", readonly=True, states={'draft': [('readonly', False)]}),
                'details': fields.char(size=30, string="Details", states={'draft': [('readonly', False)], }, readonly=True),
                'requested_date': fields.date(string="Requested Date", required=True, states={'draft': [('readonly', False)], }, readonly=True),
                'notes': fields.text('Notes'),
                'internal_state': fields.selection([('draft', 'Draft'), ('updated', 'Rfq Updated'), ], string="Internal State", readonly=True),
                'rfq_name_list': fields.function(_vals_get, method=True, string='RfQs Ref', type='char', readonly=True, store=False, multi='get_vals',),
                'product_id': fields.related('tender_line_ids', 'product_id', type='many2one', relation='product.product', string='Product'),
                'delivery_address': fields.many2one('res.partner.address', string='Delivery address', required=True),
                'tender_from_fo': fields.function(_is_tender_from_fo, method=True, type='boolean', string='Is tender from FO ?',),
                }

    _defaults = {'categ': 'other',
                 'state': 'draft',
                 'internal_state': 'draft',
                 'company_id': lambda obj, cr, uid, context: obj.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.id,
                 'creator': lambda obj, cr, uid, context: uid,
                 'creation_date': lambda *a: time.strftime('%Y-%m-%d'),
                 'requested_date': lambda *a: time.strftime('%Y-%m-%d'),
                 'priority': 'normal',
                 'warehouse_id': lambda obj, cr, uid, context: len(obj.pool.get('stock.warehouse').search(cr, uid, [])) and obj.pool.get('stock.warehouse').search(cr, uid, [])[0],
                 }

    _order = 'name desc'

    def _check_restriction_line(self, cr, uid, ids, context=None):
        '''
        Check if there is no restrictive products in lines
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]

        line_obj = self.pool.get('tender.line')

        res = True
        for tender in self.browse(cr, uid, ids, context=context):
            res = res and line_obj._check_restriction_line(cr, uid, [x.id for x in tender.tender_line_ids if x.line_state != 'cancel'], context=context)

        return res

    def default_get(self, cr, uid, fields, context=None):
        '''
        Set default data
        '''
        # Object declaration
        partner_obj = self.pool.get('res.partner')
        user_obj = self.pool.get('res.users')

        res = super(tender, self).default_get(cr, uid, fields, context=context)

        # Get the delivery address
        company = user_obj.browse(cr, uid, uid, context=context).company_id
        res['delivery_address'] = partner_obj.address_get(cr, uid, company.partner_id.id, ['delivery'])['delivery']

        return res

    def _check_tender_from_fo(self, cr, uid, ids, context=None):
        if not context:
            context = {}
        retour = True
        for tender in self.browse(cr, uid, ids, context=context):
            if not tender.tender_from_fo:
                return retour
            for sup in tender.supplier_ids:
                if sup.partner_type == 'internal':
                    retour = False
        return retour

    _constraints = [
        (_check_tender_from_fo, 'You cannot choose an internal supplier for this tender', []),
    ]

    def create(self, cr, uid, vals, context=None):
        '''
        Set the reference of the tender at this time
        '''
        if not vals.get('name', False):
            vals.update({'name': self.pool.get('ir.sequence').get(cr, uid, 'tender')})

        return super(tender, self).create(cr, uid, vals, context=context)

    def write(self, cr, uid, ids, vals, context=None):
        """
        Check consistency between lines and categ of tender
        """
        if not ids:
            return True
        # UFTP-317: Make sure ids is a list
        if isinstance(ids, (int, long)):
            ids = [ids]
        exp_sol_obj = self.pool.get('expected.sale.order.line')

        if ('state' in vals and vals.get('state') not in ('draft', 'comparison')) or \
           ('sale_order_line_id' in vals and vals.get('sale_order_line_id')):
            exp_sol_ids = exp_sol_obj.search(cr, uid, [
                ('tender_id', 'in', ids),
            ], context=context)
            exp_sol_obj.unlink(cr, uid, exp_sol_ids, context=context)

        return super(tender, self).write(cr, uid, ids, vals, context=context)

    def onchange_categ(self, cr, uid, ids, category, context=None):
        """
        Check if the list of products is valid for this new category
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls the method
        :param ids: List of ID of purchase.order to check
        :param category: DB value of the new choosen category
        :param context: Context of the call
        :return: A dictionary containing the warning message if any
        """
        nomen_obj = self.pool.get('product.nomenclature')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        message = {}
        res = False

        if ids and category in ['log', 'medical']:
            # Check if all product nomenclature of products in Tender lines are consistent with the category
            try:
                med_nomen = nomen_obj.search(cr, uid, [('level', '=', 0), ('name', '=', 'MED')], context=context)[0]
            except IndexError:
                raise osv.except_osv(_('Error'), _('MED nomenclature Main Type not found'))
            try:
                log_nomen = nomen_obj.search(cr, uid, [('level', '=', 0), ('name', '=', 'LOG')], context=context)[0]
            except IndexError:
                raise osv.except_osv(_('Error'), _('LOG nomenclature Main Type not found'))

            nomen_id = category == 'log' and log_nomen or med_nomen
            cr.execute('''SELECT l.id
                          FROM tender_line l
                            LEFT JOIN product_product p ON l.product_id = p.id
                            LEFT JOIN product_template pt ON p.product_tmpl_id = pt.id
                            LEFT JOIN tender t ON l.tender_id = t.id
                          WHERE (pt.nomen_manda_0 != %s) AND t.id in %s LIMIT 1''',
                       (nomen_id, tuple(ids)))
            res = cr.fetchall()

        if ids and category in ['service', 'transport']:
            # Avoid selection of non-service producs on Service Tender
            category = category == 'service' and 'service_recep' or 'transport'
            transport_cat = ''
            if category == 'transport':
                transport_cat = 'OR p.transport_ok = False'
            cr.execute('''SELECT l.id
                          FROM tender_line l
                            LEFT JOIN product_product p ON l.product_id = p.id
                            LEFT JOIN product_template pt ON p.product_tmpl_id = pt.id
                            LEFT JOIN tender t ON l.tender_id = t.id
                          WHERE (pt.type != 'service_recep' %s) AND t.id in %%s LIMIT 1''' % transport_cat, (tuple(ids),))  # not_a_user_entry
            res = cr.fetchall()

        if res:
            message.update({
                'title': _('Warning'),
                'message': _('This order category is not consistent with product(s) on this tender.'),
            })

        return {'warning': message}

    def onchange_warehouse(self, cr, uid, ids, warehouse_id, context=None):
        '''
        on_change function for the warehouse
        '''
        result = {'value': {}, }
        if warehouse_id:
            input_loc_id = self.pool.get('stock.warehouse').browse(cr, uid, warehouse_id, context=context).lot_input_id.id
            result['value'].update(location_id=input_loc_id)

        return result

    def wkf_generate_rfq(self, cr, uid, ids, context=None):
        '''
        generate the rfqs for each specified supplier
        '''
        if context is None:
            context = {}
        po_obj = self.pool.get('purchase.order')
        pol_obj = self.pool.get('purchase.order.line')
        partner_obj = self.pool.get('res.partner')
        obj_data = self.pool.get('ir.model.data')

        # no suppliers -> raise error
        for tender in self.browse(cr, uid, ids, context=context):
            # check some supplier have been selected
            if not tender.supplier_ids:
                raise osv.except_osv(_('Warning !'), _('You must select at least one supplier!'))
            # utp-315: check that the suppliers are not inactive (I use a SQL request because the inactive partner are ignored with the browse)
            sql = """
            select tsr.supplier_id, rp.name, rp.active
            from tender_supplier_rel tsr
            left join res_partner rp
            on tsr.supplier_id = rp.id
            where tsr.tender_id=%s
            and rp.active=False
            """
            cr.execute(sql, (ids[0],))
            inactive_supplier_ids = cr.dictfetchall()
            if any(inactive_supplier_ids):
                raise osv.except_osv(_('Warning !'), _("You can't have inactive supplier! Please remove: %s"
                                                       ) % ' ,'.join([partner['name'] for partner in inactive_supplier_ids]))
            # check some products have been selected
            tender_line_ids = self.pool.get('tender.line').search(cr, uid, [('tender_id', '=', tender.id), ('line_state', '!=', 'cancel')], context=context)
            if not tender_line_ids:
                raise osv.except_osv(_('Warning !'), _('You must select at least one product!'))
            for supplier in tender.supplier_ids:
                # create a purchase order for each supplier
                address_id = partner_obj.address_get(cr, uid, [supplier.id], ['default'])['default']
                if not address_id:
                    raise osv.except_osv(_('Warning !'), _('The supplier "%s" has no address defined!') % (supplier.name,))
                pricelist_id = supplier.property_product_pricelist_purchase.id
                values = {'origin': tender.sale_order_id and tender.sale_order_id.name + ';' + tender.name or tender.name,
                          'rfq_ok': True,
                          'partner_id': supplier.id,
                          'partner_address_id': address_id,
                          'location_id': tender.location_id.id,
                          'pricelist_id': pricelist_id,
                          'company_id': tender.company_id.id,
                          'fiscal_position': supplier.property_account_position and supplier.property_account_position.id or False,
                          'tender_id': tender.id,
                          'warehouse_id': tender.warehouse_id.id,
                          'categ': tender.categ,
                          'priority': tender.priority,
                          'details': tender.details,
                          'delivery_requested_date': tender.requested_date,
                          'rfq_delivery_address': tender.delivery_address and tender.delivery_address.id or False,
                          }
                # create the rfq - dic is udpated for default partner_address_id at purchase.order level
                po_id = po_obj.create(cr, uid, values, context=dict(context, partner_id=supplier.id, rfq_ok=True))

                for line in tender.tender_line_ids:
                    if line.line_state == 'cancel':
                        continue

                    if line.qty <= 0.00:
                        raise osv.except_osv(_('Error !'), _('You cannot generate RfQs for an line with a null quantity.'))

                    if line.product_id.id == obj_data.get_object_reference(cr, uid, 'msf_doc_import', 'product_tbd')[1]:
                        raise osv.except_osv(_('Warning !'), _('You can\'t have "To Be Defined" for the product. Please select an existing product.'))
                    newdate = datetime.strptime(line.date_planned, '%Y-%m-%d')
                    values = {'name': line.product_id.partner_ref,
                              'product_qty': line.qty,
                              'product_id': line.product_id.id,
                              'product_uom': line.product_uom.id,
                              'price_unit': 0.0,  # was price variable - uf-607
                              'date_planned': newdate.strftime('%Y-%m-%d'),
                              'notes': line.product_id.description_purchase,
                              'order_id': po_id,
                              'tender_line_id': line.id,
                              'comment': line.comment,
                              }
                    # create purchase order line
                    pol_obj.create(cr, uid, values, context=context)
                    message = "Request for Quotation '%s' has been created." % po_obj.browse(cr, uid, po_id, context=context).name
                    # create the log message
                    self.pool.get('res.log').create(cr, uid,
                                                    {'name': message,
                                                     'res_model': po_obj._name,
                                                     'secondary': False,
                                                     'res_id': po_id,
                                                     'domain': [('rfq_ok', '=', True)],
                                                     }, context={'rfq_ok': True})
                self.infolog(cr, uid, "The RfQ id:%s (%s) has been generated from tender id:%s (%s)" % (
                    po_id,
                    po_obj.read(cr, uid, po_id, ['name'], context=context)['name'],
                    tender.id,
                    tender.name,
                ))

        self.write(cr, uid, ids, {'state': 'comparison'}, context=context)
        return True


    def continue_sourcing(self, cr, uid, ids, context=None):
        '''
        call when pressing "coutinue sourcing progress" button on tender
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        self.create_po(cr, uid, ids, context=context)

        wf_service = netsvc.LocalService("workflow")
        for tender_id in ids:
            wf_service.trg_validate(uid, 'tender', tender_id, 'button_done', cr)

        return True

    def wkf_action_done(self, cr, uid, ids, context=None):
        '''
        check all rfq are updated (or cancel)
        create or update PO to selected suppliers
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        for tender in self.browse(cr, uid, ids, context=context):
            # close linked RfQ:
            rfq_list = []
            for rfq in tender.rfq_ids:
                if rfq.rfq_state not in ('updated', 'cancel'):
                    rfq_list.append(rfq.id)
                else:
                    self.pool.get('purchase.order').write(cr, uid, [rfq.id], {'rfq_state': 'done'}, context=context)

            self.write(cr, uid, [tender.id], {'state': 'done'}, context=context)
            self.infolog(cr, uid, "The tender id:%s (%s) has been closed" % (
                tender.id,
                tender.name,
            ))

        return True

    def tender_integrity(self, cr, uid, tender, context=None):
        '''
        check the state of corresponding RfQs
        '''
        po_obj = self.pool.get('purchase.order')
        # no rfq in done state
        rfq_ids = po_obj.search(cr, uid, [('tender_id', '=', tender.id), ('rfq_state', '=', 'done')], context=context)
        if rfq_ids:
            raise osv.except_osv(_('Error !'), _("Some RfQ are already Closed. Integrity failure."))
        # all rfqs must have been treated
        rfq_ids = po_obj.search(cr, uid, [('tender_id', '=', tender.id),
                                          ('rfq_state', 'in', ('draft', 'sent',)), ], context=context)
        if rfq_ids:
            raise osv.except_osv(_('Warning !'), _("Generated RfQs must be Updated or Cancelled."))
        # at least one rfq must be updated and not canceled
        rfq_ids = po_obj.search(cr, uid, [('tender_id', '=', tender.id),
                                          ('rfq_state', 'in', ('updated',)), ], context=context)
        if not rfq_ids:
            raise osv.except_osv(_('Warning !'), _("At least one RfQ must be in state Updated."))

        return rfq_ids

    def compare_rfqs(self, cr, uid, ids, context=None):
        '''
        compare rfqs button
        '''
        if len(ids) > 1:
            raise osv.except_osv(_('Warning !'), _('Cannot compare rfqs of more than one tender at a time!'))
        wiz_obj = self.pool.get('wizard.compare.rfq')
        for tender in self.browse(cr, uid, ids, context=context):
            # check if corresponding rfqs are in the good state
            rfq_ids = self.tender_integrity(cr, uid, tender, context=context)
            # gather the product_id -> supplier_id relationship to display it back in the compare wizard
            suppliers = {}
            for line in tender.tender_line_ids:
                if line.product_id and line.supplier_id and line.line_state != 'cancel':
                    suppliers.update({line.product_id.id: line.supplier_id.id, })
            # rfq corresponding to this tender with done state (has been updated and not canceled)
            # the list of rfq which will be compared
            c = dict(context, active_ids=rfq_ids, tender_id=tender.id, end_wizard=False, suppliers=suppliers,)
            # open the wizard
            action = wiz_obj.start_compare_rfq(cr, uid, ids, context=c)
        return action

    def update_supplier_info(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        update the supplier info of corresponding products
        '''
        info_obj = self.pool.get('product.supplierinfo')
        pricelist_info_obj = self.pool.get('pricelist.partnerinfo')
        # integrity check flag
        integrity_test = kwargs.get('integrity_test', False)
        for tender in self.browse(cr, uid, ids, context=context):
            # flag if at least one update
            updated = tender.tender_line_ids and False or True
            # check if corresponding rfqs are in the good state
            if integrity_test:
                self.tender_integrity(cr, uid, tender, context=context)
            for line in tender.tender_line_ids:
                if line.line_state == 'cancel':
                    continue
                # if a supplier has been selected
                if line.purchase_order_line_id:
                    # set the flag
                    updated = True
                    # get the product
                    product = line.product_id
                    # find the corresponding suppinfo with sequence -99
                    info_99_list = info_obj.search(cr, uid, [('product_id', '=', product.product_tmpl_id.id),
                                                             ('name', '=', line.purchase_order_line_id.order_id.partner_id.id),
                                                             ('sequence', '=', -99), ], context=context)

                    if info_99_list:
                        # we drop it
                        info_obj.unlink(cr, uid, info_99_list, context=context)

                    # create the new one
                    values = {'name': line.supplier_id.id,
                              'product_name': False,
                              'product_code': False,
                              'sequence': -99,
                              #'product_uom': line.product_uom.id,
                              #'min_qty': 0.0,
                              #'qty': function
                              'product_id': product.product_tmpl_id.id,
                              'delay': int(line.supplier_id.default_delay),
                              #'pricelist_ids': created just after
                              #'company_id': default value
                              }

                    new_info_id = info_obj.create(cr, uid, values, context=context)
                    # price lists creation - 'pricelist.partnerinfo
                    values = {'suppinfo_id': new_info_id,
                              'min_quantity': 1.00,
                              'price': line.price_unit,
                              'uom_id': line.product_uom.id,
                              'currency_id': line.purchase_order_line_id.currency_id.id,
                              'valid_till': line.purchase_order_id.valid_till,
                              'purchase_order_line_id': line.purchase_order_line_id.id,
                              'comment': 'RfQ original quantity for price : %s' % line.qty,
                              }
                    pricelist_info_obj.create(cr, uid, values, context=context)

            # warn the user if no update has been performed
            if not updated:
                raise osv.except_osv(_('Warning !'), _('No information available for update!'))

        return True


    def create_po(self, cr, uid, ids, context=None):
        '''
        create a po from the updated RfQs
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
        if context is None:
            context = {}

        po_to_use = False

        for tender in self.browse(cr, uid, ids, context=context):
            # check if corresponding rfqs are in the good state
            self.tender_integrity(cr, uid, tender, context=context)
            # integrity check, all lines must have purchase_order_line_id
            if not all([line.purchase_order_line_id.id for line in tender.tender_line_ids if line.line_state != 'cancel']):
                raise osv.except_osv(_('Error !'), _('All tender lines must have been compared!'))

            for tender_line in tender.tender_line_ids:
                if line.line_state == 'cancel':
                    continue

                # search or create PO to use:
                po_to_use = self.pool.get('tender.line').get_existing_po(cr, uid, [tender_line.id], context=context)
                if not po_to_use:
                    po_to_use = self.pool.get('tender.line').create_po_from_tender_line(cr, uid, [tender_line.id], context=context)
                    # log new PO:
                    po = self.pool.get('purchase.order').browse(cr, uid, po_to_use, context=context)
                    self.pool.get('purchase.order').log(cr, uid, po_to_use, 'The Purchase Order %s for supplier %s has been created.' % (po.name, po.partner_id.name))
                    self.pool.get('purchase.order').infolog(cr, uid, 'The Purchase order %s for supplier %s has been created.' % (po.name, po.partner_id.name))

                #anal_dist_to_copy = tender_line.sale_order_line_id and tender_line.sale_order_line_id.analytic_distribution_id.id or False

                # attach new PO line:
                pol_values = {
                    'order_id': po_to_use,
                    'linked_sol_id': tender_line.sale_order_line_id.id or False,
                    #'origin': tender_line.sale_order_line_id and tender_line.sale_order_line_id.order_id.name or False,
                    'name': tender_line.product_id.partner_ref,
                    'product_qty': tender_line.qty,
                    'product_id': tender_line.product_id.id,
                    'product_uom': tender_line.product_uom.id,
                    'change_price_manually': 'True',
                    'price_unit': tender_line.price_unit,
                    'date_planned': tender_line.date_planned,
                    'move_dest_id': False,
                    'notes': tender_line.product_id.description_purchase,
                    'comment': tender_line.comment,
                }
                #if anal_dist_to_copy:
                #    pol_values['analytic_distribution_id'] = self.pool.get('analytic.distribution').copy(cr, uid, anal_dist_to_copy, {}, context=context)
                self.pool.get('purchase.order.line').create(cr, uid, pol_values, context=context)

            # when the po is generated, the tender is done - no more modification or comparison
            self.wkf_action_done(cr, uid, [tender.id], context=context)

        return po_to_use

    def cancel_tender(self, cr, uid, ids, context=None):
        '''
        Ask the user if he wants to re-source all lines
        '''
        wiz_obj = self.pool.get('tender.cancel.wizard')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        for tender_id in ids:
            tender = self.read(cr, uid, ids[0], ['state', 'sale_order_id'], context=context)

            wiz_id = wiz_obj.create(cr, uid, {
                'tender_id': tender['id'],
                'not_draft': tender['state'] != 'draft',
                'no_need': not tender['sale_order_id'],
            }, context=context)

            if tender['sale_order_id'] or tender['state'] != 'draft':
                return {'type': 'ir.actions.act_window',
                        'res_model': 'tender.cancel.wizard',
                        'res_id': wiz_id,
                        'view_mode': 'form',
                        'view_type': 'form',
                        'target': 'new',
                        'context': context}
            else:
                wiz_obj.just_cancel(cr, uid, [wiz_id], context=context)

        return {}

    def wkf_action_cancel(self, cr, uid, ids, context=None):
        '''
        cancel all corresponding rfqs
        '''
        if context is None:
            context = {}

        t_line_obj = self.pool.get('tender.line')

        # set state
        self.write(cr, uid, ids, {'state': 'cancel'}, context=context)
        for tender in self.browse(cr, uid, ids, context=context):
            # trigger all related rfqs
            self.pool.get('purchase.order').cancel_rfq(cr, uid, ids, context=context)

            for line in tender.tender_line_ids:
                t_line_obj.cancel_sourcing(cr, uid, [line.id], context=context)
            self.infolog(cr, uid, "The tender id:%s (%s) has been canceled" % (
                tender.id,
                tender.name,
            ))

        return True

    def set_manually_done(self, cr, uid, ids, all_doc=True, context=None):
        '''
        Set the tender and all related documents to done state
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]

        wf_service = netsvc.LocalService("workflow")

        for tender in self.browse(cr, uid, ids, context=context):
            line_updated = False
            if tender.state not in ('done', 'cancel'):
                for line in tender.tender_line_ids:
                    if line.purchase_order_line_id:
                        line_updated = True
                # Cancel or done all RfQ related to the tender
                for rfq in tender.rfq_ids:
                    if rfq.state not in ('done', 'cancel'):
                        if rfq.state == 'draft' or not line_updated:
                            wf_service.trg_validate(uid, 'purchase.order', rfq.id, 'purchase_cancel', cr)
                        else:
                            wf_service.trg_validate(uid, 'purchase.order', rfq.id, 'rfq_sent', cr)
                            if not rfq.valid_till:
                                self.pool.get('purchase.order').write(cr, uid, [rfq.id], {'valid_till': time.strftime('%Y-%m-%d')}, context=context)
                            wf_service.trg_validate(uid, 'purchase.order', rfq.id, 'rfq_updated', cr)

                if all_doc:
                    if tender.state == 'draft' or not tender.tender_line_ids or not line_updated:
                        # Call the cancel method of the tender
                        wf_service.trg_validate(uid, 'tender', tender.id, 'tender_cancel', cr)
                    else:
                        # Call the cancel method of the tender
                        wf_service.trg_validate(uid, 'tender', tender.id, 'button_done', cr)

        return True

    def check_empty_tender(self, cr, uid, ids, context=None):
        """
        If the tender is empty, return a wizard to ask user if he wants to
        cancel the whole tender
        """
        tender_wiz_obj = self.pool.get('tender.cancel.wizard')
        data_obj = self.pool.get('ir.model.data')

        for tender in self.browse(cr, uid, ids, context=context):
            if all(x.line_state in ('cancel', 'done') for x in tender.tender_line_ids):
                wiz_id = tender_wiz_obj.create(cr, uid, {'tender_id': tender.id}, context=context)
                view_id = data_obj.get_object_reference(cr, uid, 'tender_flow', 'ask_tender_cancel_wizard_form_view')[1]
                return {'type': 'ir.actions.act_window',
                        'res_model': 'tender.cancel.wizard',
                        'view_type': 'form',
                        'view_mode': 'form',
                        'view_id': [view_id],
                        'res_id': wiz_id,
                        'target': 'new',
                        'context': context}

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'tender',
            'view_type': 'form',
            'view_mode': 'form, tree',
            'res_id': ids[0],
            'context': context,
            'target': 'crush',
        }

    def sourcing_document_state(self, cr, uid, ids, context=None):
        """
        Returns all documents that are in the sourcing for a givent tender
        """
        if not context:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        sol_obj = self.pool.get('sale.order.line')
        so_obj = self.pool.get('sale.order')
        po_obj = self.pool.get('purchase.order')

        # corresponding sale order
        so_ids = []
        for tender in self.browse(cr, uid, ids, context=context):
            if tender.sale_order_id and tender.sale_order_id.id not in so_ids:
                so_ids.append(tender.sale_order_id.id)

        # from so, list corresponding po
        all_po_ids = so_obj.get_po_ids_from_so_ids(cr, uid, so_ids, context=context)

        # from listed po, list corresponding so
        all_so_ids = po_obj.get_so_ids_from_po_ids(cr, uid, all_po_ids, context=context)

        all_sol_not_confirmed_ids = []
        # if we have sol_ids, we are treating a po which is make_to_order from sale order
        if all_so_ids:
            all_sol_not_confirmed_ids = sol_obj.search(cr, uid, [
                ('order_id', 'in', all_so_ids),
                ('type', '=', 'make_to_order'),
                ('product_id', '!=', False),
                ('procurement_id.state', '!=', 'cancel'),
                ('state', 'not in', ['confirmed', 'done']),
            ], context=context)

        return so_ids, all_po_ids, all_so_ids, all_sol_not_confirmed_ids

tender()


class tender_line(osv.osv):
    '''
    tender lines
    '''
    _name = 'tender.line'
    _rec_name = 'product_id'
    _description = 'Tender Line'

    _SELECTION_TENDER_STATE = [('draft', 'Draft'), ('comparison', 'Comparison'), ('done', 'Closed'), ]

    def on_product_change(self, cr, uid, id, product_id, uom_id, product_qty, categ, context=None):
        '''
        product is changed, we update the UoM
        '''
        if not context:
            context = {}

        prod_obj = self.pool.get('product.product')
        result = {'value': {}}
        if product_id:
            # Test the compatibility of the product with a tender
            result, test = prod_obj._on_change_restriction_error(cr, uid, product_id, field_name='product_id', values=result, vals={'constraints': ['external', 'esc', 'internal']}, context=context)
            if test:
                return result

            product = prod_obj.browse(cr, uid, product_id, context=context)
            result['value']['product_uom'] = product.uom_id.id
            result['value']['text_error'] = False
            result['value']['to_correct_ok'] = False

        res_qty = self.onchange_uom_qty(cr, uid, id, uom_id or result.get('value', {}).get('product_uom', False), product_qty)
        result['value']['qty'] = res_qty.get('value', {}).get('qty', product_qty)

        if uom_id:
            result['value']['product_uom'] = uom_id

        if categ and product_id:
            # Check consistency of product
            consistency_message = prod_obj.check_consistency(cr, uid, product_id, categ, context=context)
            if consistency_message:
                result.setdefault('warning', {})
                result['warning'].setdefault('title', 'Warning')
                result['warning'].setdefault('message', '')

                result['warning']['message'] = '%s \n %s' % \
                    (result.get('warning', {}).get('message', ''), consistency_message)

        return result

    def onchange_uom_qty(self, cr, uid, ids, uom_id, qty):
        '''
        Check round of qty according to the UoM
        '''
        res = {}

        if qty:
            res = self.pool.get('product.uom')._change_round_up_qty(cr, uid, uom_id, qty, 'qty', result=res)

        return res

    def _get_total_price(self, cr, uid, ids, field_name, arg, context=None):
        '''
        return the total price
        '''
        result = {}
        for line in self.browse(cr, uid, ids, context=context):
            result[line.id] = {}
            if line.price_unit and line.qty:
                result[line.id]['total_price'] = line.price_unit * line.qty
            else:
                result[line.id]['total_price'] = 0.0

            result[line.id]['func_currency_id'] = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.currency_id.id
            if line.purchase_order_line_id:
                result[line.id]['currency_id'] = line.purchase_order_line_id.order_id.pricelist_id.currency_id.id
            else:
                result[line.id]['currency_id'] = result[line.id]['func_currency_id']

            result[line.id]['func_total_price'] = self.pool.get('res.currency').compute(cr, uid, result[line.id]['currency_id'],
                                                                                        result[line.id]['func_currency_id'],
                                                                                        result[line.id]['total_price'],
                                                                                        round=True, context=context)

        return result

    def name_get(self, cr, user, ids, context=None):
        result = self.browse(cr, user, ids, context=context)
        res = []
        for rs in result:
            code = rs.product_id and rs.product_id.name or ''
            res += [(rs.id, code)]
        return res

    _columns = {'product_id': fields.many2one('product.product', string="Product", required=True),
                'qty': fields.float(string="Qty", required=True),
                'tender_id': fields.many2one('tender', string="Tender", required=True, ondelete='cascade'),
                'purchase_order_line_id': fields.many2one('purchase.order.line', string="Related RfQ line", readonly=True),
                'sale_order_line_id': fields.many2one('sale.order.line', string="Sale Order Line"),
                'product_uom': fields.many2one('product.uom', 'Product UOM', required=True),
                'date_planned': fields.related('tender_id', 'requested_date', type='date', string='Requested Date', store=False,),
                # functions
                'supplier_id': fields.related('purchase_order_line_id', 'order_id', 'partner_id', type='many2one', relation='res.partner', string="Supplier", readonly=True),
                'price_unit': fields.related('purchase_order_line_id', 'price_unit', type="float", string="Price unit", digits_compute=dp.get_precision('Purchase Price Computation'), readonly=True),  # same precision as related field!
                'delivery_confirmed_date': fields.related('purchase_order_line_id', 'confirmed_delivery_date', type="date", string="Delivery Confirmed Date", readonly=True),
                'total_price': fields.function(_get_total_price, method=True, type='float', string="Total Price", digits_compute=dp.get_precision('Purchase Price'), multi='total'),
                'currency_id': fields.function(_get_total_price, method=True, type='many2one', relation='res.currency', string='Cur.', multi='total'),
                'func_total_price': fields.function(_get_total_price, method=True, type='float', string="Func. Total Price", digits_compute=dp.get_precision('Purchase Price'), multi='total'),
                'func_currency_id': fields.function(_get_total_price, method=True, type='many2one', relation='res.currency', string='Func. Cur.', multi='total'),
                'purchase_order_id': fields.related('purchase_order_line_id', 'order_id', type='many2one', relation='purchase.order', string="Related RfQ", readonly=True,),
                'purchase_order_line_number': fields.related('purchase_order_line_id', 'line_number', type="char", string="Related Line Number", readonly=True,),
                'state': fields.related('tender_id', 'state', type="selection", selection=_SELECTION_TENDER_STATE, string="State",),
                'line_state': fields.selection([('draft', 'Draft'), ('cancel', 'Canceled'), ('done', 'Done')], string='State', readonly=True),
                'comment': fields.char(size=128, string='Comment'),
                'has_to_be_resourced': fields.boolean(string='Has to be resourced'),
                'created_by_rfq': fields.boolean(string='Created by RfQ'),
                }
    _defaults = {'qty': lambda *a: 1.0,
                 'state': lambda *a: 'draft',
                 'line_state': lambda *a: 'draft',
                 }

    def _check_restriction_line(self, cr, uid, ids, context=None):
        '''
        Check if there is no restrictive products in lines
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]

        for line in self.browse(cr, uid, ids, context=context):
            if line.tender_id and line.product_id:
                if not self.pool.get('product.product')._get_restriction_error(cr, uid, line.product_id.id, vals={'constraints': ['external']}, context=context):
                    return False

        return True

    _sql_constraints = [
        #        ('product_qty_check', 'CHECK( qty > 0 )', 'Product Quantity must be greater than zero.'),
    ]

    def create(self, cr, uid, vals, context=None):
        exp_sol_obj = self.pool.get('expected.sale.order.line')
        tender_obj = self.pool.get('tender')

        res = super(tender_line, self).create(cr, uid, vals, context=context)

        if 'tender_id' in vals and not vals.get('sale_order_line_id'):
            so_id = tender_obj.read(cr, uid, vals.get('tender_id'), ['sale_order_id'], context=context)['sale_order_id']
            if so_id:
                exp_sol_obj.create(cr, uid, {
                    'order_id': so_id[0],
                    'tender_line_id': res,
                }, context=context)

        return res

    def write(self, cr, uid, ids, vals, context=None):
        if not ids:
            return True
        exp_sol_obj = self.pool.get('expected.sale.order.line')

        if 'state' in vals and vals.get('state') != 'draft':
            exp_sol_ids = exp_sol_obj.search(cr, uid, [
                ('tender_line_id', 'in', ids),
            ], context=context)
            exp_sol_obj.unlink(cr, uid, exp_sol_ids, context=context)

        return super(tender_line, self).write(cr, uid, ids, vals, context=context)

    def copy(self, cr, uid, id, default=None, context=None):
        if default is None:
            default = {}

        if not 'created_by_rfq' in default:
            default['created_by_rfq'] = False

        return super(tender_line, self).copy(cr, uid, id, default, context=context)

    def cancel_sourcing(self, cr, uid, ids, context=None):
        '''
        Cancel the line and re-source the FO line
        '''
        # Objects
        sol_obj = self.pool.get('sale.order.line')
        uom_obj = self.pool.get('product.uom')
        tender_obj = self.pool.get('tender')

        # Variables
        to_remove = []
        to_cancel = []
        sol_ids = {}
        sol_to_update = {}
        sol_not_to_delete = []
        so_to_update = set()
        tender_to_update = set()

        for line in self.browse(cr, uid, ids, context=context):
            tender_to_update.add(line.tender_id.id)
            if line.sale_order_line_id and line.sale_order_line_id.state not in ('cancel', 'done'):
                so_to_update.add(line.sale_order_line_id.order_id.id)
                if line.sale_order_line_id.order_id.procurement_request:
                    sol_not_to_delete.append(line.sale_order_line_id.id)
                to_cancel.append(line.id)
                # Get the ID and the product qty of the FO line to re-source
                diff_qty = uom_obj._compute_qty(cr, uid, line.product_uom.id, line.qty, line.sale_order_line_id.product_uom.id)

                if line.has_to_be_resourced:
                    sol_ids.update({line.sale_order_line_id.id: diff_qty})

                sol_to_update.setdefault(line.sale_order_line_id.id, 0.00)
                sol_to_update[line.sale_order_line_id.id] += diff_qty
            elif line.tender_id.state == 'draft':
                to_remove.append(line.id)
            else:
                to_cancel.append(line.id)

        if to_cancel:
            self.write(cr, uid, to_cancel, {'line_state': 'cancel'}, context=context)

        if sol_ids:
            for sol in sol_ids:
                sol_obj.add_resource_line(cr, uid, sol, False, sol_ids[sol], context=context)

        # Update sale order lines
        so_to_cancel_ids = []
        for sol in sol_to_update:
            context['update_or_cancel_line_not_delete'] = sol in sol_not_to_delete
            so_to_cancel_id = sol_obj.update_or_cancel_line(cr, uid, sol, sol_to_update[sol], context=context)
            if so_to_cancel_id:
                so_to_cancel_ids.append(so_to_cancel_id)

        if context.get('update_or_cancel_line_not_delete', False):
            del context['update_or_cancel_line_not_delete']

        # Update the FO state
        # for so in so_to_update:
        #    wf_service.trg_write(uid, 'sale.order', so, cr)

        # UF-733: if all tender lines have been compared (have PO Line id), then set the tender to be ready
        # for proceeding to other actions (create PO, Done etc)
        for tender in tender_obj.browse(cr, uid, list(tender_to_update), context=context):
            if tender.internal_state == 'draft':
                flag = True
                for line in tender.tender_line_ids:
                    if line.line_state != 'cancel' and not line.purchase_order_line_id:
                        flag = False
                if flag:
                    tender_obj.write(cr, uid, [tender.id], {'internal_state': 'updated'})

        if context.get('fake_unlink'):
            return to_remove

        return so_to_cancel_ids

    def fake_unlink(self, cr, uid, ids, context=None):
        '''
        Cancel the line if it is linked to a FO line
        '''
        to_remove = self.cancel_sourcing(cr, uid, ids, context=dict(context, fake_unlink=True))

        for tl in self.browse(cr, uid, ids, context=context):
            self.infolog(cr, uid, "The tender line id:%s of tender id:%s (%s) has been canceled" % (
                tl.id,
                tl.tender_id.id,
                tl.tender_id.name,
            ))

        return self.unlink(cr, uid, to_remove, context=context)

    def ask_unlink(self, cr, uid, ids, context=None):
        '''
        Ask user if he wants to re-source the needs
        '''
        # Objects
        wiz_obj = self.pool.get('tender.line.cancel.wizard')
        tender_obj = self.pool.get('tender')
        exp_sol_obj = self.pool.get('expected.sale.order.line')

        # Variables
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        # Check if the line has been already deleted
        ids = self.search(cr, uid, [('id', 'in', ids), ('line_state', '!=', 'cancel')], context=context)
        if not ids:
            raise osv.except_osv(
                _('Error'),
                _('The line has already been canceled - Please refresh the page'),
            )

        tender_id = False
        for line in self.browse(cr, uid, ids, context=context):
            tender_id = line.tender_id.id
            wiz_id = False
            last_line = False
            exp_sol_ids = None

            if line.tender_id.sale_order_id:
                exp_sol_ids = exp_sol_obj.search(cr, uid, [
                    ('tender_id', '=', tender_id),
                    ('tender_line_id', '!=', line.id),
                ], context=context)

                tender_so_ids, po_ids, so_ids, sol_nc_ids = tender_obj.sourcing_document_state(cr, uid, [tender_id], context=context)
                if line.sale_order_line_id and line.sale_order_line_id.id in sol_nc_ids:
                    sol_nc_ids.remove(line.sale_order_line_id.id)

                if po_ids and not exp_sol_ids and not sol_nc_ids:
                    last_line = True

            if line.sale_order_line_id:
                wiz_id = wiz_obj.create(cr, uid, {
                    'tender_line_id': line.id,
                    'last_line': last_line,
                }, context=context)
            elif not exp_sol_ids and line.tender_id.sale_order_id:
                wiz_id = wiz_obj.create(cr, uid, {
                    'tender_line_id': line.id,
                    'only_exp': True,
                    'last_line': last_line,
                }, context=context)

            if wiz_id:
                return {'type': 'ir.actions.act_window',
                        'res_model': 'tender.line.cancel.wizard',
                        'view_type': 'form',
                        'view_mode': 'form',
                        'res_id': wiz_id,
                        'target': 'new',
                        'context': context}

        for line_id in ids:
            wiz_id = wiz_obj.create(cr, uid, {
                'tender_line_id': line_id,
            }, context=context)

        if wiz_id:
            return wiz_obj.just_cancel(cr, uid, wiz_id, context=context)

        return {'type': 'ir.actions.act_window',
                'res_model': 'tender',
                'view_type': 'form',
                'view_mode': 'form,tree',
                'res_id': tender_id,
                'target': 'crush',
                'context': context}


    def get_existing_po(self, cr, uid, ids, context=None):
        """
        SOURCING PROCESS: Do we have to create new PO or use an existing one ?
        If an existing one can be used, then returns his ID, otherwise returns False
        @return ID (int) of document to use or False
        """
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        res_id = False
        for tender_line in self.browse(cr, uid, ids, context=context):
            rfq_line = tender_line.purchase_order_line_id
            # common domain:
            domain = [
                ('partner_id', '=', rfq_line.partner_id.id),
                ('state', 'in', ['draft']),
                ('delivery_requested_date', '=', rfq_line.date_planned),
                ('rfq_ok', '=', False),
                ('order_type', '=', 'regular'),
            ]
            res_id = self.pool.get('purchase.order').search(cr, uid, domain, context=context)

        if res_id and isinstance(res_id, list):
            res_id = res_id[0]

        return res_id or False

    def create_po_from_tender_line(self, cr, uid, ids, context=None):
        '''
        SOURCING PROCESS: Create an new PO/DPO from tender line
        @return id of the newly created PO
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        for tender_line in self.browse(cr, uid, ids, context=context):
            # commom fields:
            pricelist = tender_line.supplier_id.property_product_pricelist_purchase.id,
            if tender_line.currency_id:
                price_ids = self.pool.get('product.pricelist').search(cr, uid, [('type', '=', 'purchase'), ('currency_id', '=', tender_line.currency_id.id)], context=context)
                if price_ids:
                    pricelist = price_ids[0]
            tender = tender_line.tender_id
            po_values = {
                'origin': (tender.sale_order_id and tender.sale_order_id.name or "") + '; ' + tender.name,
                'partner_id': tender_line.supplier_id.id,
                'partner_address_id': self.pool.get('res.partner').address_get(cr, uid, [tender_line.supplier_id.id], ['default'])['default'],
                'customer_id': tender_line.sale_order_line_id and tender_line.sale_order_line_id.order_id.partner_id.id or False,
                'location_id': tender.location_id.id,
                'company_id': tender.company_id.id,
                'cross_docking_ok': True if tender_line.sale_order_line_id else False,
                'pricelist_id': pricelist,
                'fiscal_position': tender_line.supplier_id.property_account_position and tender_line.supplier_id.property_account_position.id or False,
                'warehouse_id': tender.warehouse_id.id,
                'categ': tender.categ,
                'priority': tender.priority,
                'origin_tender_id': tender.id,
                'details': tender.details,
                'delivery_requested_date': tender.requested_date,
                'dest_address_id': tender.delivery_address.id,
            }

        return self.pool.get('purchase.order').create(cr, uid, po_values, context=context)

tender_line()


class tender2(osv.osv):
    '''
    tender class
    '''
    _inherit = 'tender'
    _columns = {'tender_line_ids': fields.one2many('tender.line', 'tender_id', string="Tender lines", states={'draft': [('readonly', False)]}, readonly=True),
                }

    def copy(self, cr, uid, id, default=None, context=None):
        '''
        reset the name to get new sequence number

        the copy method is here because upwards it goes in infinite loop
        '''
        if default is None:
            default = {}

        default.update(name=self.pool.get('ir.sequence').get(cr, uid, 'tender'),
                       rfq_ids=[],
                       sale_order_line_id=False,)

        result = super(tender2, self).copy(cr, uid, id, default, context)

        return result

    def copy_data(self, cr, uid, id, default=None, context=None):
        '''
        reset the tender line
        '''
        result = super(tender, self).copy_data(cr, uid, id, default=default, context=context)
        # reset the tender line
        for line in result['tender_line_ids']:
            line[2].update(sale_order_line_id=False,
                           purchase_order_line_id=False,
                           line_state='draft',)
        return result

tender2()


class procurement_order(osv.osv):
    '''
    tender capabilities
    '''
    _inherit = 'procurement.order'

    def _is_tender_rfq(self, cr, uid, ids, field_name, arg, context=None):
        '''
        tell if the corresponding sale order line is tender/rfq sourcing or not
        '''
        result = {}
        for proc in self.browse(cr, uid, ids, context=context):
            result[proc.id] = {'is_tender': False, 'is_rfq': False}
            for line in proc.sale_order_line_ids:
                result[proc.id]['is_tender'] = line.po_cft == 'cft'
                result[proc.id]['is_rfq'] = line.po_cft == 'rfq'

        return result

    _columns = {'is_tender': fields.function(_is_tender_rfq, method=True, type='boolean', string='Is Tender', readonly=True, multi='tender_rfq'),
                'is_rfq': fields.function(_is_tender_rfq, method=True, type='boolean', string='Is RfQ', readonly=True, multi='tender_rfq'),
                'sale_order_line_ids': fields.one2many('sale.order.line', 'procurement_id', string="Sale Order Lines"),
                'tender_id': fields.many2one('tender', string='Tender', readonly=True),
                'tender_line_id': fields.many2one('tender.line', string='Tender line', readonly=True),
                'is_tender_done': fields.boolean(string="Tender Closed"),
                'rfq_id': fields.many2one('purchase.order', string='RfQ', readonly=True),
                'rfq_line_id': fields.many2one('purchase.order.line', string='RfQ line', readonly=True),
                'is_rfq_done': fields.boolean(string="RfQ Closed"),
                'state': fields.selection([('draft', 'Draft'),
                                           ('confirmed', 'Confirmed'),
                                           ('exception', 'Exception'),
                                           ('running', 'Converted'),
                                           ('cancel', 'Cancelled'),
                                           ('ready', 'Ready'),
                                           ('done', 'Closed'),
                                           ('tender', 'Tender'),
                                           ('rfq', 'Request for Quotation'),
                                           ('waiting', 'Waiting'), ], 'State', required=True,
                                          help='When a procurement is created the state is set to \'Draft\'.\n If the procurement is confirmed, the state is set to \'Confirmed\'.\
                                                \nAfter confirming the state is set to \'Running\'.\n If any exception arises in the order then the state is set to \'Exception\'.\n Once the exception is removed the state becomes \'Ready\'.\n It is in \'Waiting\'. state when the procurement is waiting for another one to finish.'),
                'price_unit': fields.float('Unit Price from Tender', digits_compute=dp.get_precision('Purchase Price Computation')),
                }
    _defaults = {
        'is_tender_done': False,
        'is_rfq_done': False,
    }

    def no_address_error(self, cr, uid, ids, context=None):
        '''
        Put the procurement order in exception state with the good error message
        '''
        for proc in self.browse(cr, uid, ids, context=context):
            if proc.supplier and not proc.supplier.address:
                self.write(cr, uid, [proc.id], {
                    'state': 'exception',
                    'message': _('The supplier "%s" has no address defined!') % (proc.supplier.name,),
                }, context=context)

        return True

    def wkf_action_rfq_create(self, cr, uid, ids, context=None):
        '''
        creation of rfq from procurement workflow
        '''
        rfq_obj = self.pool.get('purchase.order')
        rfq_line_obj = self.pool.get('purchase.order.line')
        partner_obj = self.pool.get('res.partner')
        prsd_obj = self.pool.get('procurement.request.sourcing.document')

        if not context:
            context = {}

        # find the corresponding sale order id for rfq
        for proc in self.browse(cr, uid, ids, context=context):
            if proc.rfq_id:
                return proc.rfq_id
            sale_order = False
            sale_order_line = False
            for sol in proc.sale_order_line_ids:
                sale_order = sol.order_id
                sale_order_line = sol
                break
            # find the rfq
            rfq_id = False
            # UTP-934: If source rfq to different supplier, different rfq must be created, and cannot be using the same rfq
            rfq_ids = rfq_obj.search(cr, uid, [('sale_order_id', '=', sale_order.id), ('partner_id', '=', proc.supplier.id), ('state', '=', 'draft'), ('rfq_ok', '=', True), ], context=context)
            if rfq_ids:
                rfq_id = rfq_ids[0]
            # create if not found
            if not rfq_id:
                supplier = proc.supplier
                company = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id
                pricelist_id = supplier.property_product_pricelist_purchase.id
                address_id = partner_obj.address_get(cr, uid, [supplier.id], ['default'])['default']
                if not address_id:
                    self.write(cr, uid, [proc.id], {
                        'message': _('The supplier "%s" has no address defined!') % (supplier.name,),
                    }, context=context)
                    continue

                context['rfq_ok'] = True
                rfq_id = rfq_obj.create(cr, uid, {'sale_order_id': sale_order.id,
                                                  'categ': sale_order.categ,
                                                  'priority': sale_order.priority,
                                                  'fiscal_position': supplier.property_account_position and supplier.property_account_position.id or False,
                                                  'rfq_delivery_address': partner_obj.address_get(cr, uid, company.partner_id.id, ['delivery'])['delivery'],
                                                  'warehouse_id': sale_order.shop_id.warehouse_id.id,
                                                  'location_id': proc.location_id.id,
                                                  'partner_id': supplier.id,
                                                  'partner_address_id': address_id,
                                                  'pricelist_id': pricelist_id,
                                                  'rfq_ok': True,
                                                  'from_procurement': True,
                                                  'order_type': sale_order.order_type,
                                                  'origin': sale_order.name, }, context=context)

            prsd_obj.chk_create(cr, uid, {
                'order_id': sale_order.id,
                'sourcing_document_id': rfq_id,
                'sourcing_document_model': 'purchase.order',
                'sourcing_document_type': 'rfq',
                'line_ids': sale_order_line and sale_order_line.id or False,
            }, context=context)

            # add a line to the RfQ
            rfq_line_id = rfq_line_obj.create(cr, uid, {'product_id': proc.product_id.id,
                                                        'comment': sale_order_line.comment,
                                                        'name': sale_order_line.name,
                                                        'price_unit': 0.00,
                                                        'product_qty': proc.product_qty,
                                                        'origin': sale_order.name,
                                                        'order_id': rfq_id,
                                                        'sale_order_line_id': sale_order_line.id,
                                                        'location_id': proc.location_id.id,
                                                        'product_uom': proc.product_uom.id,
                                                        'procurement_id': proc.id,
                                                        #'date_planned': proc.date_planned, # function at line level
                                                        }, context=context)

            self.write(cr, uid, ids, {'rfq_id': rfq_id, 'rfq_line_id': rfq_line_id}, context=context)

            # log message concerning RfQ creation
            rfq_obj.log(cr, uid, rfq_id, "The Request for Quotation '%s' has been created and must be completed before purchase order creation." % rfq_obj.browse(cr, uid, rfq_id, context=context).name, context={'rfq_ok': 1})
            rfq_line = rfq_line_obj.browse(cr, uid, rfq_line_id, context=context)
            self.infolog(cr, uid, "The FO/IR line id:%s (line number: %s) has been sourced on order to RfQ line id:%s (line number: %s) of the RfQ id:%s (%s)" % (
                sale_order_line.id,
                sale_order_line.line_number,
                rfq_line.id,
                rfq_line.line_number,
                rfq_line.order_id.id,
                rfq_line.order_id.name,
            ))
        # state of procurement is Tender
        self.write(cr, uid, ids, {'state': 'rfq'}, context=context)

        return rfq_id

    def wkf_action_tender_create(self, cr, uid, ids, context=None):
        '''
        creation of tender from procurement workflow
        '''
        tender_obj = self.pool.get('tender')
        tender_line_obj = self.pool.get('tender.line')
        prsd_obj = self.pool.get('procurement.request.sourcing.document')
        # find the corresponding sale order id for tender
        for proc in self.browse(cr, uid, ids, context=context):
            if proc.tender_id:
                return proc.tender_id
            sale_order = False
            sale_order_line = False
            for sol in proc.sale_order_line_ids:
                sale_order = sol.order_id
                sale_order_line = sol
            # find the tender
            tender_id = False
            tender_ids = tender_obj.search(cr, uid, [('sale_order_id', '=', sale_order.id), ('state', '=', 'draft'), ], context=context)
            if tender_ids:
                tender_id = tender_ids[0]
            # create if not found
            if not tender_id:
                tender_id = tender_obj.create(cr, uid, {'sale_order_id': sale_order.id,
                                                        'location_id': proc.location_id.id,
                                                        'categ': sale_order.categ,
                                                        'priority': sale_order.priority,
                                                        'warehouse_id': sale_order.shop_id.warehouse_id.id,
                                                        'requested_date': proc.date_planned,
                                                        }, context=context)
            prsd_obj.chk_create(cr, uid, {
                'order_id': sale_order.id,
                'sourcing_document_id': tender_id,
                'sourcing_document_model': 'tender',
                'sourcing_document_type': 'tender',
                'line_ids': sale_order_line and sale_order_line.id or False,
            }, context=context)
            # add a line to the tender
            tender_line_id = tender_line_obj.create(cr, uid, {'product_id': proc.product_id.id,
                                                              'comment': sale_order_line.comment,
                                                              'qty': proc.product_qty,
                                                              'tender_id': tender_id,
                                                              'sale_order_line_id': sale_order_line.id,
                                                              'location_id': proc.location_id.id,
                                                              'product_uom': proc.product_uom.id,
                                                              #'date_planned': proc.date_planned, # function at line level
                                                              }, context=context)

            self.write(cr, uid, ids, {'tender_id': tender_id, 'tender_line_id': tender_line_id}, context=context)

            # log message concerning tender creation
            tender_line = tender_line_obj.browse(cr, uid, tender_line_id, context=context)
            tender_obj.log(cr, uid, tender_id, "The tender '%s' has been created and must be completed before purchase order creation." % tender_line.tender_id.name)
            self.infolog(cr, uid, "The FO/IR line id:%s (%s) has been sourced on order to tender line id:%s of the tender id:%s (%s)" % (
                sale_order_line.id,
                sale_order_line.line_number,
                tender_line.id,
                tender_line.tender_id.id,
                tender_line.tender_id.name,
            ))
        # state of procurement is Tender
        self.write(cr, uid, ids, {'state': 'tender'}, context=context)

        return tender_id

    def wkf_action_tender_done(self, cr, uid, ids, context=None):
        '''
        set is_tender_done value
        '''
        self.write(cr, uid, ids, {'is_tender_done': True, 'state': 'exception', }, context=context)
        return True

    def wkf_action_rfq_done(self, cr, uid, ids, context=None):
        '''
        set is_rfq_done value
        '''
        self.write(cr, uid, ids, {'is_rfq_done': True, 'state': 'exception', }, context=context)
        return True

    def _get_pricelist_from_currency(self, cr, uid, currency_id, context=None):
        price_obj = self.pool.get('product.pricelist')
        price_ids = price_obj.search(cr, uid, [
            ('currency_id', '=', currency_id),
            ('type', '=', 'purchase'),
        ], context=context)

        return price_ids and price_ids[0] or False

    def action_po_assign(self, cr, uid, ids, context=None):
        '''
        - convert the created rfq by the tender to a po
        - add message at po creation during on_order workflow
        '''
        po_obj = self.pool.get('purchase.order')
        sol_obj = self.pool.get('sale.order.line')

        # If the line has been created by a confirmed PO, doesn't create a new PO
        sol_ids = sol_obj.search(cr, uid, [('procurement_id', 'in', ids), ('created_by_po', '!=', False)], context=context)
        if sol_ids:
            return sol_obj.read(cr, uid, sol_ids[0], ['created_by_po'], context=context)['created_by_po'][0]

        result = super(procurement_order, self).action_po_assign(cr, uid, ids, context=context)
        # The quotation 'SO001' has been converted to a sales order.
        if result:
            # do not display a log if we come from po update backward update of so
            data = self.read(cr, uid, ids, ['so_back_update_dest_po_id_procurement_order'], context=context)
            if not data[0]['so_back_update_dest_po_id_procurement_order']:
                po_obj.log(cr, uid, result, "The Purchase Order '%s' has been created following 'on order' sourcing." % po_obj.browse(cr, uid, result, context=context).name)
        return result

    def po_values_hook(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        data for the purchase order creation
        '''
        values = super(procurement_order, self).po_values_hook(cr, uid, ids, context=context, *args, **kwargs)
        procurement = kwargs['procurement']

        values['partner_address_id'] = self.pool.get('res.partner').address_get(cr, uid, [values['partner_id']], ['default'])['default']

        # set tender link in purchase order
        if procurement.tender_id:
            values['origin_tender_id'] = procurement.tender_id.id

        # set tender line currency in purchase order
        if procurement.tender_line_id:
            cur_id = procurement.tender_line_id.currency_id.id
            pricelist_id = self._get_pricelist_from_currency(cr, uid, cur_id, context=context)
            if pricelist_id:
                values['pricelist_id'] = pricelist_id

        # set rfq link in purchase order
        if procurement.rfq_id:
            values.update({
                'origin_rfq_id': procurement.rfq_id.id,
                'pricelist_id': procurement.rfq_id.pricelist_id.id,
            })

        values['date_planned'] = procurement.date_planned

        if procurement.product_id:
            if procurement.product_id.type == 'consu':
                values['location_id'] = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock_override', 'stock_location_non_stockable')[1]
            elif procurement.product_id.type == 'service_recep':
                values['location_id'] = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_config_locations', 'stock_location_service')[1]
            else:
                wh_ids = self.pool.get('stock.warehouse').search(cr, uid, [])
                if wh_ids:
                    values['location_id'] = self.pool.get('stock.warehouse').browse(cr, uid, wh_ids[0]).lot_input_id.id
                else:
                    values['location_id'] = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_config_locations', 'stock_location_service')[1]

        return values

procurement_order()


class purchase_order(osv.osv):
    '''
    add link to tender
    '''
    _inherit = 'purchase.order'

    def _check_valid_till(self, cr, uid, ids, context=None):
        """ Checks if valid till has been completed
        """
        for obj in self.browse(cr, uid, ids, context=context):
            if obj.state == 'rfq_updated' and not obj.valid_till:
                return False
        return True

    _columns = {'tender_id': fields.many2one('tender', string="Tender", readonly=True, internal="purchase_order"),
                'rfq_delivery_address': fields.many2one('res.partner.address', string='Delivery address', internal="purchase_order"),
                'origin_tender_id': fields.many2one('tender', string='Tender', readonly=True, internal=True),
                'from_procurement': fields.boolean(string='RfQ created by a procurement order', internal=True),
                'rfq_ok': fields.boolean(string='Is RfQ ?', internal=True),
                'valid_till': fields.date(string='Valid Till', internal="purchase_order"),
                # add readonly when state is Done
                'sale_order_id': fields.many2one('sale.order', string='Link between RfQ and FO', readonly=True, internal="purchase_order"),
                'rfq_state': fields.selection([('draft', 'Draft'), ('sent', 'Sent'), ('updated', 'Updated'), ('done', 'Closed'), ('cancel', 'Cancelled')], 'Order state', required=True, readonly=True, internal="purchase_order"),
                }

    _defaults = {
        'rfq_ok': lambda self, cr, uid, c: c.get('rfq_ok', False),
        'rfq_state': 'draft',
    }

    _constraints = [
        (_check_valid_till,
            'You must specify a Valid Till date.',
            ['valid_till']), ]

    def default_get(self, cr, uid, fields, context=None):
        '''
        Set default data
        '''
        # Object declaration
        partner_obj = self.pool.get('res.partner')
        user_obj = self.pool.get('res.users')

        res = super(purchase_order, self).default_get(cr, uid, fields, context=context)

        # Get the delivery address
        company = user_obj.browse(cr, uid, uid, context=context).company_id
        res['rfq_delivery_address'] = partner_obj.address_get(cr, uid, company.partner_id.id, ['delivery'])['delivery']

        return res

    def create(self, cr, uid, vals, context=None):
        '''
        Set the reference at this step
        '''
        if context is None:
            context = {}
        if context.get('rfq_ok', False) and not vals.get('name', False):
            vals.update({'name': self.pool.get('ir.sequence').get(cr, uid, 'rfq')})
        elif not vals.get('name', False):
            vals.update({'name': self.pool.get('ir.sequence').get(cr, uid, 'purchase.order')})

        if context.get('rfq_ok', False) and not vals.get('location_id'):
            input_loc = self.pool.get('stock.location').search(cr, uid, [('input_ok', '=', True)], context=context)
            vals['location_id'] = input_loc and input_loc[0] or False

        return super(purchase_order, self).create(cr, uid, vals, context=context)


    def cancel_rfq(self, cr, uid, ids, context=None):
        '''
        method to cancel a RfQ and its lines
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        wf_service = netsvc.LocalService("workflow")

        for rfq in self.browse(cr, uid, ids, context=context):
            if not rfq.rfq_ok:
                continue
            for rfq_line in rfq.order_line:
                wf_service.trg_validate(uid, 'purchase.order.line', rfq_line.id, 'cancel', cr)

            self.write(cr, uid, [rfq.id], {'rfq_state': 'cancel'}, context=context)

        return True


    def unlink(self, cr, uid, ids, context=None):
        '''
        Display an error message if the PO has associated IN
        '''
        in_ids = self.pool.get('stock.picking').search(cr, uid, [('purchase_id', 'in', ids)], context=context)
        if in_ids:
            raise osv.except_osv(_('Error !'), _('Cannot delete a document if its associated ' \
                                                 'document remains open. Please delete it (associated IN) first.'))

        # Copy a part of purchase_order standard unlink method to fix the bad state on error message
        purchase_orders = self.read(cr, uid, ids, ['state'], context=context)
        unlink_ids = []
        for s in purchase_orders:
            if s['state'] in ['draft', 'cancel']:
                unlink_ids.append(s['id'])
            else:
                raise osv.except_osv(_('Invalid action !'), _('Cannot delete Purchase Order(s) which are in %s State!') % _(dict(PURCHASE_ORDER_STATE_SELECTION).get(s['state'])))

        return super(purchase_order, self).unlink(cr, uid, ids, context=context)

    def _hook_copy_name(self, cr, uid, ids, context=None, *args, **kwargs):
        '''
        HOOK from purchase>purchase.py for COPY function. Modification of default copy values
        define which name value will be used
        '''
        # default values from copy function
        default = kwargs.get('default', False)
        # flag defining if the new object will be a rfq
        is_rfq = False
        # calling super function
        result = super(purchase_order, self)._hook_copy_name(cr, uid, ids, context=context, *args, **kwargs)
        if default.get('rfq_ok', False):
            is_rfq = True
        elif 'rfq_ok' not in default:
            for obj in self.browse(cr, uid, ids, context=context):
                # if rfq_ok is specified as default value for new object, we base our decision on this value
                if obj.rfq_ok:
                    is_rfq = True
        if is_rfq:
            result.update(name=self.pool.get('ir.sequence').get(cr, uid, 'rfq'))
        return result

    def hook_rfq_sent_check_lines(self, cr, uid, ids, context=None):
        '''
        Please copy this to your module's method also.
        This hook belongs to the rfq_sent method from tender_flow>tender_flow.py
        - check lines after import
        '''
        pol_obj = self.pool.get('purchase.order.line')

        res = True
        empty_lines = pol_obj.search(cr, uid, [
            ('order_id', 'in', ids),
            ('product_qty', '<=', 0.00),
        ], context=context)
        if empty_lines:
            raise osv.except_osv(
                _('Error'),
                _('All lines of the RfQ should have a quantity before sending the RfQ to the supplier'),
            )
        return res

    def action_sent(self, cr, uid, ids, context=None):
        '''
        Method called when calling button Sent RfQ
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        self.write(cr, uid, ids, {
            'rfq_state': 'sent',
            'date_confirm': time.strftime('%Y-%m-%d'),
        }, context=context)

        return True

    def rfq_sent(self, cr, uid, ids, context=None):
        if not ids:
            return {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        if context is None:
            context = {}

        self.hook_rfq_sent_check_lines(cr, uid, ids, context=context)
        for rfq in self.browse(cr, uid, ids, context=context):
            self.action_sent(cr, uid, [rfq.id], context=context)
            self.infolog(cr, uid, "The RfQ id:%s (%s) has been sent." % (
                rfq.id, rfq.name,
            ))

        datas = {'ids': ids}
        if len(ids) == 1:
            # UFTP-92: give a name to report when generated from RfQ worklow sent_rfq stage
            datas['target_filename'] = 'RFQ_' + rfq.name

        return {'type': 'ir.actions.report.xml',
                'report_name': 'msf.purchase.quotation',
                'datas': datas}

    def action_updated(self, cr, uid, ids, context=None):
        '''
        method called when getting the updated state (case of RfQ)
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        self.write(cr, uid, ids, {'rfq_state': 'updated'}, context=context)

        return True

    def check_rfq_updated(self, cr, uid, ids, context=None):
        tl_obj = self.pool.get('tender.line')
        line_obj = self.pool.get('purchase.order.line')

        if isinstance(ids, (int, long)):
            ids = [ids]

        for rfq in self.browse(cr, uid, ids, context=context):
            if not rfq.valid_till:
                raise osv.except_osv(_('Error'), _('You must specify a Valid Till date.'))

            if rfq.rfq_ok and rfq.tender_id:
                for line in rfq.order_line:
                    if not line.tender_line_id:
                        tl_ids = tl_obj.search(cr, uid, [('product_id', '=', line.product_id.id), ('tender_id', '=', rfq.tender_id.id), ('line_state', '=', 'draft')], context=context)
                        if tl_ids:
                            tl_id = tl_ids[0]
                        else:
                            tl_vals = {'product_id': line.product_id.id,
                                       'product_uom': line.product_uom.id,
                                       'qty': line.product_qty,
                                       'tender_id': rfq.tender_id.id,
                                       'created_by_rfq': True}
                            tl_id = tl_obj.create(cr, uid, tl_vals, context=context)
                            self.infolog(cr, uid, "The tender line id:%s has been created by the RfQ line id:%s (line number: %s)" % (
                                tl_id, line.id, line.line_number,
                            ))
                        line_obj.write(cr, uid, [line.id], {'tender_line_id': tl_id}, context=context)
            elif rfq.rfq_ok:
                line_ids = line_obj.search(cr, uid, [
                    ('order_id', '=', rfq.id),
                    ('price_unit', '=', 0.00),
                ], count=True, context=context)
                if line_ids:
                    raise osv.except_osv(
                        _('Error'),
                        _('''You cannot update an RfQ with lines without unit
price. Please set unit price on these lines or cancel them'''),
                    )

            self.action_updated(cr, uid, [rfq.id], context=context)
            self.infolog(cr, uid, "The RfQ id:%s (%s) has been updated" % (
                rfq.id, rfq.name,
            ))

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'view_mode': 'form,tree,graph,calendar',
            'view_type': 'form',
            'target': 'crush',
            'context': {'rfq_ok': True, 'search_default_draft_rfq': 1},
            'domain': [('rfq_ok', '=', True)],
            'res_id': rfq.id,
        }

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        """
        columns for the tree
        """
        if context is None:
            context = {}
        # the search view depends on the type we want to display
        if view_type == 'search':
            if context.get('rfq_ok', False):
                # rfq search view
                view = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'tender_flow', 'view_rfq_filter')
                if view:
                    view_id = view[1]
        if view_type == 'tree':
            # the view depends on po type
            if context.get('rfq_ok', False):
                # rfq search view
                view = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'tender_flow', 'view_rfq_tree')
                if view:
                    view_id = view[1]
        if view_type == 'form':
            if context.get('rfq_ok', False):
                view = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'tender_flow', 'view_rfq_form')
                if view:
                    view_id = view[1]

        return super(purchase_order, self).fields_view_get(cr, uid, view_id, view_type, context=context, toolbar=toolbar, submenu=submenu)

    def rfq_closed(self, cr, uid, ids, context=None):
        '''
        close the Request for Quotation
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
        if context is None:
            context = {}

        for rfq in self.browse(cr, uid, ids, context=context):
            self.infolog(cr, uid, "The RfQ id:%s (%s) has been closed" % (rfq.id, rfq.name))

        return self.write(cr, uid, ids, {'rfq_state': 'done', 'state': 'done'}, context=context)

purchase_order()


class purchase_order_line(osv.osv):
    '''
    add a tender_id related field
    '''
    _inherit = 'purchase.order.line'
    _columns = {'tender_id': fields.related('order_id', 'tender_id', type='many2one', relation='tender', string='Tender',),
                'tender_line_id': fields.many2one('tender.line', string='Tender Line'),
                'rfq_ok': fields.related('order_id', 'rfq_ok', type='boolean', string='RfQ ?'),
                'sale_order_line_id': fields.many2one('sale.order.line', string='FO line', readonly=True),
                }

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        """
        columns for the tree
        """
        if context is None:
            context = {}

        # call super
        result = super(purchase_order_line, self).fields_view_get(cr, uid, view_id, view_type, context=context, toolbar=toolbar, submenu=submenu)
        if view_type == 'form':
            if context.get('rfq_ok', False):
                # the title of the screen depends on po type
                form = etree.fromstring(result['arch'])
                fields = form.xpath('//form[@string="%s"]' % _('Purchase Order Line'))
                for field in fields:
                    field.set('string', _("Request for Quotation Line"))
                result['arch'] = etree.tostring(form)

        return result

purchase_order_line()


class sale_order_line(osv.osv):
    '''
    add link one2many to tender.line
    '''
    _inherit = 'sale.order.line'

    _columns = {
        'tender_line_ids': fields.one2many('tender.line', 'sale_order_line_id', string="Tender Lines", readonly=True),
        'created_by_tender': fields.many2one('tender', string='Created by tender'),
        'created_by_tender_line': fields.many2one('tender.line', string='Created by tender line'),
    }

    def copy_data(self, cr, uid, ids, default=None, context=None):
        '''
        Remove tender lines linked
        '''
        default = default or {}

        if not 'tender_line_ids' in default:
            default['tender_line_ids'] = []

        return super(sale_order_line, self).copy_data(cr, uid, ids, default, context=context)

sale_order_line()


class pricelist_partnerinfo(osv.osv):
    '''
    add new information from specifications
    '''
    def _get_line_number(self, cr, uid, ids, field_name, args, context=None):
        res = {}
        for price in self.browse(cr, uid, ids, context=context):
            res[price.id] = 0
            if price.purchase_order_line_id:
                res[price.id] = price.purchase_order_line_id.line_number

        return res

    _inherit = 'pricelist.partnerinfo'
    _columns = {'price': fields.float('Unit Price', required=True, digits_compute=dp.get_precision('Purchase Price Computation'), help="This price will be considered as a price for the supplier UoM if any or the default Unit of Measure of the product otherwise"),
                'currency_id': fields.many2one('res.currency', string='Currency', required=True, domain="[('partner_currency', '=', partner_id)]", select=True),
                'valid_till': fields.date(string="Valid Till",),
                'comment': fields.char(size=128, string='Comment'),
                'purchase_order_id': fields.related('purchase_order_line_id', 'order_id', type='many2one', relation='purchase.order', string="Related RfQ", readonly=True,),
                'purchase_order_line_id': fields.many2one('purchase.order.line', string="RfQ Line Ref",),
                #'purchase_order_line_number': fields.related('purchase_order_line_id', 'line_number', type="integer", string="Related Line Number", ),
                'purchase_order_line_number': fields.function(_get_line_number, method=True, type="integer", string="Related Line Number", readonly=True),
                }
pricelist_partnerinfo()


class tender_line_cancel_wizard(osv.osv_memory):
    _name = 'tender.line.cancel.wizard'

    _columns = {
        'tender_line_id': fields.many2one('tender.line', string='Tender line', required=True),
        'only_exp': fields.boolean(
            string='Only added lines',
        ),
        'last_line': fields.boolean(
            string='Last line of the FO to source',
        ),
    }


    def just_cancel(self, cr, uid, ids, context=None):
        '''
        Cancel the line 
        '''
        # Objects
        line_obj = self.pool.get('tender.line')
        tender_obj = self.pool.get('tender')
        so_obj = self.pool.get('sale.order')
        wf_service = netsvc.LocalService("workflow")

        # Variables
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        line_ids = []
        tender_ids = set()
        so_ids = set()
        for wiz in self.browse(cr, uid, ids, context=context):
            tender_ids.add(wiz.tender_line_id.tender_id.id)
            line_ids.append(wiz.tender_line_id.id)
            if wiz.tender_line_id.tender_id.sale_order_id:
                so_ids.add(wiz.tender_line_id.tender_id.sale_order_id.id)

        if context.get('has_to_be_resourced'):
            line_obj.write(cr, uid, line_ids, {'has_to_be_resourced': True}, context=context)

        line_obj.fake_unlink(cr, uid, line_ids, context=context)

        tender_so_ids, po_ids, so_ids, sol_nc_ids = tender_obj.sourcing_document_state(cr, uid, list(tender_ids), context=context)
        for po_id in po_ids:
            wf_service.trg_write(uid, 'purchase.order', po_id, cr)

        so_to_cancel_ids = []
        if tender_so_ids:
            for so_id in tender_so_ids:
                if so_obj._get_ready_to_cancel(cr, uid, so_id, context=context)[so_id]:
                    so_to_cancel_ids.append(so_id)

        if so_to_cancel_ids:
            # Ask user to choose what must be done on the FO/IR
            context.update({
                'from_tender': True,
                'tender_ids': list(tender_ids),
            })
            return so_obj.open_cancel_wizard(cr, uid, set(so_to_cancel_ids), context=context)

        return tender_obj.check_empty_tender(cr, uid, list(tender_ids), context=context)

    def cancel_and_resource(self, cr, uid, ids, context=None):
        '''
        Flag the line to be re-sourced and run cancel method
        '''
        # Objects
        if context is None:
            context = {}

        context['has_to_be_resourced'] = True

        return self.just_cancel(cr, uid, ids, context=context)

tender_line_cancel_wizard()


class tender_cancel_wizard(osv.osv_memory):
    _name = 'tender.cancel.wizard'

    _columns = {
        'tender_id': fields.many2one('tender', string='Tender', required=True),
        'not_draft': fields.boolean(string='Tender not draft'),
        'no_need': fields.boolean(string='No need'),
    }

    def just_cancel(self, cr, uid, ids, context=None):
        '''
        Just cancel the wizard and the lines
        '''
        # Objects
        line_obj = self.pool.get('tender.line')
        so_obj = self.pool.get('sale.order')

        # Variables
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        wf_service = netsvc.LocalService("workflow")
        line_ids = []
        tender_ids = []
        rfq_ids = []
        so_ids = []
        for wiz in self.browse(cr, uid, ids, context=context):
            tender_ids.append(wiz.tender_id.id)
            if wiz.tender_id.sale_order_id and wiz.tender_id.sale_order_id.id not in so_ids:
                so_ids.append(wiz.tender_id.sale_order_id.id)
            for line in wiz.tender_id.tender_line_ids:
                line_ids.append(line.id)
            for rfq in wiz.tender_id.rfq_ids:
                rfq_ids.append(rfq.id)

        if context.get('has_to_be_resourced'):
            line_obj.write(cr, uid, line_ids, {'has_to_be_resourced': True}, context=context)

        line_obj.fake_unlink(cr, uid, line_ids, context=context)

        self.pool.get('purchase.order').cancel_rfq(cr, uid, rfq_ids, context=context)

        for tender in tender_ids:
            wf_service.trg_validate(uid, 'tender', tender, 'tender_cancel', cr)

        so_to_cancel_ids = []
        if so_ids:
            for so_id in so_ids:
                if so_obj._get_ready_to_cancel(cr, uid, so_id, context=context)[so_id]:
                    so_to_cancel_ids.append(so_id)

        if so_to_cancel_ids:
            # Ask user to choose what must be done on the FO/IR
            return so_obj.open_cancel_wizard(cr, uid, set(so_to_cancel_ids), context=context)

        return {'type': 'ir.actions.act_window_close'}

    def cancel_and_resource(self, cr, uid, ids, context=None):
        '''
        Flag the line to be re-sourced and run cancel method
        '''
        # Objects
        if context is None:
            context = {}

        context['has_to_be_resourced'] = True

        return self.just_cancel(cr, uid, ids, context=context)

    def close_window(self, cr, uid, ids, context=None):
        '''
        Just close the wizard and reload the tender
        '''
        return {'type': 'ir.actions.act_window_close'}

tender_cancel_wizard()


class expected_sale_order_line(osv.osv):
    _inherit = 'expected.sale.order.line'

    _columns = {
        'tender_line_id': fields.many2one(
            'tender.line',
            string='Tender line',
            ondelete='cascade',
        ),
        'tender_id': fields.related(
            'tender_line_id',
            'tender_id',
            string='Tender',
            type='many2one',
            relation='tender',
        ),
    }

expected_sale_order_line()


class ir_values(osv.osv):
    _name = 'ir.values'
    _inherit = 'ir.values'

    def get(self, cr, uid, key, key2, models, meta=False, context=None, res_id_req=False, without_user=True, key2_req=True):
        if context is None:
            context = {}
        values = super(ir_values, self).get(cr, uid, key, key2, models, meta, context, res_id_req, without_user, key2_req)
        new_values = values

        po_accepted_values = {'client_action_multi': ['Order Follow Up',
                                                      'action_view_purchase_order_group'],
                              'client_print_multi': ['Purchase Order (Merged)',
                                                     'Purchase Order',
                                                     'Allocation report',
                                                     'Order impact vs. Budget'],
                              'client_action_relate': ['ir_open_product_list_export_view',
                                                       'View_log_purchase.order',
                                                       'Allocation report'],
                              'tree_but_action': [],
                              'tree_but_open': []}

        rfq_accepted_values = {'client_action_multi': [],
                               'client_print_multi': ['Request for Quotation'],
                               'client_action_relate': [],
                               'tree_but_action': [],
                               'tree_but_open': []}
        if context.get('purchase_order', False) and 'purchase.order' in [x[0] for x in models]:
            new_values = []
            for v in values:
                if key == 'action' and v[1] in po_accepted_values[key2] \
                        or v[1] == 'Purchase Order Excel Export' \
                        or v[1] == 'Purchase Order' \
                        or v[1] == 'Purchase Order (Merged)' \
                        or v[1] == 'Allocation report' \
                        or v[1] == 'Order impact vs. Budget':
                    new_values.append(v)
        elif context.get('request_for_quotation', False) and 'purchase.order' in [x[0] for x in models]:
            new_values = []
            for v in values:
                if key == 'action' and v[1] in rfq_accepted_values[key2] \
                        or v[1] == 'Request for Quotation' \
                        or v[1] == 'Request For Quotation Excel Export':
                    new_values.append(v)

        return new_values

ir_values()
