<?xml version="1.0"?>
<?mso-application progid="Excel.Sheet"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:o="urn:schemas-microsoft-com:office:office"
 xmlns:x="urn:schemas-microsoft-com:office:excel"
 xmlns:dt="uuid:C2F41010-65B3-11d1-A29F-00AA00C14882"
 xmlns:s="uuid:BDC6E3F0-6DA3-11d1-A2A3-00AA00C14882"
 xmlns:rs="urn:schemas-microsoft-com:rowset" xmlns:z="#RowsetSchema"
 xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:html="http://www.w3.org/TR/REC-html40">
 <DocumentProperties xmlns="urn:schemas-microsoft-com:office:office">
  <Author>Tempo Consulting</Author>
  <LastAuthor>Tempo Consulting</LastAuthor>
  <Created>2015-05-19T15:32:58Z</Created>
  <Version>14.00</Version>
 </DocumentProperties>
 <OfficeDocumentSettings xmlns="urn:schemas-microsoft-com:office:office">
  <AllowPNG/>
 </OfficeDocumentSettings>
 <ExcelWorkbook xmlns="urn:schemas-microsoft-com:office:excel">
  <WindowHeight>7995</WindowHeight>
  <WindowWidth>20115</WindowWidth>
  <WindowTopX>240</WindowTopX>
  <WindowTopY>75</WindowTopY>
  <ProtectStructure>False</ProtectStructure>
  <ProtectWindows>False</ProtectWindows>
 </ExcelWorkbook>
 <Styles>
  <Style ss:ID="Default" ss:Name="Normal">
   <Alignment ss:Vertical="Bottom"/>
   <Borders/>
   <Font ss:FontName="Calibri" x:Family="Swiss" ss:Size="11" ss:Color="#000000"/>
   <Interior/>
   <NumberFormat/>
   <Protection/>
  </Style>
  <Style ss:ID="s63">
   <NumberFormat ss:Format="Standard"/>
  </Style>
  <Style ss:ID="s66">
   <Alignment ss:Horizontal="Left" ss:Vertical="Bottom" ss:Indent="1"/>
  </Style>
  <Style ss:ID="s67">
   <Font ss:FontName="Calibri" x:Family="Swiss" ss:Size="11" ss:Color="#000000"
    ss:Bold="1"/>
   <NumberFormat ss:Format="Standard"/>
  </Style>
  <Style ss:ID="s69">
   <Alignment ss:Horizontal="Left" ss:Vertical="Bottom" ss:Indent="1"/>
   <Font ss:FontName="Calibri" x:Family="Swiss" ss:Size="11" ss:Color="#000000"
    ss:Bold="1"/>
  </Style>
  <Style ss:ID="s74">
   <Font ss:FontName="Calibri" x:Family="Swiss" ss:Size="11" ss:Color="#000000"
    ss:Bold="1"/>
   <Interior ss:Color="#DCE6F1" ss:Pattern="Solid"/>
  </Style>
  <Style ss:ID="s75">
   <Alignment ss:Horizontal="Left" ss:Vertical="Bottom"/>
   <Font ss:FontName="Calibri" x:Family="Swiss" ss:Size="11" ss:Color="#000000"
    ss:Bold="1"/>
   <Interior ss:Color="#DCE6F1" ss:Pattern="Solid"/>
  </Style>
  <Style ss:ID="s76">
   <Font ss:FontName="Calibri" x:Family="Swiss" ss:Size="11" ss:Color="#000000"
    ss:Bold="1"/>
   <Interior ss:Color="#DCE6F1" ss:Pattern="Solid"/>
   <NumberFormat ss:Format="Standard"/>
  </Style>
  <Style ss:ID="s98">
   <Borders/>
  </Style>
  <Style ss:ID="s99">
   <Alignment ss:Horizontal="Left" ss:Vertical="Bottom"/>
   <Borders>
    <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="2"
     ss:Color="#8DB4E2"/>
   </Borders>
   <Font ss:FontName="Calibri" x:Family="Swiss" ss:Size="11" ss:Color="#000000"
    ss:Bold="1"/>
  </Style>
  <Style ss:ID="s100">
   <Borders>
    <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="2"
     ss:Color="#8DB4E2"/>
   </Borders>
   <Font ss:FontName="Calibri" x:Family="Swiss" ss:Size="11" ss:Color="#000000"
    ss:Bold="1"/>
   <NumberFormat ss:Format="Standard"/>
  </Style>
 </Styles>
 % for o in objects:
 <Worksheet ss:Name="${(o.number or title(o)+' '+str(o.id))|x}">
  <Table x:FullColumns="1"
   x:FullRows="1" ss:DefaultColumnWidth="90" ss:DefaultRowHeight="15">
   <Column ss:AutoFitWidth="0" ss:Width="110.25"/>
   <Column ss:AutoFitWidth="0" ss:Width="95.25"/>
   <Column ss:AutoFitWidth="0" ss:Width="69.75"/>
   <Column ss:Width="121.5"/>
   <Column ss:Width="96"/>
   <Row ss:AutoFitHeight="0">
    <Cell><Data ss:Type="String">Invoice :</Data></Cell>
    <Cell><Data ss:Type="String">${(o.number or ' ')|x}</Data></Cell>
   </Row>
   <Row ss:AutoFitHeight="0">
    <Cell><Data ss:Type="String">Type :</Data></Cell>
    <Cell><Data ss:Type="String">${(title(o))|x}</Data></Cell>
   </Row>
   <Row ss:AutoFitHeight="0">
    <Cell><Data ss:Type="String">Supplier :</Data></Cell>
    <Cell><Data ss:Type="String">${(o.partner_id.name)|x}</Data></Cell>
   </Row>
   <Row ss:AutoFitHeight="0">
    <Cell><Data ss:Type="String">Posting date :</Data></Cell>
    <Cell><Data ss:Type="String">${(o.date_invoice or ' ')|x}</Data></Cell>
   </Row>
   <Row ss:AutoFitHeight="0">
    <Cell><Data ss:Type="String">Currency :</Data></Cell>
    <Cell><Data ss:Type="String">${(o.currency_id.name)|x}</Data></Cell>
   </Row>
   <Row ss:AutoFitHeight="0"/>
   <Row ss:AutoFitHeight="0">
    <Cell ss:StyleID="s74"><Data ss:Type="String">Row labels</Data></Cell>
    <Cell ss:StyleID="s74"><Data ss:Type="String">Sum of Amount</Data></Cell>
   </Row>
   % for row in get_data(o.id):
   % if level(row) == 1:
   <Row ss:AutoFitHeight="0">
    <Cell ss:StyleID="s99"><Data ss:Type="String">${(row[0])|x}</Data></Cell>
    <Cell ss:StyleID="s100"><Data ss:Type="Number">${(row[2])|x}</Data></Cell>
   </Row>
   % endif
   % if level(row) == 2:
   <Row ss:AutoFitHeight="0">
    <Cell ss:StyleID="s66"><Data ss:Type="String">${(row[1])|x}</Data></Cell>
    <Cell ss:StyleID="s63"><Data ss:Type="Number">${(row[2])|x}</Data></Cell>
   </Row>
   % endif
   % if level(row) == -1:
   <Row ss:AutoFitHeight="0">
    <Cell ss:StyleID="s75"><Data ss:Type="String">Grand Total</Data></Cell>
    <Cell ss:StyleID="s76"><Data ss:Type="Number">${(row[2])|x}</Data></Cell>
   </Row>
   % endif
   % endfor
  </Table>
  <WorksheetOptions xmlns="urn:schemas-microsoft-com:office:excel">
   <PageSetup>
    <Header x:Margin="0.3"/>
    <Footer x:Margin="0.3"/>
    <PageMargins x:Bottom="0.75" x:Left="0.7" x:Right="0.7" x:Top="0.75"/>
   </PageSetup>
   <Unsynced/>
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
 </Worksheet>
 % endfor
</Workbook>
