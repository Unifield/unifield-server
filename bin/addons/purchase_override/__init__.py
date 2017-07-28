ORDER_PRIORITY = [
	('emergency', 'Emergency'), 
	('normal', 'Normal'), 
	('priority', 'Priority'),
]

ORDER_CATEGORY = [
	('medical', 'Medical'),
	('log', 'Logistic'),
	('service', 'Service'),
	('transport', 'Transport'),
	('other', 'Other'),
]

PURCHASE_ORDER_LINE_STATE_SELECTION = [
	('draft', 'Draft'),
	('validated_n', 'Validated-n'),
	('validated', 'Validated'),
	('sourced_s', 'Sourced-s'),
	('sourced_v', 'Sourced-v'),
	('sourced_n', 'Sourced-n'),
	('confirmed', 'Confirmed'),
	('done', 'Closed'),
	('cancel', 'Cancelled'),
]

PURCHASE_ORDER_STATE_SELECTION = PURCHASE_ORDER_LINE_STATE_SELECTION + [('draft_p', 'Draft-p'), ('validated_p', 'Validated-p'), ('sourced_p', 'Sourced-p'), ('confirmed_p', 'Confirmed-p')]


import purchase
import report
import wizard
