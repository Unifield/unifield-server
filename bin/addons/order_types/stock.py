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
from order_types import ORDER_PRIORITY, ORDER_CATEGORY
from tools.translate import _

# US-28: Refactored the method decoration to be reused for both RW and CP
def cp_rw_warning(func, rw_flag, *args, **kwargs):
    self = args[0]
    kw_keys = kwargs.keys()

    from_button = False
    if kwargs.get('context'):
        from_button = kwargs['context'].get('from_button')
    elif len(args) > 4 and isinstance(args[4], dict ):
        from_button = args[4].get('from_button')

    from_cp_check = kwargs.get('context', {}).get('from_cp_check')
    wargs = kwargs.get('context', {}).get('callback', {}) or kwargs
    if from_button and not from_cp_check:
        cr = args[1]
        uid = args[2]
        ids = args[3]
        pick_obj = self.pool.get('stock.picking')
        rw_type = hasattr(pick_obj, '_get_usb_entity_type') and pick_obj._get_usb_entity_type(cr, uid) or False

        text = "remote warehouse"
        this_instance = "central platform"
        if rw_flag == pick_obj.REMOTE_WAREHOUSE:
            text = "central platform"
            this_instance = "remote warehouse"

        if rw_type == rw_flag:
            name = """This action should only be performed at the %s instance! Are you sure to proceed it at this %s instance?""" %(text, this_instance)
            model = 'confirm'
            step = 'default'
            question = name
            clazz = self._name
            args = [ids]
            kwargs = {}
            wiz_obj = self.pool.get('wizard')
            # open the selected wizard
            callback = {
                'clazz': clazz,
                'func': func.__name__,
                'args': args,
                'kwargs': kwargs,
                'from_cp_check': True,
            }
            tmp_context = dict(kwargs.get('context', {}),
                               question=question,
                               callback=callback,
                               from_cp_check=True)


            res = wiz_obj.open_wizard(cr, uid, ids,
                                      name=name,
                                      model=model,
                                      step=step,
                                      context=tmp_context)
            return res
    new_kwargs = {}
    for kwk in kw_keys:
        if kwk in wargs:
            new_kwargs[kwk] = wargs[kwk]

    res = func(*args, **new_kwargs)
    if from_cp_check and not (isinstance(res, dict) and res.get('res.model') != 'wizard'):
        return {'type': 'ir.actions.act_window_close'}
    else:
        return res

# US-28: Refactored the method decoration to be reused for both RW and CP warning
def check_cp_rw(func):
    def decorated(*args, **kwargs):
        return cp_rw_warning(func, "central_platform", *args, **kwargs)
    return decorated

# US-28: Refactored the method decoration to be reused for both RW and CP warning
def check_rw_warning(func):
    def decorated(*args, **kwargs):
        return cp_rw_warning(func, "remote_warehouse", *args, **kwargs)
    return decorated

