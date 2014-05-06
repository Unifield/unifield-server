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
    <Style ss:ID="ssCell">
        <Alignment ss:Vertical="Top" ss:WrapText="1"/>
    </Style>
    <Style ss:ID="ssCellBold">
        <Alignment ss:Vertical="Top" ss:WrapText="1"/>
        <Font ss:Bold="1" />
    </Style>
    <Style ss:ID="ssCellRightBold">
        <Alignment ss:Horizontal="Right" ss:Vertical="Top" ss:WrapText="1"/>
        <Font ss:Bold="1" />
    </Style>
    <Style ss:ID="header">
        <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
        <Font ss:Bold="1" />
        <Interior ss:Color="#dddddd" ss:Pattern="Solid"/>
        <Borders>
          <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
        </Borders>
    </Style>
    <Style ss:ID="headerLeft">
        <Alignment ss:Horizontal="Left" ss:Vertical="Center" ss:WrapText="1"/>
        <Font ss:Bold="1" />
        <Interior ss:Color="#dddddd" ss:Pattern="Solid"/>
        <Borders>
          <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
        </Borders>
    </Style>
    <Style ss:ID="headerRight">
        <Alignment ss:Horizontal="Right" ss:Vertical="Center" ss:WrapText="1"/>
        <Font ss:Bold="1" />
        <Interior ss:Color="#dddddd" ss:Pattern="Solid"/>
        <Borders>
          <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
        </Borders>
    </Style>
    <Style ss:ID="line">
        <Alignment ss:Horizontal="Left" ss:Vertical="Center" ss:WrapText="1"/>
        <Borders>
          <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
        </Borders>
    </Style>
    <Style ss:ID="lineRight">
        <Alignment ss:Horizontal="Right" ss:Vertical="Center" ss:WrapText="1"/>
        <Borders>
          <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
        </Borders>
    </Style>
    <Style ss:ID="lineNumber">
    <Alignment ss:Horizontal="Right" ss:Vertical="Top" ss:WrapText="1"/>
    <Borders>
      <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
      <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
      <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
      <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
    </Borders>
    <NumberFormat ss:Format="#,##0.00"/>
    </Style>
    <Style ss:ID="short_date">
     <Alignment ss:Horizontal="Left" ss:Vertical="Center" ss:WrapText="1"/>
     <Borders>
      <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
      <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
      <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
      <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
     </Borders>
     <NumberFormat ss:Format="Short Date"/>
    </Style>
</Styles>
<%
col_count = 12
header_merge_accross_count = col_count - 1
%>
% for o in objects:
<ss:Worksheet ss:Name="FO Follow Up">
<Table x:FullColumns="1" x:FullRows="1">
<Column ss:AutoFitWidth="1" ss:Width="120" />
<Column ss:AutoFitWidth="1" ss:Width="120" />
<Column ss:AutoFitWidth="1" ss:Width="80" />
<Column ss:AutoFitWidth="1" ss:Width="80" />
<Column ss:AutoFitWidth="1" ss:Width="80" />
<Column ss:AutoFitWidth="1" ss:Width="80" />
<Column ss:AutoFitWidth="1" ss:Width="80" />
<Column ss:AutoFitWidth="1" ss:Width="80" />
<Column ss:AutoFitWidth="1" ss:Width="80" />
<Column ss:AutoFitWidth="1" ss:Width="80" />
<Column ss:AutoFitWidth="1" ss:Width="80" />
<Column ss:AutoFitWidth="1" ss:Width="80" />
## Worksheet Header
<%
if header_merge_accross_count:
    merge_accross = ' ss:MergeAcross="%d"' % (header_merge_accross_count, )
else:
    merge_accross = ''
%>
<Row>
    <Cell ss:StyleID="ssCellBold"><Data ss:Type="String">${_('Internal reference:')}</Data></Cell>
    <Cell ss:StyleID="line"${merge_accross}><Data ss:Type="String">${o.order_id and o.order_id.name or ''|x}</Data></Cell>
</Row>
<Row>
    <Cell ss:StyleID="ssCellBold"><Data ss:Type="String">${_('Customer reference:')}</Data></Cell>
    <Cell ss:StyleID="line"${merge_accross}><Data ss:Type="String">${o.cust_ref or ''|x}</Data></Cell>
