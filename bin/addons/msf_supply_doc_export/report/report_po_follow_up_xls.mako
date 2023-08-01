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
        <Font ss:FontName="Calibri" x:Family="Swiss" ss:Color="#000000" ss:Bold="1"/>
        <Interior ss:Color="#ffcc99" ss:Pattern="Solid"/>
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

    <Style ss:ID="lgrey">
        <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
        <Borders>
          <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
          <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
        </Borders>
        <Font ss:Color="#747474"/>
    </Style>
    
  <Style ss:ID="short_date">
   <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
   <Borders>
    <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
    <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
    <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
    <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
   </Borders>
   <NumberFormat ss:Format="[ENG][$-409]d\-mmm\-yyyy;@"/>
  </Style>
  <Style ss:ID="short_date_grey">
   <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
   <Borders>
    <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
    <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
    <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
    <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
   </Borders>
   <Font ss:Color="#747474"/>
   <NumberFormat ss:Format="[ENG][$-409]d\-mmm\-yyyy;@"/>
  </Style>
  <Style ss:ID="short_date_fr">
   <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
   <Borders>
    <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
    <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
    <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
    <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
   </Borders>
   <NumberFormat ss:Format="Short Date"/>
  </Style>
  <Style ss:ID="short_date_grey_fr">
   <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
   <Borders>
    <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
    <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
    <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
    <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
   </Borders>
   <Font ss:Color="#747474"/>
   <NumberFormat ss:Format="Short Date"/>
  </Style>
</Styles>

<ss:Worksheet ss:Name="${_('PO Follow Up')}">
## definition of the columns' size
<% nb_of_columns = 21 %>
<Table x:FullColumns="1" x:FullRows="1">
    # Order ref
    <Column ss:AutoFitWidth="1" ss:Width="150" />
    # Supplier
    <Column ss:AutoFitWidth="1" ss:Width="150" />
    # Order Type
    <Column ss:AutoFitWidth="1" ss:Width="65" />
    # Order Category
    <Column ss:AutoFitWidth="1" ss:Width="65" />
    # Priority
    <Column ss:AutoFitWidth="1" ss:Width="65" />
    # Line
    <Column ss:AutoFitWidth="1" ss:Width="40" />
    # Product Code
    <Column ss:AutoFitWidth="1" ss:Width="100" />
    # Product Description
    <Column ss:AutoFitWidth="1" ss:Width="200" />
    # Qty ordered
    <Column ss:AutoFitWidth="1" ss:Width="57" />
    # UoM
    <Column ss:AutoFitWidth="1" ss:Width="40" />
    # Qty received
    <Column ss:AutoFitWidth="1" ss:Width="65" />
    # IN
    <Column ss:AutoFitWidth="1" ss:Width="60" />
    # Qty backorder
    <Column ss:AutoFitWidth="1" ss:Width="58" />
    # Unit Price
    <Column ss:AutoFitWidth="1" ss:Width="65" />
    # IN Unit Price
    <Column ss:AutoFitWidth="1" ss:Width="65" />
    # Currency
    <Column ss:AutoFitWidth="1" ss:Width="65" />
    # Total Currency
    <Column ss:AutoFitWidth="1" ss:Width="95" />
    # Total Functional Currency
    <Column ss:AutoFitWidth="1" ss:Width="95" />
    # Created (order)
    <Column ss:AutoFitWidth="1" ss:Width="80" />
    # Requested Delivery Date
    <Column ss:AutoFitWidth="1" ss:Width="80" />
    # Estimated Delivery Date
    <Column ss:AutoFitWidth="1" ss:Width="80" />
    # Confirmed Delivery Date
    <Column ss:AutoFitWidth="1" ss:Width="80" />
    # Status (line)
    <Column ss:AutoFitWidth="1" ss:Width="80" />
    # Status (order)
    <Column ss:AutoFitWidth="1" ss:Width="80" />
    # PO Details
    <Column ss:AutoFitWidth="1" ss:Width="200" />
    # Customer
    <Column ss:AutoFitWidth="1" ss:Width="120" />
    # Customer ref
    <Column ss:AutoFitWidth="1" ss:Width="150" />
    # Source document
    <Column ss:AutoFitWidth="1" ss:Width="150" />
    # Source Creation Date
    <Column ss:AutoFitWidth="1" ss:Width="80" />
    # Supplier ref
    <Column ss:AutoFitWidth="1" ss:Width="150" />
    # MML Status
    <Column ss:AutoFitWidth="1" ss:Width="40" />
    # MSL Status
    <Column ss:AutoFitWidth="1" ss:Width="40" />
