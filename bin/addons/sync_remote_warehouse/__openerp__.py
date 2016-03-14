{
    'name': 'Remote Warehouse USB Synchronisation Engine',
    'description': """
    Provides the ability to synchronize data between two instances using physical files, as opposed to an internet connection
    """,
    'category': 'Tools',
    'author': 'OpenERP SA',
    'developer': 'Max Mumford',
    'init_xml': [
        'data/setup_remote_warehouse.xml',
        'data/usb_synchronisation.xml',
        'data/usb_recovery.xml',
    ],
    'update_xml': [
        'views/update.xml',
        'views/message.xml',
        'views/setup_remote_warehouse.xml',
        'views/download_dump.xml',
        'views/usb_synchronisation.xml',
        'views/usb_recovery.xml',
        'views/sync_monitor.xml',
    ],
    'depends': ['sync_remote_warehouse_common'],
    'installable': True,
}
