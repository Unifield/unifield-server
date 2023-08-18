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
        fields_as_ro = False
        for pick in self.browse(cr, uid, ids, context=context):
            if pick.type == 'in':
                fields_as_ro = pick.partner_id.partner_type == 'esc' and pick.state == 'updated'

            if pick.type in ['in', 'out']:
                if not context.get('yesorno', False):
                    for move in pick.move_lines:
                        if pick.type == 'out' and move.state not in ['done', 'cancel'] and \
                                move.product_id and move.product_id.state.code == 'forbidden':  # Check constraints on lines
                            check_vals = {'location_dest_id': move.location_dest_id.id, 'move': move}
                            self.pool.get('product.product')._get_restriction_error(cr, uid, [move.product_id.id],
                                                                                    check_vals, context=context)
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

                if pick.type == 'in':
                    domain = [('picking_id', '=', pick.id), ('draft', '=', True), ('already_processed', '=', False)]
                else:
                    domain = [('picking_id', '=', pick.id), ('draft', '=', True)]
                wiz_ids = wizard_obj.search(cr, uid, domain, context=context)
                if wiz_ids:
                    proc_id = wiz_ids[0]
                else:
                    write_data = {'picking_id': pick.id}
                    if fields_as_ro:
                        write_data['fields_as_ro'] = fields_as_ro
                    proc_id = wizard_obj.create(cr, uid, write_data)
                wizard_obj.create_lines(cr, uid, proc_id, context=context)

                res = {
                    'type': 'ir.actions.act_window',
                    'res_model': wizard_obj._name,
                    'res_id': proc_id,
                    'view_type': 'form',
                    'view_mode': 'form',
                    'target': 'new',
                }

                if not context.get('force_process', False) and pick.type == 'in' and not pick.in_dpo and pick.state != 'shipped' \
                        and pick.partner_id and pick.partner_id.partner_type in ('internal', 'section', 'intermission') \
                        and pick.company_id.partner_id.id != pick.partner_id.id \
                        and self.pool.get('stock.move').search_exists(cr, uid, [('picking_id', '=', pick.id), ('in_forced', '=', False)], context=context):
                    view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'msf_outgoing', 'stock_incoming_processor_internal_warning_form_view')[1]
                    res['view_id'] = [view_id]

                return res

        return super(stock_picking, self).action_process(cr, uid, ids, context=context)


stock_picking()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