<Row>
    <Cell ss:MergeAcross="2" ss:StyleID="mainheader"><Data ss:Type="String">${getRunParms()['title'] or '' |x}</Data></Cell>
</Row>
<Row ss:AutoFitHeight="1">
   <Cell ss:MergeAcross="1" ss:StyleID="poheader"><Data ss:Type="String">${getRunParms()['run_date_title'] or '' |x}</Data></Cell>
   % if getRunParms()['run_date'] and isDate(getRunParms()['run_date']):
       % if getLang() == 'fr_MF':
       <Cell ss:StyleID="short_date_fr"><Data ss:Type="DateTime">${getRunParms()['run_date']|n}T00:00:00.000</Data></Cell>
       % else:
       <Cell ss:StyleID="short_date"><Data ss:Type="DateTime">${getRunParms()['run_date']|n}T00:00:00.000</Data></Cell>
       % endif
   % else:
   <Cell ss:StyleID="line"><Data ss:Type="String"></Data></Cell>
   % endif
</Row>
<Row ss:AutoFitHeight="1">
   <Cell ss:MergeAcross="1" ss:StyleID="poheader"><Data ss:Type="String">${getRunParms()['date_from_title'] or ''|x}</Data></Cell>
   % if getRunParms()['date_from'] and isDate(getRunParms()['date_from']):
       % if getLang() == 'fr_MF':
       <Cell ss:StyleID="short_date_fr"><Data ss:Type="DateTime">${getRunParms()['date_from']|n}T00:00:00.000</Data></Cell>
       % else:
       <Cell ss:StyleID="short_date"><Data ss:Type="DateTime">${getRunParms()['date_from']|n}T00:00:00.000</Data></Cell>
       % endif
   % else:
   <Cell ss:StyleID="line"><Data ss:Type="String"></Data></Cell>
   % endif
</Row>
<Row ss:AutoFitHeight="1">
   <Cell ss:MergeAcross="1" ss:StyleID="poheader"><Data ss:Type="String">${getRunParms()['date_thru_title'] or '' |x}</Data></Cell>
   % if getRunParms()['date_thru'] and isDate(getRunParms()['date_thru']):
       % if getLang() == 'fr_MF':
       <Cell ss:StyleID="short_date_fr"><Data ss:Type="DateTime">${getRunParms()['date_thru']|n}T00:00:00.000</Data></Cell>
       % else:
       <Cell ss:StyleID="short_date"><Data ss:Type="DateTime">${getRunParms()['date_thru']|n}T00:00:00.000</Data></Cell>
       % endif
   % else:
   <Cell ss:StyleID="line"><Data ss:Type="String"></Data></Cell>
   % endif
</Row>

    <Row ss:AutoFitHeight="1" > 
      % for header in getPOLineHeaders():
    	    <Cell ss:StyleID="header"><Data ss:Type="String">${header}</Data></Cell>
       % endfor       
    </Row>
    
