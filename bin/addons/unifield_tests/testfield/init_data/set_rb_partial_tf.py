from oerplib import OERP
import time
import os

"""
Set data for testfield supply ct1 / ct2
"""


DB_PREFIX = ''
SRV_ADDRESS = '%s.rb.unifield.org' % DB_PREFIX
XMLRPC_PORT = ''
UNIFIELD_ADMIN = ''
UNIFIELD_PASSWORD = ''

if os.path.exists('credentials.py'):
    execfile('credentials.py')

def reset_po(oerp):
    po_o = oerp.get('purchase.order')
    po_ids = po_o.search([('state', '=', 'draft')])
    if po_ids:
        po_o.write(po_ids, {'delivery_requested_date': '2030-01-01'})

oerp = OERP(server=SRV_ADDRESS, protocol='xmlrpc', port=XMLRPC_PORT, timeout=3600, version='6.0')
l = oerp.login(UNIFIELD_ADMIN, UNIFIELD_PASSWORD, '%s_SYNC_SERVER' % DB_PREFIX)
ids = oerp.get('sync.server.entity').search([])
oerp.get('sync.server.entity').write(ids, {'user_id': 1})


sync_needed = False
l = oerp.login(UNIFIELD_ADMIN, UNIFIELD_PASSWORD, '%s_HQ1C1' % DB_PREFIX)
prod_o = oerp.get('product.product')
if not prod_o.search([('default_code', '=', 'AZAZA')]):
    print 'Create Prod AZAZA'
    sync_needed = True
    oerp.get('product.product').create({
        'default_code': 'AZAZA',
        'name': 'Product test',
        'procure_method': 'make_to_order',
        'international_status': 1,
        'nomen_manda_0': 5,
        'nomen_manda_1': 9,
        'nomen_manda_2': 23,
        'nomen_manda_3': 483,
    })
reset_po(oerp)
p_ids = oerp.get('res.partner').search([('name', '=', 'ESC'), ('active', 'in', ['t', 'f'])])
if p_ids:
    print 'Update Partner'
    sync_needed = True
    oerp.get('res.partner').write(p_ids, {'active': True})

loc_o = oerp.get('stock.location')
loc_ids = loc_o.search([('name', '=', 'LOG')])
prod_o = oerp.get('product.product')
p1_ids = prod_o.search([('default_code', '=', 'ADAPCABL1S-')])
p2_ids = prod_o.search([('default_code', '=', 'ADAPDCDRB--')])
p3_ids = prod_o.search([('default_code', '=', 'ADAPMEMK1--')])
inv_o = oerp.get('stock.inventory')
inv_id = inv_o.create({
    'name': 'inv %s' % time.time(),
    'inventory_line_id': [
        (0, 0, {'location_id': loc_ids[0], 'product_id': p1_ids[0], 'product_uom': 1, 'product_qty': 1000, 'reason_type_id': 12}),
        (0, 0, {'location_id': loc_ids[0], 'product_id': p2_ids[0], 'product_uom': 1, 'product_qty': 1000, 'reason_type_id': 12}),
        (0, 0, {'location_id': loc_ids[0], 'product_id': p3_ids[0], 'product_uom': 1, 'product_qty': 1000, 'reason_type_id': 12}),
    ],
})
inv_o.action_confirm([inv_id])
inv_o.action_done([inv_id])


conn_manager = oerp.get('sync.client.sync_server_connection')
conn_ids = conn_manager.search([])
conn_manager.disconnect()
conn_manager.write(conn_ids, {'password': UNIFIELD_PASSWORD, 'login': UNIFIELD_ADMIN})
conn_manager.connect()
if sync_needed:
    oerp.get('sync.client.entity').sync()

ext_name = 'OFFICE'
loc_o = oerp.get('stock.location')
if not loc_o.search([('name', '=', ext_name)]):
    print 'Create Loc'
    stock_wiz = oerp.get('stock.location.configuration.wizard')
    w_id = stock_wiz.create({'location_usage': 'consumption_unit', 'location_type': 'customer', 'location_name': ext_name})
    stock_wiz.confirm_creation(w_id)




l = oerp.login(UNIFIELD_ADMIN, UNIFIELD_PASSWORD, '%s_HQ1C1P1' % DB_PREFIX)
conn_manager = oerp.get('sync.client.sync_server_connection')
conn_ids = conn_manager.search([])
conn_manager.disconnect()
conn_manager.write(conn_ids, {'password': UNIFIELD_PASSWORD, 'login': UNIFIELD_ADMIN})
conn_manager.connect()
if sync_needed:
    oerp.get('sync.client.entity').sync()

reset_po(oerp)

ext_name = 'Ext CU Sara'
loc_o = oerp.get('stock.location')
if not loc_o.search([('name', '=', ext_name)]):
    print 'Create Loc'
    stock_wiz = oerp.get('stock.location.configuration.wizard')
    w_id = stock_wiz.create({'location_usage': 'consumption_unit', 'location_type': 'customer', 'location_name': ext_name})
    stock_wiz.confirm_creation(w_id)

