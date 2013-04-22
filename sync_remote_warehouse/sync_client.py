# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
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

from osv import osv, fields, orm
from tools.translate import _
import csv
import base64
from zipfile import ZipFile
from datetime import datetime

class Entity(osv.osv):
    _inherit = "sync.client.entity"

    def create_update_zip(self, cr, uid, logger=None, context=None):
        """
        Create packages out of all total_updates marked as "to send", format as CSV, zip and attach to entity record 
        """
        
        csv_contents = []
        
        def create_package():
            return self.pool.get('sync_remote_warehouse.update_to_send').create_package(cr, uid, entity.session_id, max_packet_size)

        def add_and_mark_as_sent(ids, packet):
            """
            add the package contents to the csv_contents dictionary and mark the package as sent
            @return: (number of total_updates, number of delete_sdref rules)
            """
            
            # create header row if needed
            columns = ['source', 'model', 'version', 'fields', 'values', 'sdref', 'is_deleted']
            if not csv_contents:
                csv_contents.append(columns)
            
            # insert update data
            for update in packet['load']:
                csv_contents.append([
                    entity.name,
                    packet['model'], # model
                    update['version'],
                    packet['fields'],
                    update['values'],
                    update['sdref'],
                    False,
                ])
                
            # insert delete data
            for delete_sdref in packet['unload']:
                csv_contents.append([
                    entity.name,
                    packet['model'],
                    '',
                    '',
                    '',
                    delete_sdref,
                    True,
                ])
            
            self.pool.get('sync_remote_warehouse.update_to_send').write(cr, uid, ids, {'sent' : True}, context=context)
            return (len(packet['load']), len(packet['unload']))

        # get number of update to process
        updates_todo = self.pool.get('sync_remote_warehouse.update_to_send').search(cr, uid, [('sent','=',False)], count=True, context=context)
        if updates_todo == 0:
            return 0
        
        # prepare some variables and create the first package
        max_packet_size = self.pool.get("sync.client.sync_server_connection")._get_connection_manager(cr, uid, context=context).max_size
        entity = self.get_entity(cr, uid, context=context)

        total_updates, total_deletions = 0, 0
        logger_id = None
        package = create_package()
        
        while package:
            # add the package to the csv_contents dictionary and mark it has 'sent'
            new_updates, new_deletions = add_and_mark_as_sent(*package)
            
            # add new updates and deletions to total
            total_updates += new_updates
            total_deletions += new_deletions
            
            # update the log entry with the new total
            if logger:
                if logger_id is None: logger_id = logger.append()
                logger.replace(logger_id, _("USB Push in progress with %d updates and %d deletions processed out of %d total") % (total_updates, total_deletions, updates_todo))
                logger.write()
                
            # create next package
            package = create_package()

        # finished all packages so 
        if logger and (total_updates or total_deletions):
            logger.replace(logger_id, _("USB Push prepared with %d updates and %d deletions equating to %d") % (total_updates, total_deletions, (total_updates + total_deletions)))
            
        # create csv file
        csv_file_name = 'sync_remote_warehouse.update_received.csv'
        with open(csv_file_name, 'wb') as csv_file:
            csv_writer = csv.writer(csv_file, delimiter=',', quotechar='"', quoting=csv.QUOTE_ALL)
            for data_row in csv_contents:
                csv_writer.writerow(data_row)
                
        # compress csv file into zip
        zip_file_name = '%s.zip' % entity.session_id
        with ZipFile(zip_file_name, 'w') as zip_file:
            zip_file.write(csv_file_name)
                
        # add to entity object
        zip_base64 = ''
        with open(zip_file_name, "rb") as zip_file:
            zip_base64 = base64.b64encode(zip_file.read())

        self.write(cr, uid, entity.id, {'usb_last_push_file': zip_base64, 'usb_last_push_date': datetime.now()})
        
        return (total_updates, total_deletions)
    
Entity()
