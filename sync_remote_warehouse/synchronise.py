from osv import osv, fields
import base64
import zipfile
from cStringIO import StringIO
import csv
import copy
from tools.translate import _

IMPORT_ERROR_NOT_CSV = 'Not a CSV file'
IMPORT_ERROR_NOT_OBJECT = 'Could not find object in object pool'

def _update_usb_sync_step(obj, cr, uid, step):
    entity_pool = obj.pool.get('sync.client.entity')
    entity = entity_pool.get_entity(cr, uid)
    return entity_pool.write(cr, uid, entity.id, {'usb_sync_step': step})

def pull(obj, cr, uid, uploaded_file_base64, context=None):
    """
    Takes the base64 for the uploaded zip file, unzips the csv files, parses them and inserts them into the database.
    @param uploaded_file_base64: The Base64 representation of a file - direct from the OpenERP api, i.e. wizard_object.pull_data
    @return: A dictionary of the CSV files enclosed in the ZIP, with their import status. Refer to STATIC error codes in this file
    """
    
    if obj.pool.get('sync.client.entity').get_entity(cr, uid, context).usb_sync_step not in ['push_performed', 'first_sync']:
        raise osv.except_osv('Cannot Pull', 'We cannot perform a Pull until we have performed a Pushed')
    
    # decode base64 and unzip
    uploaded_file = base64.decodestring(uploaded_file_base64)
    zip_stream = StringIO(uploaded_file)
    zip_file = zipfile.ZipFile(zip_stream, 'r')
    
    # loop through csv files in zip, parse them and add them to import_data dictionary to be processed later
    update_received_model_name = 'sync_remote_warehouse.update_received'
    
    if '%s.csv' % update_received_model_name not in zip_file.namelist():
        raise osv.except_osv(_('USB Synchronisation Data Not Found'), _('The zip file must contain a file called sync_remote_warehouse.update_received.csv which contains the data for the USB Synchronisation. Please check your file...'))
        
    # get CSV object to read data
    csv_file = zip_file.read('%s.csv' % update_received_model_name)
    csv_reader = csv.reader(StringIO(csv_file))
    
    import_data = {}
    results = {}
    first = True
    fields = []
    data = []
    
    # loop through csv rows and insert into fields or data array
    for row in csv_reader:
        if first:
            fields = row
            first = False
        else:
            data.append(row)
            
    zip_file.close()
    
    # insert into import_data
    import_data['fields'] = fields
    import_data['data'] = data
    
    # do importation and set result[model] = [True/False, [any error messages,...]]
    model_pool = obj.pool.get(update_received_model_name)
    import_error = None
    
    try:
        model_pool.import_data(cr, uid, fields, data, context=context)
    except Exception as e:
        import_error =  '%s %s: %s' % (_('Import Error: '), type(e), str(e))
    except KeyError as e:
        import_error =  '%s %s: %s' % (_('Import Error: '), type(e), str(e)) 
    except ValueError as e:
        import_error =  '%s %s: %s' % (_('Import Error: '), type(e), str(e))
    
    # run updates
    updates_ran = None
    run_error = ''
    context_usb = dict(copy.deepcopy(context), usb_sync_update_push=True)
    if not import_error:
        try:
            entity_pool = obj.pool.get('sync.client.entity')
            updates_ran = entity_pool.execute_updates(cr, uid, logger=None, context=context_usb)
            _update_usb_sync_step(obj, cr, uid, 'pull_performed')
        except AttributeError, e:
            run_error = '%s: %s' % (type(e), str(e))

    # increment usb sync step and return results
    return (len(data), import_error, updates_ran, run_error)

def validate(obj, cr, uid, ids, context=None):
    
    # init
    entity_pool = obj.pool.get('sync.client.entity')
    entity = entity_pool.get_entity(cr, uid, context)
    context_usb = dict(copy.deepcopy(context), usb_sync_update_push=True)
    
    # check step
    if entity.usb_sync_step != 'pull_performed':
        raise osv.except_osv('Cannot Validated', 'We cannot Validate the last Pull until we have performed a Pull')
    
    # get session id and latest updates
    session_id = entity.session_id
    update_pool = obj.pool.get('sync_remote_warehouse.update_to_send')
    update_ids = update_pool.search(cr, uid, [('session_id', '=', session_id)], context=context_usb)
    
    # mark latest updates as sync finished (set usb_sync_date) and clear entity session_id
    update_pool.sync_finished(cr, uid, update_ids, context=context_usb)
    entity_pool.write(cr, uid, entity.id, {'session_id' : ''}, context=context_usb)
    
    # increment usb sync step
    _update_usb_sync_step(obj, cr, uid, 'pull_validated')
    
def push(obj, cr, uid, ids, context=None):
    
    if obj.pool.get('sync.client.entity').get_entity(cr, uid, context).usb_sync_step not in ['pull_validated', 'first_sync']:
        raise osv.except_osv('Cannot Push', 'We cannot perform a Push until we have Validated the last Pull')
    
    # prepare
    context_usb = dict(copy.deepcopy(context), usb_sync_update_push=True)
    entity = obj.pool.get('sync.client.entity')
    
    # udpate rules then create updates_to_send
    updates_count = entity.create_update(cr, uid, context=context_usb)
    
    if updates_count:
        updates, deletions = entity.create_update_zip(cr, uid, context=context_usb)
    else:
        return 0
    
    _update_usb_sync_step(obj, cr, uid, 'push_performed')
    
    return updates, deletions