loc_ids = loc_o.search([('name', '=', 'LOG')])
prod_o = oerp.get('product.product')
p_ids = prod_o.search([('default_code', '=', 'ADAPCABL2S-')])
inv_o = oerp.get('stock.inventory')
inv_id = inv_o.create({
    'name': 'inv %s' % time.time(),
    'inventory_line_id': [(0, 0, {'location_id': loc_ids[0], 'product_id': p_ids[0], 'product_uom': 1, 'product_qty': 1000, 'reason_type_id': 12})],
})
inv_o.action_confirm([inv_id])
inv_o.action_done([inv_id])

newprod = {
    'default_code': 'ADAPZCOO1',
    'name': 'Local Product',
    'xmlid_code': 'ADAPZCOO1',
    'type': 'product',
    'procure_method': 'make_to_order',
    'standard_price': '0.00935',
    'international_status': 4,
}

def get_nom_info(oerp, nom_name):
    nom = oerp.get('product.nomenclature')
    data = {}
    x = 0
    for name in nom_name:
        n_ids = nom.search([('name', '=', name)])
        data['nomen_manda_%d'%x] = n_ids[0]
        x += 1
    return data

def create_product(oerp, newprod):
    if not oerp.get('product.product').search([('default_code','=', newprod['default_code'])]):
        newprod.update(get_nom_info(oerp, ['LOG', 'A - Administration', 'ADAP - Data Processing', 'MISC - Miscellaneous']))
        oerp.get('product.product').create(newprod)

def activate_partner(oerp, partner_name):
    p_ids = oerp.get('res.partner').search([('name', '=', '%s_%s' % (DB_PREFIX, partner_name)), ('active', 'in', ['t', 'f']), ('partner_type', 'in', ['intermission', 'section'])])
    if p_ids:
        oerp.get('res.partner').write(p_ids, {'active': True})

#### Intermission ####
dbs = oerp.db.list()
if '%s_HQ2C1' % DB_PREFIX in dbs:
    oerp.login(UNIFIELD_ADMIN, UNIFIELD_PASSWORD, '%s_HQ2C1' % DB_PREFIX)
    activate_partner(oerp, 'HQ1C1')
    oerp.login(UNIFIELD_ADMIN, UNIFIELD_PASSWORD, '%s_HQ1C1' % DB_PREFIX)
    activate_partner(oerp, 'HQ2C1')


if '%s_HQ1C2' % DB_PREFIX in dbs:
    l = oerp.login(UNIFIELD_ADMIN, UNIFIELD_PASSWORD, '%s_HQ1C2' % DB_PREFIX)
    reset_po(oerp)
    loc_o = oerp.get('stock.location')
    extra = 'EXTRA'
    if not loc_o.search([('name', '=', extra)]):
        stock_wiz = oerp.get('stock.location.configuration.wizard')
        w_id = stock_wiz.create({'location_usage': 'stock', 'location_name': extra})
        stock_wiz.confirm_creation(w_id)

    activate_partner(oerp, 'HQ1C1')

    create_product(oerp, newprod)

    l = oerp.login(UNIFIELD_ADMIN, UNIFIELD_PASSWORD, '%s_HQ1C1' % DB_PREFIX)
    reset_po(oerp)
    activate_partner(oerp, 'HQ1C2')
    create_product(oerp, newprod)

    loc_o = oerp.get('stock.location')
    loc_ids = loc_o.search([('name', '=', 'LOG')])
    med_ids = loc_o.search([('name', '=', 'MED')])

    prod_o = oerp.get('product.product')
    p1_ids = prod_o.search([('default_code', '=', 'ADAPZCOO1')])
    p2_ids = prod_o.search([('default_code', '=', 'DINJCEFA1V-')])

    batch_name = 'BCOO1'
    exp_date = '2020-10-31'
    batch_o = oerp.get('stock.production.lot')
    batch_ids = batch_o.search([('name', '=', batch_name)])
    if not batch_ids:
        batch_id = batch_o.create({'product_id': p2_ids[0], 'name': batch_name, 'life_date': exp_date})
        batch_ids = [batch_id]

    inv_o = oerp.get('stock.inventory')
    inv_id = inv_o.create({
        'name': 'inv %s' % time.time(),
        'inventory_line_id': [
            (0, 0, {'location_id': loc_ids[0], 'product_id': p1_ids[0], 'product_uom': 1, 'product_qty': 100000, 'reason_type_id': 12}),
            (0, 0, {'location_id': med_ids[0], 'product_id': p2_ids[0], 'product_uom': 1, 'product_qty': 100000, 'prod_lot_id': batch_ids[0], 'reason_type_id': 12, 'expiry_date': exp_date}),
        ],
    })
    inv_o.action_confirm([inv_id])
    inv_o.action_done([inv_id])