</Row>
<Row>
    <Cell ss:StyleID="ssCellBold"><Data ss:Type="String">${_('Creation date:')}</Data></Cell>
    <Cell ss:StyleID="short_date"${merge_accross}><Data ss:Type="DateTime">${parse_date_xls(o.creation_date, is_datetime=True)|n}</Data></Cell>
</Row>
<Row>
    <Cell ss:StyleID="ssCellBold"><Data ss:Type="String">${_('Order state:')}</Data></Cell>
    <Cell ss:StyleID="line"${merge_accross}><Data ss:Type="String">${o.state or ''|x}</Data></Cell>
</Row>
<Row>
    <Cell ss:StyleID="ssCellBold"><Data ss:Type="String">${_('Requested date:')}</Data></Cell>
    <Cell ss:StyleID="short_date"${merge_accross}><Data ss:Type="DateTime">${parse_date_xls(o.requested_date)|n}</Data></Cell>
</Row>
<Row>
    <Cell ss:StyleID="ssCellBold"><Data ss:Type="String">${_('Confirmed date:')}</Data></Cell>
    <Cell ss:StyleID="short_date"${merge_accross}><Data ss:Type="DateTime">${parse_date_xls(o.confirmed_date)|n}</Data></Cell>
</Row>
<Row>
% for c in range(0, col_count):
    <Cell ss:StyleID="line"><Data ss:Type="String"></Data></Cell>
% endfor
</Row>
## Tab Data Header
<Row>
    <Cell ss:StyleID="header"><Data ss:Type="String">ORDER LINE</Data></Cell>
    <Cell ss:StyleID="header"><Data ss:Type="String">PRODUCT CODE</Data></Cell>
    <Cell ss:StyleID="header"><Data ss:Type="String">PROC. METHOD</Data></Cell>
    <Cell ss:StyleID="header"><Data ss:Type="String">PO/FCT</Data></Cell>
    <Cell ss:StyleID="header"><Data ss:Type="String">ORDERED QTY</Data></Cell>
    <Cell ss:StyleID="header"><Data ss:Type="String">UOM</Data></Cell>
    <Cell ss:StyleID="header"><Data ss:Type="String">SOURCED</Data></Cell>
    <Cell ss:StyleID="header"><Data ss:Type="String">TENDER</Data></Cell>
    <Cell ss:StyleID="header"><Data ss:Type="String">PURCHASE ORDER</Data></Cell>
    <Cell ss:StyleID="header"><Data ss:Type="String">INCOMING SHIPMENT</Data></Cell>
    <Cell ss:StyleID="header"><Data ss:Type="String">PRODUCT AVAILABLE</Data></Cell>
    <Cell ss:StyleID="header"><Data ss:Type="String">OUTGOING DELIVERY</Data></Cell>
</Row>
## Tab Data Lines
##    % for line in o.order_line:
##<Row>
##    <Cell ss:StyleID="line" ><Data ss:Type="String"></Data></Cell>
## </Row>
##    % endfor
</Table>
<WorksheetOptions xmlns="urn:schemas-microsoft-com:office:excel">
   <PageSetup>
    <Layout x:Orientation="Landscape"/>
    <Header x:Data="&amp;L&amp;&quot;Arial,Bold&quot;&amp;12$vg-uftp-233_HQ1 / vg-uftp-233_MISSION_OC / vg-uftp-233_HQ1&amp;C&amp;&quot;Arial,Bold&quot;&amp;14EXPIRY REPORT"/>
    <Footer x:Data="Page &amp;P of &amp;N"/>
   </PageSetup>
   <Print>
    <ValidPrinterInfo/>
    <PaperSizeIndex>9</PaperSizeIndex>
    <HorizontalResolution>600</HorizontalResolution>
    <VerticalResolution>600</VerticalResolution>
   </Print>
   <Selected/>
   <Panes>
    <Pane>
     <Number>3</Number>
     <ActiveRow>17</ActiveRow>
    </Pane>
   </Panes>
   <ProtectObjects>False</ProtectObjects>
   <ProtectScenarios>False</ProtectScenarios>
</WorksheetOptions></ss:Worksheet>
% endfor
</Workbook>
