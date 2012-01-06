ORDER_PRIORITY = [('emergency', 'Emergency'), 
                  ('normal', 'Normal'), 
                  ('priority', 'Priority'),]

ORDER_CATEGORY = [('medical', 'Medical'),
                  ('log', 'Logistic'),
                  ('service', 'Service'),
                  ('transport', 'Transport'),
                  ('other', 'Other')]

PURCHASE_ORDER_STATE_SELECTION = [
    ('draft', 'Draft'),
    ('wait', 'Waiting'),
    ('confirmed', 'Validated'),
    ('approved', 'Confirmed'),
    ('except_picking', 'Receipt Exception'),
    ('except_invoice', 'Invoice Exception'),
    ('done', 'Closed'),
    ('cancel', 'Cancelled'),
    ('rfq_sent', 'Sent'),
    ('rfq_updated', 'Updated'),
]


import purchase
import report
