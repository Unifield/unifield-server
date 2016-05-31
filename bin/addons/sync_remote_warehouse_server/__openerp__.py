{
    'name': 'Remote Warehouse USB Synchronisation Engine Server',
    'description': """
    The server component for the USB Synchronization Engine. Provides modifications to features only available at the server level, like rule views
    """,
    'category': 'Tools',
    'author': 'OpenERP SA',
    'developer': 'Max Mumford',
    'update_xml': [
        'views/sync_update_rule.xml',
        'views/sync_message_rule.xml',
    ],
    'depends': ['sync_server'],
    'installable': True,
}