class stock_move(osv.osv):
    _name = 'stock.move'
    _inherit = 'stock.move'

    def _search_order(self, cr, uid, obj, name, args, context=None):
        if not len(args):
            return []
        matching_fields = {'order_priority': 'priority', 'order_category': 'categ'}
        sale_obj = self.pool.get('sale.order')
        purch_obj = self.pool.get('purchase.order')

        search_args = []
        for arg in args:
            search_args.append((matching_fields.get(arg[0], arg[0]), arg[1], arg[2]))

        # copy search_args, because it's modified by sale_obj.search
        sale_ids = sale_obj.search(cr, uid, search_args[:], limit=0)
        purch_ids = purch_obj.search(cr, uid, search_args, limit=0)

        newrgs = []
        if sale_ids:
            newrgs.append(('sale_ref_id', 'in', sale_ids))
        if purch_ids:
            newrgs.append(('purchase_ref_id', 'in', purch_ids))

        if not newrgs:
            return [('id', '=', 0)]

        if len(newrgs) > 1:
            newrgs.insert(0, '|')

        return newrgs

    def _get_order_information(self, cr, uid, ids, fields_name, arg, context=None):
        '''
        Returns information about the order linked to the stock move
        '''
        res = {}

        for move in self.browse(cr, uid, ids, context=context):
            res[move.id] = {'order_priority': False,
                            'order_category': False,
                            'order_type': False}
            order = False

            if move.purchase_line_id and move.purchase_line_id.id:
                order = move.purchase_line_id.order_id
            elif move.sale_line_id and move.sale_line_id.id:
                order = move.sale_line_id.order_id

            if order:
                res[move.id] = {}
                if 'order_priority' in fields_name:
                    res[move.id]['order_priority'] = order.priority
                if 'order_category' in fields_name:
                    res[move.id]['order_category'] = order.categ
                if 'order_type' in fields_name:
                    res[move.id]['order_type'] = order.order_type

        return res

    _columns = {
        'order_priority': fields.function(_get_order_information, method=True, string='Priority', type='selection',
                                          selection=ORDER_PRIORITY, multi='move_order', fnct_search=_search_order),
        'order_category': fields.function(_get_order_information, method=True, string='Category', type='selection',
                                          selection=ORDER_CATEGORY, multi='move_order', fnct_search=_search_order),
        'order_type': fields.function(_get_order_information, method=True, string='Order Type', type='selection',
                                      selection=[('regular', 'Regular'), ('donation_exp', 'Donation before expiry'),
                                                 ('donation_st', 'Standard donation'), ('loan', 'Loan'),
                                                 ('in_kind', 'In Kind Donation'), ('purchase_list', 'Purchase List'),
                                                 ('direct', 'Direct Purchase Order')], multi='move_order', fnct_search=_search_order),
        'sale_ref_id': fields.related('sale_line_id', 'order_id', type='many2one', relation='sale.order', string='Sale', readonly=True),
        'purchase_ref_id': fields.related('purchase_line_id', 'order_id', type='many2one', relation='purchase.order', string='Purchase', readonly=True),
    }

stock_move()

