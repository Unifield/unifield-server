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

  <Style ss:ID="header_hour_date">
    <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
    <Interior ss:Color="#ffcc99" ss:Pattern="Solid"/>
   <Borders>
    <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
    <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
    <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
    <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
   </Borders>
   <NumberFormat ss:Format="dd/mm/yyyy\ h:mm;@"/>
  </Style>
  <Style ss:ID="header_short_date">
    <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
    <Interior ss:Color="#ffcc99" ss:Pattern="Solid"/>
   <Borders>
    <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
    <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
    <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
    <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
   </Borders>
   <NumberFormat ss:Format="Short Date"/>
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
  <Style ss:ID="hour_date">
   <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
   <Borders>
    <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
    <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
    <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
    <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
   </Borders>
   <NumberFormat ss:Format="dd/mm/yyyy\ h:mm;@"/>
  </Style>
</Styles>

<ss:Worksheet ss:Name="${_('IN & OUT Report')|x}">
## definition of the columns' size
<% nb_of_columns = 15 %>
<Table x:FullColumns="1" x:FullRows="1">
    # Product code
    <Column ss:AutoFitWidth="1" ss:Width="90" />
    # Product Description
    <Column ss:AutoFitWidth="1" ss:Width="200" />
    # UoM
    <Column ss:AutoFitWidth="1" ss:Width="55" />
    # Stock Move Date
    <Column ss:AutoFitWidth="1" ss:Width="110" />
    # Batch
    <Column ss:AutoFitWidth="1" ss:Width="100" />
    # Exp Date
    <Column ss:AutoFitWidth="1" ss:Width="100" />
    # Quantity
    <Column ss:AutoFitWidth="1" ss:Width="80" />
    # Unit Price (EUR / CHF)
    <Column ss:AutoFitWidth="1" ss:Width="80" />
    # Movement value (EUR / CHF)
    <Column ss:AutoFitWidth="1" ss:Width="100" />
    # BN stock after movement (instance/selected location(s))
    <Column ss:AutoFitWidth="1" ss:Width="100" />
    # Total stock after movement (instance/selected location(s))
    <Column ss:AutoFitWidth="1" ss:Width="100" />
    # Source
    <Column ss:AutoFitWidth="1" ss:Width="150" />
    # Destination
    <Column ss:AutoFitWidth="1" ss:Width="150" />
    # Reason Type
    <Column ss:AutoFitWidth="1" ss:Width="120" />
    # Document Ref
    <Column ss:AutoFitWidth="1" ss:Width="80" />

