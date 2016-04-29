# encoding=utf-8
import psycopg2
import locale
import psycopg2.extras
import time
import sys
import oerplib
import copy

start_time = time.time()
locale.setlocale(locale.LC_ALL, '')

HOST_ORIGIN = 'localhost'
PORT_ORIGIN = '11041'
DB_ORIGIN = 'SP_222_20160425_OCG_nc'

HOST_COMPRESSED = 'localhost'
PORT_COMPRESSED = '11031'
DB_COMPRESSED = 'SP_222_20160425_OCG_zip'

# before to launch this script, ensure you have the right privileges on the origin db:
# psql SP_222_20160425_OCG_nc
#SP_222_20160425_OCG_nc=> GRANT ALL PRIVILEGES ON sync_client_update_received to "fm-sp-222-oca-zip";

SDREF_TO_IGNORE = [
    'module_meta_information',
    '_Prodcuts_List_filter_by_creator',  # wrong domain of the rule making the
                                         # script fail
]

conn_origin = psycopg2.connect("dbname=%s" % DB_ORIGIN)
conn_compressed = psycopg2.connect("dbname=%s" % DB_COMPRESSED)

oerp_origin = oerplib.OERP(HOST_ORIGIN, DB_ORIGIN, protocol='netrpc',
                           port=PORT_ORIGIN, timeout=300)
oerp_origin.login('admin', 'admin', DB_ORIGIN)
oerp_compressed = oerplib.OERP(HOST_COMPRESSED, DB_COMPRESSED, protocol='netrpc',
                               port=PORT_COMPRESSED, timeout=300)
oerp_compressed.login('admin', 'admin', DB_COMPRESSED)

# get a list of synchrnoized models
cr = conn_origin.cursor(cursor_factory=psycopg2.extras.DictCursor)
cr.execute("""SELECT DISTINCT(model)
        FROM sync_client_update_received ORDER BY model""", ())
synchronized_model = [x[0] for x in cr.fetchall()]
cr.close()

print 'connexion done'

def update_progress(progress, checked):
    '''Displays or updates a console progress bar
    '''
    bar_length = 50  # Modify this to change the length of the progress bar
    status = ""
    if isinstance(progress, int):
        progress = float(progress)
    if not isinstance(progress, float):
        progress = 0
        status = "error: progress var must be float\r\n"
    elif progress < 0:
        progress = 0
        status = "Halt...\r\n"
    elif progress >= 1:
        progress = 1
        status = "Done...\r\n"
    block = int(round(bar_length * progress))
    progress = round(progress, 3)
    text = "\rPercent: [{0}] {1}% {2} ({3} checked)"\
        .format("#"*block + "-"*(bar_length - block),
                progress * 100, status, checked)
    sys.stdout.write(text)
    sys.stdout.flush()

def diff(a, b):
    '''get differences between two dict
    '''
    ret_dict = {}
    for key, val in a.items():
        if key in b.keys():
            if b[key] != val:
                ret_dict[key] = [val, b[key]]
        else:
            ret_dict[key] = [val]
    return ret_dict

# get all the ir_model_data objects from the origin db:
not_existing_count = 0
object_not_synchronized_count = 0
data_id_list = oerp_origin.search('ir.model.data',
                                  [('model', 'in', tuple(synchronized_model)),
                                   ('name', 'not in', tuple(SDREF_TO_IGNORE)),
                                   ('module', '=', 'sd'),
                                   ])
data_count = len(data_id_list)
counter = 0
time_stamp = time.strftime("%Y%m%d-%H%M%S")
file_name = 'db_comparison_%s.txt' % time_stamp
result_file = open(file_name, "a")

PRINT_SCREEN = True
PRINT_FILE = True
def print_file_and_screen(string):
    if PRINT_FILE:
        result_file.write(string+'\n')
        result_file.flush()
    if PRINT_SCREEN:
        print string
