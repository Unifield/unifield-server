from osv import osv, fields
import base64
import zipfile
from cStringIO import StringIO
import csv

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
    import_data = {}
    results = {}
    for file_name in zip_file.namelist():
        
        if file_name[-4:] != '.csv':
            results[file_name] = IMPORT_ERROR_NOT_CSV
            continue
        
        model_name = file_name[:-4]
        
        if not obj.pool.get(model_name):
            results[model_name] = IMPORT_ERROR_NOT_OBJECT
            continue
        
        # get CSV object to read data
        csv_file = zip_file.read(file_name)
        csv_reader = csv.reader(StringIO(csv_file))
        
        first = True
        fields = []
        data = []
        
        # loop through csv rows and insert into fields or data
        for data_line in csv_reader:
            if first:
                fields = data_line
                first = False
            else:
                data.append(data_line)
        
        # insert into import_data
        import_data[model_name] = {}
        import_data[model_name]['fields'] = fields
        import_data[model_name]['data'] = data
    
    # do importation and set result[model] = [True/False, [any error messages,...]]
    for model_name in import_data.keys():
        model_pool = obj.pool.get(model_name)
        csv_result = [True,[]]
        try:
            model_pool.import_data(cr, uid, fields, data, mode='update', context=None)
            results[model_name] = True
        except Exception as e:
            csv_result[0] = False
            csv_result[1].append('%s: %s' % (type(e), str(e))) # KeyError: 'state'
        except KeyError as k:
            csv_result[0] = False
            csv_result[1].append('%s: %s' % (type(e), str(k))) 
        except ValueError as v:
            csv_result[0] = False
            csv_result[1].append('%s: %s' % (type(e), str(v)))
        results[model_name] = tuple(csv_result)

    # clean up and increment usb sync step
    zip_file.close()
    _update_usb_sync_step(obj, cr, uid, 'pull_performed')
    
    return results

def validate(obj, cr, uid, ids, context=None):
    
    if obj.pool.get('sync.client.entity').get_entity(cr, uid, context).usb_sync_step != 'pull_performed':
        raise osv.except_osv('Cannot Validated', 'We cannot Validate the last Pull until we have performed a Pull')
    
    _update_usb_sync_step(obj, cr, uid, 'pull_validated')
    
def push(obj, cr, uid, ids, context=None):
    
    if obj.pool.get('sync.client.entity').get_entity(cr, uid, context).usb_sync_step not in ['pull_validated', 'first_sync']:
        raise osv.except_osv('Cannot Push', 'We cannot perform a Push until we have Validated the last Pull')
    
    _update_usb_sync_step(obj, cr, uid, 'push_performed')