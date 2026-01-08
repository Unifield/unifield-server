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
        <field name="transport_type">${(o.purchase_id and getSel(o.purchase_id, 'transport_type') or '')|x}</field>
        <field name="note">${o.note or ''}</field>
        <field name="message_esc"></field>
        <field name="move_lines">
          <record>
            <field name="parcel_from"></field>
            <field name="parcel_to"></field>
            <field name="parcel_qty"></field>
            <field name="total_weight"></field>
            <field name="total_volume"></field>
            <field name="total_height"></field>
            <field name="total_length"></field>
            <field name="total_width"></field>
            <field name="packing_list"></field>
            <field name="message_esc1"></field>
            <field name="message_esc2"></field>
        % for l in o.move_lines:
            % if l.state != 'cancel':
            <record>
                <field name="line_number">${l.line_number or ''}</field>
                <field name="external_ref">${(l.purchase_line_id and l.purchase_line_id.external_ref or '')|x}</field>
                <field name="product_id" key="default_code,name">
                    <field name="product_code">${(l.product_id and l.product_id.default_code or '')|x}</field>
                    <field name="product_name">${(l.product_id and l.product_id.name or '')|x}</field>
                </field>
                <field name="product_qty">${l.product_qty or 0.00}</field>
                <field name="product_uom" key="name">
                    <field name="name">${(l.product_uom and l.product_uom.name or '')|x}</field>
                </field>
                <field name="price_unit">${((l.purchase_line_id and l.purchase_line_id.price_unit) or (l.product_id and l.product_id.standard_price) or 0.00)|x}</field>
                <field name="price_currency_id" key="name">
                    <field name="name">${(l.picking_id and l.picking_id.purchase_id and l.picking_id.purchase_id.pricelist_id.currency_id.name or l.company_id.currency_id.name or '')|x}</field>
                </field>
                <field name="prodlot_id">${(l.prodlot_id and l.prodlot_id.name or '')|x}</field>
                % if l.expired_date and l.expired_date not in (False, 'False'):
                <field name="expired_date">${l.expired_date|n}</field>
                % else:
                <field name="expired_date"></field>
                % endif
                <field name="message_esc1"></field>
                <field name="message_esc2"></field>
            </record>
            % endif
        % endfor
           </record>
        </field>
    </record>
    % endfor
</data>