% for o in objects:

    <Row ss:AutoFitHeight="1">
        <Cell ss:MergeAcross="1" ss:StyleID="mainheader"><Data ss:Type="String">${_('DB/instance name')|x}</Data></Cell>
        <Cell ss:MergeAcross="3" ss:StyleID="poheader"><Data ss:Type="String">${o.company_id.name or ''|x}</Data></Cell>
    </Row>
    <Row ss:AutoFitHeight="1">
        <Cell ss:MergeAcross="1" ss:StyleID="mainheader"><Data ss:Type="String">${_('Generated on')|x}</Data></Cell>
        % if o.name and isDateTime(o.name):
            <Cell ss:MergeAcross="3" ss:StyleID="header_hour_date"><Data ss:Type="DateTime">${o.name[:10]|n}T${o.name[-8:]|n}.000</Data></Cell>
        % else:
            <Cell ss:MergeAcross="3" ss:StyleID="poheader"><Data ss:Type="String"></Data></Cell>
        % endif
    </Row>
    <Row ss:AutoFitHeight="1">
        <Cell ss:MergeAcross="1" ss:StyleID="mainheader"><Data ss:Type="String">${_('From')|x}</Data></Cell>
        % if o.date_from and isDate(o.date_from):
            <Cell ss:MergeAcross="3" ss:StyleID="header_short_date"><Data ss:Type="DateTime">${o.date_from[:10]|n}T${o.name[-8:]|n}.000</Data></Cell>
        % else:
            <Cell ss:MergeAcross="3" ss:StyleID="poheader"><Data ss:Type="String"></Data></Cell>
        % endif
    </Row>
    <Row ss:AutoFitHeight="1">
        <Cell ss:MergeAcross="1" ss:StyleID="mainheader"><Data ss:Type="String">${_('To')|x}</Data></Cell>
        % if o.date_to and isDate(o.date_to):
            <Cell ss:MergeAcross="3" ss:StyleID="header_short_date"><Data ss:Type="DateTime">${o.date_to[:10]|n}T${o.name[-8:]|n}.000</Data></Cell>
        % else:
            <Cell ss:MergeAcross="3" ss:StyleID="poheader"><Data ss:Type="String"></Data></Cell>
        % endif
    </Row>
    <Row ss:AutoFitHeight="1">
        <Cell ss:MergeAcross="1" ss:StyleID="mainheader"><Data ss:Type="String">${_('Specific partner')|x}</Data></Cell>
        <Cell ss:MergeAcross="3" ss:StyleID="poheader"><Data ss:Type="String">${o.partner_id and o.partner_id.name or ''|x}</Data></Cell>
    </Row>
    <Row ss:AutoFitHeight="1">
        <Cell ss:MergeAcross="1" ss:StyleID="mainheader"><Data ss:Type="String">${_('Specific location(s)')|x}</Data></Cell>
        <Cell ss:MergeAcross="3" ss:StyleID="poheader"><Data ss:Type="String">${o.location_ids and ' ; '.join([l.name for l in o.location_ids]) or ''|x}</Data></Cell>
    </Row>
    <Row ss:AutoFitHeight="1">
        <Cell ss:MergeAcross="1" ss:StyleID="mainheader"><Data ss:Type="String">${_('Specific product list')|x}</Data></Cell>
        <Cell ss:MergeAcross="3" ss:StyleID="poheader"><Data ss:Type="String">${o.product_list_id and o.product_list_id.name or ''|x}</Data></Cell>
    </Row>
    <Row ss:AutoFitHeight="1">
        <Cell ss:MergeAcross="1" ss:StyleID="mainheader"><Data ss:Type="String">${_('Specific product')|x}</Data></Cell>
        <Cell ss:MergeAcross="3" ss:StyleID="poheader"><Data ss:Type="String">${o.product_id and o.product_id.default_code or ''|x}</Data></Cell>
    </Row>
    <Row ss:AutoFitHeight="1">
        <Cell ss:MergeAcross="1" ss:StyleID="mainheader"><Data ss:Type="String">${_('Specific batch')|x}</Data></Cell>
        <Cell ss:MergeAcross="3" ss:StyleID="poheader"><Data ss:Type="String">${o.prodlot_id and o.prodlot_id.name or ''|x}</Data></Cell>
    </Row>
    <Row ss:AutoFitHeight="1">
        <Cell ss:MergeAcross="1" ss:StyleID="mainheader"><Data ss:Type="String">${_('Specific expiry date')|x}</Data></Cell>
        % if o.expiry_date and isDate(o.expiry_date):
            <Cell ss:MergeAcross="3" ss:StyleID="header_short_date"><Data ss:Type="DateTime">${o.expiry_date[:10]|n}T${o.name[-8:]|n}.000</Data></Cell>
        % else:
            <Cell ss:MergeAcross="3" ss:StyleID="poheader"><Data ss:Type="String"></Data></Cell>
        % endif
    </Row>
    <Row ss:AutoFitHeight="1">
        <Cell ss:MergeAcross="1" ss:StyleID="mainheader"><Data ss:Type="String">${_('Only display standard stock location(s)')|x}</Data></Cell>
        <Cell ss:MergeAcross="3" ss:StyleID="poheader"><Data ss:Type="String">${o.only_standard_loc and _('Yes') or _('No')|x}</Data></Cell>
    </Row>
    <Row ss:AutoFitHeight="1">
        <Cell ss:MergeAcross="1" ss:StyleID="mainheader"><Data ss:Type="String">${_('Specific reason types')|x}</Data></Cell>
        <Cell ss:MergeAcross="3" ss:StyleID="poheader"><Data ss:Type="String">${o.reason_type_ids and ' ; '.join([r.complete_name for r in o.reason_type_ids]) or ''|x}</Data></Cell>
    </Row>

    <Row></Row>

    <Row ss:AutoFitHeight="1">
        <Cell ss:StyleID="header"><Data ss:Type="String">${_('Product Code')|x}</Data></Cell>
        <Cell ss:StyleID="header"><Data ss:Type="String">${_('Product Description')|x}</Data></Cell>
        <Cell ss:StyleID="header"><Data ss:Type="String">${_('UoM')|x}</Data></Cell>
        <Cell ss:StyleID="header"><Data ss:Type="String">${_('Stock Move Date')|x}</Data></Cell>
        <Cell ss:StyleID="header"><Data ss:Type="String">${_('Batch')|x}</Data></Cell>
        <Cell ss:StyleID="header"><Data ss:Type="String">${_('Exp Date')|x}</Data></Cell>
        <Cell ss:StyleID="header"><Data ss:Type="String">${_('Quantity')|x}</Data></Cell>
        <Cell ss:StyleID="header"><Data ss:Type="String">${_('Unit Price (%s)') % (o.company_id.currency_id.name,)|x}</Data></Cell>
        <Cell ss:StyleID="header"><Data ss:Type="String">${_('Movement value (%s)') % (o.company_id.currency_id.name,)|x}</Data></Cell>
        % if o.location_ids:
            <Cell ss:StyleID="header"><Data ss:Type="String">${_('BN stock after movement (selected location(s))')|x}</Data></Cell>
            <Cell ss:StyleID="header"><Data ss:Type="String">${_('Total stock after movement (selected location(s))')|x}</Data></Cell>
        % else:
            <Cell ss:StyleID="header"><Data ss:Type="String">${_('BN stock after movement (instance)')|x}</Data></Cell>
            <Cell ss:StyleID="header"><Data ss:Type="String">${_('Total stock after movement (instance)')|x}</Data></Cell>
        % endif
        <Cell ss:StyleID="header"><Data ss:Type="String">${_('Source')|x}</Data></Cell>
        <Cell ss:StyleID="header"><Data ss:Type="String">${_('Destination')|x}</Data></Cell>
        <Cell ss:StyleID="header"><Data ss:Type="String">${_('Reason Type')|x}</Data></Cell>
        <Cell ss:StyleID="header"><Data ss:Type="String">${_('Document Ref.')|x}</Data></Cell>
    </Row>

    % for line in getLines(o.company_id.currency_id.id):
    <Row ss:AutoFitHeight="1">
        <Cell ss:StyleID="line"><Data ss:Type="String">${(line['product_code'])|x}</Data></Cell>
        <Cell ss:StyleID="line"><Data ss:Type="String">${(line['product_name'])|x}</Data></Cell>
        <Cell ss:StyleID="line"><Data ss:Type="String">${(line['uom'])|x}</Data></Cell>
        % if line['date_done'] and isDateTime(line['date_done']):
            <Cell ss:StyleID="hour_date"><Data ss:Type="DateTime">${line['date_done'][:10]|n}T${line['date_done'][-8:]|n}.000</Data></Cell>
        % else:
            <Cell ss:StyleID="line"><Data ss:Type="String"></Data></Cell>
        % endif
        <Cell ss:StyleID="line"><Data ss:Type="String">${(line['batch'])|x}</Data></Cell>
        % if isDate(line['expiry_date']):
            <Cell ss:StyleID="short_date" ><Data ss:Type="DateTime">${(line['expiry_date'])|n}T00:00:00.000</Data></Cell>
        % else:
            <Cell ss:StyleID="line"><Data ss:Type="String"></Data></Cell>
        % endif
        <Cell ss:StyleID="line"><Data ss:Type="Number">${(line['qty'])|x}</Data></Cell>
        <Cell ss:StyleID="line"><Data ss:Type="Number">${(line['unit_price'])|x}</Data></Cell>
        <Cell ss:StyleID="line"><Data ss:Type="Number">${(line['move_value'])|x}</Data></Cell>
        % if line['need_batch']:
        <Cell ss:StyleID="line"><Data ss:Type="Number">${(line['prod_stock_bn'])|x}</Data></Cell>
        % else:
        <Cell ss:StyleID="line"><Data ss:Type="String">${_('NA')|x}</Data></Cell>
        % endif
        <Cell ss:StyleID="line"><Data ss:Type="Number">${(line['prod_stock'])|x}</Data></Cell>
        <Cell ss:StyleID="line"><Data ss:Type="String">${(line['source'])|x}</Data></Cell>
        <Cell ss:StyleID="line"><Data ss:Type="String">${(line['destination'])|x}</Data></Cell>
        <Cell ss:StyleID="line"><Data ss:Type="String">${(line['reason_type'])|x}</Data></Cell>
        <Cell ss:StyleID="line"><Data ss:Type="String">${(line['doc_ref'])|x}</Data></Cell>
    </Row>
    % endfor
 % endfor

</Table>
<WorksheetOptions xmlns="urn:schemas-microsoft-com:office:excel">
   <PageSetup>
    <Layout x:Orientation="Landscape"/>
    <Header x:Data="&amp;C&amp;&quot;Arial,Bold&quot;&amp;14"/>
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
