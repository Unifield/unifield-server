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
    <Style ss:ID="lineInt">
    <Alignment ss:Horizontal="Right" ss:Vertical="Top" ss:WrapText="1"/>
    <Borders>
      <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" />
      <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" />
      <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" />
      <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" />
    </Borders>
    <NumberFormat ss:Format="##0"/>
    </Style>
    <Style ss:ID="lineFloat">
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

## COLUMNS
<%
col_count = 14
header_merge_accross_count = col_count - 2  ## merging cell self deduced
%>
% for o in objects:
<ss:Worksheet ss:Name="${_('PO Follow Up')}">
<Table x:FullColumns="1" x:FullRows="1">
## order line
<Column ss:AutoFitWidth="1" ss:Width="80" />
## product code
<Column ss:AutoFitWidth="1" ss:Width="80" />
## product description
<Column ss:AutoFitWidth="1" ss:Width="170" />
## comment
<Column ss:AutoFitWidth="1" ss:Width="200" />
## proc. method
<Column ss:AutoFitWidth="1" ss:Width="60"  />
## po/cft
<Column ss:AutoFitWidth="1" ss:Width="70"  />
## ordered qty
<Column ss:AutoFitWidth="1" ss:Width="70"  />
## uom
<Column ss:AutoFitWidth="1" ss:Width="70"  />
## sourced  
<Column ss:AutoFitWidth="1" ss:Width="70"  />
## tender (status)
<Column ss:AutoFitWidth="1" ss:Width="250" />
## purchase order (status)
<Column ss:AutoFitWidth="1" ss:Width="60" />
## incoming shipment (status)
<Column ss:AutoFitWidth="1" ss:Width="70" />
## product available (status)
<Column ss:AutoFitWidth="1" ss:Width="70" />
## outgoing delivery (status)
<Column ss:AutoFitWidth="1" ss:Width="100" />

## WORKSHEET HEADER
<%
if header_merge_accross_count > 0:
    merge_accross = ' ss:MergeAcross="%d"' % (header_merge_accross_count, )
else:
    merge_accross = ''
%>
## order reference
<Row>
    <Cell ss:StyleID="ssCellBold"><Data ss:Type="String">${_('Order reference:')|x}</Data></Cell>
    <Cell ss:StyleID="line"${merge_accross}><Data ss:Type="String">${o.order_id and o.order_id.name or ''|x}</Data></Cell>
</Row>
## supplier referene
<Row>
    <Cell ss:StyleID="ssCellBold"><Data ss:Type="String">${_('Supplier reference:')|x}</Data></Cell>
    <Cell ss:StyleID="line"${merge_accross}><Data ss:Type="String">${o.supplier_ref or ''|x}</Data></Cell>
</Row>
## supplier
<Row>
    <Cell ss:StyleID="ssCellBold"><Data ss:Type="String">${_('Supplier:')|x}</Data></Cell>
    <Cell ss:StyleID="line"${merge_accross}><Data ss:Type="String">${o.partner_id and o.partner_id.name or ''|x}</Data></Cell>
</Row>
## order type
<Row>
    <Cell ss:StyleID="ssCellBold"><Data ss:Type="String">${_('Order type:')|x}</Data></Cell>
    <Cell ss:StyleID="line"${merge_accross}><Data ss:Type="String">${o.order_type and getSel(o, 'order_type') or ''|x}</Data></Cell>
</Row>
## priority
<Row>
    <Cell ss:StyleID="ssCellBold"><Data ss:Type="String">${_('Priority:')|x}</Data></Cell>
    <Cell ss:StyleID="line"${merge_accross}><Data ss:Type="String">${o.priority and getSel(o, 'priority') or ''|x}</Data></Cell>
</Row>
## order category
<Row>
    <Cell ss:StyleID="ssCellBold"><Data ss:Type="String">${_('Order category:')|x}</Data></Cell>
    <Cell ss:StyleID="line"${merge_accross}><Data ss:Type="String">${o.categ and getSel(o, 'categ') or ''|x}</Data></Cell>
