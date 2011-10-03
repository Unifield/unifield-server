'''
Created on 12 sept. 2011

@author: openerp
'''
from osv import osv
from osv import fields

class test(osv.osv_memory):
    
    _name = "sync.client.test.create_data"
    
    _rec_name = 'nb'
    _columns = {
            'nb' : fields.integer('NB of record to create', required=True),
            'partner_name' : fields.char('Partner Prefix', size=64, required=True),
    }
    
    
    def create_partner(self, cr, uid, ids, context=None):
        for wiz in self.browse(cr, uid, ids, context=context):
            for i in xrange(0, wiz.nb):
                self.pool.get('res.partner').create(cr, uid,  {'name' : '%s%s' % (wiz.partner_name, i), 
                            'address' : [(0,0, {'name' : '%s%s' % (wiz.partner_name, i)})] }, context=context)
                
        return {'type': 'ir.actions.act_window_close'}
    
test()