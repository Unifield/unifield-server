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
    </Style>
    <Style ss:ID="line">
        <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
        <Borders>
          <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
        </Borders>
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
  </Style>
</Styles>
## ==================================== we loop over the purchase_order "objects" == purchase_order  ====================================================
% for o in objects:
<ss:Worksheet ss:Name="Sheet1">
<Table x:FullColumns="1" x:FullRows="1">
<Column ss:AutoFitWidth="1" ss:Width="250" />
## ROW 0
    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">Order Reference</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">Supplier Reference</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">Delivery Confirmed Date</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">Est. Transport Lead Time</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">Transport Mode</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">Arrival Date in the country</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">Incoterm</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">Line</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">Product Code</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">Quantity</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">UoM</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">Price</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">Delivery requested date</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">Currency</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">Comment</Data></Cell>
    </Row>
    % for line in o.order_line:
    <Row>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(o.name or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(o.partner_ref or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(o.delivery_confirmed_date or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(o.est_transport_lead_time or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(o.transport_type or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(o.arrival_date or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(o.incoterm_id or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.line_number or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.product_id.default_code or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="Number">${(line.product_qty or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.product_uom.name or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="Number">${(line.price_unit or '')|x}</Data></Cell>
        % if line.date_planned :
        <Cell ss:StyleID="short_date" ><Data ss:Type="DateTime">${line.date_planned|n}T00:00:00.000</Data></Cell>
        % elif o.delivery_requested_date:
        ## if the date does not exist in the line we take the one from the header
        <Cell ss:StyleID="short_date" ><Data ss:Type="DateTime">${o.delivery_requested_date|n}T00:00:00.000</Data></Cell>
        % endif
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.functional_currency_id.name or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.comment or '')|x}</Data></Cell>
    </Row>
    % endfor
</Table>
<x:WorksheetOptions/>
</ss:Worksheet>
% endfor
</Workbook>