% for o in objects:
  % for line in getPOLines(getRunParms()['export_format'], o.id):
    % if (getRunParms()['pending_only_ok'] and float(line['qty_backordered']) > 0) or not getRunParms()['pending_only_ok']: 
    <Row ss:AutoFitHeight="1">
      <Cell ss:StyleID="${getLineStyle(line)|x}"><Data ss:Type="String">${(line['order_ref'])|x}</Data></Cell>
      <Cell ss:StyleID="${getLineStyle(line)|x}"><Data ss:Type="String">${(line['supplier'])|x}</Data></Cell>
      <Cell ss:StyleID="${getLineStyle(line)|x}"><Data ss:Type="String">${(line['order_type'])|x}</Data></Cell>
      <Cell ss:StyleID="${getLineStyle(line)|x}"><Data ss:Type="String">${(line['order_category'])|x}</Data></Cell>
      <Cell ss:StyleID="${getLineStyle(line)|x}"><Data ss:Type="String">${(line['priority'])|x}</Data></Cell>
      <Cell ss:StyleID="${getLineStyle(line)|x}"><Data ss:Type="Number">${(line['item'])|x}</Data></Cell>
      <Cell ss:StyleID="${getLineStyle(line)|x}"><Data ss:Type="String">${(line['code'])|x}</Data></Cell>
      <Cell ss:StyleID="${getLineStyle(line)|x}"><Data ss:Type="String">${(line['description'])|x}</Data></Cell>
      <Cell ss:StyleID="${getLineStyle(line)|x}"><Data ss:Type="Number">${(line['qty_ordered'])|x}</Data></Cell>
      <Cell ss:StyleID="${getLineStyle(line)|x}"><Data ss:Type="String">${(line['uom'])|x}</Data></Cell>
      <Cell ss:StyleID="${getLineStyle(line)|x}"><Data ss:Type="Number">${(line['qty_received'])|x}</Data></Cell>
      <Cell ss:StyleID="${getLineStyle(line)|x}"><Data ss:Type="String">${(line['in'])|x}</Data></Cell>
      <Cell ss:StyleID="${getLineStyle(line)|x}"><Data ss:Type="Number">${(line['qty_backordered'])|x}</Data></Cell>
      <Cell ss:StyleID="${getLineStyle(line)|x}"><Data ss:Type="Number">${(line['unit_price'])|x}</Data></Cell>
      <Cell ss:StyleID="${getLineStyle(line)|x}"><Data ss:Type="Number">${(line['in_unit_price'])|x}</Data></Cell>
      <Cell ss:StyleID="${getLineStyle(line)|x}"><Data ss:Type="String">${(line['currency'])|x}</Data></Cell>
      <Cell ss:StyleID="${getLineStyle(line)|x}"><Data ss:Type="Number">${(line['total_currency'])|x}</Data></Cell>
      <Cell ss:StyleID="${getLineStyle(line)|x}"><Data ss:Type="Number">${(line['total_func_currency'])|x}</Data></Cell>
      % if line['order_created'] and isDate(line['order_created']):
        % if line['raw_state'] in ['cancel', 'cancel_r']:
          % if getLang() == 'fr_MF':
          <Cell ss:StyleID="short_date_grey_fr"><Data ss:Type="DateTime">${line['order_created']|n}T00:00:00.000</Data></Cell>
          % else:
          <Cell ss:StyleID="short_date_grey"><Data ss:Type="DateTime">${line['order_created']|n}T00:00:00.000</Data></Cell>
          % endif
        % else:
          % if getLang() == 'fr_MF':
          <Cell ss:StyleID="short_date_fr"><Data ss:Type="DateTime">${line['order_created']|n}T00:00:00.000</Data></Cell>
          % else:
          <Cell ss:StyleID="short_date"><Data ss:Type="DateTime">${line['order_created']|n}T00:00:00.000</Data></Cell>
          % endif
        % endif
      % else:
      <Cell ss:StyleID="${getLineStyle(line)|x}"><Data ss:Type="String"></Data></Cell>
      % endif
      % if line['delivery_requested_date'] and isDate(line['delivery_requested_date']):
        % if line['raw_state'] in ['cancel', 'cancel_r']:
          % if getLang() == 'fr_MF':
          <Cell ss:StyleID="short_date_grey_fr"><Data ss:Type="DateTime">${line['delivery_requested_date']|n}T00:00:00.000</Data></Cell>
          % else:
          <Cell ss:StyleID="short_date_grey"><Data ss:Type="DateTime">${line['delivery_requested_date']|n}T00:00:00.000</Data></Cell>
          % endif
        % else:
          % if getLang() == 'fr_MF':
          <Cell ss:StyleID="short_date_fr"><Data ss:Type="DateTime">${line['delivery_requested_date']|n}T00:00:00.000</Data></Cell>
          % else:
          <Cell ss:StyleID="short_date"><Data ss:Type="DateTime">${line['delivery_requested_date']|n}T00:00:00.000</Data></Cell>
          % endif
        % endif
      % else:
      <Cell ss:StyleID="${getLineStyle(line)|x}"><Data ss:Type="String"></Data></Cell>
      % endif
      % if line['estimated_delivery_date'] and isDate(line['estimated_delivery_date']):
        % if line['raw_state'] in ['cancel', 'cancel_r']:
          % if getLang() == 'fr_MF':
          <Cell ss:StyleID="short_date_grey_fr"><Data ss:Type="DateTime">${line['estimated_delivery_date']|n}T00:00:00.000</Data></Cell>
          % else:
          <Cell ss:StyleID="short_date_grey"><Data ss:Type="DateTime">${line['estimated_delivery_date']|n}T00:00:00.000</Data></Cell>
          % endif
        % else:
          % if getLang() == 'fr_MF':
          <Cell ss:StyleID="short_date_fr"><Data ss:Type="DateTime">${line['estimated_delivery_date']|n}T00:00:00.000</Data></Cell>
          % else:
          <Cell ss:StyleID="short_date"><Data ss:Type="DateTime">${line['estimated_delivery_date']|n}T00:00:00.000</Data></Cell>
          % endif
        % endif
      % else:
      <Cell ss:StyleID="${getLineStyle(line)|x}"><Data ss:Type="String"></Data></Cell>
      % endif
      % if line['order_confirmed_date'] and isDate(line['order_confirmed_date']):
        % if line['raw_state'] in ['cancel', 'cancel_r']:
          % if getLang() == 'fr_MF':
          <Cell ss:StyleID="short_date_grey_fr"><Data ss:Type="DateTime">${line['order_confirmed_date']|n}T00:00:00.000</Data></Cell>
          % else:
          <Cell ss:StyleID="short_date_grey"><Data ss:Type="DateTime">${line['order_confirmed_date']|n}T00:00:00.000</Data></Cell>
          % endif
        % else:
          % if getLang() == 'fr_MF':
          <Cell ss:StyleID="short_date_fr"><Data ss:Type="DateTime">${line['order_confirmed_date']|n}T00:00:00.000</Data></Cell>
          % else:
          <Cell ss:StyleID="short_date"><Data ss:Type="DateTime">${line['order_confirmed_date']|n}T00:00:00.000</Data></Cell>
          % endif
        % endif
      % else:
      <Cell ss:StyleID="${getLineStyle(line)|x}"><Data ss:Type="String"></Data></Cell>
      % endif
      <Cell ss:StyleID="${getLineStyle(line)|x}"><Data ss:Type="String">${(line['state'])|x}</Data></Cell>
      <Cell ss:StyleID="${getLineStyle(line)|x}"><Data ss:Type="String">${(line['order_status'])|x}</Data></Cell>
      <Cell ss:StyleID="${getLineStyle(line)|x}"><Data ss:Type="String">${(line['po_details'])|x}</Data></Cell>
      <Cell ss:StyleID="${getLineStyle(line)|x}"><Data ss:Type="String">${(line['customer'])|x}</Data></Cell>
      <Cell ss:StyleID="${getLineStyle(line)|x}"><Data ss:Type="String">${(line['customer_ref'])|x}</Data></Cell>
      <Cell ss:StyleID="${getLineStyle(line)|x}"><Data ss:Type="String">${(line['source_doc'])|x}</Data></Cell>
      % if line['source_creation_date'] and isDate(line['source_creation_date']):
        % if line['raw_state'] in ['cancel', 'cancel_r']:
          % if getLang() == 'fr_MF':
          <Cell ss:StyleID="short_date_grey_fr"><Data ss:Type="DateTime">${line['source_creation_date']|n}T00:00:00.000</Data></Cell>
          % else:
          <Cell ss:StyleID="short_date_grey"><Data ss:Type="DateTime">${line['source_creation_date']|n}T00:00:00.000</Data></Cell>
          % endif
        % else:
          % if getLang() == 'fr_MF':
          <Cell ss:StyleID="short_date_fr"><Data ss:Type="DateTime">${line['source_creation_date']|n}T00:00:00.000</Data></Cell>
          % else:
          <Cell ss:StyleID="short_date"><Data ss:Type="DateTime">${line['source_creation_date']|n}T00:00:00.000</Data></Cell>
          % endif
        % endif
      % else:
      <Cell ss:StyleID="${getLineStyle(line)|x}"><Data ss:Type="String"></Data></Cell>
      % endif
      <Cell ss:StyleID="${getLineStyle(line)|x}"><Data ss:Type="String">${(line['supplier_ref'])|x}</Data></Cell>
      <Cell ss:StyleID="${getLineStyle(line)|x}"><Data ss:Type="String">${(line['mml_status'])|x}</Data></Cell>
      <Cell ss:StyleID="${getLineStyle(line)|x}"><Data ss:Type="String">${(line['msl_status'])|x}</Data></Cell>
    </Row>
    % endif
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
