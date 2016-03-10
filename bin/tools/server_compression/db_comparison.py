# encoding=utf-8
import psycopg2
import locale
import psycopg2.extras
import time
import oerplib
import traceback
import copy

start_time = time.time()
locale.setlocale(locale.LC_ALL, '')

#HOST_ORIGIN = 'fm-sp-222.uf5.unifield.org'
HOST_ORIGIN = 'localhost'
PORT_ORIGIN = '10091'
DB_ORIGIN = 'fm_sp_222_OCB_ALL_GROUP_V6'

#HOST_COMPRESSED = 'fm-sp-222-ocg-compressed.uf5.unifield.org'
HOST_COMPRESSED = 'localhost'
PORT_COMPRESSED = '10251'
DB_COMPRESSED = 'fm_sp_222_OCB_ALL_cpressV1'

MODEL_TO_IGNORE = [
    'financing.contract.contract',
    'deleted.object',
    'ir.cron',
]

FIELDS_TO_IGNORE = [
    'date',
]

SDREF_TO_IGNORE = [
    'module_meta_information',
    '_Prodcuts_List_filter_by_creator', # wrong domain of the rule making the
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

db_origin_id = oerp_origin.get('sync.client.entity').browse(1).identifier
db_compressed_id = oerp_compressed.get('sync.client.entity').browse(1).identifier

# get a list of synchrnoized models
cr = conn_origin.cursor(cursor_factory=psycopg2.extras.DictCursor)
cr.execute("""SELECT DISTINCT(model)
        FROM sync_client_update_received ORDER BY model""", ())
synchronized_model = [x[0] for x in cr.fetchall()]
cr.close()

def diff(a, b):
     ret_dict = {}
     for key,val in a.items():
         if b.has_key(key):
             if b[key] != val:
                 ret_dict[key] = [val,b[key]]
         else:
             ret_dict[key] = [val]
     return ret_dict

# get all the ir_model_data objects from the origin db:
deleted_object_count = 0
model_to_ignore_count = 0
object_not_synchronized_count = 0
data_id_list = oerp_origin.search('ir.model.data')
data_count = len(data_id_list)
counter = 0
try:
    for data_object in oerp_origin.browse('ir.model.data', data_id_list):
        if data_object.model in MODEL_TO_IGNORE or\
                data_object.model not in synchronized_model:
            model_to_ignore_count += 1
            continue
        if not data_object.res_id:
            continue
        # check if the related object still exists
        origin_id = oerp_origin.search(data_object.model, [('id', '=',
            data_object.res_id)])
        if not origin_id:
            deleted_object_count += 1
            continue
        #if data_object.name.startswith(db_origin_id):
        #    sdref = data_object.name.replace(db_origin_id, db_compressed_id)
        #else:
        sdref = data_object.name

        if sdref in SDREF_TO_IGNORE:
            continue

        if not oerp_origin.search('sync.client.update_received', [('sdref',
            '=', data_object.name)]):
            # this object has not been syncrhonized
            object_not_synchronized_count += 1
            continue

        try:
            origin_obj = oerp_origin.browse(data_object.model, data_object.res_id)
        except:
            print 'Object with sdref %s cannot been checked' % data_object.name
            continue
        compressed_data_obj_id = oerp_compressed.search('ir.model.data',
                [('name', '=', sdref)])
        if compressed_data_obj_id:
            compressed_data_obj = oerp_compressed.browse('ir.model.data',
                    compressed_data_obj_id[0])
            compressed_local_id = compressed_data_obj.res_id
            compressed_obj = oerp_compressed.browse(compressed_data_obj.model,
                    compressed_local_id)
            compressed_values = copy.copy(compressed_obj.__data__['values'])
            origin_values = copy.copy(origin_obj.__data__['values'])
            # remove fields to ignore
            for field in FIELDS_TO_IGNORE:
                if field in compressed_values:
                    compressed_values.pop(field)
                if field in origin_values:
                    origin_values.pop(field)
            if origin_values != compressed_values:
                diff_result = diff(origin_values, compressed_values)
                if diff_result:
                    print 'Objects type %s with sdref %s are different : %r\n' % \
                            (data_object.model, sdref, diff_result)
                else:
                    diff_result2 = set(compressed_values) - set(origin_values)
                    print 'Object type %s with sdref %s have different values on '
                    'compressed version : %r\n' % diff_result2
        else:
            print "Object with sdref %s doesn't exists on compressed db" % data_object.name
        counter+=1
        if counter % 1000 == 0:
            print '%s/%s objects parsed' % (counter, data_count)

            # reset the connexion as seems to be a problem if it not reset for
            # a long time
            conn_origin = psycopg2.connect("dbname=%s" % DB_ORIGIN)
            conn_compressed = psycopg2.connect("dbname=%s" % DB_COMPRESSED)

            oerp_origin = oerplib.OERP(HOST_ORIGIN, DB_ORIGIN, protocol='netrpc',
                                       port=PORT_ORIGIN, timeout=300)
            oerp_origin.login('admin', 'admin', DB_ORIGIN)
            oerp_compressed = oerplib.OERP(HOST_COMPRESSED, DB_COMPRESSED, protocol='netrpc',
                                           port=PORT_COMPRESSED, timeout=300)
            oerp_compressed.login('admin', 'admin', DB_COMPRESSED)

            db_origin_id = oerp_origin.get('sync.client.entity').browse(1).identifier
            db_compressed_id = oerp_compressed.get('sync.client.entity').browse(1).identifier
except Exception as e:
    print traceback.format_exc()
    import pdb; pdb.set_trace()

print '%s objects have never been synchronized' % object_not_synchronized_count
print '%s models ignored.' % model_to_ignore_count
print '%s objects have an sdref but don\'t exists in base.' % deleted_object_count
elapsed_time = time.time() - start_time
minute, second = divmod(elapsed_time, 60)
hour, minute = divmod(minute, 60)
print "Elapsed time : %d:%02d:%02d" % (hour, minute, second)
