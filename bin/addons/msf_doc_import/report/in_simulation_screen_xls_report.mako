<?xml version="1.0"?>
<?mso-application progid="Excel.Sheet"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:o="urn:schemas-microsoft-com:office:office"
 xmlns:x="urn:schemas-microsoft-com:office:excel"
 xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:html="http://www.w3.org/TR/REC-html40">
 <DocumentProperties xmlns="urn:schemas-microsoft-com:office:office">
  <Author>MSFUser</Author>
  <LastAuthor>MSFUser</LastAuthor>
  <Created>2012-06-18T15:46:09Z</Created>
  <Company>Medecins Sans Frontieres</Company>
  <Version>11.9999</Version>
 </DocumentProperties>
 <ExcelWorkbook xmlns="urn:schemas-microsoft-com:office:excel">
  <WindowHeight>13170</WindowHeight>
  <WindowWidth>19020</WindowWidth>
  <WindowTopX>120</WindowTopX>
  <WindowTopY>60</WindowTopY>
  <ProtectStructure>False</ProtectStructure>
  <ProtectWindows>False</ProtectWindows>
 </ExcelWorkbook>
<Styles>
    <Style ss:ID="header">
        <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
        <Interior ss:Color="#ffcc99" ss:Pattern="Solid"/>
        <Borders>
          <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
        </Borders>
        <Protection />
    </Style>
    <Style ss:ID="line">
        <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
        <Borders>
          <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
        </Borders>
        <Protection ss:Protected="0" />
    </Style>
    <Style ss:ID="line_change">
        <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
        <Borders>
          <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
        </Borders>
        <Interior ss:Color="#ff0000" ss:Pattern="Solid" />>
        <Protection ss:Protected="0" />
    </Style>
    <Style ss:ID="line_change_short_date">
        <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
        <Borders>
          <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
        </Borders>
        <NumberFormat ss:Format="Short Date"/>
        <Interior ss:Color="#ff0000" ss:Pattern="Solid" />>
        <Protection ss:Protected="0" />
    </Style>
  <Style ss:ID="short_date">
   <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
   <Borders>
    <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
    <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
    <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
    <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
   </Borders>
   <NumberFormat ss:Format="Short Date"/>
   <Protection ss:Protected="0" />
  </Style>
