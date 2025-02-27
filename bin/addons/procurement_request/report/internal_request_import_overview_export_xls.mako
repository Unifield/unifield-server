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
    <Style ss:ID="line_left">
        <Alignment ss:Horizontal="Left" ss:Vertical="Center" ss:WrapText="1"/>
        <Borders>
          <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
        </Borders>
    </Style>
    <Style ss:ID="line_bold">
        <Alignment ss:Horizontal="Left" ss:Vertical="Center" ss:WrapText="1"/>
        <Borders>
          <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
        </Borders>
        <Font ss:Bold="1" />
    </Style>
    <Style ss:ID="line_red">
        <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
        <Borders>
          <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
        </Borders>
        <Font ss:Color="#ff0000"/>
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
<ss:Worksheet ss:Name="${_('IR Import Informations')|x}">
<Table x:FullColumns="1" x:FullRows="1">
    ## Line Number
    <Column ss:AutoFitWidth="1" ss:Width="85.0" />
    ## Error Message
    <Column ss:AutoFitWidth="1" ss:Width="450.25" />
    ## Data Summary
    <Column ss:AutoFitWidth="1" ss:Width="600.75" />
    <Row ss:Height="18">
        <Cell ss:StyleID="big_header" ss:MergeAcross="1"><Data ss:Type="String">${_('IMPORT INFORMATIONS')}</Data></Cell>
    </Row>
    % if o.error_line_ids:
        % if o.has_header_error:
        <Row></Row>
        <Row ss:Height="14">
            <Cell ss:StyleID="line_bold" ss:MergeAcross="1"><Data ss:Type="String">${_('Header messages:')}</Data></Cell>
        </Row>
        % for line in getHeaderErrors(o.id):
        <Row>
            <Cell ss:StyleID="line_left" ss:MergeAcross="1" ><Data ss:Type="String">${line.line_message or '' | x}</Data></Cell>
        </Row>
        % endfor
        %endif
        % if o.has_line_error:
        <Row></Row>
        <Row ss:Height="14">
            <Cell ss:StyleID="line_bold" ss:MergeAcross="2"><Data ss:Type="String">${_('Line messages:')}</Data></Cell>
        </Row>
        <Row>
            <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Line Number')}</Data></Cell>
            <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Error Message')}</Data></Cell>
            <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Data Summary')}</Data></Cell>
        </Row>
        % for line in getErrors(o.id):
        % if line.red:
        <Row>
            <Cell ss:StyleID="line_red" ><Data ss:Type="String">${line.line_number or '' | x}</Data></Cell>
            <Cell ss:StyleID="line_red" ><Data ss:Type="String">${line.line_message or '' | x}</Data></Cell>
            <Cell ss:StyleID="line_red" ><Data ss:Type="String">${line.data_summary or '' | x}</Data></Cell>
        </Row>
        % else:
        <Row>
            <Cell ss:StyleID="line" ><Data ss:Type="String">${line.line_number or '' | x}</Data></Cell>
            <Cell ss:StyleID="line" ><Data ss:Type="String">${line.line_message or '' | x}</Data></Cell>
            <Cell ss:StyleID="line" ><Data ss:Type="String">${line.data_summary or '' | x}</Data></Cell>
        </Row>
        %endif
        % endfor
        %endif
    %endif
</Table>
</ss:Worksheet>
% endfor

% for o in objects:
<ss:Worksheet ss:Name="${_('IR Import Overview')|x}">
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
        <Cell ss:StyleID="line" ><Data ss:Type="String">${o.in_ref or '' | x}</Data></Cell>
    </Row>
    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('State')}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String"></Data></Cell>
    </Row>
    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Order Category')}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${o.in_categ or '' | x}</Data></Cell>
    </Row>
    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Priority')}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${o.in_priority or '' | x}</Data></Cell>
    </Row>
    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Creation Date')}</Data></Cell>
        % if isDate(o.in_creation_date):
        <Cell ss:StyleID="short_date" ><Data ss:Type="DateTime">${o.in_creation_date | n}T00:00:00.000</Data></Cell>
        % else:
        <Cell ss:StyleID="line" ><Data ss:Type="String">${o.in_creation_date or ''|x}</Data></Cell>
        %endif
    </Row>
    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Requested Delivery Date')}</Data></Cell>
        % if isDate(o.in_requested_date):
        <Cell ss:StyleID="short_date" ><Data ss:Type="DateTime">${o.in_requested_date | n}T00:00:00.000</Data></Cell>
        % else:
        <Cell ss:StyleID="line" ><Data ss:Type="String">${o.in_requested_date or ''|x}</Data></Cell>
        %endif
    </Row>
    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Requestor')}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${o.in_requestor or '' | x}</Data></Cell>
    </Row>
    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Location Requestor')}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${o.in_loc_requestor or '' | x}</Data></Cell>
    </Row>
    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Origin')}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${o.in_origin or '' | x}</Data></Cell>
    </Row>
    <Row>
        <Cell ss:StyleID="header" ><Data ss:Type="String">${_('Functional Currency')}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${o.in_currency or ''| x}</Data></Cell>
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
    % for line in o.imp_line_ids:
    <Row>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${line.in_line_number or '' | x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${line.in_product or '' | x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${line.in_product_desc or '' | x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${line.in_qty or '' | x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${line.in_cost_price or '' | x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${line.in_uom or ''| x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${o.in_currency or ''| x}</Data></Cell>
        <Cell ss:StyleID="line" ><Data ss:Type="String">${line.in_comment or ''| x}</Data></Cell>
        % if isDate(line.in_stock_take_date):
        <Cell ss:StyleID="short_date" ><Data ss:Type="DateTime">${line.in_stock_take_date | n}T00:00:00.000</Data></Cell>
        % else:
        <Cell ss:StyleID="line" ><Data ss:Type="String">${line.in_stock_take_date or ''|x}</Data></Cell>
        %endif
    </Row>
    % endfor
</Table>
</ss:Worksheet>
% endfor
</Workbook>
