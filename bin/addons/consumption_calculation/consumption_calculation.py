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

from osv import osv
from osv import fields
from mx.DateTime import DateFrom, RelativeDate, RelativeDateTime, Age, strptime, now

from tools.translate import _

import time
import netsvc
import decimal_precision as dp

from order_types import ORDER_CATEGORY


def _get_asset_mandatory(product):
    return product.type == 'product' and product.subtype == 'asset'


class real_average_consumption(osv.osv):
    _name = 'real.average.consumption'
    _description = 'Real Average Consumption'

    def _get_nb_lines(self, cr, uid, ids, field_name, args, context=None):
        '''
        Returns the # of lines on the real average consumption
        '''
        res = {}

        for mrc in self.browse(cr, uid, ids, context=context):
            res[mrc.id] = len(mrc.line_ids)

        return res

    def _check_active_product(self, cr, uid, ids, context=None):
        '''
        Check if the real consumption report contains a line with an inactive product
        '''
        inactive_lines = self.pool.get('real.average.consumption.line').search(cr, uid, [
            ('product_id.active', '=', False),
            ('rac_id', 'in', ids),
            ('rac_id.created_ok', '=', True)
        ], context=context)

        if inactive_lines:
            plural = len(inactive_lines) == 1 and _('A product has') or _('Some products have')
            l_plural = len(inactive_lines) == 1 and _('line') or _('lines')
            p_plural = len(inactive_lines) == 1 and _('this inactive product') or _('those inactive products')
            raise osv.except_osv(_('Error'), _('%s been inactivated. If you want to validate this document you have to remove/correct the %s containing %s (see red %s of the document)') % (plural, l_plural, p_plural, l_plural))
        return True

    def unlink(self, cr, uid, ids, context=None):
        '''
        Display a message to the user if the report has been confirmed
        and stock moves has been generated
        '''
        for report in self.browse(cr, uid, ids, context=context):
            if report.state == 'done':
                raise osv.except_osv(_('Error'), _('This report is closed. You cannot delete it !'))
            if report.created_ok and report.picking_id:
                if report.picking_id.state != 'cancel':
                    raise osv.except_osv(_('Error'), _(u'You cannot delete this report because stock moves has been generated and validated from this report !'))
                else:
                    for move in report.picking_id.move_lines:
                        if move.state != 'cancel':
                            raise osv.except_osv(_('Error'), _(u'You cannot delete this report because stock moves has been generated and validated from this report !'))

        return super(real_average_consumption, self).unlink(cr, uid, ids, context=context)

    def copy(self, cr, uid, ids, default=None, context=None):
        '''
        Unvalidate all lines of the duplicate report
        '''
        # Change default values
        if default is None:
            default = {}
        if context is None:
            context = {}
        if not 'picking_id' in default:
            default['picking_id'] = False

        default['name'] = self.pool.get('ir.sequence').get(cr, uid, 'consumption.report')

        # Copy the report
        res = super(real_average_consumption, self).copy(cr, uid, ids, default, context=context)

        # Unvalidate all lines of the report
        for report in self.browse(cr, uid, [res], context=context):
            lines = []
            for line in report.line_ids:
                lines.append(line.id)
            if lines:
                self.pool.get('real.average.consumption.line').write(cr, uid, lines, {'move_id': False, 'kcl_id': False}, context=context)

        # update created_ok at this end to disable _check qty on line
        self.write(cr, uid, res, {'created_ok': False})
        self.button_update_stock(cr, uid, res)
        return res


    def get_bool_values(self, cr, uid, ids, fields, arg, context=None):
        res = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        for obj in self.browse(cr, uid, ids, context=context):
            res[obj.id] = False
            if any([item for item in obj.line_ids  if item.to_correct_ok]):
                res[obj.id] = True
        return res

    def _get_stock_location(self, cr, uid, ids, context=None):
        """
        Return the list of real consumption reports to update
        """
        return self.pool.get('real.average.consumption').search(cr, uid, [
            '|',
            ('cons_location_id', 'in', ids),
            ('activity_id', 'in', ids),
        ], context=context)

    def _get_act_name(self, cr, uid, ids, fields, arg, context=None):
        """
        Set the activity name when the activity_id is changed
        """
        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        res = {}
        for rac in self.browse(cr, uid, ids, context=context):
            res[rac.id] = {}
            res[rac.id]['activity_name'] = rac.activity_id and rac.activity_id.name or ''
            res[rac.id]['cons_location_name'] = rac.cons_location_id and rac.cons_location_id.name or ''

        return res

    _columns = {
        'name': fields.char(size=64, string='Reference'),
        'creation_date': fields.datetime(string='Creation date', required=1),
        'cons_location_id': fields.many2one('stock.location', string='Source Location', domain=[('usage', '=', 'internal')], required=True, select=1),
        'cons_location_name': fields.function(_get_act_name, method=True, type='char', string='Consumer location Name', readonly=True, size=128, multi='loc_name', store={
            'real.average.consumption': (lambda obj, cr, uid, ids, c={}: ids, ['cons_location_id'], 10),
            'stock.location': (_get_stock_location, ['name'], 20),
        },),
        'activity_id': fields.many2one('stock.location', string='Destination Location', domain=[('usage', '=', 'customer'), ('location_category', '=', 'consumption_unit')], required=1, select=1),
        'activity_name': fields.function(_get_act_name, method=True, type='char', string='Destination Location', readonly=True, size=128, multi='loc_name', store={
            'real.average.consumption': (lambda obj, cr, uid, ids, c={}: ids, ['activity_id'], 10),
            'stock.location': (_get_stock_location, ['name'], 20),
        },),
        'period_from': fields.date(string='Period from', required=True),
        'period_to': fields.date(string='Period to', required=True),
        'sublist_id': fields.many2one('product.list', string='List/Sublist', ondelete='set null'),
        'line_ids': fields.one2many('real.average.consumption.line', 'rac_id', string='Lines'),
        'picking_id': fields.many2one('stock.picking', string='Picking', readonly=True),
        'created_ok': fields.boolean(string='Out moves created'),
        'nb_lines': fields.function(_get_nb_lines, method=True, type='integer', string='# lines', readonly=True,),
        'nomen_manda_0': fields.many2one('product.nomenclature', 'Main Type', ondelete='set null'),
        'nomen_manda_1': fields.many2one('product.nomenclature', 'Group', ondelete='set null'),
        'nomen_manda_2': fields.many2one('product.nomenclature', 'Family', ondelete='set null'),
        'nomen_manda_3': fields.many2one('product.nomenclature', 'Root', ondelete='set null'),
        'hide_column_error_ok': fields.function(get_bool_values, method=True, readonly=True, type="boolean", string="Show column errors", store=False),
        'state': fields.selection([('draft', 'Draft'), ('done', 'Closed'),('cancel','Cancelled')], string="State", readonly=True),
        'categ': fields.selection(ORDER_CATEGORY, string='Category', required=True, states={'done':[('readonly',True)]}, add_empty=True),
        'details': fields.char(size=86, string='Details', states={'done':[('readonly',True)]}),
        'notes': fields.text('Notes', states={'done':[('readonly',True)]}),
    }

    _defaults = {
        'creation_date': lambda *a: time.strftime('%Y-%m-%d %H:%M:%S'),
        'period_to': lambda *a: time.strftime('%Y-%m-%d'),
        'nb_lines': lambda *a: 0,
        'state': lambda *a: 'draft',
        'categ': lambda *a: False,
    }

    _sql_constraints = [
        ('date_coherence', "check (period_from <= period_to)", '"Period from" must be less than or equal to "Period to"'),
    ]

    _constraints = [
        (_check_active_product, "You cannot confirm this real consumption report because it contains a line with an inactive product", ['line_ids', 'created_ok']),
    ]

    _order = 'id desc'

    def create(self, cr, uid, vals, context=None):
        '''
        Add name of the report at creation
        '''
        if not vals:
            vals = {}

        if not 'name' in vals:
            vals.update({'name': self.pool.get('ir.sequence').get(cr, uid, 'consumption.report')})

        if 'cons_location_id' in vals:
            if self.pool.get('stock.location').search(cr, uid, [('id', '=', vals['cons_location_id']), ('active', '=', False)], context=context):
                raise osv.except_osv(_('Warning'), _("Source Location is inactive"))

        if 'activity_id' in vals:
            if self.pool.get('stock.location').search(cr, uid, [('id', '=', vals['activity_id']), ('active', '=', False)], context=context):
                raise osv.except_osv(_('Warning'), _("Destination Location is inactive"))

        return super(real_average_consumption, self).create(cr, uid, vals, context=context)


    def onchange_categ(self, cr, uid, ids, category, context=None):
        """
        Check if the list of products is valid for this new category
        :param cr: Cursor to the database
        :param uid: ID of the res.users that calls the method
        :param ids: List of ID of Real consumption to check
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
            # Check if all product nomenclature of products in FO/IR lines are consistent with the category
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
                          FROM real_average_consumption_line l
                            LEFT JOIN product_product p ON l.product_id = p.id
                            LEFT JOIN product_template t ON p.product_tmpl_id = t.id
                            LEFT JOIN real_average_consumption rac ON l.rac_id = rac.id
                          WHERE (t.nomen_manda_0 != %s) AND rac.id in %s LIMIT 1''',
                       (nomen_id, tuple(ids)))
            res = cr.fetchall()

        if ids and category in ['service', 'transport']:
            # Avoid selection of non-service products on Service FO
            category = category == 'service' and 'service_recep' or 'transport'
            transport_cat = ''
            if category == 'transport':
                transport_cat = 'OR p.transport_ok = False'
            cr.execute('''SELECT l.id
                          FROM real_average_consumption_line l
                            LEFT JOIN product_product p ON l.product_id = p.id
                            LEFT JOIN product_template t ON p.product_tmpl_id = t.id
                            LEFT JOIN real_average_consumption rac ON l.rac_id = rac.id
                          WHERE (t.type != 'service_recep' %s) AND rac.id in %%s LIMIT 1''' % transport_cat,
                       (tuple(ids),))  # not_a_user_entry
            res = cr.fetchall()

        if res:
            message.update({
                'title': _('Warning'),
                'message': _('This order category is not consistent with product(s) on this order.'),
            })

        return {'warning': message}


    def change_cons_location_id(self, cr, uid, ids, context=None):
        '''
        Open the wizard to change the location
        '''
        wiz_id = self.pool.get('real.consumption.change.location').create(cr, uid, {'report_id': ids[0]}, context=context)
        return {'type': 'ir.actions.act_window',
                'res_model': 'real.consumption.change.location',
                'view_mode': 'form',
                'view_type': 'form',
                'res_id': wiz_id,
                'target': 'new'}

    def button_update_stock(self, cr, uid, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        to_update = []
        for line in self.read(cr, uid, ids, ['created_ok','line_ids']):
            if line['created_ok']:
                continue
            to_update += line['line_ids']

        if to_update:
            self.pool.get('real.average.consumption.line')._check_qty(cr, uid, to_update, {'noraise': True})
        return True

    def save_and_process(self, cr, uid, ids, context=None):
        '''
        Returns the wizard to confirm the process of all lines
        '''
        if context is None:
            context = {}
        self.check_lines_to_fix(cr, uid, ids, context)
        view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'consumption_calculation', 'real_average_consumption_confirmation_view')[1],

        return {'type': 'ir.actions.act_window',
                'res_model': 'real.average.consumption',
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'view_id': [view_id],
                'res_id': ids[0],
                }

    def draft_button(self, cr, uid, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        if context is None:
            context = {}

        for x in self.browse(cr, uid, ids, fields_to_fetch=['cons_location_id', 'activity_id'], context=context):
            if not x.cons_location_id.active:
                raise osv.except_osv(_('Warning'), _("Source Location %s is inactive") % (x.cons_location_id.name,))
            if not x.activity_id.active:
                raise osv.except_osv(_('Warning'), _("Destination Location %s is inactive") % (x.activity_id.name,))

        self.write(cr, uid, ids, {'state':'draft'}, context=context)

        return {'type': 'ir.actions.act_window',
                'res_model': 'real.average.consumption',
                'view_type': 'form',
                'view_mode': 'form,tree',
                'target': 'dummy',
                'res_id': ids[0],
                }

    def cancel_button(self, cr, uid, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        if context is None:
            context = {}

        for report in self.read(cr, uid, ids, ['name'], context=context):
            self.infolog(cr, uid, 'The consumption report id:%s (%s) has been canceled' % (
                report['id'], report['name'],
            ))

        self.write(cr, uid, ids, {'state':'cancel'}, context=context)

        return {'type': 'ir.actions.act_window',
                'res_model': 'real.average.consumption',
                'view_type': 'form',
                'view_mode': 'form,tree',
                'target': 'dummy',
                'res_id': ids[0],
                }


    def process_moves(self, cr, uid, ids, context=None):
        '''
        Creates all stock moves according to the report lines
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
        if context is None:
            context = {}

        move_obj = self.pool.get('stock.move')
        line_obj = self.pool.get('real.average.consumption.line')
        wf_service = netsvc.LocalService("workflow")

        reason_type_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_consumption_report')[1]

        move_ids = []

        # check and update lines
        for rac in self.browse(cr, uid, ids, context=context):
            if rac.state != 'draft':
                raise osv.except_osv(
                    _('Error'),
                    _('Only draft Consumption reports can be processed. Maybe this one has been already processed.'),
                )
            if DateFrom(rac.period_to) > now():
                raise osv.except_osv(_('Error'), _('"Period to" can\'t be in the future.'))

            if rac.created_ok:
                return {'type': 'ir.actions.close_window'}
            line_obj._check_qty(cr, uid, [x.id for x in rac.line_ids])

        partner_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.partner_id.id
        addresses = self.pool.get('res.partner').address_get(cr, uid, partner_id, ['delivery', 'default'])
        address_id = addresses.get('delivery') or addresses.get('default')

        for rac in self.browse(cr, uid, ids, context=context):
            date = '%s %s'%(rac.period_to, time.strftime('%H:%M:%S'))
            picking_id = self.pool.get('stock.picking').create(cr, uid, {'name': 'OUT-%s' % rac.name,
                                                                         'origin': rac.name,
                                                                         'partner_id': partner_id,
                                                                         'address_id': address_id,
                                                                         'type': 'out',
                                                                         'subtype': 'standard',
                                                                         'state': 'auto',
                                                                         'move_type': 'one',
                                                                         'invoice_state': 'none',
                                                                         'date': date,
                                                                         'rac_id': rac.id,
                                                                         'reason_type_id': reason_type_id}, context=context)

            self.write(cr, uid, [rac.id], {'created_ok': True}, context=context)
            for line in rac.line_ids:
                if line.consumed_qty != 0.00:
                    move_id = move_obj.create(cr, uid, {'name': '%s/%s' % (rac.name, line.product_id.name),
                                                        'picking_id': picking_id,
                                                        'product_uom': line.uom_id.id,
                                                        'product_id': line.product_id.id,
                                                        'date_expected': date,
                                                        'date': date,
                                                        'product_qty': line.consumed_qty,
                                                        'prodlot_id': line.prodlot_id.id,
                                                        'expiry_date': line.expiry_date,
                                                        'asset_id': line.asset_id.id,
                                                        'location_id': rac.cons_location_id.id,
                                                        'location_dest_id': rac.activity_id.id,
                                                        'state': 'done',
                                                        'reason_type_id': reason_type_id,
                                                        'composition_list_id': line.kcl_id and line.kcl_id.id})
                    move_ids.append(move_id)
                    line_obj.write(cr, uid, [line.id], {'move_id': move_id})
                    if line.product_subtype == 'kit' and line.kcl_id:
                        self.pool.get('composition.kit').close_kit(cr, uid, [line.kcl_id.id], self._name, context=context)

            self.write(cr, uid, [rac.id], {'picking_id': picking_id, 'state': 'done'}, context=context)

            # Confirm the picking
            wf_service.trg_validate(uid, 'stock.picking', picking_id, 'button_confirm', cr)

            # Confirm all moves
            move_obj.action_done(cr, uid, move_ids, context=context)
            #move_obj.write(cr, uid, move_ids, {'date': rac.period_to}, context=context)

        for report in self.read(cr, uid, ids, ['name'], context=context):
            self.infolog(cr, uid, 'The consumption report id:%s (%s) has been processed' % (
                report['id'], report['name'],
            ))

        return {'type': 'ir.actions.act_window',
                'res_model': 'real.average.consumption',
                'view_type': 'form',
                'view_mode': 'form,tree',
                'target': 'dummy',
                'res_id': ids[0],
                }

    def import_rac(self, cr, uid, ids, context=None):
        '''
        Launches the wizard to import lines from a file
        '''
        if context is None:
            context = {}
        context.update({'active_id': ids[0]})

        return {'type': 'ir.actions.act_window',
                'res_model': 'wizard.import.rac',
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'context': context,
                }

    def export_rac(self, cr, uid, ids, context=None):
        '''
        Creates an XML file and launches the wizard to save it
        '''
        rac = self.browse(cr, uid, ids[0], fields_to_fetch=['cons_location_id'], context=context)

        return {
            'type': 'ir.actions.report.xml',
            'report_name': 'real.consumption.xls',
            'datas': {'ids': [ids[0]], 'target_filename': 'rac_%s' % rac.cons_location_id.name.replace(' ', '_')},
            'nodestroy': True,
            'context': context,
        }

    def copy_all(self, cr, uid, ids, context=None):
        '''
        Fill all lines according to defined location with pre-filled lines
        '''
        if context is None:
            context = {}

        self.write(cr, uid, ids, {'created_ok': True})
        for report in self.browse(cr, uid, ids, context=context):
            cr.execute('''select distinct sm.product_id, sm.prodlot_id, sm.expired_date,
                            pp.batch_management, pp.perishable, pp.product_tmpl_id,
                            pt.uom_id
                        from stock_move sm, product_product pp, product_template pt
                        where (sm.location_id = %s or sm.location_dest_id = %s) and pp.id = sm.product_id and pt.id = pp.product_tmpl_id and sm.state = 'done'
                        ''', (report.cons_location_id.id, report.cons_location_id.id ))
            products_by_location = cr.dictfetchall()

            context['location_id'] = report.cons_location_id.id
            for product in products_by_location:
                rm_line_ids = self.pool.get('real.average.consumption.line').search(cr, uid, [
                    ('product_id', '=', product['product_id']),
                    ('prodlot_id', '=', product['prodlot_id']),
                    ('uom_id', '=', product['uom_id']),
                    ('rac_id', '=', report.id),
                ], context=context)
                batch_mandatory = product['batch_management']
                date_mandatory = product['perishable']
                values = {
                    'product_id': product['product_id'],
                    'uom_id': product['uom_id'],
                    'batch_mandatory': batch_mandatory,
                    'date_mandatory': date_mandatory,
                    'expiry_date': product['expired_date'],
                    'prodlot_id': product['prodlot_id'],
                    'rac_id': report.id,
                    'consumed_qty': 0.00,
                }

                v = self.pool.get('real.average.consumption.line').product_onchange(cr, uid, [], product['product_id'], report.cons_location_id.id,
                                                                                    product['uom_id'], product['prodlot_id'], context=context)['value']

                values.update(v)
                if batch_mandatory and not product['prodlot_id']:
                    values.update({'remark': 'You must assign a batch number'})
                elif date_mandatory and not product['expired_date']:
                    values.update({'remark': 'You must assign an expiry date'})
                else:
                    values.update({'remark': ''})
                if product['prodlot_id']:
                    product_qty = self.pool.get('stock.production.lot')._get_stock(cr, uid, product['prodlot_id'], [], None, context=context)
                    values.update({'product_qty':product_qty[product['prodlot_id']]})
                if rm_line_ids:
                    self.pool.get('real.average.consumption.line').write(cr, uid, rm_line_ids, values, context=context)
                elif values.get('product_qty', 0.00) > 0.00:
                    self.pool.get('real.average.consumption.line').create(cr, uid, values, context=context)

        self.write(cr, uid, ids, {'created_ok': False})
        return {'type': 'ir.actions.act_window',
                'res_model': 'real.average.consumption',
                'view_type': 'form',
                'view_mode': 'form,tree',
                'res_id': ids[0],
                'target': 'dummy',
                'context': context}

    def fill_lines(self, cr, uid, ids, context=None):
        '''
        Fill all lines according to defined nomenclature level and sublist
        '''
        if context is None:
            context = {}
        self.write(cr, uid, ids, {'created_ok': True})
        for report in self.browse(cr, uid, ids, context=context):
            product_ids = []
            products = []

            nom = False
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
                    self.pool.get('real.average.consumption.line').unlink(cr, uid, line.id, context=context)

            for product in self.pool.get('product.product').browse(cr, uid, product_ids, context=context):
                # Check if the product is not already on the report
                if product.id not in products:
                    batch_mandatory = product.batch_management
                    date_mandatory = product.perishable
                    asset_mandatory = _get_asset_mandatory(product)
                    values = {'product_id': product.id,
                              'uom_id': product.uom_id.id,
                              'consumed_qty': 0.00,
                              'batch_mandatory': batch_mandatory,
                              'date_mandatory': date_mandatory,
                              'asset_mandatory': asset_mandatory,
                              'rac_id': report.id,}
                    v = self.pool.get('real.average.consumption.line').product_onchange(cr, uid, [], product.id, report.cons_location_id.id,
                                                                                        product.uom_id.id, False, context=context)['value']
                    values.update(v)
                    if batch_mandatory:
                        values.update({'remark': _('You must assign a batch number')})
                    if date_mandatory:
                        values.update({'remark': _('You must assign an expiry date')})
                    if asset_mandatory:
                        values.update({'remark': _('You must assign an asset')})
                    self.pool.get('real.average.consumption.line').create(cr, uid, values)

        self.write(cr, uid, ids, {'created_ok': False})
        return {'type': 'ir.actions.act_window',
                'res_model': 'real.average.consumption',
                'view_type': 'form',
                'view_mode': 'form',
                'res_id': ids[0],
                'target': 'dummy',
                'context': context}

    def get_nomen(self, cr, uid, id, field):
        return self.pool.get('product.nomenclature').get_nomen(cr, uid, self, id, field, context={'withnum': 1})

    def onChangeSearchNomenclature(self, cr, uid, id, position, type, nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, num=True, context=None):
        return self.pool.get('product.product').onChangeSearchNomenclature(cr, uid, 0, position, type, nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, False, context={'withnum': 1})

    def write(self, cr, uid, ids, vals, context=None):
        if not ids:
            return True
        if vals.get('sublist_id',False):
            vals.update({'nomen_manda_0':False,'nomen_manda_1':False,'nomen_manda_2':False,'nomen_manda_3':False})
        if vals.get('nomen_manda_0',False):
            vals.update({'sublist_id':False})
        ret = super(real_average_consumption, self).write(cr, uid, ids, vals, context=context)
        return ret

    def button_remove_lines(self, cr, uid, ids, context=None):
        '''
        Remove lines
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        vals = {}
        vals['line_ids'] = []
        for line in self.browse(cr, uid, ids, context=context):
            line_browse_list = line.line_ids
            for var in line_browse_list:
                vals['line_ids'].append((2, var.id))
            self.write(cr, uid, ids, vals, context=context)
        return True

    def check_lines_to_fix(self, cr, uid, ids, context=None):
        """
        Check the lines that need to be corrected
        """
        if isinstance(ids, (int, long)):
            ids = [ids]

        for var in self.browse(cr, uid, ids, context=context):
            # we check the lines that need to be fixed
            if var.line_ids:
                for var in var.line_ids:
                    if var.consumed_qty and var.to_correct_ok:
                        raise osv.except_osv(_('Warning !'), _('Some lines need to be fixed before.'))
                    else:
                        self.pool.get('real.average.consumption.line').write(cr, uid, var.id, {},context)
        return True

real_average_consumption()


class real_average_consumption_line(osv.osv):
    _name = 'real.average.consumption.line'
    _description = 'Real average consumption line'
    _rec_name = 'product_id'
    _order = 'ref, id'

    def _get_checks_all(self, cr, uid, ids, name, arg, context=None):
        result = {}
        for id in ids:
            result[id] = {'batch_number_check': False, 'expiry_date_check': False, 'type_check': False, 'to_correct_ok': False}

        for out in self.browse(cr, uid, ids, context=context):
            if out.product_id:
                result[out.id]['batch_number_check'] = out.product_id.batch_management
                result[out.id]['expiry_date_check'] = out.product_id.perishable
                result[out.id]['asset_check'] = _get_asset_mandatory(out.product_id)
            # the lines with to_correct_ok=True will be red
            if out.text_error:
                result[out.id]['to_correct_ok'] = True
            result[out.id]['uom_rounding_is_pce'] = out.uom_id and out.uom_id.rounding == 1 or False
        return result

    def _get_qty(self, cr, uid, product, lot, location, uom):
        if not product and not lot:
            return False
        context = {'location_id': location, 'location': location, 'uom': uom, 'compute_child': False}
        if not lot:
            return self.pool.get('product.product').read(cr, uid, product, ['qty_available'], context=context)['qty_available']

        return self.pool.get('stock.production.lot').read(cr, uid, lot, ['stock_available'], context=context)['stock_available']

    def _check_qty(self, cr, uid, ids, context=None):

        if context is None:
            context = {}
        noraise = context.get('noraise')
        context.update({'error_message': ''})
        if isinstance(ids, (int, long)):
            ids = [ids]
        error_message = []
        for obj in self.browse(cr, uid, ids):
            if obj.rac_id.created_ok:
                continue

            # Prevent negative consumption qty.
            if obj.consumed_qty < 0.00:
                if not noraise:
                    raise osv.except_osv(_('Error'), _('The consumed qty. must be positive or 0.00'))
                elif context.get('import_in_progress'):
                    error_message.append(_('The consumed qty. must be positive or 0.00'))
                    context.update({'error_message': error_message})
            if obj.consumed_qty > 1 and obj.kcl_id:
                if not noraise:
                    raise osv.except_osv(_('Error'), _('If the Kit Reference is filled, the consumed qty can not be greater than 1'))
                elif context.get('import_in_progress'):
                    error_message.append(_('If the Kit Reference is filled, the consumed qty can not be greater than 1'))
                    context.update({'error_message': error_message})

            location = obj.rac_id.cons_location_id.id
            prodlot_id = None
            expiry_date = None
            asset_id = None

            batch_mandatory = obj.product_id.batch_management
            date_mandatory = obj.product_id.perishable
            asset_mandatory = _get_asset_mandatory(obj.product_id)

            if batch_mandatory:
                if not obj.prodlot_id:
                    if not noraise:
                        raise osv.except_osv(_('Error'),
                                             _("Product: %s, You must assign a Batch Number to process it.")%(obj.product_id.name,))
                    elif context.get('import_in_progress'):
                        error_message.append(_("You must assign a Batch Number to process it."))
                        context.update({'error_message': error_message})
                elif obj.prodlot_id:
                    prodlot_id = obj.prodlot_id.id
                    expiry_date = obj.prodlot_id.life_date

            if date_mandatory and not batch_mandatory:
                prod_ids = self.pool.get('stock.production.lot').search(cr, uid, [('life_date', '=', obj.expiry_date),
                                                                                  ('type', '=', 'internal'),
                                                                                  ('product_id', '=', obj.product_id.id)], context=context)
                expiry_date = obj.expiry_date or None  # None because else it is False and a date can't have a boolean value
                if not prod_ids:
                    if not noraise:
                        raise osv.except_osv(_('Error'),
                                             _("Product: %s, no internal batch found for expiry (%s)")%(obj.product_id.name, obj.expiry_date or _('No expiry date set')))
                    elif context.get('import_in_progress'):
                        error_message.append(_("Line %s of the imported file: no internal batch number found for ED %s (please correct the data)"
                                               ) % (context.get('line_num', False), expiry_date and strptime(expiry_date, '%Y-%m-%d').strftime('%d-%m-%Y')))
                        context.update({'error_message': error_message})
                else:
                    prodlot_id = prod_ids[0]

            if asset_mandatory:
                if not obj.asset_id:
                    if not noraise:
                        raise osv.except_osv(_('Error'),
                                             _("Product: %s, You must assign an Asset to process it.")%(obj.product_id.name,))
                    elif context.get('import_in_progress'):
                        error_message.append(_("You must assign an Asset to process it."))
                        context.update({'error_message': error_message})
                elif obj.asset_id:
                    asset_id = obj.asset_id.id

            product_qty = self._get_qty(cr, uid, obj.product_id.id, prodlot_id, location, obj.uom_id and obj.uom_id.id)

            if prodlot_id and obj.consumed_qty > product_qty:
                if not noraise:
                    raise osv.except_osv(_('Error'),
                                         _("Product: %s, Qty Consumed (%s) can't be greater than the Indicative Stock (%s)")%(obj.product_id.name, obj.consumed_qty, product_qty))
                elif context.get('import_in_progress'):
                    error_message.append(_("Line %s of the imported file: Qty Consumed (%s) can't be greater than the Indicative Stock (%s)") % (context.get('line_num', False), obj.consumed_qty, product_qty))
                    context.update({'error_message': error_message})
            #recursion: can't use write
            cr.execute('UPDATE '+self._table+' SET product_qty=%s, batch_mandatory=%s, date_mandatory=%s, asset_mandatory=%s, prodlot_id=%s, expiry_date=%s, asset_id=%s  where id=%s', (product_qty, batch_mandatory, date_mandatory, asset_mandatory, prodlot_id, expiry_date, asset_id, obj.id))  # not_a_user_entry

        self._unique_product(cr, uid, ids, context=context)

        return True

    def _get_product(self, cr, uid, ids, context=None):
        return self.pool.get('real.average.consumption.line').search(cr, uid, [('product_id', 'in', ids)], context=context)

    def _get_inactive_product(self, cr, uid, ids, field_name, args, context=None):
        '''
        Fill the error message if the product of the line is inactive
        '''
        res = {}
        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = {'inactive_product': False,
                            'inactive_error': ''}
            if line.product_id and not line.product_id.active:
                res[line.id] = {
                    'inactive_product': True,
                    'inactive_error': _('The product in line is inactive !')
                }

        return res

    _columns = {
        'product_id': fields.many2one('product.product', string='Product', required=True, select=1),
        'ref': fields.related('product_id', 'default_code', type='char', size=64, readonly=True,
                              store={'product.product': (_get_product, ['default_code'], 10),
                                     'real.average.consumption.line': (lambda self, cr, uid, ids, c=None: ids, ['product_id'], 20)}),
        'uom_id': fields.many2one('product.uom', string='UoM', required=True),
        'uom_rounding': fields.function(_get_checks_all, method=True, type='boolean', string="UoM Rounding is PCE", store=False, readonly=True, multi="m"),
        'product_qty': fields.float(digits=(16,2), string='Indicative stock', readonly=True, related_uom='uom_id'),
        'consumed_qty': fields.float(digits=(16,2), string='Qty consumed', required=True, related_uom='uom_id'),
        'batch_number_check': fields.function(_get_checks_all, method=True, string='Batch Number Check', type='boolean', readonly=True, multi="m"),
        'expiry_date_check': fields.function(_get_checks_all, method=True, string='Expiry Date Check', type='boolean', readonly=True, multi="m"),
        'asset_check': fields.function(_get_checks_all, method=True, string='Asset Check', type='boolean', readonly=True, multi="m"),
        'prodlot_id': fields.many2one('stock.production.lot', string='Batch number'),
        'batch_mandatory': fields.boolean(string='BM'),
        'expiry_date': fields.date(string='Expiry date'),
        'date_mandatory': fields.boolean(string='DM'),
        'asset_id': fields.integer(string='Asset'),
        'asset_mandatory': fields.boolean('AM'),
        'remark': fields.char(size=256, string='Comment'),
        'move_id': fields.many2one('stock.move', string='Move'),
        'rac_id': fields.many2one('real.average.consumption', string='RAC', ondelete='cascade', select=1),
        'rac_state': fields.related('rac_id', 'state', type='char', size=64, string='Real Consumption State', readonly=True),
        'text_error': fields.text('Errors', readonly=True),
        'to_correct_ok': fields.function(_get_checks_all, method=True, type="boolean", string="To correct", store=False, readonly=True, multi="m"),
        'just_info_ok': fields.boolean(string='Just for info'),
        'inactive_product': fields.function(_get_inactive_product, method=True, type='boolean', string='Product is inactive', store=False, multi='inactive'),
        'inactive_error': fields.function(_get_inactive_product, method=True, type='char', string='System message', store=False, multi='inactive'),
        'kcl_id': fields.many2one('composition.kit', 'Kit', domain="[('composition_product_id', '=', product_id), ('composition_type', '=', 'real'), ('state', '=', 'completed'), ('kcl_used_by', '=', False)]"),
        'product_subtype': fields.related('product_id', 'subtype', type='selection', string='Product Subtype', selection=[('single', 'Single Item'), ('kit', 'Kit/Module'), ('asset', 'Asset')], store=False, write_relate=False, readonly=True),
    }

    _defaults = {
        'inactive_product': False,
        'inactive_error': lambda *a: '',
    }

    def _unique_product(self, cr, uid, ids, context=None):
        if not ids:
            return True
        cr.execute('''
            select product.default_code, bn.name, bn.id, bn.life_date, rac.id, rac.name
                from real_average_consumption rac
                left join real_average_consumption_line line on line.rac_id = rac.id
                left join product_product product on product.id = line.product_id
                left join stock_production_lot bn on bn.id = line.prodlot_id
            where
                rac.state = 'draft' and
                (rac.id, line.product_id, coalesce(line.prodlot_id,0)) in (select rac_id, product_id, coalesce(prodlot_id, 0) from real_average_consumption_line where id in %s)
            group by
                product.default_code, bn.name, bn.id, rac.id, rac.name
            having count(*) > 1
        ''', (tuple(ids), ))
        error = []
        for x in cr.fetchall():
            error.append('%s: %s %s' % (x[5], x[0], x[1] or ''))
            if len(error) > 5:
                error.append('...')
                break
        if error:
            raise osv.except_osv(_('Error'), _('Each product or couple product plus batch number has to be unique:\n%s')
                                 % "\n".join(error))

        return True

    def create(self, cr, uid, vals=None, context=None):
        '''
        Call the constraint
        '''
        if context is None:
            context = {}
        res = super(real_average_consumption_line, self).create(cr, uid, vals, context=context)
        check = self._check_qty(cr, uid, res, context)
        if not check:
            raise osv.except_osv(_('Error'), _('The Qty Consumed cant\'t be greater than the Indicative Stock'))
        if vals.get('uom_id') and vals.get('product_id'):
            product_id = vals.get('product_id')
            product_uom = vals.get('uom_id')
            if not self.pool.get('uom.tools').check_uom(cr, uid, product_id, product_uom, context):
                raise osv.except_osv(_('Warning !'), _("You have to select a product UOM in the same category than the purchase UOM of the product"))
        return res

    def write(self, cr, uid, ids, vals, context=None):
        if not ids:
            return True
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not context.get('import_in_progress') and not context.get('button'):
            obj_data = self.pool.get('ir.model.data')
            tbd_uom = obj_data.get_object_reference(cr, uid, 'msf_doc_import', 'uom_tbd')[1]
            tbd_product = obj_data.get_object_reference(cr, uid, 'msf_doc_import', 'product_tbd')[1]
            message = ''
            if vals.get('uom_id'):
                if vals.get('uom_id') == tbd_uom:
                    message += _('You have to define a valid UOM, i.e. not "To be define".')
            if vals.get('product_id'):
                if vals.get('product_id') == tbd_product:
                    message += _('You have to define a valid product, i.e. not "To be define".')
            if vals.get('uom_id') and vals.get('product_id'):
                product_id = vals.get('product_id')
                product_uom = vals.get('uom_id')
                if not self.pool.get('uom.tools').check_uom(cr, uid, product_id, product_uom, context):
                    message += _("You have to select a product UOM in the same category than the purchase UOM of the product")
            if message:
                raise osv.except_osv(_('Warning !'), message)
            else:
                vals['text_error'] = False
        res = super(real_average_consumption_line, self).write(cr, uid, ids, vals, context=context)
        check = self._check_qty(cr, uid, ids, context)
        if not check:
            raise osv.except_osv(_('Error'), _('The Qty Consumed cant\'t be greater than the Indicative Stock'))
        return res

    def change_expiry(self, cr, uid, id, expiry_date, product_id, location_id, uom, remark=False, context=None):
        '''
        expiry date changes, find the corresponding internal prod lot
        '''
        if context is None:
            context = {}
        prodlot_obj = self.pool.get('stock.production.lot')
        result = {'value':{}}
        context.update({'location': location_id})

        if expiry_date and product_id:
            prod_ids = prodlot_obj.search(cr, uid, [('life_date', '=', expiry_date),
                                                    ('type', '=', 'internal'),
                                                    ('product_id', '=', product_id)], context=context)
            if not prod_ids:
                # display warning
                result['warning'] = {'title': _('Error'),
                                     'message': _('The selected Expiry Date does not exist in the system.')}
                # clear date
                result['value'].update(expiry_date=False, prodlot_id=False)
            else:
                # return first prodlot
                result = self.change_prodlot(cr, uid, id, product_id, prod_ids[0], expiry_date, location_id, uom, context={})
                result.setdefault('value',{}).update(prodlot_id=prod_ids[0])
                if remark and remark in ('You must assign a batch number', 'You must assign an expiry date') :
                    result['value']['remark'] = ''
                return result

        else:
            # clear expiry date, we clear production lot
            result['value'].update(prodlot_id=False)

        context.update(uom=uom)
        context.update({'compute_child': False})
        product = self.pool.get('product.product').browse(cr, uid, product_id, context=context)
        result['value'].update({'product_qty': product.qty_available})

        return result

    def change_asset(self, cr, uid, id, asset, product_id, location_id, uom, remark=False, context=None):
        '''
        Asset change, remove the remark
        '''
        if context is None:
            context = {}

        result = {'value':{}}
        if remark and remark == 'You must assign an asset':
            result.setdefault('value', {}).update(remark='')

        return result


    def change_qty(self, cr, uid, ids, qty, product_id, prodlot_id, location, uom, context=None):
        if context is None:
            context = {}

        res = {'value': {}}

        stock_qty = self._get_qty(cr, uid, product_id, prodlot_id, location, uom)
        warn_msg = {'title': _('Error'), 'message': _("The Qty Consumed is greater than the Indicative Stock")}

        if qty:
            res = self.pool.get('product.uom')._change_round_up_qty(cr, uid, uom, qty, 'consumed_qty', result=res)

        if prodlot_id and qty > stock_qty:
            res.setdefault('warning', {}).update(warn_msg)
            res.setdefault('value', {}).update({'consumed_qty': 0})
        if qty > stock_qty:
            res.setdefault('warning', {}).update(warn_msg)

        return res

    def change_prodlot(self, cr, uid, ids, product_id, prodlot_id, expiry_date, location_id, uom, remark=False, context=None):
        '''
        Set the expiry date according to the prodlot
        '''
        if context is None:
            context = {}
        res = {'value': {}}
        context.update({'location': location_id, 'uom': uom})
        if prodlot_id and not expiry_date:
            if remark and remark in ('You must assign a batch number', 'You must assign an expiry date') :
                res['value']['remark'] = ''
            res['value'].update({'expiry_date': self.pool.get('stock.production.lot').browse(cr, uid, prodlot_id, context=context).life_date})
        elif not prodlot_id and expiry_date:
            res['value'].update({'expiry_date': False})

        if not prodlot_id:
            context.update({'compute_child': False})
            product_qty = self.pool.get('product.product').browse(cr, uid, product_id, context=context).qty_available
        else:
            if remark and remark in ('You must assign a batch number', 'You must assign an expiry date') :
                res['value']['remark'] = ''
            context.update({'location_id': location_id})
            product_qty = self.pool.get('stock.production.lot').browse(cr, uid, prodlot_id, context=context).stock_available
        res['value'].update({'product_qty': product_qty})

        return res

    def uom_onchange(self, cr, uid, ids, product_id, product_qty, location_id=False, uom=False, lot=False, context=None):
        if context is None:
            context = {}
        qty_available = 0
        d = {}
        if uom and product_id:
            qty_available = self._get_qty(cr, uid, product_id, lot, location_id, uom)

        if not uom and product_id:
            product = self.pool.get('product.product').browse(cr, uid, product_id, context=context)
            d['uom_id'] = [('category_id', '=', product.uom_id.category_id.id)]

        res = {'value': {'product_qty': qty_available, 'kcl_id': False}, 'domain': d}

        if not uom or self.pool.get('product.uom').browse(cr, uid, uom, fields_to_fetch=['rounding']).rounding != 1:
            res['value'].update({'item_uom_rounding_is_pce': False, 'kcl_id': False})

        if product_qty:
            res = self.pool.get('product.uom')._change_round_up_qty(cr, uid, uom, product_qty, 'consumed_qty', result=res)

        return res

    def product_onchange(self, cr, uid, ids, product_id, location_id=False, uom=False, lot=False, categ=False, context=None):
        '''
        Set the product uom when the product change
        '''
        if context is None:
            context = {}
        product_obj = self.pool.get('product.product')
        v = {'batch_mandatory': False, 'date_mandatory': False, 'asset_mandatory': False, 'kcl_id': False}
        d = {'uom_id': []}
        warning = False
        if product_id:
            # Test the compatibility of the product with a consumption report
            res, test = product_obj._on_change_restriction_error(cr, uid, product_id, field_name='product_id', values={'value': v}, vals={'constraints': 'consumption'}, context=context)
            if test:
                return res
            if location_id:
                context.update({'location': location_id, 'uom': uom})

            context.update({'compute_child': False})
            product = self.pool.get('product.product').browse(cr, uid, product_id, context=context)
            qty_available = product.qty_available

            if product.batch_management:
                v.update({'batch_mandatory': True, 'remark': _('You must assign a batch')})
            if product.perishable:
                v.update({'date_mandatory': True, 'remark': _('You must assign an expiry date')})
            if product.type == 'product' and product.subtype == 'asset':
                v.update({'asset_mandatory': True, 'remark': _('You must assign an asset')})

            uom = product.uom_id.id
            v.update({'uom_id': uom})
            d['uom_id'] = [('category_id', '=', product.uom_id.category_id.id)]
            if location_id:
                v.update({'product_qty': qty_available})

            # Check consistency of product according to the selected order category:
            if categ:
                consistency_message = product_obj.check_consistency(cr, uid, product_id, categ, context=context)
                if consistency_message:
                    warning = {
                        'title': _('Warning'),
                        'message': '%s \n %s' % (res.get('warning', {}).get('message', ''), consistency_message)
                    }
        else:
            v.update({'uom_id': False, 'product_qty': 0.00, 'prodlot_id': False, 'expiry_date': False, 'consumed_qty': 0.00})

        return {'value': v, 'domain': d, 'warning': warning}

    def copy(self, cr, uid, line_id, default=None, context=None):
        if not context:
            context = {}

        if not default:
            default = {}

        default.update({'prodlot_id': False, 'expiry_date': False, 'asset_id': False, 'kcl_id': False})

        if 'consumed_qty' in default and default['consumed_qty'] < 0.00:
            default['consumed_qty'] = 0.00

        return super(real_average_consumption_line, self).copy(cr, uid, line_id[0], default=default, context={'noraise': True})


real_average_consumption_line()


class real_consumption_change_location(osv.osv_memory):
    _name = 'real.consumption.change.location'

    _columns = {
        'report_id': fields.many2one('real.average.consumption', string='Report'),
        'location_id': fields.many2one('stock.location', string='Source Location', required=True),
    }

    def change_location(self, cr, uid, ids, context=None):
        '''
        Change location of the report and reload the report
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]

        wiz = self.browse(cr, uid, ids[0], context=context)

        self.infolog(cr, uid, 'Consumer location has been changed on consumption report id:%s (%s) from id:%s (%s) to id:%s (%s)' % (
            wiz.report_id.id, wiz.report_id.name,
            wiz.report_id.cons_location_id.id, wiz.report_id.cons_location_id.name,
            wiz.location_id.id, wiz.location_id.name))

        self.pool.get('real.average.consumption').write(cr, uid, [wiz.report_id.id], {'cons_location_id': wiz.location_id.id}, context=context)
        self.pool.get('real.average.consumption').button_update_stock(cr, uid, [wiz.report_id.id], context=context)

        return {'type': 'ir.actions.act_window',
                'res_model': 'real.average.consumption',
                'view_type': 'form',
                'view_mode': 'form,tree',
                'res_id': wiz.report_id.id,
                'target': 'dummy'}

real_consumption_change_location()


class monthly_review_consumption(osv.osv):
    _name = 'monthly.review.consumption'
    _description = 'Monthly review consumption'
    _rec_name = 'creation_date'
    _order = 'id desc'

    def _get_nb_lines(self, cr, uid, ids, field_name, args, context=None):
        '''
        Returns the # of lines on the monthly review consumption
        '''
        res = {}

        for mrc in self.browse(cr, uid, ids, context=context):
            res[mrc.id] = len(mrc.line_ids)

        return res

    def get_bool_values(self, cr, uid, ids, fields, arg, context=None):
        res = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        for obj in self.browse(cr, uid, ids, context=context):
            res[obj.id] = False
            if any([item for item in obj.line_ids  if item.to_correct_ok]):
                res[obj.id] = True
        return res

    _columns = {
        'creation_date': fields.date(string='Creation date'),
        'cons_location_id': fields.char(size=256, string='Location', readonly=True),
        'company_id': fields.many2one('res.company', string='Company', readonly=True),
        'period_from': fields.date(string='Period from', required=True),
        'period_to': fields.date(string='Period to', required=True),
        'sublist_id': fields.many2one('product.list', string='List/Sublist', ondelete='set null'),
        'nomen_id': fields.many2one('product.nomenclature', string='Products\' nomenclature level'),
        'line_ids': fields.one2many('monthly.review.consumption.line', 'mrc_id', string='Lines'),
        'nb_lines': fields.function(_get_nb_lines, method=True, type='integer', string='# lines', readonly=True,),
        'nomen_manda_0': fields.many2one('product.nomenclature', 'Main Type', ondelete='set null'),
        'nomen_manda_1': fields.many2one('product.nomenclature', 'Group', ondelete='set null'),
        'nomen_manda_2': fields.many2one('product.nomenclature', 'Family', ondelete='set null'),
        'nomen_manda_3': fields.many2one('product.nomenclature', 'Root', ondelete='set null'),
        'hide_column_error_ok': fields.function(get_bool_values, method=True, readonly=True, type="boolean", string="Show column errors", store=False),
    }

    _defaults = {
        'period_to': lambda *a: (DateFrom(time.strftime('%Y-%m-%d')) + RelativeDateTime(months=1, day=1, days=-1)).strftime('%Y-%m-%d'),
        'creation_date': lambda *a: time.strftime('%Y-%m-%d'),
        'cons_location_id': lambda *a: 'MSF Instance',
        'company_id': lambda self, cr, uid, ids, c={}: self.pool.get('res.users').browse(cr, uid, uid).company_id.id,
    }

    def period_change(self, cr, uid, ids, period_from, period_to, context=None):
        '''
        Get the first day of month and the last day
        '''
        res = {}

        if period_from:
            res.update({'period_from': (DateFrom(period_from) + RelativeDateTime(day=1)).strftime('%Y-%m-%d')})
        if period_to:
            res.update({'period_to': (DateFrom(period_to) + RelativeDateTime(months=1, day=1, days=-1)).strftime('%Y-%m-%d')})

        return {'value': res}

    def import_fmc(self, cr, uid, ids, context=None):
        '''
        Launches the wizard to import lines from a file
        '''
        if context is None:
            context = {}
        context.update({'active_id': ids[0]})

        return {'type': 'ir.actions.act_window',
                'res_model': 'wizard.import.fmc',
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'context': context,
                }

    def export_fmc(self, cr, uid, ids, context=None):
        """
        Return an xml file to open with Excel
        """
        datas = {'ids': ids}

        return {'type': 'ir.actions.report.xml',
                'report_name': 'monthly.consumption.xls',
                'datas': datas}

    def fill_lines(self, cr, uid, ids, context=None):
        '''
        Fill all lines according to defined nomenclature level and sublist
        '''
        if context is None:
            context = {}
        line_obj = self.pool.get('monthly.review.consumption.line')
        for report in self.browse(cr, uid, ids, context=context):
            product_ids = []
            products = []
            # Get all products for the defined nomenclature
            nom = False
            field = False
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
                if line.name.id in product_ids:
                    products.append(line.name.id)
                else:
                    self.pool.get('monthly.review.consumption.line').unlink(cr, uid, line.id, context=context)

            amc_context = context.copy()
            amc_context.update({'from_date': report.period_from, 'to_date': report.period_to})
            if amc_context.get('from_date', False):
                from_date = (DateFrom(amc_context.get('from_date')) + RelativeDateTime(day=1)).strftime('%Y-%m-%d')
                amc_context.update({'from_date': from_date})

            if amc_context.get('to_date', False):
                to_date = (DateFrom(amc_context.get('to_date')) + RelativeDateTime(months=1, day=1, days=-1)).strftime('%Y-%m-%d')
                amc_context.update({'to_date': to_date})


            prod_amc = self.pool.get('product.product').compute_amc(cr, uid, product_ids, context=amc_context)
            for product in self.pool.get('product.product').browse(cr, uid, product_ids, context=context):
                # Check if the product is not already on the report
                if product.id not in products:
                    products.append(product.id)
                    last_fmc_reviewed = False
                    line_ids = line_obj.search(cr, uid, [('name', '=', product.id), ('valid_ok', '=', True)], order='valid_until desc, id desc', context=context)
                    if line_ids:
                        for line in line_obj.browse(cr, uid, [line_ids[0]], context=context):
                            last_fmc_reviewed = line.mrc_id.creation_date
                    self.pool.get('monthly.review.consumption.line').create(cr, uid, {'name': product.id,
                                                                                      'amc': prod_amc.get(product.id),
                                                                                      'fmc': prod_amc.get(product.id),
                                                                                      'fmc2': prod_amc.get(product.id),
                                                                                      'last_reviewed': last_fmc_reviewed,
                                                                                      'last_reviewed2': last_fmc_reviewed,
                                                                                      'mrc_id': report.id})

        return {'type': 'ir.actions.act_window',
                'res_model': 'monthly.review.consumption',
                'view_type': 'form',
                'view_mode': 'form',
                'res_id': ids[0],
                'target': 'dummy',
                'context': context}


    def valid_multiple_lines(self, cr, uid, ids, context=None):
        '''
        Validate multiple lines
        '''
        if context is None:
            context = {}
        self.check_lines_to_fix(cr, uid, ids, context)
        for report in self.browse(cr, uid, ids, context=context):
            for line in report.line_ids:
                if not line.valid_ok:
                    self.pool.get('monthly.review.consumption.line').valid_line(cr, uid, line.id, context=context)

        return {'type': 'ir.actions.act_window',
                'res_model': 'monthly.review.consumption',
                'view_type': 'form',
                'view_mode': 'form',
                'res_id': ids[0],
                'target': 'dummy',
                'context': context}

    def write(self, cr, uid, ids, vals, context=None):
        if not ids:
            return True
        if vals.get('sublist_id',False):
            vals.update({'nomen_manda_0':False,'nomen_manda_1':False,'nomen_manda_2':False,'nomen_manda_3':False})
        if vals.get('nomen_manda_0',False):
            vals.update({'sublist_id':False})
        ret = super(monthly_review_consumption, self).write(cr, uid, ids, vals, context=context)
        return ret

    def onChangeSearchNomenclature(self, cr, uid, id, position, type, nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, num=True, context=None):
        return self.pool.get('product.product').onChangeSearchNomenclature(cr, uid, 0, position, type, nomen_manda_0, nomen_manda_1, nomen_manda_2, nomen_manda_3, False, context={'withnum': 1})

    def get_nomen(self, cr, uid, id, field):
        return self.pool.get('product.nomenclature').get_nomen(cr, uid, self, id, field, context={'withnum': 1})

    def button_remove_lines(self, cr, uid, ids, context=None):
        '''
        Remove lines
        '''
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        vals = {}
        vals['line_ids'] = []
        for line in self.browse(cr, uid, ids, context=context):
            line_browse_list = line.line_ids
            for var in line_browse_list:
                vals['line_ids'].append((2, var.id))
            self.write(cr, uid, ids, vals, context=context)
        return True

    def check_lines_to_fix(self, cr, uid, ids, context=None):
        """
        Check the lines that need to be corrected.
        """
        if isinstance(ids, (int, long)):
            ids = [ids]
        for var in self.browse(cr, uid, ids, context=context):
            # we check the lines that need to be fixed
            if var.line_ids:
                for var in var.line_ids:
                    if var.to_correct_ok:
                        raise osv.except_osv(_('Warning !'), _('Some lines need to be fixed before.'))
        return True

monthly_review_consumption()


class monthly_review_consumption_line(osv.osv):
    _name = 'monthly.review.consumption.line'
    _description = 'Monthly review consumption line'
    _order = 'ref'

    def _get_amc(self, cr, uid, ids, field_name, arg, ctx=None):
        '''
        Calculate the product AMC for the period
        '''
        if ctx is None:
            ctx = {}
        context = ctx.copy()
        res = {}
        # TODO TEST JFB
        prod_obj = self.pool.get('product.product')
        data_mrc_id = {}
        for line in self.browse(cr, uid, ids, context=context):
            if line.mrc_id.id not in data_mrc_id:
                context = ctx.copy()
                context['from_date'] = line.mrc_id.period_from
                context['to_date'] = line.mrc_id.period_to
                if context.get('from_date', False):
                    from_date = (DateFrom(context.get('from_date')) + RelativeDateTime(day=1)).strftime('%Y-%m-%d')
                    context.update({'from_date': from_date})

                if context.get('to_date', False):
                    to_date = (DateFrom(context.get('to_date')) + RelativeDateTime(months=1, day=1, days=-1)).strftime('%Y-%m-%d')
                    context.update({'to_date': to_date})
                data_mrc_id[line.mrc_id.id] = {
                    'context': context,
                    'prod_line': {}
                }

            data_mrc_id[line.mrc_id.id]['prod_line'].setdefault(line.name.id, []).append(line.id)

        for mrc_id in data_mrc_id:
            amc = prod_obj.compute_amc(cr, uid, data_mrc_id[mrc_id]['prod_line'].keys(), data_mrc_id[mrc_id]['context'])
            for prod_id in amc:
                for line_id in data_mrc_id[mrc_id]['prod_line'][prod_id]:
                    res[line_id] = amc[prod_id]

        return res

    def _get_last_fmc(self, cr, uid, ids, field_name, args, context=None):
        '''
        Returns the last fmc date
        '''
        if context is None:
            context = {}
        res = {}

        for line in self.browse(cr, uid, ids, context=context):
            res[line.id] = self.product_onchange(cr, uid, line.id, line.name.id, line.mrc_id.id, context=context).get('value', {}).get('last_reviewed', None)

        return res

    def create(self, cr, uid, vals, context=None):
        if context is None:
            context = {}
        if 'fmc2' in vals:
            vals.update({'fmc': vals.get('fmc2')})
        if 'last_reviewed2' in vals:
            vals.update({'last_reviewed': vals.get('last_reviewed2')})

        if vals.get('valid_ok') and not vals.get('last_reviewed'):
            vals.update({'last_reviewed': time.strftime('%Y-%m-%d'),
                         'last_reviewed2': time.strftime('%Y-%m-%d')})

        return super(monthly_review_consumption_line, self).create(cr, uid, vals, context=context)

    def write(self, cr, uid, ids, vals, context=None):
        if not ids:
            return True
        if context is None:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]
        if not context.get('import_in_progress') and not context.get('button'):
            obj_data = self.pool.get('ir.model.data')
            tbd_product = obj_data.get_object_reference(cr, uid, 'msf_doc_import', 'product_tbd')[1]
            if vals.get('name'):
                if vals.get('name') == tbd_product:
                    raise osv.except_osv(_('Warning !'), _('You have to define a valid product, i.e. not "To be define".'))
                else:
                    vals['to_correct_ok'] = False
                    vals['text_error'] = False
        if 'fmc2' in vals:
            vals.update({'fmc': vals.get('fmc2')})
        if 'last_reviewed2' in vals:
            vals.update({'last_reviewed': vals.get('last_reviewed2')})

        if vals.get('valid_ok') and not vals.get('last_reviewed'):
            vals.update({'last_reviewed': time.strftime('%Y-%m-%d'),
                         'last_reviewed2': time.strftime('%Y-%m-%d')})

        return super(monthly_review_consumption_line, self).write(cr, uid, ids, vals, context=context)

    def _get_mrc_change(self, cr, uid, ids, context=None):
        '''
        Returns MRC ids when Date change
        '''
        result = {}
        for mrc in self.pool.get('monthly.review.consumption').browse(cr, uid, ids, context=context):
            for line in mrc.line_ids:
                result[line.id] = True

        return result.keys()

    def _get_product(self, cr, uid, ids, context=None):
        return self.pool.get('monthly.review.consumption.line').search(cr, uid, [('name', 'in', ids)], context=context)

    def _get_checks_all(self, cr, uid, ids, name, arg, context=None):
        result = {}
        for id in ids:
            result[id] = {'to_correct_ok': False}

        for out in self.browse(cr, uid, ids, context=context):
            # the lines with to_correct_ok=True will be red
            if out.text_error:
                result[out.id]['to_correct_ok'] = True
        return result

    def _get_security_stock(self, cr, uid, ids, field_name, args, context=None):
        # TODO JFB RR
        """
        Get the security stock of the last created order cycle line with the same product
        """
        res = {}

        if isinstance(ids, (int, long)):
            ids = [ids]
        for _id in ids:
            res[_id] = 0
        return res

    def _get_order_cycle_line(self, cr, uid, ids, context=None):
        """
        for which values have changed.

        Return the list of ids of monthly.review.consumption.line which need
        to get their fields updated.

        """
        line_obj = self.pool.get('monthly.review.consumption.line')

        if context is None:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        res = []
        for cycle_line in self.browse(cr, uid, ids, context=context):
            res.extend(line_obj.search(cr, uid, [
                ('name', '=', cycle_line.product_id.id),
            ], context=context))

        return res


    _columns = {
        'name': fields.many2one('product.product', string='Product', required=True),
        'ref': fields.related('name', 'default_code', type='char', size=64, readonly=True,
                              store={'product.product': (_get_product, ['default_code'], 10),
                                     'monthly.review.consumption.line': (lambda self, cr, uid, ids, c=None: ids, ['name'], 20)}),
        'amc': fields.function(_get_amc, string='AMC', method=True, readonly=True,
                               store={'monthly.review.consumption': (_get_mrc_change, ['period_from', 'period_to'], 20),
                                      'monthly.review.consumption.line': (lambda self, cr, uid, ids, c=None: ids, [],20),}),
        'fmc': fields.float(digits=(16,2), string='FMC'),
        'fmc2': fields.float(digits=(16,2), string='FMC (hidden)'),
        'security_stock': fields.function(
            _get_security_stock,
            method=True,
            type='float',
            string='Safety Stock (qty)',
            readonly=True,
            store={
                'monthly.review.consumption.line': (lambda self, cr, uid, ids, c=None: ids, ['name'], 10),
            },
        ),
        #'last_reviewed': fields.function(_get_last_fmc, method=True, type='date', string='Last reviewed on', readonly=True, store=True),
        'last_reviewed': fields.date(string='Last reviewed on', readonly=True),
        'last_reviewed2': fields.date(string='Last reviewed on (hidden)'),
        'valid_until': fields.date(string='Valid until'),
        'valid_ok': fields.boolean(string='Validated', readonly=False),
        'mrc_id': fields.many2one('monthly.review.consumption', string='MRC', required=True, ondelete='cascade'),
        'mrc_creation_date': fields.related('mrc_id', 'creation_date', type='date', store=True, write_relate=False),
        'text_error': fields.text('Errors', readonly=True),
        'to_correct_ok': fields.function(_get_checks_all, method=True, type="boolean", string="To correct", store=False, readonly=True, multi="m"),
    }

    def valid_line(self, cr, uid, ids, context=None):
        '''
        Valid the line and enter data in product form
        '''
        if not context:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        for line in self.browse(cr, uid, ids, context=context):
            if line.valid_ok:
                raise osv.except_osv(_('Error'), _('The line is already validated !'))

            self.write(cr, uid, [line.id], {'valid_ok': True,
                                            'last_reviewed': time.strftime('%Y-%m-%d'),
                                            'last_reviewed2': time.strftime('%Y-%m-%d')}, context=context)

        return

    def display_graph(self, cr, uid, ids, context=None):
        '''
        Display the graph view of the line
        '''
        raise osv.except_osv('Error !', 'Not implemented yet !')

    def fmc_change(self, cr, uid, ids, amc, fmc, product_id, context=None):
        '''
        Valid the line if the FMC is manually changed
        '''
        if context is None:
            context = {}
        res = {}

        if fmc != amc:
            res.update({'valid_ok': True, 'last_reviewed': time.strftime('%Y-%m-%d'), 'fmc2': fmc, 'last_reviewed2': time.strftime('%Y-%m-%d')})
        else:
            last_fmc_reviewed = False
            domain = [('name', '=', product_id), ('valid_ok', '=', True)]
            line_ids = self.search(cr, uid, domain, order='valid_until desc, mrc_creation_date desc', context=context)

            if line_ids:
                for line in self.browse(cr, uid, [line_ids[0]], context=context):
                    last_fmc_reviewed = line.mrc_id.creation_date

            res.update({'last_reviewed': last_fmc_reviewed, 'last_reviewed2': last_fmc_reviewed, 'fmc2': fmc})

        return {'value': res}

    def product_onchange(self, cr, uid, ids, product_id, mrc_id=False, from_date=False, to_date=False, context=None):
        '''
        Fill data in the line
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]

        if not context:
            context = {}

        # Compute the AMC on the period of the consumption report
        context.update({'from_date': from_date, 'to_date': to_date})

        product_obj = self.pool.get('product.product')
        line_obj = self.pool.get('monthly.review.consumption.line')

        last_fmc_reviewed = False

        if not product_id:
            return {'value': {'amc': 0.00,
                              'fmc': 0.00,
                              'fmc2': 0.00,
                              'last_reviewed2': 0.00,
                              'last_reviewed': None,
                              'valid_until': False,
                              'valid_ok': False}}

        domain = [('name', '=', product_id), ('valid_ok', '=', True)]

        line_ids = line_obj.search(cr, uid, domain, order='valid_until desc, mrc_creation_date desc', context=context)

        if line_ids:
            for line in self.browse(cr, uid, [line_ids[0]], context=context):
                last_fmc_reviewed = line.mrc_id.creation_date

        if context.get('from_date', False):
            from_date = (DateFrom(context.get('from_date')) + RelativeDateTime(day=1)).strftime('%Y-%m-%d')
            context.update({'from_date': from_date})

        if context.get('to_date', False):
            to_date = (DateFrom(context.get('to_date')) + RelativeDateTime(months=1, day=1, days=-1)).strftime('%Y-%m-%d')
            context.update({'to_date': to_date})

        amc = product_obj.compute_amc(cr, uid, product_id, context=context)[product_id]
        return {'value': {'amc': amc,
                          'fmc': amc,
                          'fmc2': amc,
                          'last_reviewed': last_fmc_reviewed,
                          'last_reviewed2': last_fmc_reviewed,
                          'valid_until': False,
                          'valid_ok': False}}


monthly_review_consumption_line()


class product_product(osv.osv):
    _name = 'product.product'
    _inherit = 'product.product'

    def _compute_fmc(self, cr, uid, ids, field_name, args, context=None):
        '''
        Returns the last value of the FMC
        '''
        if not context:
            context = {}

        res = {}
        #fmc_obj = self.pool.get('monthly.review.consumption')
        fmc_line_obj = self.pool.get('monthly.review.consumption.line')

        # Search all Review report for locations
        #fmc_ids = fmc_obj.search(cr, uid, [], order='period_to desc, creation_date desc', limit=1, context=context)

        for product in ids:
            res[product] = 0.00

            # Search all validated lines with the product
            #line_ids = fmc_line_obj.search(cr, uid, [('name', '=', product), ('valid_ok', '=', True), ('mrc_id', 'in', fmc_ids)], context=context)
            line_ids = fmc_line_obj.search(cr, uid, [('name', '=', product), ('valid_ok', '=', True)], order='last_reviewed desc, mrc_id desc', limit=1, context=context)

            # Get the last created line
            for line in fmc_line_obj.browse(cr, uid, line_ids, context=context):
                res[product] = line.fmc

        return res

    def compute_mac(self, cr, uid, ids, field_name, args, context=None):
        '''
        Compute the Real Average Consumption
        '''
        if isinstance(ids, (int, long)):
            ids = [ids]
        if context is None:
            context = {}

        uom_obj = self.pool.get('product.uom')

        rac_domain = [('created_ok', '=', True)]
        res = {}

        from_date = False
        to_date = False

        location_ids = []

        # Read if a interval is defined
        if context.get('from_date', False):
            from_date = context.get('from_date')
            rac_domain.append(('period_to', '>=', from_date))

        if context.get('to_date', False):
            to_date = context.get('to_date')
            rac_domain.append(('period_to', '<=', to_date))

        # Filter for one or some locations
        if context.get('location_id', False):
            if type(context['location_id']) == type(1):
                location_ids = [context['location_id']]
            elif type(context['location_id']) in (type(''), type(u'')):
                location_ids = self.pool.get('stock.location').search(cr, uid, [('name','ilike',context['location'])], context=context)
            else:
                location_ids = context.get('location_id', [])

        for id in ids:
            res[id] = 0.00
            if from_date and to_date:
                rac_search_domain = [
                    ('cons_location_id', 'in', location_ids),
                    ('state', 'not in', ['draft', 'cancel']),
                    # All lines with a report started out the period and finished in the period
                    '|', '&', ('period_to', '>=', from_date), ('period_to', '<=', to_date),
                    #  All lines with a report started in the period and finished out the period
                    '|', '&', ('period_from', '<=', to_date), ('period_from', '>=', from_date),
                    #  All lines with a report started before the period  and finished after the period
                    '&', ('period_from', '<=', from_date), ('period_to', '>=', to_date),
                ]
                if context.get('location_dest_id'):
                    rac_search_domain.append(('activity_id', '=', context['location_dest_id']))
                rac_ids = self.pool.get('real.average.consumption').search(cr, uid, rac_search_domain)
                rcr_domain = [('product_id', '=', id), ('rac_id', 'in', rac_ids)]

                rcr_line_ids = self.pool.get('real.average.consumption.line').search(cr, uid, rcr_domain, context=context)
                for line in self.pool.get('real.average.consumption.line').browse(cr, uid, rcr_line_ids, context=context):
                    cons = self._get_period_consumption(cr, uid, line, from_date, to_date, context=context)
                    res[id] += uom_obj._compute_qty(cr, uid, line.uom_id.id, cons, line.product_id.uom_id.id)

                # We want the average for the entire period
                if to_date < from_date:
                    raise osv.except_osv(_('Error'), _('You cannot have a \'To Date\' younger than \'From Date\'.'))
                # Calculate the # of months in the period
                try:
                    to_date_str = strptime(to_date, '%Y-%m-%d')
                except ValueError:
                    to_date_str = strptime(to_date, '%Y-%m-%d %H:%M:%S')

                try:
                    from_date_str = strptime(from_date, '%Y-%m-%d')
                except ValueError:
                    from_date_str = strptime(from_date, '%Y-%m-%d %H:%M:%S')

                nb_months = self._get_date_diff(from_date_str, to_date_str)

                if not nb_months: nb_months = 1

                uom_id = self.browse(cr, uid, ids[0], context=context).uom_id.id
                res[id] = res[id]/float(nb_months)
                res[id] = round(self.pool.get('product.uom')._compute_qty(cr, uid, uom_id, res[id], uom_id), 2)

        return res

    def _get_domain_compute_amc(self, cr, uid, context):
        # Get all reason types
        get_object_reference = self.pool.get('ir.model.data').get_object_reference
        loan_id = get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_loan')[1]
        donation_id = get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_donation')[1]
        donation_exp_id = get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_donation_expiry')[1]
        loss_id = get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_loss')[1]
        discrepancy_id = get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_discrepancy')[1]

        # Update the domain
        domain = [('state', '=', 'done'), ('reason_type_id', 'not in', (loan_id, donation_id, donation_exp_id, loss_id, discrepancy_id))]
        int_return_qery = False

        return_id = get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_return_from_unit')[1] # code 4
        return_good_id = get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_goods_return')[1] # code 16
        replacement_id = get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_goods_replacement')[1] # code 17
        internal_return = get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_internal_return')[1] # code 18

        src_locations = context.get('histo_src_location_ids') or context.get('amc_location_ids')
        dest_locations = context.get('histo_dest_location_ids')
        #if src_locations and not dest_locations:
        #    # SRC INTERNAL // SAME AS RR
        #    out_locations = self.pool.get('stock.location').search(cr, uid, [('usage', '=', 'customer')], context=context, order='NO_ORDER')
        #    domain += [
        #        '|',
        #        '&', '&', '&', ('type', '=', 'out'), ('location_dest_id', 'in', out_locations), ('reason_type_id', 'not in', [return_id, return_good_id, replacement_id]), '|', ('location_id', 'in', src_locations), ('initial_location', 'in', src_locations),
        #        '&', '&', ('type', '=', 'in'), ('reason_type_id', 'in', [return_id, return_good_id]), ('location_dest_id', 'in', src_locations)
        #    ]


        #   #INT chained to a IN reason_type_return_from_unit  with location_dest_id in histo_src_location_ids
        #   int_return_qery = '''
        #       select
        #           move_int.id
        #       from
        #           stock_move move_int, stock_picking pick_int, stock_picking pick_in, stock_move move_in
        #       where
        #           move_int.picking_id = pick_int.id and
        #           move_in.picking_id = pick_in.id and
        #           move_in.reason_type_id in %(return_reason)s and
        #           move_int.type = 'internal' and
        #           pick_int.previous_chained_pick_id = pick_in.id and
        #           move_int.product_id in %(product_ids)s and
        #           move_int.location_dest_id in %(src_locations)s and
        #           move_int.state = 'done' and
        #           move_int.date >= %(from_date)s and
        #           move_int.date <= %(to_date)s
        #   '''

        if not context.get('histo_src_location_ids') and context.get('histo_dest_location_ids'):
            # DEST EXTERNAL
            input_loc = get_object_reference(cr, uid, 'msf_cross_docking', 'stock_location_input')[1]
            domain += [ '|',
                        '&', '&', ('type', '=', 'out'), ('location_dest_id', 'in', dest_locations), ('reason_type_id', 'not in', [return_id, return_good_id, replacement_id]),
                        '&', '&', '&', ('type', '=', 'in'), ('reason_type_id', 'in', [return_id, return_good_id]), ('location_id', 'in', dest_locations), ('location_dest_id', '!=', input_loc)
                        ]

            int_return_qery = '''
                select
                    move_int.id
                from
                    stock_move move_int, stock_picking pick_int, stock_picking pick_in, stock_move move_in
                where
                    move_int.picking_id = pick_int.id and
                    move_in.picking_id = pick_in.id and
                    move_in.reason_type_id in %(return_reason)s and
                    move_int.type = 'internal' and
                    pick_int.previous_chained_pick_id = pick_in.id and
                    move_int.product_id in %(product_ids)s and
                    move_in.location_id in %(dest_locations)s and
                    move_int.state = 'done' and
                    move_int.date >= %(from_date)s and
                    move_int.date <= %(to_date)s
            '''

        elif src_locations:
            # SRC INTERNAL
            # DEST: INTERNAL + EXTERNAL  OR EMPTY (same as segment RR-AMC)
            if not dest_locations:
                dest_locations = self.pool.get('stock.location').search(cr, uid, [('id', 'not in', src_locations), ('usage', 'in', ['internal', 'customer']), ('location_category', '!=', 'transition')], context=context)
            domain += ['|', '|', '|',
                       # DEST & SRC: internal
                       '&', '&', '&', '&', '&',
                       ('type', '=', 'internal'), ('location_id', 'in', src_locations), ('location_id', 'not in', dest_locations), ('location_dest_id', 'in', dest_locations), ('location_dest_id', 'not in', src_locations), ('reason_type_id', '!=', internal_return),
                       '&', '&', '&', '&', '&',
                       ('type', '=', 'internal'), ('location_id', 'not in', src_locations), ('location_id', 'in', dest_locations), ('location_dest_id', 'not in', dest_locations), ('location_dest_id', 'in', src_locations), ('reason_type_id', '=', internal_return),
                       # SRC INTERNAL , DEST: EXTERNAL
                       '&', '&', '&', ('type', '=', 'out'), ('location_dest_id', 'in', dest_locations), '|', ('location_id', 'in', src_locations), ('initial_location', 'in', src_locations), ('reason_type_id', 'not in', [return_id, return_good_id, replacement_id]),
                       '&', '&', '&', ('type', '=', 'in'), ('reason_type_id', 'in', [return_id, return_good_id]), ('location_id', 'in', dest_locations), ('location_dest_id', 'in', src_locations),
                       ]

            #INT chained return from unit wher src.In= dest and dest.INT = src
            int_return_qery = '''
                select
                    move_int.id
                from
                    stock_move move_int, stock_picking pick_int, stock_picking pick_in, stock_move move_in
                where
                    move_int.picking_id = pick_int.id and
                    move_in.picking_id = pick_in.id and
                    move_in.reason_type_id in %(return_reason)s and
                    move_int.type = 'internal' and
                    pick_int.previous_chained_pick_id = pick_in.id and
                    move_int.product_id in %(product_ids)s and
                    move_in.location_id in %(dest_locations)s and
                    move_int.location_dest_id in %(src_locations)s and
                    move_int.state = 'done' and
                    move_int.date >= %(from_date)s and
                    move_int.date <= %(to_date)s
            '''
        else:
            # no src, no dst
            internal_locations = self.pool.get('stock.location').search(cr, uid, [('usage', '=', 'internal')], context=context, order='NO_ORDER')
            customer_locations = self.pool.get('stock.location').search(cr, uid, [('usage', '=', 'customer')], context=context, order='NO_ORDER')
            domain += ['|', '&', ('location_id', 'in', internal_locations), ('location_dest_id', 'in', customer_locations), '&', ('type', '=', 'in'), ('reason_type_id', 'in', [return_id, return_good_id])]

        return domain, int_return_qery, dest_locations

    def compute_amc(self, cr, uid, ids, context=None, compute_amc_by_month=False, remove_negative_amc=False, rounding=True):
        '''
        Compute the Average Monthly Consumption with this formula :
            AMC = (sum(OUTGOING (except reason types Loan, Donation, Loss, Discrepancy))
                  -
                  sum(INCOMING with reason type Return from unit)) / Number of period's months
            The AMC is the addition of all done stock moves for a product within a period.
            For stock moves generated from a real consumption report, the qty of product is computed
            according to the average of consumption for the time of the period.
        '''
        if not context:
            context = {}
        if isinstance(ids, (int, long)):
            ids = [ids]

        if not ids:
            if compute_amc_by_month:
                return {}, {}
            return {}

        move_obj = self.pool.get('stock.move')
        uom_obj = self.pool.get('product.uom')
        res = {}
        for _id in ids:
            res[_id] = 0

        from_date = False
        to_date = False

        # Read if a interval is defined
        if context.get('from_date', False):
            from_date = context.get('from_date')
        if context.get('to_date', False):
            to_date = context.get('to_date')

        amc_by_month = {}
        get_object_reference = self.pool.get('ir.model.data').get_object_reference
        return_id = get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_return_from_unit')[1] # code 4
        return_good_id = get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_goods_return')[1] # code 16
        internal_return = get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_internal_return')[1] # code 18
        replacement_id = get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_goods_replacement')[1] # code 17

        domain, extra_sql, dest_locations = self._get_domain_compute_amc(cr, uid, context)
        domain.insert(0, ('product_id', 'in', ids))

        if to_date:
            domain.insert(0, ('date', '<=', to_date))
        if from_date:
            domain.insert(0, ('date', '>=', from_date))

        # Search all real consumption line included in the period
        # If no period found, take all stock moves
        if from_date and to_date:
            rcr_domain = ['&', '&', ('rac_id.state', 'not in', ['draft', 'cancel']), ('product_id', 'in', ids),
                          # All lines with a report started out the period and finished in the period
                          '|', '&', ('rac_id.period_to', '>=', from_date), ('rac_id.period_to', '<=', to_date),
                          # All lines with a report started in the period and finished out the period
                          '|', '&', ('rac_id.period_from', '<=', to_date), ('rac_id.period_from', '>=', from_date),
                          # All lines with a report started before the period  and finished after the period
                          '&', ('rac_id.period_from', '<=', from_date), ('rac_id.period_to', '>=', to_date)]

            if context.get('amc_location_ids'):
                rcr_domain = ['&', ('rac_id.cons_location_id', 'in', context.get('amc_location_ids'))] + rcr_domain

            if context.get('histo_src_location_ids'):
                rcr_domain = ['&', ('rac_id.cons_location_id', 'in', context.get('histo_src_location_ids'))] + rcr_domain
            if context.get('histo_dest_location_ids'):
                rcr_domain = ['&', ('rac_id.activity_id', 'in', context.get('histo_dest_location_ids'))] + rcr_domain


            racl_obj = self.pool.get('real.average.consumption.line')
            rcr_line_ids = racl_obj.search(cr, uid, rcr_domain, context=context, order='NO_ORDER')
            report_move_ids = []
            for line in racl_obj.browse(cr, uid, rcr_line_ids, context=context):
                report_move_ids.append(line.move_id.id)
                if compute_amc_by_month:
                    res[line.product_id.id] += self._get_period_consumption(cr, uid, line, from_date, to_date, context=context, amc_by_month=amc_by_month)
                else:
                    res[line.product_id.id] += self._get_period_consumption(cr, uid, line, from_date, to_date, context=context)

            if report_move_ids:
                domain.insert(0, ('id', 'not in', report_move_ids))


        customer_locations_ids = []
        if 'histo_src_location_ids' in context:
            # Histo RR-AMC
            src_locations = context['histo_src_location_ids']
        elif 'amc_location_ids' in context:
            # RR from Segment
            src_locations = context.get('amc_location_ids')
        else:
            src_locations = None
            # get cusomer locations
            customer_locations_ids = self.pool.get('stock.location').search(cr, uid, [('active', 'in', ['t', 'f']), ('usage', '=', 'customer')])


        # get uom_id of all product_id
        product_result = self.pool.get('product.product').read(cr, uid, ids, ['uom_id'],
                                                               context=context)
        product_dict = dict((x['id'], x) for x in product_result)



        out_move_ids = move_obj.search(cr, uid, domain, context=context, order='NO_ORDER')
        int_return = []
        if extra_sql:
            cr.execute(extra_sql, {
                'from_date': from_date or '1970-01-01 00:00:00',
                'to_date': to_date or '2300-01-01 00:00:00',
                'product_ids': tuple(ids),
                'src_locations': tuple(src_locations),
                'dest_locations': tuple(dest_locations),
                'return_reason': tuple([return_id, return_good_id]),
            })
            int_return = [x[0] for x in cr.fetchall()]
            out_move_ids += int_return

        move_result = move_obj.read(cr, uid, out_move_ids, ['location_id',
                                                            'reason_type_id', 'product_uom', 'product_qty', 'product_id',
                                                            'location_dest_id', 'date', 'type'], context=context)

        for move in move_result:
            sign = False
            if src_locations is None:
                if move['reason_type_id'][0] in [return_id, return_good_id] and move['type'] == 'in':
                    sign = -1

                elif move['location_dest_id'][0] in customer_locations_ids and  move['reason_type_id'][0] not in [return_id, return_good_id, replacement_id]:
                    sign = 1
            else:
                if move['reason_type_id'][0] in [return_id, return_good_id, internal_return] or move['id'] in int_return:
                    sign = -1
                else:
                    sign = 1

            if sign is not False:
                qty = sign * uom_obj._compute_qty(cr, uid, move['product_uom'][0], move['product_qty'], product_dict[move['product_id'][0]]['uom_id'][0])
                res[move['product_id'][0]] += qty
                if compute_amc_by_month:
                    period = strptime(move['date'], '%Y-%m-%d %H:%M:%S').strftime('%Y-%m')
                    amc_by_month.setdefault(move['product_id'][0], {}).setdefault(period, 0)
                    amc_by_month[move['product_id'][0]][period] += qty

            # Update the limit in time
            if not context.get('from_date') and (not from_date or move['date'] < from_date):
                from_date = move['date']
            if not context.get('to_date') and (not to_date or move['date'] > to_date):
                to_date = move['date']

        if remove_negative_amc:
            for prod in amc_by_month:
                for period in amc_by_month[prod]:
                    qty = amc_by_month[prod][period]
                    if qty < 0:
                        amc_by_month[prod][period] = 0
                        res[prod] -= qty

        if not to_date or not from_date or not res:
            return 0.00

        # We want the average for the entire period
        if to_date < from_date:
            raise osv.except_osv(_('Error'), _('You cannot have a \'To Date\' younger than \'From Date\'.'))
        # Calculate the # of months in the period
        try:
            to_date_str = strptime(to_date, '%Y-%m-%d')
        except ValueError:
            to_date_str = strptime(to_date, '%Y-%m-%d %H:%M:%S')
        try:
            from_date_str = strptime(from_date, '%Y-%m-%d')
        except ValueError:
            from_date_str = strptime(from_date, '%Y-%m-%d %H:%M:%S')

        to_date_str = min(now(), to_date_str)
        nb_months = self._get_date_diff(from_date_str, to_date_str)

        if not nb_months:
            nb_months = 1

        adjusted_qty = {}
        adjusted_day = {}
        adjusted_period_day = {}
        adjusted_period_qty = {}

        if context.get('amc_location_ids') or (not context.get('histo_dest_location_ids') and context.get('adjusted_rr_amc')):
            if 'amc_location_ids' in context:
                stock_out_loc = context.get('amc_location_ids')
            else:
                if context.get('histo_src_location_ids'):
                    stock_out_loc = context.get('histo_src_location_ids')
                else:
                    stock_out_loc = self.pool.get('stock.location').search(cr, uid, [('usage', '=', 'internal')], context=context, order='NO_ORDER')

            cr.execute('''
                select line.product_id, line.from_date, line.to_date, line.qty_missed, substitute_1_product_id, substitute_1_qty, substitute_2_product_id, substitute_2_qty,substitute_3_product_id, substitute_3_qty
                    from product_stock_out_line line, product_stock_out st
                    where
                        line.stock_out_id = st.id and
                        st.state = 'closed' and
                        st.adjusted_amc = 't' and
                        ( line.product_id in %(product)s or substitute_1_product_id in %(product)s or substitute_2_product_id in %(product)s or substitute_3_product_id in %(product)s ) and
                        st.location_id in %(location)s and
                        (from_date, to_date) OVERLAPS (%(from)s, %(to)s)
            ''', {'product': tuple(res.keys()), 'location': tuple(stock_out_loc), 'from': from_date, 'to': to_date})

            for x in cr.fetchall():
                from_over = max(from_date, x[1])
                to_over = min(to_date, x[2])
                dt_to_over = strptime(to_over, '%Y-%m-%d')
                dt_from_over = strptime(from_over, '%Y-%m-%d')
                overlap_days = (dt_to_over - dt_from_over).days
                if x[0] in res.keys():
                    if  x[3] is None:
                        # qty no set
                        adjusted_day.setdefault(x[0], 0)
                        adjusted_day[x[0]] -= overlap_days
                        if compute_amc_by_month:
                            tmp_dt_from_over = dt_from_over
                            while tmp_dt_from_over <= dt_to_over:
                                period = tmp_dt_from_over.strftime('%Y-%m')
                                last_period_day = tmp_dt_from_over + RelativeDateTime(months=1, day=1)
                                adjusted_period_day.setdefault(x[0], {}).setdefault(period, 0)
                                adjusted_period_day[x[0]][period] -= (min(last_period_day, dt_to_over) - tmp_dt_from_over).days
                                tmp_dt_from_over += RelativeDateTime(months=1, day=1)

                    else:
                        adjusted_qty.setdefault(x[0], 0)
                        adjusted_qty_by_day = x[3]/float((strptime(x[2], '%Y-%m-%d') - strptime(x[1], '%Y-%m-%d')).days)
                        adjusted_qty[x[0]] += adjusted_qty_by_day * overlap_days
                        if compute_amc_by_month:
                            tmp_dt_from_over = dt_from_over
                            while tmp_dt_from_over <= dt_to_over:
                                period = tmp_dt_from_over.strftime('%Y-%m')
                                last_period_day = tmp_dt_from_over + RelativeDateTime(months=1, day=1)
                                adjusted_period_qty.setdefault(x[0], {}).setdefault(period, 0)
                                adjusted_period_qty[x[0]][period] += (min(last_period_day, dt_to_over) - tmp_dt_from_over).days * adjusted_qty_by_day
                                tmp_dt_from_over += RelativeDateTime(months=1, day=1)
                for idx in [4, 6, 8]:
                    if x[idx] in res.keys() and x[idx+1]:
                        adjusted_qty.setdefault(x[idx], 0)
                        adjusted_qty_by_day = x[idx+1]/float((strptime(x[2], '%Y-%m-%d') - strptime(x[1], '%Y-%m-%d')).days)
                        adjusted_qty[x[idx]] -= adjusted_qty_by_day * overlap_days
                        if compute_amc_by_month:
                            tmp_dt_from_over = dt_from_over
                            while tmp_dt_from_over <= dt_to_over:
                                period = tmp_dt_from_over.strftime('%Y-%m')
                                last_period_day = tmp_dt_from_over + RelativeDateTime(months=1, day=1)
                                adjusted_period_qty.setdefault(x[idx], {}).setdefault(period, 0)
                                adjusted_period_qty[x[idx]][period] -= (min(last_period_day, dt_to_over) - tmp_dt_from_over).days * adjusted_qty_by_day
                                tmp_dt_from_over += RelativeDateTime(months=1, day=1)


            nb_months = ((to_date_str-from_date_str).days + 1)/30.44

        for p_id in res:
            p_nb_nb_months = float(nb_months)
            adj = False
            if p_id in adjusted_day:
                adj = True
                p_nb_nb_months += adjusted_day[p_id]/30.44

            if p_id in adjusted_qty:
                adj = True
                res[p_id] += adjusted_qty[p_id]

            if adj and remove_negative_amc and res[p_id] < 0:
                res[p_id] = 0

            if p_id in product_dict and rounding:
                prod_uom = product_dict[p_id]['uom_id'][0]
                res[p_id] = uom_obj._compute_qty(cr, uid, prod_uom, res[p_id]/p_nb_nb_months, prod_uom)
            else:
                res[p_id] = round(res[p_id]/p_nb_nb_months, 4)

        if compute_amc_by_month:
            for p_id in res:
                for adj_period in adjusted_period_day.get(p_id, {}):
                    if amc_by_month.get(p_id, {}).get(adj_period):
                        amc_by_month[p_id][adj_period] = round((amc_by_month[p_id][adj_period]/(30.44-adjusted_period_day[p_id][adj_period])) * 30.44, 2)
                for period in adjusted_period_qty.get(p_id, {}):
                    amc_by_month.setdefault(p_id, {}).setdefault(period, 0)
                    amc_by_month[p_id][period] = round(amc_by_month[p_id][period] + adjusted_period_qty[p_id][period], 2)
                    if remove_negative_amc and amc_by_month[p_id][period] < 0:
                        amc_by_month[p_id][period] = 0

            return res, amc_by_month

        return res

    def _get_date_diff(self, from_date, to_date):
        '''
        Returns the number of months between to dates according to the number
        of days in the month.
        '''
        diff_date = Age(to_date, from_date)
        res = 0.0

        def days_in_month(month, year):
            '''
            Returns the # of days in the month
            '''
            res = 30
            if month == 2 and year%4 == 0:
                res = 29
            elif month == 2 and year%4 != 0:
                res = 28
            elif month in (1, 3, 5, 7, 8, 10, 12):
                res = 31
            return res

        while from_date <= to_date:
            # Add 12 months by years between the two dates
            if diff_date.years:
                res += diff_date.years*12
                from_date += RelativeDate(years=diff_date.years)
                diff_date = Age(to_date, from_date)
            else:
                # If two dates are in the same month
                if from_date.month == to_date.month:
                    nb_days_in_month = days_in_month(from_date.month, from_date.year)
                    # We divided the # of days between the two dates by the # of days in month
                    # to have a percentage of the number of month
                    res += (to_date.day-from_date.day+1)/float(nb_days_in_month)
                    break
                elif to_date.month - from_date.month > 1 or to_date.year - from_date.year > 0:
                    res += 1
                    from_date += RelativeDate(months=1)
                else:
                    # Number of month till the end of from month
                    fr_nb_days_in_month = days_in_month(from_date.month, from_date.year)
                    nb_days = fr_nb_days_in_month - from_date.day + 1
                    res += nb_days/float(fr_nb_days_in_month)
                    # Number of month till the end of from month
                    to_nb_days_in_month = days_in_month(to_date.month, to_date.year)
                    res += to_date.day/float(to_nb_days_in_month)
                    break

        return res

    def _compute_product_amc(self, cr, uid, ids, field_name, args, ctx=None):
        if ctx is None:
            ctx = {}
        context = ctx.copy()

        if context.get('from_date', False):
            from_date = (DateFrom(context.get('from_date')) + RelativeDateTime(day=1)).strftime('%Y-%m-%d')
        else:
            from_date = (DateFrom(time.strftime('%Y-%m-%d')) + RelativeDateTime(months=-3, day=1)).strftime('%Y-%m-%d')

        if context.get('to_date', False):
            to_date = (DateFrom(context.get('to_date')) + RelativeDateTime(months=1, day=1, days=-1)).strftime('%Y-%m-%d')
        else:
            to_date = (DateFrom(time.strftime('%Y-%m-%d')) + RelativeDateTime(day=1, days=-1)).strftime('%Y-%m-%d')

        context.update({
            'from_date': from_date,
            'to_date': to_date})

        return self.compute_amc(cr, uid, ids, context=context)


    def _get_period_consumption(self, cr, uid, line, from_date, to_date, context=None, amc_by_month=None):
        '''
        Returns the average quantity of product in the period
        '''
        # Compute the # of days in the report period
        if context is None:
            context = {}
        from datetime import datetime
        from dateutil.relativedelta import relativedelta
        report_from = datetime.strptime(line.rac_id.period_from, '%Y-%m-%d')
        report_to = datetime.strptime(line.rac_id.period_to, '%Y-%m-%d')
        dt_from_date = datetime.strptime(from_date, '%Y-%m-%d')
        dt_to_date = datetime.strptime(to_date, '%Y-%m-%d')
        delta = report_to - report_from

        # Add 1 to include the last day of report to
        report_nb_days = delta.days + 1
        days_incl = 0

        # Case where the report is totally included in the period
        if line.rac_id.period_from >= from_date and line.rac_id.period_to <= to_date:
            days_incl = report_nb_days
        # Case where the report started before the period and done after the period
        elif line.rac_id.period_from <= from_date and line.rac_id.period_to >= to_date:
            # Compute the # of days of the period
            delta2 = dt_to_date - dt_from_date
            days_incl = delta2.days +1
        # Case where the report started before the period and done in the period
        elif line.rac_id.period_from <= from_date and line.rac_id.period_to <= to_date and line.rac_id.period_to >= from_date:
            # Compute the # of days of the report included in the period
            # Add 1 to include the last day of report to
            delta2 = report_to - dt_from_date
            days_incl = delta2.days +1
        # Case where the report started in the period and done after the period
        elif line.rac_id.period_from >= from_date and line.rac_id.period_to >= to_date and line.rac_id.period_from <= to_date:
            # Compute the # of days of the report included in the period
            # Add 1 to include the last day of to_date
            delta2 = dt_to_date - report_from
            days_incl = delta2.days +1

        # Compute the quantity consumed in the period for this line
        consumed_qty = (line.consumed_qty/float(report_nb_days))*days_incl

        if amc_by_month is not None:
            fromd = max(report_from, dt_from_date)
            tod = min(report_to, dt_to_date)
            total_age = (tod - fromd).days + 1
            while fromd <= tod:
                amc_by_month.setdefault(line.product_id.id, {}).setdefault(fromd.strftime('%Y-%m'), 0)
                amc_by_month[line.product_id.id][fromd.strftime('%Y-%m')] += consumed_qty/float(total_age) * (min(tod+relativedelta(days=1), fromd+relativedelta(months=1))-fromd).days
                fromd += relativedelta(months=1)
        if consumed_qty:
            result = self.pool.get('product.uom')._compute_qty(cr, uid,
                                                               line.uom_id.id, consumed_qty, line.uom_id.id)
        else:
            result = consumed_qty
        return result

    _columns = {
        'procure_delay': fields.float(digits=(16,2), string='Procurement Lead Time',
                                      help='It\'s the default time to procure this product. This lead time will be used on the Order cycle procurement computation'),
        'monthly_consumption': fields.function(compute_mac, method=True, type='float', string='Real Consumption', readonly=True),
        'product_amc': fields.function(_compute_product_amc, method=True, type='float', string='Monthly consumption', readonly=True),
        'reviewed_consumption': fields.function(_compute_fmc, method=True, type='float', string='Forecasted Monthly Consumption', readonly=True),
    }

    _defaults = {
        'procure_delay': lambda *a: 60,
    }


product_product()


class stock_picking(osv.osv):
    _inherit = 'stock.picking'
    _name = 'stock.picking'

    _columns = {
        'rac_id': fields.many2one('real.average.consumption', string='Real consumption report'),
    }

    def _hook_log_picking_modify_message(self, cr, uid, ids, context=None, message='', pick=False):
        '''
        Possibility to change the message
        '''
        report_ids = self.pool.get('real.average.consumption').search(cr, uid, [('picking_id', '=', pick.id)], context=context)
        if report_ids:
            name = self.pool.get('real.average.consumption').browse(cr, uid, report_ids[0], context=context).picking_id.name
            return 'Delivery Order %s generated from the consumption report is closed.' % name
        else:
            return super(stock_picking, self)._hook_log_picking_modify_message(cr, uid, ids, context=context, message=message, pick=pick)

stock_picking()

class stock_location(osv.osv):
    _inherit = 'stock.location'

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        if context is None:
            context = {}
        if context.get('no3buttons') and view_type == 'search':
            view_id = self.pool.get('ir.model.data').get_object_reference(cr, uid, 'consumption_calculation', 'view_stock_location_without_buttons')
        return super(stock_location, self).fields_view_get(cr, uid, view_id, view_type, context=context, toolbar=toolbar, submenu=submenu)
stock_location()
