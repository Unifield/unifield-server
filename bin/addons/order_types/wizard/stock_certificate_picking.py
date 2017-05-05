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

class stock_certificate_picking(osv.osv_memory):
    _name = 'stock.certificate.picking'
    _description = 'Attach a certificate to an Incoming donation'
    
    _columns = {
        'donation_ok': fields.boolean(string='Have you a certificate of donation to attach to this picking ?'),
        'attachment': fields.binary('Certificate of donation'),
        'att_fname': fields.char('Filename',size=256),
        'picking_id': fields.many2one('stock.picking', 'Picking id'),
    }
    
    def attach_certificate(self, cr, uid, ids, context=None):
        '''
        Attach the certificate if any and goes to the next step
        '''
        if context is None:
            context = {}
        attachment = self.pool.get('ir.attachment')
        
        picking_ids = []
        for cert in self.browse(cr, uid, ids, context=context):
            picking_ids.append(cert.picking_id.id)
            if cert.donation_ok:
                self.pool.get('stock.picking').write(cr, uid, [cert.picking_id.id], {'attach_cert': True})
                if cert.att_fname and cert.attachment:
                    # Make the attachment
                    import base64
                    data_attach = {
                            'name': cert.att_fname,
                            'datas': cert.attachment,
                            'datas_fname': cert.att_fname,
                            'description': 'Certificate of Donation',
                            'res_model': 'stock.picking',
                            'res_id': cert.picking_id.id,}
                    attachment.create(cr, uid, data_attach)
                
        context.update({'attach_ok': True})
                
        return self.pool.get('stock.picking').action_process(cr, uid, picking_ids, context=context)
    
stock_certificate_picking()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
