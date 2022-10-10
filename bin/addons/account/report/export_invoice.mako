<?xml version="1.0"?>
<?mso-application progid="Excel.Sheet"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:o="urn:schemas-microsoft-com:office:office"
 xmlns:x="urn:schemas-microsoft-com:office:excel"
 xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:html="http://www.w3.org/TR/REC-html40">
 <DocumentProperties xmlns="urn:schemas-microsoft-com:office:office">
  <Title>${_('Export - Invoice')}</Title>
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
  <Style ss:ID="editable">
    <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
    <Borders>
      <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
      <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
      <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
      <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
    </Borders>
    <Protection ss:Protected="0"/>
  </Style>
  <Style ss:ID="editable_number">
    <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
    <Borders>
      <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
      <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
      <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
      <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
    </Borders>
    <NumberFormat ss:Format="Standard"/>
    <Protection ss:Protected="0"/>
  </Style>
  <Style ss:ID="non_editable">
    <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
    <Interior ss:Color="#ffcc99" ss:Pattern="Solid"/>
    <Borders>
      <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
      <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
      <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
      <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
    </Borders>
    <Protection/>
  </Style>
  <Style ss:ID="editable_red_bold">
    <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
    <Font ss:Bold="1" ss:Color="#FF0000"/>
    <Borders>
      <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
      <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
      <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
      <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
    </Borders>
    <Protection ss:Protected="0"/>
  </Style>
  <Style ss:ID="non_editable_number">
    <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
    <Interior ss:Color="#ffcc99" ss:Pattern="Solid"/>
    <Borders>
      <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
      <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
      <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
      <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
    </Borders>
    <NumberFormat ss:Format="Standard"/>
    <Protection/>
  </Style>
  <Style ss:ID="non_editable_date">
    <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
    <Interior ss:Color="#ffcc99" ss:Pattern="Solid"/>
    <Borders>
      <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
      <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
      <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
      <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
    </Borders>
    <NumberFormat ss:Format="Short Date"/>
    <Protection/>
  </Style>
