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
    ('sourced', 'Sourced'),
    ('wait', 'Waiting'),
    ('confirmed', 'Validated'),
    ('confirmed_wait', 'Confirmed (waiting)'),
    ('approved', 'Confirmed'),
    ('except_picking', 'Receipt Exception'),
    ('except_invoice', 'Invoice Exception'),
    ('done', 'Closed'),
    ('cancel', 'Cancelled'),
    ('rfq_sent', 'Sent'),
    ('rfq_updated', 'Updated'),
    ('split', 'Split'),
    ('rw', 'RW'),
]


import purchase
import report
import wizard
