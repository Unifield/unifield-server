<?xml version="1.0"?>
<?mso-application progid="Excel.Sheet"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:o="urn:schemas-microsoft-com:office:office"
 xmlns:x="urn:schemas-microsoft-com:office:excel"
 xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:html="http://www.w3.org/TR/REC-html40">
 <DocumentProperties xmlns="urn:schemas-microsoft-com:office:office">
  <Title>${_('Export - CV')}</Title>
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
<!-- Default Sheet name is "Sheet1" (we can export only one cv at a time) -->
<ss:Worksheet ss:Name="${o.name or "%s%s" % (_('Sheet'), 1)|x}" ss:Protected="1">
<Table x:FullColumns="1" x:FullRows="1">
  <Column ss:AutoFitWidth="1" ss:Width="50"/>
  <Column ss:AutoFitWidth="1" ss:Width="150"/>
  <Column ss:AutoFitWidth="1" ss:Width="50"/>
  <Column ss:AutoFitWidth="1" ss:Width="100"/>
  <Column ss:AutoFitWidth="1" ss:Width="150" ss:Span="1"/>
  <Column ss:AutoFitWidth="1" ss:Width="300" ss:Span="1"/>

  <Row>
      <Cell ss:StyleID="non_editable" ss:MergeAcross="1"><Data ss:Type="String">${_('Journal')}</Data></Cell>
      <Cell ss:StyleID="non_editable" ss:MergeAcross="1"><Data ss:Type="String">${o.journal_id.code or ''|x}</Data></Cell>
  </Row>
  <Row>
      <Cell ss:StyleID="non_editable" ss:MergeAcross="1"><Data ss:Type="String">${_('Number')}</Data></Cell>
      <Cell ss:StyleID="non_editable" ss:MergeAcross="1"><Data ss:Type="String">${o.name or ''|x}</Data></Cell>
  </Row>
  <Row>
      <Cell ss:StyleID="non_editable" ss:MergeAcross="1"><Data ss:Type="String">${_('Commitment Date')}</Data></Cell>
      % if isDate(o.date):
          <Cell ss:StyleID="non_editable_date" ss:MergeAcross="1"><Data ss:Type="DateTime">${o.date|n}T00:00:00.000</Data></Cell>
      % else:
          <Cell ss:StyleID="non_editable" ss:MergeAcross="1"><Data ss:Type="String"></Data></Cell>
      % endif
  </Row>
  <Row>
      <Cell ss:StyleID="non_editable" ss:MergeAcross="1"><Data ss:Type="String">${_('Currency')}</Data></Cell>
      <Cell ss:StyleID="non_editable" ss:MergeAcross="1"><Data ss:Type="String">${o.currency_id.name or ''|x}</Data></Cell>
  </Row>
  <Row>
      <Cell ss:StyleID="non_editable" ss:MergeAcross="1"><Data ss:Type="String">${_('Description')}</Data></Cell>
      <Cell ss:StyleID="non_editable" ss:MergeAcross="1"><Data ss:Type="String">${o.description or ''|x}</Data></Cell>
  </Row>
  <Row>
      <Cell ss:StyleID="non_editable" ss:MergeAcross="1"><Data ss:Type="String">${_('Supplier')}</Data></Cell>
      <Cell ss:StyleID="non_editable" ss:MergeAcross="1"><Data ss:Type="String">${o.partner_id.name or ''|x}</Data></Cell>
  </Row>
  <Row>
      <Cell ss:StyleID="non_editable" ss:MergeAcross="1"><Data ss:Type="String">${_('Source Document')}</Data></Cell>
      <Cell ss:StyleID="non_editable" ss:MergeAcross="1"><Data ss:Type="String">${o.purchase_id and o.purchase_id.name or o.sale_id and o.sale_id.name or ''|x}</Data></Cell>
  </Row>
  <Row>
      <Cell ss:StyleID="non_editable" ss:MergeAcross="1"><Data ss:Type="String">${_('Period')}</Data></Cell>
      <Cell ss:StyleID="non_editable" ss:MergeAcross="1"><Data ss:Type="String">${o.period_id.name or ''|x}</Data></Cell>
  </Row>
  <Row>
      <Cell ss:StyleID="non_editable" ss:MergeAcross="1"><Data ss:Type="String">${_('Type')}</Data></Cell>
      <Cell ss:StyleID="non_editable" ss:MergeAcross="1"><Data ss:Type="String">${getSel(o, 'type')|x}</Data></Cell>
  </Row>

  <Row><Cell ss:StyleID="editable"><Data ss:Type="String"></Data></Cell></Row>

  <Row>
      <Cell ss:StyleID="non_editable"><Data ss:Type="String">${_('Internal ID')}</Data></Cell>
      <Cell ss:StyleID="non_editable"><Data ss:Type="String">${_('Commitment Voucher Lines')}</Data></Cell>
      <Cell ss:StyleID="non_editable"><Data ss:Type="String">${_('Line number')}</Data></Cell>
      <Cell ss:StyleID="non_editable"><Data ss:Type="String">${_('Account')}</Data></Cell>
      <Cell ss:StyleID="non_editable"><Data ss:Type="String">${_('Initial Amount')}</Data></Cell>
      <Cell ss:StyleID="non_editable"><Data ss:Type="String">${_('Left Amount')}</Data></Cell>
      <Cell ss:StyleID="non_editable"><Data ss:Type="String">${_('Analytic Distribution')}</Data></Cell>
      <Cell ss:StyleID="non_editable"><Data ss:Type="String">${_('Cost Center')}</Data></Cell>
      <Cell ss:StyleID="non_editable"><Data ss:Type="String">${_('Destination')}</Data></Cell>
      <Cell ss:StyleID="non_editable"><Data ss:Type="String">${_('Funding Pool')}</Data></Cell>
  </Row>

  % for cv_line in o.line_ids:
    <Row>
        <Cell ss:StyleID="non_editable"><Data ss:Type="String">${cv_line.id or ''|x}</Data></Cell>
        <Cell ss:StyleID="non_editable"><Data ss:Type="String">${cv_line.line_product_id and cv_line.line_product_id.default_code or ''|x}</Data></Cell>
        <Cell ss:StyleID="non_editable"><Data ss:Type="String">${cv_line.line_number or ''|x}</Data></Cell>
        <Cell ss:StyleID="editable"><Data ss:Type="String">${cv_line.account_id and cv_line.account_id.code or ''|x}</Data></Cell>
        <Cell ss:StyleID="non_editable_number"><Data ss:Type="Number">${cv_line.initial_amount|x}</Data></Cell>
        <Cell ss:StyleID="non_editable_number"><Data ss:Type="Number">${cv_line.amount|x}</Data></Cell>
        <% ad_obj = cv_line.analytic_distribution_id or cv_line.commit_id.analytic_distribution_id or False %>
        % if ad_obj and len(ad_obj.funding_pool_lines) == 1 :
            <Cell ss:StyleID="non_editable"><Data ss:Type="String">${'100%'|x}</Data></Cell>
            <Cell ss:StyleID="editable"><Data ss:Type="String">${ad_obj.funding_pool_lines[0].cost_center_id.code or ''|x}</Data></Cell>
            <Cell ss:StyleID="editable"><Data ss:Type="String">${ad_obj.funding_pool_lines[0].destination_id.code or ''|x}</Data></Cell>
            <Cell ss:StyleID="editable"><Data ss:Type="String">${ad_obj.funding_pool_lines[0].analytic_id.code or ''|x}</Data></Cell>
        % elif ad_obj and len(ad_obj.funding_pool_lines) > 1:
            <Cell ss:StyleID="editable_red_bold"><Data ss:Type="String">${'SPLIT'|x}</Data></Cell>
            <Cell ss:StyleID="editable"><Data ss:Type="String"></Data></Cell>
            <Cell ss:StyleID="editable"><Data ss:Type="String"></Data></Cell>
            <Cell ss:StyleID="editable"><Data ss:Type="String"></Data></Cell>
        % else:
            <Cell ss:StyleID="editable"><Data ss:Type="String"></Data></Cell>
            <Cell ss:StyleID="editable"><Data ss:Type="String"></Data></Cell>
            <Cell ss:StyleID="editable"><Data ss:Type="String"></Data></Cell>
            <Cell ss:StyleID="editable"><Data ss:Type="String"></Data></Cell>
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
