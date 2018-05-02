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
  <Style ss:ID="mainheader">
        <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="0"/>
        <Font ss:FontName="Calibri" x:Family="Swiss" ss:Color="#000000"/>
        <Interior ss:Color="#E6E6E6" ss:Pattern="Solid"/>
        <Borders>
          <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
        </Borders>
    </Style>

    <Style ss:ID="poheader">
        <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
        <Interior ss:Color="#ffcc99" ss:Pattern="Solid"/>
        <Borders>
          <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
        </Borders>
    </Style>
    
    <Style ss:ID="header">
        <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
        <Interior ss:Color="#d3d3d3" ss:Pattern="Solid"/>
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

<ss:Worksheet ss:Name="PO Follow Up">
## definition of the columns' size
<% nb_of_columns = 12 %>
<Table x:FullColumns="1" x:FullRows="1">
    # Order name
    <Column ss:AutoFitWidth="1" ss:Width="65" />
    # Item
    <Column ss:AutoFitWidth="1" ss:Width="40" />
    # Code
    <Column ss:AutoFitWidth="1" ss:Width="81" />
    # Description
    <Column ss:AutoFitWidth="1" ss:Width="161" />
    # Qty ordered
    <Column ss:AutoFitWidth="1" ss:Width="57" />
    # UoM
    <Column ss:AutoFitWidth="1" ss:Width="65" />
    # Qty received
    <Column ss:AutoFitWidth="1" ss:Width="80" />
    # IN
    <Column ss:AutoFitWidth="1" ss:Width="60" />
    # Qty backorder
    <Column ss:AutoFitWidth="1" ss:Width="58" />
    # Unit Price
    <Column ss:AutoFitWidth="1" ss:Width="95" />
    # IN Unit Price
    <Column ss:AutoFitWidth="1" ss:Width="95" />
    # Created (order)
    <Columns ss:AutoFitWidth="1" ss:Width="95" />
    # Delivery Confirmed (order)
    <Columns ss:AutoFitWidth="1" ss:Width="95" />
    # Status (line)
    <Columns ss:AutoFitWidth="1" ss:Width="95" />
    # Status (order)
    <Columns ss:AutoFitWidth="1" ss:Width="95" />
    # Destination
    <Column ss:AutoFitWidth="1" ss:Width="95" />
    # Cost Center
    <Column ss:AutoFitWidth="1" ss:Width="95" />

<Row>
    <Cell ss:MergeAcross="11" ss:StyleID="mainheader"><Data ss:Type="String">${getRunParms()['title'] or '' |x}</Data></Cell>
</Row>
<Row ss:AutoFitHeight="1">
   <Cell ss:MergeAcross="2" ss:StyleID="mainheader"><Data ss:Type="String">Report run date: ${getRunParms()['run_date'] or '' |x}</Data></Cell>
   <Cell ss:MergeAcross="1" ss:StyleID="mainheader"><Data ss:Type="String">PO date from: ${getRunParms()['date_from'] or ''|x}</Data></Cell>
   <Cell ss:MergeAcross="1" ss:StyleID="mainheader"><Data ss:Type="String">PO date to: ${getRunParms()['date_thru'] or '' |x}</Data></Cell>
   <Cell ss:MergeAcross="1" ss:StyleID="mainheader"><Data ss:Type="String">Supplier: ${getRunParms()['supplier'] or '' |x}</Data></Cell>
   <Cell ss:MergeAcross="2" ss:StyleID="mainheader"><Data ss:Type="String">PO State: ${getRunParms()['state'] or '' | x}</Data></Cell>
</Row>

    <Row ss:AutoFitHeight="1" > 
      % for header in getPOLineHeaders():
    	    <Cell ss:StyleID="header"><Data ss:Type="String">${header}</Data></Cell>
       % endfor       
    </Row>
    
% for o in objects:
    
    % for line in getPOLines(o.id):
    <Row ss:AutoFitHeight="1">
        <Cell ss:StyleID="line"><Data ss:Type="String">${(line['order_ref'])|x}</Data></Cell>
        <Cell ss:StyleID="line"><Data ss:Type="Number">${(line['item'])|x}</Data></Cell>
        <Cell ss:StyleID="line"><Data ss:Type="String">${(line['code'])|x}</Data></Cell>
        <Cell ss:StyleID="line"><Data ss:Type="String">${(line['description'])|x}</Data></Cell>
        <Cell ss:StyleID="line"><Data ss:Type="Number">${(line['qty_ordered'])|x}</Data></Cell>
        <Cell ss:StyleID="line"><Data ss:Type="String">${(line['uom'])|x}</Data></Cell>
        <Cell ss:StyleID="line"><Data ss:Type="Number">${(line['qty_received'])|x}</Data></Cell>
        <Cell ss:StyleID="line"><Data ss:Type="String">${(line['in'])|x}</Data></Cell>
        <Cell ss:StyleID="line"><Data ss:Type="Number">${(line['qty_backordered'])|x}</Data></Cell>
        <Cell ss:StyleID="line"><Data ss:Type="Number">${(line['unit_price'])|x}</Data></Cell>
        <Cell ss:StyleID="line"><Data ss:Type="Number">${(line['in_unit_price'])|x}</Data></Cell>
        <Cell ss:StyleID="line"><Data ss:Type="String">${(line['order_created'])|x}</Data></Cell>
        <Cell ss:StyleID="line"><Data ss:Type="String">${(line['order_confirmed_date'])|x}</Data></Cell>
        <Cell ss:StyleID="line"><Data ss:Type="String">${(line['order_status'])|x}</Data></Cell>
        <Cell ss:StyleID="line"><Data ss:Type="String">${(line['state'])|x}</Data></Cell>
        <Cell ss:StyleID="line"><Data ss:Type="String">${(line['destination'])|x}</Data></Cell>
        <Cell ss:StyleID="line"><Data ss:Type="String">${(line['cost_centre'])|x}</Data></Cell>
    </Row>
    % endfor
 % endfor   
    
</Table>
<WorksheetOptions xmlns="urn:schemas-microsoft-com:office:excel">
   <PageSetup>
    <Layout x:Orientation="Landscape"/>
    <Header x:Data="&amp;C&amp;&quot;Arial,Bold&quot;&amp;14${getRunParms()['title'] or '' |x}"/>
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