</Styles>
% for o in objects:
<!-- Sheet must be protected otherwise the protection on the cells has no effect -->
<!-- Default Sheet name is "Sheet1" (we can export only one inv. at a time) -->
<ss:Worksheet ss:Name="${o.number or "%s%s" % (_('Sheet'), 1)|x}" ss:Protected="1">
<Table x:FullColumns="1" x:FullRows="1">
  <Column ss:AutoFitWidth="1" ss:Width="100"/>
  <Column ss:AutoFitWidth="1" ss:Width="250"/>
  <Column ss:AutoFitWidth="1" ss:Width="100"/>
  <Column ss:AutoFitWidth="1" ss:Width="150" ss:Span="1"/>
  <Column ss:AutoFitWidth="1" ss:Width="300" ss:Span="1"/>

  <Row>
      <Cell ss:StyleID="non_editable"><Data ss:Type="String">${_('Number')}</Data></Cell>
      <Cell ss:StyleID="non_editable"><Data ss:Type="String">${o.number or ''|x}</Data></Cell>
  </Row>
  <Row>
      <Cell ss:StyleID="non_editable"><Data ss:Type="String">${_('Journal')}</Data></Cell>
      <Cell ss:StyleID="non_editable"><Data ss:Type="String">${o.journal_id.code|x}</Data></Cell>
  </Row>
  <Row>
      <Cell ss:StyleID="non_editable"><Data ss:Type="String">${_('Currency')}</Data></Cell>
      <Cell ss:StyleID="non_editable"><Data ss:Type="String">${o.currency_id.name|x}</Data></Cell>
  </Row>
  <Row>
      <Cell ss:StyleID="non_editable"><Data ss:Type="String">${_('Partner')}</Data></Cell>
      <Cell ss:StyleID="non_editable"><Data ss:Type="String">${o.partner_id.name|x}</Data></Cell>
  </Row>
  <Row>
      <Cell ss:StyleID="non_editable"><Data ss:Type="String">${_('Document Date')}</Data></Cell>
      % if isDate(o.document_date):
          <Cell ss:StyleID="non_editable_date"><Data ss:Type="DateTime">${o.document_date|n}T00:00:00.000</Data></Cell>
      % else:
          <Cell ss:StyleID="non_editable"><Data ss:Type="String"></Data></Cell>
      % endif
  </Row>
  <Row>
      <Cell ss:StyleID="non_editable"><Data ss:Type="String">${_('Posting Date')}</Data></Cell>
      % if isDate(o.date_invoice):
          <Cell ss:StyleID="non_editable_date"><Data ss:Type="DateTime">${o.date_invoice|n}T00:00:00.000</Data></Cell>
      % else:
          <Cell ss:StyleID="non_editable"><Data ss:Type="String"></Data></Cell>
      % endif
  </Row>
  <Row>
      <Cell ss:StyleID="non_editable"><Data ss:Type="String">${_('Account')}</Data></Cell>
      <Cell ss:StyleID="non_editable"><Data ss:Type="String">${o.account_id.code|x}</Data></Cell>
  </Row>

  <Row><Cell ss:StyleID="editable"><Data ss:Type="String"></Data></Cell></Row>

  <Row>
      <Cell ss:StyleID="non_editable"><Data ss:Type="String">${_('Line number')}</Data></Cell>
      <Cell ss:StyleID="non_editable"><Data ss:Type="String">${_('Product')}</Data></Cell>
      <Cell ss:StyleID="non_editable"><Data ss:Type="String">${_('Account')}</Data></Cell>
      <Cell ss:StyleID="non_editable"><Data ss:Type="String">${_('Quantity')}</Data></Cell>
      <Cell ss:StyleID="non_editable"><Data ss:Type="String">${_('Unit Price')}</Data></Cell>
      <Cell ss:StyleID="non_editable"><Data ss:Type="String">${_('Description')}</Data></Cell>
      <Cell ss:StyleID="non_editable"><Data ss:Type="String">${_('Notes')}</Data></Cell>
      <Cell ss:StyleID="non_editable"><Data ss:Type="String">${_('Analytic Distribution')}</Data></Cell>
      <Cell ss:StyleID="non_editable"><Data ss:Type="String">${_('Cost Center')}</Data></Cell>
      <Cell ss:StyleID="non_editable"><Data ss:Type="String">${_('Destination')}</Data></Cell>
      <Cell ss:StyleID="non_editable"><Data ss:Type="String">${_('Funding Pool')}</Data></Cell>
  </Row>

  <% is_ro = is_readonly(o) %>
  % for inv_line in o.invoice_line:
    <Row>
        <Cell ss:StyleID="non_editable"><Data ss:Type="String">${inv_line.line_number or ''|x}</Data></Cell>
        % if is_ro:
            <Cell ss:StyleID="non_editable">
        % else:
            <Cell ss:StyleID="editable">
        % endif
        <Data ss:Type="String">${inv_line.product_id and inv_line.product_id.default_code or ''|x}</Data></Cell>

        <Cell ss:StyleID="editable"><Data ss:Type="String">${inv_line.account_id and inv_line.account_id.code or ''|x}</Data></Cell>

        % if is_ro:
            <Cell ss:StyleID="non_editable_number">
        % else:
            <Cell ss:StyleID="editable_number">
        % endif
        <Data ss:Type="Number">${inv_line.quantity|x}</Data></Cell>

        <Cell ss:StyleID="editable_number"><Data ss:Type="Number">${inv_line.price_unit|x}</Data></Cell>

        <Cell ss:StyleID="editable"><Data ss:Type="String">${inv_line.name or ''|x}</Data></Cell>


        <!-- export Notes including line breaks (|xn) -->
        <Cell ss:StyleID="editable"><Data ss:Type="String">${inv_line.note or ''|xn}</Data></Cell>

        <% ad_obj = inv_line.account_id.is_analytic_addicted and (inv_line.analytic_distribution_id or inv_line.invoice_id.analytic_distribution_id) or False %>
        % if ad_obj and len(ad_obj.funding_pool_lines) == 1 :
            <Cell ss:StyleID="non_editable"><Data ss:Type="String">${'100%'|x}</Data></Cell>
            <Cell ss:StyleID="editable"><Data ss:Type="String">${ad_obj.funding_pool_lines[0].cost_center_id.code or ''|x}</Data></Cell>
            <Cell ss:StyleID="editable"><Data ss:Type="String">${ad_obj.funding_pool_lines[0].destination_id.code or ''|x}</Data></Cell>
            <Cell ss:StyleID="editable"><Data ss:Type="String">${ad_obj.funding_pool_lines[0].analytic_id.code or ''|x}</Data></Cell>
        % elif ad_obj and len(ad_obj.funding_pool_lines) > 1:
            <Cell ss:StyleID="editable_red_bold"><Data ss:Type="String">${'SPLIT'|x}</Data></Cell>
            <Cell ss:StyleID="editable"><Data ss:Type="String">${''|x}</Data></Cell>
            <Cell ss:StyleID="editable"><Data ss:Type="String">${''|x}</Data></Cell>
            <Cell ss:StyleID="editable"><Data ss:Type="String">${''|x}</Data></Cell>
        % else:
            <Cell ss:StyleID="editable"><Data ss:Type="String">${''|x}</Data></Cell>
            <Cell ss:StyleID="editable"><Data ss:Type="String">${''|x}</Data></Cell>
            <Cell ss:StyleID="editable"><Data ss:Type="String">${''|x}</Data></Cell>
            <Cell ss:StyleID="editable"><Data ss:Type="String">${''|x}</Data></Cell>
        % endif
    </Row>
  % endfor

</Table>
<WorksheetOptions xmlns="urn:schemas-microsoft-com:office:excel">
   <FitToPage/>
   <PageSetup>
       <Layout x:Orientation="Portrait"/>
       <Header x:Margin="0.4921259845"/>
       <Footer x:Margin="0.4921259845"/>
       <PageMargins x:Bottom="0.984251969" x:Left="0.78740157499999996" x:Right="0.78740157499999996" x:Top="0.984251969"/>
   </PageSetup>
   <Print>
       <ValidPrinterInfo/>
       <PaperSizeIndex>9</PaperSizeIndex>
       <HorizontalResolution>600</HorizontalResolution>
       <VerticalResolution>600</VerticalResolution>
   </Print>
   <Selected/>
   <ProtectObjects>False</ProtectObjects>
   <ProtectScenarios>False</ProtectScenarios>
</WorksheetOptions>
</ss:Worksheet>
% endfor
</Workbook>