class stock_picking(osv.osv):
    _name = 'stock.picking'
    _inherit = 'stock.picking'

    def _get_certificate(self, cr, uid, ids, field_name, arg, context=None):
        '''
        Return True if at least one stock move requires a donation certificate
        '''
        res = dict.fromkeys(ids, False)
        new_ids = self.search(cr, uid, [('id', 'in', ids),
                                        ('type', '=', 'out')], context=context)
        if new_ids:
            stock_move_obj = self.pool.get('stock.move')
            move_line_read_list = self.read(cr, uid, new_ids, ['id', 'move_lines', 'type'],
                                            context=context)
            for move_line_dict in move_line_read_list:
                stock_move_ids = move_line_dict['move_lines']
                if stock_move_obj.search(cr, uid, [('id', 'in', stock_move_ids),
                                                   ('order_type', 'in',
                                                    ('donation_exp',
                                                     'donation_st',
                                                     'in_kind')),
                                                   ], context=context):
                    res[move_line_dict['id']] = True
        return res

    _columns = {
        'certificate_donation': fields.function(_get_certificate, string='Certif ?', type='boolean', method=True),
        'attach_cert': fields.boolean(string='Certificate attached ?', readonly=True),
        'cd_from_bo':  fields.boolean(string='CD from BO'),
    }

    _defaults = {
        'attach_cert': lambda *a: False,
    }

    def print_certificate(self, cr, uid, ids, context=None):
        '''
        Launches the wizard to print the certificate
        '''
        if context is None:
            context = {}

        newuid = hasattr(uid, 'realUid') and uid.realUid or uid
        print_id = self.pool.get('stock.print.certificate').create(cr, newuid, {'type': 'donation', 'picking_id': ids[0]})

        for picking in self.browse(cr, uid, ids):
            for move in picking.move_lines:
                self.pool.get('stock.certificate.valuation').create(cr, newuid,
                                                                    {'picking_id': picking.id,
                                                                     'product_id': move.product_id.id,
                                                                     'qty': move.product_qty,
                                                                     'print_id': print_id,
                                                                     'move_id': move.id,
                                                                     'prodlot_id': move.prodlot_id.id,
                                                                     'unit_price': move.product_id.list_price})

        return {'type': 'ir.actions.act_window',
                'res_model': 'stock.print.certificate',
                'view_mode': 'form',
                'view_type': 'form',
                'context': context,
                'res_id': print_id,
                'target': 'new'}


    def print_donation_certificate(self, cr, uid, ids, context=None):
        '''
        Launch printing of the donation certificate
        '''
        certif = False
        for pick in self.browse(cr, uid, ids, context=context):
            if pick.certificate_donation:
                certif = True

        if certif:
            data = self.read(cr, uid, ids, [], context)[0]
            datas = {'ids': ids,
                     'model': 'stock.picking',
                     'form': data}

            return {'type': 'ir.actions.report.xml',
                    'report_name': 'order.type.donation.certificate',
                    'datas': datas}
        else:
            raise osv.except_osv(_('Warning'), _('This picking doesn\'t require a donation certificate'))


    def _hook_check_cp_instance(self, cr, uid, ids, context=None):
        return False

    @check_cp_rw
    def action_process(self, cr, uid, ids, context=None):
        '''
        Override the method to display a message to attach
        a certificate of donation
        '''
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        if context.get('out', False):
            return {'type': 'ir.actions.act_window_close'}

        self._check_restriction_line(cr, uid, ids, context=context)

        certif = False
        for pick in self.browse(cr, uid, ids, context=context):
            if pick.type in ['in', 'out']:
                if not context.get('yesorno', False) :
                    for move in pick.move_lines:
                        if move.order_type in ['donation_exp', 'donation_st', 'in_kind']:
                            certif = True
                            break

        if certif and not context.get('attach_ok', False):
            partial_id = self.pool.get("stock.certificate.picking").create(
                cr, uid, {'picking_id': ids[0]}, context=dict(context, active_ids=ids))
            return {'name':_("Attach a certificate of donation"),
                    'view_mode': 'form',
                    'view_id': False,
                    'view_type': 'form',
                    'res_model': 'stock.certificate.picking',
                    'res_id': partial_id,
                    'type': 'ir.actions.act_window',
                    'nodestroy': True,
                    'target': 'new',
                    'domain': '[]',
                    'context': dict(context, active_ids=ids)}
        else:
            for pick in self.browse(cr, uid, ids, context=context):
                wizard_obj = self.pool.get('stock.picking.processor')
                if pick.type == 'in':
                    wizard_obj = self.pool.get('stock.incoming.processor')
                elif pick.type == 'out':
                    wizard_obj = self.pool.get('outgoing.delivery.processor')
                else:
                    wizard_obj = self.pool.get('internal.picking.processor')

                if pick.type == 'out' and pick.subtype == 'picking':
                    raise osv.except_osv(
                        _('Error'),
                        _('You cannot do this action on a Picking Ticket. Please check you are in the right view.')
                    )

                # US-148
                if pick.type == 'in':
                    domain = [('picking_id', '=', pick.id), ('draft', '=', True), ('already_processed', '=', False)]
                    wiz_ids = wizard_obj.search(cr, uid, domain, context=context)
                    if wiz_ids:
                        proc_id = wiz_ids[0]
                    else:
                        proc_id = wizard_obj.create(cr, uid,
                                                    {'picking_id': pick.id})
                        wizard_obj.create_lines(cr, uid, proc_id,
                                                context=context)
                else:
                    proc_id = wizard_obj.create(cr, uid,
                                                {'picking_id': pick.id})
                    wizard_obj.create_lines(cr, uid, proc_id, context=context)

                res = {
                    'type': 'ir.actions.act_window',
                    'res_model': wizard_obj._name,
                    'res_id': proc_id,
                    'view_type': 'form',
                    'view_mode': 'form',
                    'target': 'new',
                }

                if not context.get('force_process', False) and pick.type == 'in' \
                   and not pick.in_dpo \
                   and pick.state != 'shipped' and pick.partner_id.partner_type == 'internal':
                    view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid,
                                                                                  'msf_outgoing', 'stock_incoming_processor_internal_warning_form_view')[1]
                    res['view_id'] = [view_id]

                return res

        return super(stock_picking, self).action_process(cr, uid, ids, context=context)

stock_picking()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
