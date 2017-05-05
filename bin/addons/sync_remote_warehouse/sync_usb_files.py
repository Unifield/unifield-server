from osv import osv, fields
import hashlib

class SyncUsbFiles(osv.osv):
    _name = 'sync.usb.files'
    _columns = {
        'sum' : fields.char(string="Check Sum", size=256, readonly=True),
        'date' : fields.datetime(string="Import Date", readonly=True),
    }
    
    def md5(self, filebase64):
        return hashlib.md5(filebase64).hexdigest()

SyncUsbFiles()
