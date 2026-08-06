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

from osv import osv
from osv import fields
from tools.translate import _
from lxml import etree


class change_dest_location(osv.osv_memory):
    _name = 'change.dest.location'

    _columns = {
        'picking_id': fields.many2one('stock.picking', string='Move', required=True),
        'dest_location_id': fields.many2one('stock.location', string='Destination location'),
        'src_location_id': fields.many2one('stock.location', string='Source Location'),
        'type': fields.selection([('internal','internal'), ('out', 'out')], 'Type'),
        'warn_msg': fields.text(string='Warning message', readonly=True),
        'state': fields.selection([('start', 'Start'), ('end', 'Finished')], string='State', readonly=True),
        'wizard_title': fields.char('Title', size=256),
    }

    _defaults = {
        'state': lambda *a: 'start',
        'type': 'internal',
        'wizard_title': lambda *a: _('Change Location'),
    }

    def create(self, cr, uid, vals, context=None):
        '''
        Check if a picking is passed to columns
        Then check if the picking type is internal
        '''
        if not context:
            context = {}

        if not vals.get('picking_id'):
            raise osv.except_osv(_('Error'), _('You must define an Internal move to launch this wizard on.'))

        picking = self.pool.get('stock.picking').browse(cr, uid, vals.get('picking_id'), fields_to_fetch=['type'], context=context)
        vals['type'] = picking.type
        if picking.type == 'out':
            if not context.get('button_selected_ids'):
                raise osv.except_osv(_('Warning'),  _('Please select at least one line'))
            vals['wizard_title'] = _('Change Sources')
        if picking.type not in ('internal', 'out'):
            raise osv.except_osv(_('Error'), _('The modification of the locations is only available for Internal moves and Picking Ticket.'))
        return super(change_dest_location, self).create(cr, uid, vals, context=context)


    def close_window(self, cr, uid, ids, context=None):
        '''
        Close window
        '''
        if not context:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        close_wiz = {'type': 'ir.actions.act_window_close'}

        if context.get('button_selected_ids'):
            close_wiz['o2m_refresh'] = 'move_lines'
        return close_wiz

    def getSelection(self,o,fields):
        sel =  o.fields_get(self.cr, self.uid, fields)
        for i in sel[fields]['selection']:
            if i[0] == getattr(o,fields):
                if i[1]:
                    try:
                        return i[1].encode('utf8')
                    except:
                        return i[1]
            return ""
        return getattr(o,fields) or ""


    def change_dest_location_selected(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        return self.change_dest_location(cr, uid, ids, context=context, selection=context.get('button_selected_ids', []))

    def change_dest_location(self, cr, uid, ids, context=None, selection=None):
        '''
        Change the destination location for all stock moves
        '''
        if not context:
            context = {}

        if isinstance(ids, int):
            ids = [ids]

        loc_obj = self.pool.get('stock.location')
        move_obj = self.pool.get('stock.move')
        data_obj = self.pool.get('ir.model.data')
        nb = 0
        for wizard in self.browse(cr, uid, ids, context=context):
            warn_msg = []
            state_to_change = ['draft', 'confirmed', 'assigned']
            if wizard.type != 'internal':
                state_to_change = ['draft', 'confirmed']

            move_domain = [('picking_id', '=', wizard.picking_id.id), ('state', 'in', state_to_change), ('product_qty', '!=', 0)]
            if selection is not None:
                move_domain.append(('id', 'in', selection))
            move_ids = move_obj.search(cr, uid, move_domain, context=context)

            if not move_ids:
                raise osv.except_osv(_('Warning'), _('No stock move found.'))

            move_changed = []
            for move in move_obj.browse(cr, uid, move_ids, context=context):
                if wizard.type == 'internal':
                    # Check if the new destination location is not the source location
                    if move.location_id.id == wizard.dest_location_id.id:
                        warn_msg.append(_('Line %s : The new destination location is the same as the source location of the move, so the destination location has not been changed for this move. \n') % move.line_number)
                        continue

                    # Check if the new destination location is compatible with the product type
                    location_ids = loc_obj.search(cr, uid, [('internal_dest', '=', move.product_id.id),
                                                            ('usage', '!=', 'view')], context=context)
                    if wizard.dest_location_id.id not in location_ids:
                        warn_msg.append(_('Line %s : The new destination location is not compatible with the product type, so the destination location has not been changed for this move. \n') % move.line_number)
                        continue

                    # Same restrictions as the method location_dest_change
                    int_move_rt_id = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_internal_move')[1]
                    quarantine_loc_id = data_obj.get_object_reference(cr, uid, 'stock_override', 'stock_location_quarantine_analyze')[1]
                    exp_dam_scrap_loc_id = data_obj.get_object_reference(cr, uid, 'stock_override', 'stock_location_quarantine_scrap')[1]
                    destr_loc_id = data_obj.get_object_reference(cr, uid, 'stock', 'stock_location_scrapped')[1]
                    destr_rt_id = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_destruction')[1]
                    cross_loc_id = data_obj.get_object_reference(cr, uid, 'msf_cross_docking', 'stock_location_cross_docking')[1]
                    restr_loc_ids = [
                        data_obj.get_object_reference(cr, uid, 'stock', 'stock_location_stock')[1],
                        data_obj.get_object_reference(cr, uid, 'msf_config_locations', 'stock_location_intermediate_client_view')[1],
                        data_obj.get_object_reference(cr, uid, 'msf_config_locations', 'stock_location_eprep_view')[1]
                    ]
                    child_loc_ids = loc_obj.search(cr, uid, [('location_id', 'in', restr_loc_ids)], context=context)
                    restr_loc_ids.extend(child_loc_ids)
                    restr_qua_loc_ids = restr_loc_ids.copy()
                    restr_qua_loc_ids.append(quarantine_loc_id)
                    restr_cross_loc_ids = restr_qua_loc_ids.copy()
                    restr_cross_loc_ids.append(cross_loc_id)
                    if move.location_id.id == exp_dam_scrap_loc_id and wizard.dest_location_id.id in restr_qua_loc_ids:
                        warn_msg.append(_('Line %s: If the Source Location is "Expired / Damaged / For Scrap", you can not select a Stock location, an Intermediate Stocks location, an EPREP Stocks location or "Quarantine (analyze)" as Destination Location\n')
                                        % (move.line_number,))
                        continue
                    if move.reason_type_id.id == int_move_rt_id and wizard.dest_location_id.id not in restr_cross_loc_ids:
                        warn_msg.append(_('Line %s: The selected Destination Location can not be used with the Reason Type "7 Internal Move". Please use a Stock location, an Intermediate Stocks location, an EPREP Stocks location or "Quarantine (analyze)"\n')
                                        % (move.line_number,))
                        continue
                    elif move.location_id.id in restr_loc_ids and wizard.dest_location_id.id == quarantine_loc_id and\
                            move.reason_type_id.id != int_move_rt_id:
                        warn_msg.append(_('Line %s: If the Source Location is a Stock location, an Intermediate Stocks location or an EPREP Stocks location and the Destination Location is "Quarantine (analyze)", the only authorized Reason Type is "7 Internal Move"\n')
                                        % (move.line_number,))
                        continue
                    elif move.location_id.id == quarantine_loc_id and wizard.dest_location_id.id in restr_loc_ids and\
                            move.reason_type_id.id != int_move_rt_id:
                        warn_msg.append(_('Line %s: If the Source Location is "Quarantine (analyze)" and the Destination Location is a Stock location, an Intermediate Stocks location or an EPREP Stocks location, the only authorized Reason Type is "7 Internal Move"\n')
                                        % (move.line_number,))
                        continue
                    elif move.reason_type_id.id and move.location_id.id in restr_qua_loc_ids and\
                            wizard.dest_location_id.id == exp_dam_scrap_loc_id:
                        loss_rt_id = data_obj.get_object_reference(cr, uid, 'reason_types_moves', 'reason_type_loss')[1]
                        loss_children_rt_ids = self.pool.get('stock.reason.type').search(cr, uid, [('parent_id', '=', loss_rt_id)], context=context)
                        if move.reason_type_id.id not in loss_children_rt_ids:
                            warn_msg.append(_('Line %s: If the Source Location is a Stock location, an Intermediate Stocks location, an EPREP Stocks location or "Quarantine (analyze)" and the Destination Location is "Expired / Damaged / For Scrap", the only authorized Reason Types are "12.1 Loss / Scrap", "12.2 Loss / Sample", "12.3 Loss / Expiry", "12.4 Loss / Damage" and "12.5 Loss / Batch Recall"\n')
                                            % (move.line_number,))
                            continue
                    elif move.reason_type_id.id == destr_rt_id and (move.location_id.id != exp_dam_scrap_loc_id or
                                                                    wizard.dest_location_id.id != destr_loc_id):
                        warn_msg.append(_('Line %s: The Reason Type "23 Destruction" can only be selected if the Source Location is "Expired / Damaged / For Scrap" and the Destination Location is "Destruction"\n')
                                        % (move.line_number,))
                        continue

                    nb += 1
                    move_obj.write(cr, uid, [move.id], {'location_dest_id': wizard.dest_location_id.id}, context=context)

                else: # out
                    if move.location_id.id == wizard.src_location_id.id:
                        move_changed.append(move.id)
                        continue
                    if not loc_obj.search_exist(cr, uid, [('picking_ticket_src', '=', move.product_id.id), ('id', '=', wizard.src_location_id.id)], context=context):
                        warn_msg.append(_('Line %s : The new source location is not compatible with the product type, so the destination location has not been changed for this move. \n') % move.line_number)
                        continue

                    new_data = {'location_id': wizard.src_location_id.id}
                    if move.state == 'assigned':
                        new_data['state'] = 'confirmed'
                    move_changed.append(move.id)
                    move_obj.write(cr, uid, [move.id], new_data, context=context)
                    nb += 1

            if move_changed:
                move_obj.action_assign(cr, uid, move_changed)
            if nb:
                if wizard.type == 'internal':
                    warn_msg.append(_('The destination location has been changed on %d stock moves.') % (nb,))
                else:
                    warn_msg.append(_('The source location has been changed on %d stock moves.') % (nb,))
            else:
                warn_msg.append(_('No change on location'))


            self.write(cr, uid, [wizard.id], {'warn_msg': "\n".join(warn_msg),
                                              'state': 'end'}, context=context)

            self.infolog(cr, uid, "The location has been changed on picking id:%s (%s) to id:%s (%s)" % (
                wizard.picking_id.id,
                wizard.picking_id.name,
                wizard.dest_location_id.id or wizard.src_location_id.id,
                wizard.dest_location_id.name or wizard.src_location_id.name,
            ))

        return {'type': 'ir.actions.act_window',
                'res_model': 'change.dest.location',
                'res_id': ids[0],
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'context': context}

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        if context is None:
            context = {}
        res = super(change_dest_location, self).fields_view_get(cr, uid, view_id=view_id, view_type=view_type, context=context, toolbar=toolbar, submenu=submenu)
        has_selection = context.get('button_selected_ids')
        view_xml = etree.fromstring(res['arch'])
        if has_selection:
            fields = view_xml.xpath("//button[@name='change_dest_location']")
            #fields[0].set('string',  _('Change location - All lines'))
            fields[0].set('invisible', '1')
        else:
            fields = view_xml.xpath("//button[@name='change_dest_location_selected']")
            fields[0].set('invisible', '1')
        res['arch'] = etree.tostring(view_xml, encoding='unicode')
        return res

change_dest_location()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