</Row>
<Row>
## separator line
% for c in range(0, col_count):
    <Cell ss:StyleID="line"><Data ss:Type="String"></Data></Cell>
% endfor
</Row>

## TABLE DATA HEADER
<%
headers_list = [
    _('#'),
    _('PRODUCT CODE'),
    _('PRODUCT DESCRIPTION'),
    _('COMMENT'),
    _('QTY'),
    _('UOM'),
    _('DEL. CONF. DATE'),
    _('% OF LINE RECEIVED'),
    _('INCOMING SHIPMENT'),
    _('NEW PRODUCT'),
    _('NEW QTY'),
    _('NEW UOM'),
    _('NEW DEL. DATE'),
    _('STATE'),
]
%>
<Row>
% for h in headers_list:
    <Cell ss:StyleID="header"><Data ss:Type="String">${h|x}</Data></Cell>
% endfor
</Row>

## TABLE DATA ROWS
% for line in o.line_ids:
<Row>
## 1) order line
    <Cell ss:StyleID="line"><Data ss:Type="String">${line.line_name|x}</Data></Cell>
## 2) purchase line product code
    <Cell ss:StyleID="line"><Data ss:Type="String">${line.line_product_id and line.line_product_id.default_code or ''|x}</Data></Cell>
## 3) purchase line product description
    <Cell ss:StyleID="line"><Data ss:Type="String">${line.line_product_id and line.line_product_id.name or ''|x}</Data></Cell>
## 4) purchase line comment
    <Cell ss:StyleID="line"><Data ss:Type="String">${line.line_comment or ''|x}</Data></Cell>
## 5) purchase line qty
% if line.line_product_qty:
    <Cell ss:StyleID="lineFloat"><Data ss:Type="Number">${line.line_product_qty}</Data></Cell>
% else:
    <Cell ss:StyleID="line"><Data ss:Type="String"></Data></Cell>
% endif
## 6) purchase line uom
    <Cell ss:StyleID="line"><Data ss:Type="String">${line.line_uom_id and line.line_uom_id.name or ''|x}</Data></Cell>
## 7) purchase line confirmed date
<% dt = parse_date_xls(line.line_confirmed_date) %>
% if dt:
    <Cell ss:StyleID="short_date"><Data ss:Type="DateTime">${dt|n}</Data></Cell>
% else:
    <Cell ss:StyleID="line"><Data ss:Type="String"></Data></Cell>
% endif
## 8) shipped rate0
    <Cell ss:StyleID="line"><Data ss:Type="String">${line.line_product_id and '%s %%' % min(line.line_shipped_rate, 100.00) or ''|x}</Data></Cell>
## 9) incoming shipment
    <Cell ss:StyleID="line"><Data ss:Type="String">${line.picking_id and line.picking_id.name or ''|x}</Data></Cell>
## 10) move product
    <Cell ss:StyleID="line"><Data ss:Type="String">${line.move_product_id and '[%s] %s' % (line.move_product_id.default_code, line.move_product_id.name) or ''|x}</Data></Cell>
## 11) move qty
% if line.move_product_qty:
    <Cell ss:StyleID="lineFloat"><Data ss:Type="Number">${line.move_product_qty}</Data></Cell>
% else:
    <Cell ss:StyleID="line"><Data ss:Type="String"></Data></Cell>
% endif
## 12) move uom
    <Cell ss:StyleID="line"><Data ss:Type="String">${line.move_uom_id and line.move_uom_id.name or ''|x}</Data></Cell>
## 13) move delivery date
<% dt = parse_date_xls(line.move_delivery_date) %>
% if dt:
    <Cell ss:StyleID="short_date"><Data ss:Type="DateTime">${dt|n}</Data></Cell>
% else:
    <Cell ss:StyleID="line"><Data ss:Type="String"></Data></Cell>
% endif
## 14) move state
    <Cell ss:StyleID="line"><Data ss:Type="String">${line.move_state or ''|x}</Data></Cell>
</Row>
% endfor

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
</WorksheetOptions>
</ss:Worksheet>
% endfor
</Workbook>
