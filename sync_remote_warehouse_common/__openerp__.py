{
    'name': 'Remote Warehouse USB Synchronisation Engine Common Functionality',
    'description': """
    Provides functionality common to both the sync_remote_warehouse and sync_remote_warehouse_server modules
    """,
    'category': 'Tools',
    'author': 'OpenERP SA',
    'developer': 'Max Mumford',
    'installable': True,
    'function': [
        ('workflow.witm_trans', 'generate_sd_refs')
    ]
}
