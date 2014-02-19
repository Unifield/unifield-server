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
    'init_xml': [
        'data/rule_group_type.xml',
    ],
    'depends': ['sync_client', 'sync_server', 'sync_remote_warehouse_common'],
    'installable': True,
}
