from osv import osv, fields

class ir_model_data(osv.osv):
    _inherit = 'ir.model.data'
    _columns = {
        # The date that marks the last time the object was synchronized using the usb synchronisation engine
        'usb_sync_date':fields.datetime('Last USB Synchronization Date'),
        'usb_message_date': fields.datetime('Last USB message generation Date'),
    } 

ir_model_data()