</Styles>
% for o in objects:
<ss:Worksheet ss:Name="${"%s"%(o.picking_id.name.split('/')[-1] or 'Sheet1')|x}" ss:Protected="0">
## definition of the columns' size
<% nb_of_columns = 17 %>
<Table x:FullColumns="1" x:FullRows="1">
<Column ss:AutoFitWidth="1" ss:Width="120" />
<Column ss:AutoFitWidth="1" ss:Width="300" />
% for x in range(2,nb_of_columns - 1):
<Column ss:AutoFitWidth="1" ss:Width="60" />
% endfor
<Column ss:AutoFitWidth="1" ss:Width="250" />

    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Order Reference')}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(o.picking_id.name or '')|x}</Data></Cell>
    </Row>

    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Supplier')}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(o.picking_id and o.picking_id.partner_id2 and o.picking_id.partner_id2.name or '')|x}</Data></Cell>
    </Row>

    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Notes')}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(o.picking_id.note or '')|x}</Data></Cell>
    </Row>

    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Message ESC Header')}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(o.message_esc or '')|x}</Data></Cell>
    </Row>

    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Field name')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Original value')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Imported value')}</Data></Cell>
    </Row>

    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Freight Number')}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(o.freight_number or '')|x}</Data></Cell>
        % if o.freight_number != o.imp_freight_number:
        <Cell ss:StyleID="line_change" ><Data ss:Type="String">${(o.imp_freight_number or '')|x}</Data></Cell>
        % else:
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(o.imp_freight_number or '')|x}</Data></Cell>
        % endif
    </Row>

    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Origin')}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(o.origin or '')|x}</Data></Cell>
        % if o.imp_origin != o.origin:
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(o.imp_origin or '')|x}</Data></Cell>
        % else:
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(o.imp_origin or '')|x}</Data></Cell>
        % endif
    </Row>

    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Transport mode')}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(getSel(o, 'transport_type') or '')|x}</Data></Cell>
        % if o.imp_transport_type != o.transport_type:
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(getSel(o, 'imp_transport_type') or '')|x}</Data></Cell>
        % else:
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(getSel(o, 'imp_transport_type') or '')|x}</Data></Cell>
        % endif
    </Row>

    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Product')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Ordered Qty')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Ordered UoM')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Price Unit')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Curr.')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Line')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Ext. Ref')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('CHG')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String"></Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Product')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Qty to Process')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('UoM')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Price Unit')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Unit Cost')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Discre.')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Curr.')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Batch Number')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Expiry date')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Message ESC 1')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Message ESC 2')}</Data></Cell>
    </Row>
    % for l in o.line_ids:
    <Row>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(l.move_product_id and obj_name_get('product.product', l.move_product_id.id) or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="Number">${(l.move_product_qty or 0.00)|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(l.move_uom_id.name or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="Number">${(l.move_price_unit or 0.00)|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(l.move_currency_id.name or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(l.line_number or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(l.external_ref or '')|x}</Data></Cell>
        % if l.type_change == 'error':
        <Cell ss:StyleID="line_change" ><Data ss:Type="String">${(getSel(l, 'type_change') or '')|x}</Data></Cell>
        <Cell ss:StyleID="line_change" ><Data ss:Type="String">${(getSel(l, 'integrity_status') or '')|x}</Data></Cell>
        % else:
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(getSel(l, 'type_change') or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(getSel(l, 'integrity_status') or '')|x}</Data></Cell>
        % endif
        % if l.imp_product_id.id != l.move_product_id.id:
        <Cell ss:StyleID="line_change" ><Data ss:Type="String">${(l.imp_product_id and '[%s] %s' % (l.imp_product_id.default_code, l.imp_product_id.name) or '')|x}</Data></Cell>
        % else:
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(l.imp_product_id and '[%s] %s' % (l.imp_product_id.default_code, l.imp_product_id.name) or '')|x}</Data></Cell>
        % endif
        % if l.imp_product_qty != l.move_product_qty:
        <Cell ss:StyleID="line_change" ><Data ss:Type="Number">${(l.imp_product_qty or 0.00)|x}</Data></Cell>
        % else:
        <Cell ss:StyleID="line" ><Data ss:Type="Number">${(l.imp_product_qty or 0.00)|x}</Data></Cell>
        % endif
        % if l.imp_uom_id.id != l.move_uom_id.id:
        <Cell ss:StyleID="line_change" ><Data ss:Type="String">${(l.imp_uom_id.name or '')|x}</Data></Cell>
        % else:
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(l.imp_uom_id.name or '')|x}</Data></Cell>
        % endif
        % if l.imp_price_unit != l.move_price_unit:
        <Cell ss:StyleID="line_change" ><Data ss:Type="Number">${(l.imp_price_unit or 0.00)|x}</Data></Cell>
        % else:
        <Cell ss:StyleID="line" ><Data ss:Type="Number">${(l.imp_price_unit or 0.00)|x}</Data></Cell>
        % endif
        % if (l.imp_price_unit != l.move_price_unit) or (l.imp_product_qty != l.move_product_qty):
        <Cell ss:StyleID="line_change" ><Data ss:Type="Number">${(l.imp_cost or 0.00)|x}</Data></Cell>
        % else:
        <Cell ss:StyleID="line" ><Data ss:Type="Number">${(l.imp_cost or 0.00)|x}</Data></Cell>
        % endif
        % if l.discrepancy:
        <Cell ss:StyleID="line_change" ><Data ss:Type="Number">${(l.discrepancy or 0.00)|x}</Data></Cell>
        % else:
        <Cell ss:StyleID="line" ><Data ss:Type="Number">${(l.discrepancy or 0.00)|x}</Data></Cell>
        % endif
        % if l.imp_currency_id.id != l.move_currency_id.id:
        <Cell ss:StyleID="line_change" ><Data ss:Type="String">${(l.imp_currency_id.name or '')|x}</Data></Cell>
        % else:
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(l.imp_currency_id.name or '')|x}</Data></Cell>
        % endif
        % if l.imp_batch_name:
        <Cell ss:StyleID="line_change" ><Data ss:Type="String">${(l.imp_batch_name or '')|x}</Data></Cell>
        % else:
        <Cell ss:StyleID="line" ><Data ss:Type="String"></Data></Cell>
        % endif
        % if isDate(l.imp_exp_date):
        <Cell ss:StyleID="line_change_short_date" ><Data ss:Type="DateTime">${(l.imp_exp_date)|n}T00:00:00.000</Data></Cell>
        % else:
        <Cell ss:StyleID="line" ></Cell>
        % endif
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(l.message_esc1 or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(l.message_esc2 or '')|x}</Data></Cell>
    </Row>
    % endfor

    <Row></Row>

    <Row>
        <Cell ss:StyleID="header" MergeAcross="3"><Data ss:Type="String">${_('Information')}</Data></Cell>
    </Row>
    <Row>
        <Cell ss:StyleID="line" MergeAcross="3" ><Data ss:Type="String">${(o.message or '')|x}</Data></Cell>
    </Row>

</Table>
<x:WorksheetOptions xmlns="urn:schemas-microsoft-com:office:excel">
    <!--    <ProtectObjects>False</ProtectObjects>
    <ProtectScenarios>False</ProtectScenarios>
    <EnableSelection>UnlockedCells</EnableSelection>
    <AllowInsertRows />-->
</x:WorksheetOptions>
</ss:Worksheet>
% endfor
</Workbook>
