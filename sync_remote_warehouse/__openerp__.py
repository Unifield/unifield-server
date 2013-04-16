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
    ],
    'update_xml': [
        'views/logging.xml',
        'views/setup_remote_warehouse.xml',
        'views/usb_synchronisation.xml',
    ],
    'depends': ['sync_client'],
    'installable': True,
}
