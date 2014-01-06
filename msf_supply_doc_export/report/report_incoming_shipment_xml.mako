<?xml version="1.0"?>
<data>
% for o in objects:
    <record model="stock.picking" key="name">
        <field name="freight"></field>
        <field name="name">${o.name or ''}</field>
        <field name="origin">${o.origin or ''}</field>
        <field name="partner_id" key="name">
            <field name="name">${o.partner_id and o.partner_id.name or ''}</field>
        </field>
        <field name="transport_mode"></field>
        <field name="note">${o.note or ''}</field>
        <field name="message_esc"></field>
        <field name="move_lines">
        % for l in o.move_lines:
			<record>
				<field name="line_number">${l.line_number or ''}</field>
				<field name="product_id" key="default_code,name">
					<field name="product_code">${l.product_id and l.product_id.default_code or ''}</field>
					<field name="product_name">${l.product_id and l.product_id.name or ''}</field>
				</field>
				<field name="product_qty">${l.product_qty or 0.00}</field>
				<field name="product_uom" key="name">
					<field name="name">${l.product_uom and l.product_uom.name or ''}</field>
				</field>
				<field name="price_unit">${l.price_unit or 0.00}</field>
				<field name="price_currency_id" key="name">
					<field name="name">${l.price_currency_id and l.price_currency_id.name or ''}</field>
				</field>
                <field name="prodlot_id">${l.prodlot_id and l.prodlot_id.name or ''}</field>
                % if l.expired_date and l.expired_date not in (False, 'False'):
                <field name="expired_date">${l.expired_date|n}</field>
                % else:
                <field name="expired_date"></field>
                % endif
				<field name="packing_list"></field>
				<field name="message_esc1"></field>
				<field name="message_esc2"></field>
			</record>
        % endfor
        </field>
    </record>
    % endfor
</data>
