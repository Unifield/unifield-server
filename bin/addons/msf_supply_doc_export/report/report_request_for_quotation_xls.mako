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
## we loop over the purchase_order so "objects" == purchase_order 
% for o in objects:
## we loop over the purchase_order_line
<ss:Worksheet ss:Name="${"%s"%(o.name.split('/')[-1] or 'Sheet1')|x}">
## definition of the columns' size
<% nb_of_columns = 8 %>
<Table x:FullColumns="1" x:FullRows="1">
<Column ss:AutoFitWidth="1" ss:Width="120" />
<Column ss:AutoFitWidth="1" ss:Width="300" />
% for x in range(2,nb_of_columns - 1):
<Column ss:AutoFitWidth="1" ss:Width="60" />
% endfor
<Column ss:AutoFitWidth="1" ss:Width="250" />
<Column ss:AutoFitWidth="1" ss:Width="60" />
    
    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Line Number')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Product Code')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Product Description')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Quantity')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('UoM')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Price')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Requested Delivery Date')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Confirmed Delivery Date')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Currency')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Comment')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('State')}</Data></Cell>
    </Row>
    % for line in o.order_line:
    <Row>
        <Cell ss:StyleID="line" ><Data ss:Type="Number">${(line.line_number or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.product_id.default_code or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.product_id.name or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="Number">${(line.product_qty or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.product_uom.name or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="Number">${(line.price_unit or '')|x}</Data></Cell>
        % if isDate(line.date_planned) :
        <Cell ss:StyleID="short_date" ><Data ss:Type="DateTime">${line.date_planned|n}T00:00:00.000</Data></Cell>
        % elif isDate(o.delivery_requested_date):
        ## if the date does not exist in the line we take the one from the header
        <Cell ss:StyleID="short_date" ><Data ss:Type="DateTime">${o.delivery_requested_date|n}T00:00:00.000</Data></Cell>
        % else:
        <Cell ss:StyleID="line" ><Data ss:Type="String">${('')|x}</Data></Cell>
        % endif
        % if isDate(line.confirmed_delivery_date):
            <Cell ss:StyleID="short_date" ><Data ss:Type="DateTime">${line.confirmed_delivery_date or ' '|n}T00:00:00.000</Data></Cell>
        % else:
            <Cell ss:StyleID="line" ><Data ss:Type="String">${('')|x}</Data></Cell>
        % endif
        
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.currency_id.name or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.comment or '')|x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${(line.rfq_line_state and getSel(line, 'rfq_line_state') or '')|x}</Data></Cell>
    </Row>
    % endfor
</Table>
<x:WorksheetOptions/></ss:Worksheet>
% endfor
</Workbook>
