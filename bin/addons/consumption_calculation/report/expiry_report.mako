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
<ss:Worksheet ss:Name="Expiry report">
<Table x:FullColumns="1" x:FullRows="1">
<%
cols_count = 10
now = time.strftime('%Y-%m-%d')
%>
<Column ss:AutoFitWidth="1" ss:Width="80" />
<Column ss:AutoFitWidth="1" ss:Width="120" />
<Column ss:AutoFitWidth="1" ss:Width="50" />
<Column ss:AutoFitWidth="1" ss:Width="60" />
<Column ss:AutoFitWidth="1" ss:Width="30" />
<Column ss:AutoFitWidth="1" ss:Width="80" />
<Column ss:AutoFitWidth="1" ss:Width="70" />
<Column ss:AutoFitWidth="1" ss:Width="60" />
<Column ss:AutoFitWidth="1" ss:Width="60" />
<Column ss:AutoFitWidth="1" ss:Width="60" />
## header
<Row>
<Cell ss:StyleID="ssCellBold"><Data ss:Type="String">Report date :</Data></Cell>
<Cell ss:StyleID="ssCell" ss:MergeAcross="8"><Data ss:Type="String">${toDate()|x}</Data></Cell>
</Row>
<Row>
<Cell ss:StyleID="ssCellBold"><Data ss:Type="String">Location :</Data></Cell>
<Cell ss:StyleID="ssCell" ss:MergeAcross="8"><Data ss:Type="String">${(objects[0].location_id and objects[0].location_id.name or '')|x}</Data></Cell>
</Row>
<Row>
<Cell ss:StyleID="ssCellBold"><Data ss:Type="String">Period of&#10;calculation :</Data></Cell>
<Cell ss:StyleID="ssCell" ss:MergeAcross="8"><Data ss:Type="String">${objects[0].week_nb} week${objects[0].week_nb > 1 and 's' or ''}</Data></Cell>
</Row>
<Row>
<Cell ss:StyleID="ssCellBold"><Data ss:Type="String">Limit date :</Data></Cell>
<Cell ss:StyleID="ssCell" ss:MergeAcross="8"><Data ss:Type="String">${toDate(objects[0].date_to)|x}</Data></Cell>
</Row>
<Row>
<Cell ss:StyleID="ssCellBold"><Data ss:Type="String">Currency :</Data></Cell>
<Cell ss:StyleID="ssCell" ss:MergeAcross="8"><Data ss:Type="String">${getCurrency()|x}</Data></Cell>
</Row>
<Row>
% for c in range(cols_count):
<Cell ss:StyleID="ssCell"></Cell>
% endfor
</Row>
## products/batches already expired
<Row>
<Cell ss:StyleID="headerLeft" ss:MergeAcross="9"><Data ss:Type="String">Products/batches already expired</Data></Cell>
</Row>
<Row>
<Cell ss:StyleID="header"><Data ss:Type="String">CODE</Data></Cell>
<Cell ss:StyleID="header"><Data ss:Type="String">DESCRIPTION</Data></Cell>
<Cell ss:StyleID="header"><Data ss:Type="String">Location</Data></Cell>
<Cell ss:StyleID="headerRight"><Data ss:Type="String">Stock</Data></Cell>
<Cell ss:StyleID="header"><Data ss:Type="String">UoM</Data></Cell>
<Cell ss:StyleID="header"><Data ss:Type="String">Batch</Data></Cell>
<Cell ss:StyleID="header"><Data ss:Type="String">Expirity Date</Data></Cell>
<Cell ss:StyleID="headerRight"><Data ss:Type="String">Exp. Qty</Data></Cell>
<Cell ss:StyleID="headerRight"><Data ss:Type="String">Unit Cost</Data></Cell>
<Cell ss:StyleID="headerRight"><Data ss:Type="String">Exp. Value</Data></Cell>
</Row>
% for l in objects[0].line_ids:
% if l.expiry_date < now:
<Row>
<Cell ss:StyleID="line"><Data ss:Type="String">${(l.product_id.default_code or '')|x}</Data></Cell>
<Cell ss:StyleID="line"><Data ss:Type="String">${l.product_name|x}</Data></Cell>
<Cell ss:StyleID="line"><Data ss:Type="String">${l.location_id and l.location_id.name|x}</Data></Cell>
<Cell ss:StyleID="lineNumber"><Data ss:Type="Number">${l.real_stock or 0.0}</Data></Cell>
<Cell ss:StyleID="line"><Data ss:Type="String">${l.uom_id and l.uom_id.name|x}</Data></Cell>
<Cell ss:StyleID="line"><Data ss:Type="String">${l.batch_number|x}</Data></Cell>
<Cell ss:StyleID="line"><Data ss:Type="String">${l.expiry_date|x}</Data></Cell>
<Cell ss:StyleID="lineNumber"><Data ss:Type="Number">${l.expired_qty or 0.00}</Data></Cell>
<Cell ss:StyleID="lineNumber"><Data ss:Type="Number">${l.product_id and l.product_id.standard_price or 0.00}</Data></Cell>
<Cell ss:StyleID="lineNumber"><Data ss:Type="Number">${l.product_id and l.product_id.standard_price*l.expired_qty or 0.0}</Data></Cell>
</Row>
% endif
% endfor
<Row>
<Cell ss:StyleID="ssCell"></Cell>
<Cell ss:StyleID="ssCell"></Cell>
<Cell ss:StyleID="ssCell"></Cell>
<Cell ss:StyleID="ssCell"></Cell>
<Cell ss:StyleID="ssCell"></Cell>
<Cell ss:StyleID="ssCell"></Cell>
<Cell ss:StyleID="ssCell"></Cell>
<Cell ss:StyleID="ssCell"></Cell>
<Cell ss:StyleID="ssCellRightBold"><Data ss:Type="String">TOTAL</Data></Cell>
<Cell ss:StyleID="ssCellRightBold"><Data ss:Type="String">${formatLang(getTotal(objects[0], 'expired'))}</Data></Cell>
</Row>
## products/batches to expire
<Row>
% for c in range(cols_count):
<Cell ss:StyleID="ssCell"></Cell>
% endfor
</Row>
<Row>
<Cell ss:StyleID="headerLeft" ss:MergeAcross="9"><Data ss:Type="String">Products/batches to expire</Data></Cell>
</Row>
<Row>
<Cell ss:StyleID="header"><Data ss:Type="String">CODE</Data></Cell>
<Cell ss:StyleID="header"><Data ss:Type="String">DESCRIPTION</Data></Cell>
<Cell ss:StyleID="header"><Data ss:Type="String">Location</Data></Cell>
<Cell ss:StyleID="headerRight"><Data ss:Type="String">Stock</Data></Cell>
<Cell ss:StyleID="header"><Data ss:Type="String">UoM</Data></Cell>
<Cell ss:StyleID="header"><Data ss:Type="String">Batch</Data></Cell>
<Cell ss:StyleID="header"><Data ss:Type="String">Expirity Date</Data></Cell>
<Cell ss:StyleID="headerRight"><Data ss:Type="String">Exp. Qty</Data></Cell>
<Cell ss:StyleID="headerRight"><Data ss:Type="String">Unit Cost</Data></Cell>
<Cell ss:StyleID="headerRight"><Data ss:Type="String">Exp. Value</Data></Cell>
</Row>
% for l in objects[0].line_ids:
% if l.expiry_date >= now:
<Row>
<Cell ss:StyleID="line"><Data ss:Type="String">${(l.product_id.default_code or '')|x}</Data></Cell>
<Cell ss:StyleID="line"><Data ss:Type="String">${l.product_name|x}</Data></Cell>
<Cell ss:StyleID="line"><Data ss:Type="String">${l.location_id and l.location_id.name|x}</Data></Cell>
<Cell ss:StyleID="lineNumber"><Data ss:Type="Number">${l.real_stock or 0.0}</Data></Cell>
<Cell ss:StyleID="line"><Data ss:Type="String">${l.uom_id and l.uom_id.name|x}</Data></Cell>
<Cell ss:StyleID="line"><Data ss:Type="String">${l.batch_number|x}</Data></Cell>
<Cell ss:StyleID="line"><Data ss:Type="String">${l.expiry_date|x}</Data></Cell>
<Cell ss:StyleID="lineNumber"><Data ss:Type="Number">${l.expired_qty or 0.00}</Data></Cell>
<Cell ss:StyleID="lineNumber"><Data ss:Type="Number">${l.product_id and l.product_id.standard_price or 0.00}</Data></Cell>
<Cell ss:StyleID="lineNumber"><Data ss:Type="Number">${l.product_id and l.product_id.standard_price*l.expired_qty or 0.0}</Data></Cell>
</Row>
% endif
% endfor
<Row>
<Cell ss:StyleID="ssCell"></Cell>
<Cell ss:StyleID="ssCell"></Cell>
<Cell ss:StyleID="ssCell"></Cell>
<Cell ss:StyleID="ssCell"></Cell>
<Cell ss:StyleID="ssCell"></Cell>
<Cell ss:StyleID="ssCell"></Cell>
<Cell ss:StyleID="ssCell"></Cell>
<Cell ss:StyleID="ssCell"></Cell>
<Cell ss:StyleID="ssCellRightBold"><Data ss:Type="String">TOTAL</Data></Cell>
<Cell ss:StyleID="ssCellRightBold"><Data ss:Type="String">${formatLang(getTotal(objects[0], 'expiry'))}</Data></Cell>
</Row>
## ALL TOTAL
<Row>
% for c in range(cols_count):
<Cell ss:StyleID="ssCell"></Cell>
% endfor
</Row>
<Row>
<Cell ss:StyleID="ssCell"></Cell>
<Cell ss:StyleID="ssCell"></Cell>
<Cell ss:StyleID="ssCell"></Cell>
<Cell ss:StyleID="ssCell"></Cell>
<Cell ss:StyleID="ssCell"></Cell>
<Cell ss:StyleID="ssCell"></Cell>
<Cell ss:StyleID="ssCell"></Cell>
<Cell ss:StyleID="ssCell"></Cell>
<Cell ss:StyleID="ssCellRightBold"><Data ss:Type="String">ALL TOTAL</Data></Cell>
<Cell ss:StyleID="ssCellRightBold"><Data ss:Type="String">${formatLang(getTotal(objects[0], 'all'))}</Data></Cell>
</Row>
</Table>
<WorksheetOptions xmlns="urn:schemas-microsoft-com:office:excel">
   <PageSetup>
    <Layout x:Orientation="Landscape"/>
    <Header x:Data="&amp;L&amp;&quot;Arial,Bold&quot;&amp;12$${getAddress()}&amp;C&amp;&quot;Arial,Bold&quot;&amp;14EXPIRY REPORT"/>
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
</WorksheetOptions>
</ss:Worksheet>
</Workbook>
