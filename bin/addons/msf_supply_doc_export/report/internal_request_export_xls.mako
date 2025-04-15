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
    <Style ss:ID="big_header">
        <Font x:Family="Swiss" ss:Size="14" ss:Bold="1"/>
        <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
    </Style>
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

% for o in objects:
<ss:Worksheet ss:Name="${_('Internal Request Export')|x}">
<Table x:FullColumns="1" x:FullRows="1">
    ## Line Number
    <Column ss:AutoFitWidth="1" ss:Width="120.75" />
    ## Product code
    <Column ss:AutoFitWidth="1" ss:Width="145.75" />
    ## Product description
    <Column ss:AutoFitWidth="1" ss:Width="250.25" />
    ## Qty
    <Column ss:AutoFitWidth="1" ss:Width="58.75" />
    ## Cost Price
    <Column ss:AutoFitWidth="1" ss:Width="75.75" />
    ## UoM
    <Column ss:AutoFitWidth="1" ss:Width="63.75" />
    ## Currency
    <Column ss:AutoFitWidth="1" ss:Width="63.75" />
    ## Comment
    <Column ss:AutoFitWidth="1" ss:Width="209.25" />
    ## Date of Stock Take
    <Column ss:AutoFitWidth="1" ss:Width="75.75" />

    <Row ss:Height="18">
        <Cell ss:StyleID="big_header" ss:MergeAcross="2"><Data ss:Type="String">${_('INTERNAL REQUEST')}</Data></Cell>
    </Row>
    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Order Reference')}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${o.name or '' | x}</Data></Cell>
    </Row>
    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('State')}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${getSel(o, 'state') or '' | x}</Data></Cell>
    </Row>
    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Order Category')}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${getSel(o, 'categ') or '' | x}</Data></Cell>
    </Row>
    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Priority')}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${getSel(o, 'priority') or '' | x}</Data></Cell>
    </Row>
    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Creation Date')}</Data></Cell>
        <Cell ss:StyleID="short_date" ><Data ss:Type="DateTime">${o.date_order | n}T00:00:00.000</Data></Cell>
    </Row>
    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Requested Delivery Date')}</Data></Cell>
        % if isDate(o.delivery_requested_date):
        <Cell ss:StyleID="short_date" ><Data ss:Type="DateTime">${o.delivery_requested_date | n}T00:00:00.000</Data></Cell>
        % else:
        <Cell ss:StyleID="line" ><Data ss:Type="String"></Data></Cell>
        %endif
    </Row>
    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Requestor')}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${o.requestor or '' | x}</Data></Cell>
    </Row>
    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Location Requestor')}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${o.location_requestor_id.name or '' | x}</Data></Cell>
    </Row>
    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Origin')}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${o.origin or '' | x}</Data></Cell>
    </Row>
    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Functional Currency')}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${o.functional_currency_id.name or '' | x}</Data></Cell>
    </Row>
    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Line Number')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Product Code')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Product Description')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Quantity')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Unit Price')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('UoM')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Currency')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Comment')}</Data></Cell>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Date of Stock Take')}</Data></Cell>
    </Row>
    % for line in o.order_line:
    <Row>
        <Cell ss:StyleID="line" ><Data ss:Type="Number">${line.line_number or '' | x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${line.product_id.default_code or '' | x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${line.product_id.name or '' | x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="Number">${line.product_uom_qty or '' | x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="Number">${line.price_unit or (line.product_id and line.product_id.standard_price) or '' | x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${line.product_uom.name or ''| x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${line.functional_currency_id.name or ''| x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${line.comment or ''| x}</Data></Cell>
        % if isDate(line.stock_take_date):
        <Cell ss:StyleID="short_date" ><Data ss:Type="DateTime">${line.stock_take_date | n}T00:00:00.000</Data></Cell>
        % else:
        <Cell ss:StyleID="line" ><Data ss:Type="String"></Data></Cell>
        %endif
    </Row>
    % endfor
</Table>
<x:WorksheetOptions/>
<DataValidation xmlns="urn:schemas-microsoft-com:office:excel">
    <Range>R4C2:R4C2</Range>
    <Type>List</Type>
    <CellRangeList/>
    <Value>&quot;${_('Medical,Logistic,Service,Transport,Other')|x}&quot;</Value>
</DataValidation>
<DataValidation xmlns="urn:schemas-microsoft-com:office:excel">
    <Range>R5C2:R5C2</Range>
    <Type>List</Type>
    <CellRangeList/>
    <Value>&quot;${_('Normal,Emergency,Priority')|x}&quot;</Value>
</DataValidation>
</ss:Worksheet>
% endfor
</Workbook>
