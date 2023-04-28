# -*- coding: utf-8 -*-

from osv import fields, osv


class PhysicalInventoryImportWizard(osv.osv_memory):
    _name = "physical.inventory.import.wizard"
    _description = "Physical inventory import wizard"

    _columns = {
        'message': fields.text('Message', readonly=True),
        'line_ids': fields.one2many('physical.inventory.import.line.wizard', 'parent_id', string='Details'),
        'inventory_id': fields.many2one('physical.inventory', 'PI', readonly=1),
    }

    def action_close(self, cr, uid, ids, context=None):
        return self.close_action()

    def message(self, cr, button_uid, title, message, context=None):
        uid = hasattr(button_uid, 'realUid') and button_uid.realUid or button_uid
        return {
            'name': title,
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': self._name,
            'res_id': self.create(cr, uid, {'message': message}, context=context),
            'type': 'ir.actions.act_window',
            'view_id': [self.get_view_by_name(cr, uid, 'physical_inventory_import_wizard_view_fullerror')],
            'target': 'new',
            'context': context or {},
        }

    def message_box_noclose(self, cr, button_uid, title, message, context=None):
        uid = hasattr(button_uid, 'realUid') and button_uid.realUid or button_uid
        return {
            'name': title,
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': self._name,
            'res_id': self.create(cr, uid, {'message': message}, context=context),
            'type': 'ir.actions.act_window',
            'view_id': [self.get_view_by_name(cr, uid, 'physical_inventory_import_wizard_view_noclose')],
            'target': 'new',
            'context': context or {},
        }

    def message_box(self, cr, button_uid, title, message, context=None):
        uid = hasattr(button_uid, 'realUid') and button_uid.realUid or button_uid
        return {
            'name': title,
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': self._name,
            'res_id': self.create(cr, uid, {'message': message}, context=context),
            'type': 'ir.actions.act_window',
            'view_id': [self.get_view_by_name(cr, uid, 'physical_inventory_import_wizard_view')],
            'target': 'new',
            'context': context or {},
        }

    def _set_action_for_all(self, cr, uid, ids, action, context=None):
        lines = self.pool.get('physical.inventory.import.line.wizard')
        line_ids = lines.search(cr, uid, [('parent_id', 'in', ids)])
        lines.write(cr, uid, line_ids, {'action': action}, context=context)

    def action_ignore_all(self, cr, uid, ids, context=None):
        self._set_action_for_all(cr, uid, ids, 'ignore', context)
        return self.no_action()

    def action_count_all(self, cr, uid, ids, context=None):
        self._set_action_for_all(cr, uid, ids, 'count', context)
        return self.no_action()

    def action_validate(self, cr, uid, ids, context=None):
        lines = self.pool.get('physical.inventory.import.line.wizard')
        line_ids = lines.search(cr, uid, [('parent_id', 'in', ids)])
        items = lines.read(cr, uid, line_ids, ['line_id', 'action'])
        # Search for undefined actions
        for row in items:
            if not row['action']:
                break
        else:
            # Not found, all actions are defined
            iv_ids = []
            for x in  self.read(cr, uid, ids, ['inventory_id'], context=context):
                if x['inventory_id']:
                    iv_ids.append(x['inventory_id'])
            inventory_obj = self.pool.get('physical.inventory')
            if iv_ids:
                inventory_obj.write(cr, uid, iv_ids, {'discrepancies_generated': True}, context=context)
            inventory_obj.pre_process_discrepancies(cr, uid, items, context=context)
            for iv_id in iv_ids:
                inventory_obj._update_total_product(cr, uid, iv_id, context=context)
            return self.close_action()
        # Found, an action is missing on a line
        return self.no_action()

    @staticmethod
    def close_action():
        return {'type': 'ir.actions.act_window_close'}

    @staticmethod
    def no_action():
        return {}

    def get_view_by_name(self, cr, uid, name):
        return self.pool.get('ir.model.data').get_object_reference(cr, uid, 'stock', name)[1]

    def action_box(self, cr, button_uid, title, items=None, inventory_id=False, context=None):
        uid = hasattr(button_uid, 'realUid') and button_uid.realUid or button_uid
        result = {
            'name': title,
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': self._name,
            'res_id': self.create(cr, uid, {'line_ids': [(0, 0, item) for item in items or []], 'inventory_id': inventory_id}, context=context),
            'type': 'ir.actions.act_window',
            'view_id': [self.get_view_by_name(cr, uid, 'physical_inventory_action_box_wizard_view')],
            'target': 'new',
            'context': context or {},
        }
        return result


PhysicalInventoryImportWizard()


class PhysicalInventoryImportLineWizard(osv.osv_memory):
    _name = "physical.inventory.import.line.wizard"
    _description = "Physical inventory import line wizard"

    ACTION_LIST = [
        ('ignore', 'Ignore'),
        ('count', 'Count as 0'),
    ]

    _columns = {
        'parent_id': fields.many2one('physical.inventory.import.wizard', string='Parent'),
        'line_id': fields.integer('Line ID', readonly=True),
        'message': fields.text('Message', readonly=True),
        'action': fields.selection(ACTION_LIST, string='Action')
    }


PhysicalInventoryImportLineWizard()