print_file_and_screen('comparing %s with %s' % (DB_ORIGIN, DB_COMPRESSED))
print_file_and_screen('%s object to checks...' % data_count)
for data_object in oerp_origin.browse('ir.model.data', data_id_list):
    if counter % 10 == 0:
        progress = counter/float(data_count)
        update_progress(progress, counter)
    counter += 1
    if not data_object.res_id:
        continue
    sdref = data_object.name
    # check if the related object still exists
    origin_id = oerp_origin.search(data_object.model, [('id', '=',
                                                        data_object.res_id)])
    if not origin_id:
        not_existing_count += 1
        continue
    if not oerp_origin.search('sync.client.update_received',
                              [('sdref', '=', sdref)]):
        # this object has not been syncrhonized
        object_not_synchronized_count += 1
        continue
    origin_obj = oerp_origin.browse(data_object.model, data_object.res_id)
    compressed_data_obj_id = oerp_compressed.search('ir.model.data',
                                                    [('name', '=', sdref)])
    if compressed_data_obj_id:
        compressed_data_obj = oerp_compressed.browse('ir.model.data',
                                                     compressed_data_obj_id[0])
        compressed_local_id = compressed_data_obj.res_id
        compressed_obj = oerp_compressed.browse(data_object.model, compressed_local_id)
        compressed_values = oerp_compressed.read(compressed_data_obj.model, compressed_local_id)
        origin_values = oerp_origin.read(data_object.model, origin_obj.id)
        if origin_values and not compressed_values:
            print_file_and_screen('Objects type %s with sdref %s have no compressed_values : %r' %
                    (data_object.model, sdref, compressed_values))
            continue

        compressed_instance_id = oerp_compressed.read('sync.client.entity', 1, ['identifier'])['identifier']
        origin_instance_id = oerp_origin.read('sync.client.entity', 1, ['identifier'])['identifier']

        def set_xmlid_for_many2one(current_obj, eoerp, values, instance_id):
            '''
            replace the id of the many2one fields by their corresponding xml_id
            to be able to compare it with the compressed values as the id might differ
            '''
            # remove id:
            values.pop('id')

            for field, value in values.items():
                if field in ('menu_access', 'group_ids') and isinstance(value, list):
                    # some list need to be sorted to be compared
                    values[field] = sorted(value)
                field_type = None
                if value and hasattr(current_obj.__osv__['columns'][field], 'type'):
                    field_type = getattr(current_obj.__osv__['columns'][field], 'type', False)
                else:
                    continue
                if field_type == 'many2one':
                    model = current_obj.__osv__['columns'][field].relation
                    imd_id = eoerp.search('ir.model.data',
                        [('model', '=', model),
                         ('res_id', '=' , value[0])])
                    if imd_id:
                        imd_obj = eoerp.browse('ir.model.data', imd_id[0])
                        xml_id = imd_obj.name
                        if xml_id:
                            if xml_id.startswith(instance_id):
                                xml_id = xml_id.split(instance_id)[1]
                            # replace the id of the many2one with the correponding xml_id
                            values[field] = (xml_id, values[field][1])
                elif field_type == 'many2many':
                    model = current_obj.__osv__['columns'][field].relation
                    imd_id_list = eoerp.search('ir.model.data',
                        [('model', '=', model),
                         ('res_id', 'in' , value)])
                    if imd_id_list:
                        imd_obj_list = eoerp.browse('ir.model.data', imd_id_list)
                        value_list = []
                        for imd_obj in imd_obj_list:
                            xml_id = imd_obj.name
                            if xml_id:
                                if xml_id.startswith(instance_id):
                                    xml_id = xml_id.split(instance_id)[1]
                                # replace the id of the many2one with the correponding xml_id
                                value_list.append(xml_id)
                        value_list.sort()
                        values[field] = value_list
            return values

        origin_values = set_xmlid_for_many2one(origin_obj, oerp_origin, origin_values, origin_instance_id)
        compressed_values = set_xmlid_for_many2one(compressed_obj, oerp_compressed, compressed_values, compressed_instance_id)

        if origin_values != compressed_values:
            diff_result = diff(origin_values, compressed_values)
            if diff_result:
                print_file_and_screen('Objects type %s with sdref %s are different : %r' %
                                      (data_object.model, sdref, diff_result))
            else:
                diff_result2 = set(compressed_values) - set(origin_values)
                print_file_and_screen('Object type %s with sdref %s have different values on '
                                      'compressed version : %r' % (data_object.model, sdref, diff_result2))
    else:
        print_file_and_screen("Object with sdref %s doesn't exists on compressed db" % data_object.name)

print_file_and_screen('%s objects have never been synchronized' %
                      object_not_synchronized_count)
print_file_and_screen('%s objects have an sdref but don\'t exists in base.' %
                      not_existing_count)
elapsed_time = time.time() - start_time
minute, second = divmod(elapsed_time, 60)
hour, minute = divmod(minute, 60)
print_file_and_screen("Elapsed time : %d:%02d:%02d" % (hour, minute, second))
result_file.close()
