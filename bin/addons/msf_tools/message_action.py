#!/usr/bin/env python
# -*- coding: utf-8 -*-

from osv import osv
from osv import fields
from tools.translate import _


class message_action(osv.osv_memory):
    _name = 'message.action'

    _columns = {
        'res_id': fields.integer('res_id'),
        'yes_action': fields.char('Action yes', size=256),
        'no_action': fields.char('Action No', size=256),
        'message': fields.text('Message'),
        'title': fields.char('Title', size=256),
        'yes_label': fields.char('Yes Label', size=256),
        'no_label': fields.char('No Label', size=256),
        'refresh_o2m': fields.char('refresh on yes close', size=256),
    }

    _defaults = {
        'yes_label': _('Yes'),
        'no_label': _('No'),
        'message': ' ',
        'refresh_o2m': False
    }
    def pop_up(self, cr, uid, ids, context=None):
        if context is None:
            context = {}
        context['message_action_wizard_id'] = ids[0]
        wiz = self.browse(cr, uid, ids[0], context=context)
        return {
            'name': wiz.title,
            'type': 'ir.actions.act_window',
            'res_model': 'message.action',
            'target': 'new',
            'view_mode': 'form',
            'view_type': 'form',
            'res_id': [wiz.id],
            'context': context,
            'height': '200px',
            'width': '720px',
            'keep_open': True,
        }


    def do_yes(self, cr, uid, ids, context=None):
        wiz = self.browse(cr, uid, ids[0], context=context)
        action_return = wiz.yes_action(cr, uid, context)
        if wiz.refresh_o2m and not isinstance(action_return, dict):
            # on PO Validation / Confirmation refresh o2m lines
            return {'type': 'ir.actions.act_window_close', 'o2m_refresh': wiz.refresh_o2m}

        return action_return

    def do_no(self, cr, uid, ids, context=None):
        wiz = self.browse(cr, uid, ids[0], context=context)
        if not wiz.no_action:
            return {'type': 'closepref'}
            #return {'type': 'ir.actions.act_window_close'}

    def fields_view_get(self, cr, uid, view_id=None, view_type='form', context=None, toolbar=False, submenu=False):
        wiz = self.read(cr, uid, context['message_action_wizard_id'], ['no_label', 'yes_label'], context=context)
        res = super(message_action, self).fields_view_get(cr, uid, view_id, view_type, context, toolbar, submenu)
        for x in ['yes_action', 'no_action']:
            if x in res['fields']:
                del(res['fields'][x])

        res['arch'] = """
            <form string="">
                    <field name="message" nolabel="1" colspan="4" widget="html_text"/>
                    <separator colspan="4"/>
                    <button string="%(no_label)s" icon="gtk-cancel" colspan="2" name="do_no" type="object"/>
                    <button string="%(yes_label)s" icon="gtk-apply" colspan="2" name="do_yes" type="object"/>
            </form>
        """ % wiz
        return res

message_action()
