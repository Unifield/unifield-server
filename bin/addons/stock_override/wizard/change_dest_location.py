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


class change_dest_location(osv.osv_memory):
    _name = 'change.dest.location'

    _columns = {
        'picking_id': fields.many2one('stock.picking', string='Internal move', required=True),
        'dest_location_id': fields.many2one('stock.location', string='Destination location', required=True),
        'warn_msg': fields.text(string='Warning message', readonly=True),
        'state': fields.selection([('start', 'Start'), ('end', 'Finished')], string='State', readonly=True),
    }

    _defaults = {
        'state': lambda *a: 'start',
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

        picking = self.pool.get('stock.picking').browse(cr, uid, vals.get('picking_id'), context=context)
        if picking.type != 'internal':
            raise osv.except_osv(_('Error'), _('The modification of the destination locations is only available for Internal moves.'))
        return super(change_dest_location, self).create(cr, uid, vals, context=context)


    def close_window(self, cr, uid, ids, context=None):
        '''
        Close window
        '''
        if not context:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        return {'type': 'ir.actions.act_window_close'}

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


    def change_dest_location(self, cr, uid, ids, context=None):
        '''
        Change the destination location for all stock moves
        '''
        if not context:
            context = {}

        if isinstance(ids, (int, long)):
            ids = [ids]

        loc_obj = self.pool.get('stock.location')
        move_obj = self.pool.get('stock.move')

        for wizard in self.browse(cr, uid, ids, context=context):
            warn_msg = ''
            show_warn_msg = False
            for move in wizard.picking_id.move_lines:
                # Check if the new destination location is not the source location
                if move.location_id.id == wizard.dest_location_id.id:
                    show_warn_msg = True
                    warn_msg += _('Line %s : The new destination location is the same as the source location of the move, so the destination location has not been changed for this move. \n') % move.line_number
                    continue

                if move.state not in ('draft', 'confirmed', 'assigned'):
                    show_warn_msg = True
                    warn_msg += _('Line %s : The state \'%s\' of the move doesn\'t allow a modification of the destination location. \n') % (move.line_number, self.getSelection(move, 'state'))
                    continue


                # Check if the new destination location is compatible with the product type
                location_ids = loc_obj.search(cr, uid, [('internal_dest', '=', move.product_id.id), 
                                                        ('usage', '!=', 'view')], context=context)
                if wizard.dest_location_id.id not in location_ids:
                    show_warn_msg = True
                    warn_msg += _('Line %s : The new destination location is not compatible with the product type, so the destination location has not been changed for this move. \n') % move.line_number
                    continue

                self.pool.get('stock.move').write(cr, uid, [move.id], {'location_dest_id': wizard.dest_location_id.id}, context=context)

            if not show_warn_msg:
                warn_msg = _('The destination location has been changed on all stock moves.')

            self.write(cr, uid, [wizard.id], {'warn_msg': warn_msg,
                                              'state': 'end'}, context=context)

            self.infolog(cr, uid, "The destination location has been changed on Internal picking id:%s (%s) to id:%s (%s)" % (
                wizard.picking_id.id,
                wizard.picking_id.name,
                wizard.dest_location_id.id,
                wizard.dest_location_id.name,
            ))

        return {'type': 'ir.actions.act_window',
                'res_model': 'change.dest.location',
                'res_id': ids[0],
                'view_type': 'form',
                'view_mode': 'form',
                'target': 'new',
                'context': context}

change_dest_location()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
