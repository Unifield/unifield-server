from osv import orm

super_get_unique_xml_name = orm.orm.get_unique_xml_name

def get_unique_xml_name(self, cr, uid, uuid, table_name, res_id):
    sd_ref = super_get_unique_xml_name(self, cr, uid, uuid, table_name, res_id)
    entity = self.pool.get('sync.client.entity').get_entity(cr, uid)

    # state checks
    if 'usb_instance_type' in entity._columns.keys() and entity.usb_instance_type == 'remote_warehouse':
        sd_ref += "/RW"
    return sd_ref

orm.orm.get_unique_xml_name = get_unique_xml_name

def usb_need_to_push(self, cr, uid, context=None):
    """

    Check if records need to be pushed to the next USB synchronization process
    or not.

    One of these conditions need to match:
        - Last modification > clone_date
        - sync_date > clone_date

    ~ AND ~

    One of these conditions needs to match: 
        - usb_sync_date < last_modification
        - usb_sync_date < sync_date
        - usb_sync_date is not set
        - record is deleted
        - watched fields are present in modified fields

    Return type:
        - it returns a list of ids to push.

    :param cr: database cursor
    :param uid: current user id
    :param context: optional context arguments, like lang, time zone
    :type context: dictionary
    :return: list of ids that need to be pushed (or False for per record call)

    """

    clone_date = self.pool.get('sync.client.entity').get_entity(cr, uid, context).clone_date


    # Optimization for not deleted records:
    # Filter data where sync_date < last_modification OR sync_date IS NULL
    cr.execute("""\
            SELECT res_id
                FROM ir_model_data
                WHERE module = 'sd' AND
                      model = %s AND
                      (last_modification > %s OR sync_date > %s OR (last_modification is null and sync_date is null))
                      AND
                      (usb_sync_date < last_modification OR usb_sync_date < sync_date OR usb_sync_date IS NULL)""", (self._name, clone_date, clone_date))

    return [row[0] for row in cr.fetchall()]

orm.orm.usb_need_to_push = usb_need_to_push
