#!/usr/bin/env python
# -*- encoding: utf-8 -*-

from osv import osv

class ir_model_data(osv.osv):
    """
    Because XML IDs for imported data are not created as part of the create method,
    inherit ir.model.data to override create to generate button access rights for views
    once they have xml id. We must do this because we need the view xml id to create the
    button access rule sd ref in order to synchronise them once generated at each instance
    """

    _inherit = "ir.model.data"
    
    def create(self, cr, uid, values, context=None):
        """
        If we are creating an xml_id for an ir.ui.view, trigger creation of button access rules
        """
        imd_id = super(ir_model_data, self).create(cr, uid, values, context=context)

        if values['model'] == 'ir.ui.view' and values['module'] not in ['sd', '__export__']:
            self.pool.get('ir.ui.view').generate_button_access_rules(cr, uid, values['res_id'], context=context)

        return imd_id
    
ir_model_data()
