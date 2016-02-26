from datetime import datetime
import base64

from osv import osv, fields

class download_dump(osv.osv_memory):
    """ 
    A wizard that allows the user to download a dump file 
    after it is created with the setup_remote_warehouse wizard 
    """
    def get_dump_file(self, cr, uid, ids, field_name=None, arg=None, context=None):
        res = dict.fromkeys(ids)
        for wizard_id in ids:
            wizard_record = self.browse(cr, uid, wizard_id)
            f = open(wizard_record.dump_path)
            res[wizard_id] = f.read()
            f.close()
        return res
    
    _name = 'download_dump'

    _columns = {
        'dump_path': fields.char('File Location', size="128"),
        'database_dump': fields.function(get_dump_file, method=True, store=False, type='binary', string="Download Backup"),
        'dump_name': fields.char('File name', 40, readonly=True),
    }
    
    _defaults = {
        'dump_name': lambda self, cr, uid, context: '%s_RW-%s.dump' % (cr.dbname, datetime.now().strftime('%Y%m%d-%H%M%S')),
    }
    
download_dump()
