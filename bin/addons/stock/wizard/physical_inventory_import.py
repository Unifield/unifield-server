# -*- coding: utf-8 -*-

from osv import fields, osv


class PhysicalInventoryImportWizard(osv.osv_memory):
    _name = "physical.inventory.import.wizard"
    _description = "Physical inventory import wizard"

    _columns = {
        'message': fields.text('Message', readonly=True),
    }

    def action_close(self, cr, uid, ids, context=None):
        return {'type': 'ir.actions.act_window_close'}

    def message_box(self, cr, uid, title, message, context=None):
        return {
            'name': title,
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': self._name,
            'res_id': self.create(cr, uid, {'message': message}, context=context),
            'type': 'ir.actions.act_window',
            'target': 'new',
            'context': context or {},
        }


PhysicalInventoryImportWizard()
