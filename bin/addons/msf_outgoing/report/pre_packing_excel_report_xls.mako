<?xml version="1.0"?>
<?mso-application progid="Excel.Sheet"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:o="urn:schemas-microsoft-com:office:office"
 xmlns:x="urn:schemas-microsoft-com:office:excel"
 xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:html="http://www.w3.org/TR/REC-html40">
 <DocumentProperties xmlns="urn:schemas-microsoft-com:office:office">
  <Author>Unifield</Author>
  <LastAuthor>MSFUser</LastAuthor>
  <Created>2014-04-16T22:36:07Z</Created>
  <Company>Medecins Sans Frontieres</Company>
  <Version>11.9999</Version>
 </DocumentProperties>
 <ExcelWorkbook xmlns="urn:schemas-microsoft-com:office:excel">
  <WindowHeight>11640</WindowHeight>
  <WindowWidth>15480</WindowWidth>
  <WindowTopX>120</WindowTopX>
  <WindowTopY>75</WindowTopY>
  <ProtectStructure>False</ProtectStructure>
  <ProtectWindows>False</ProtectWindows>
 </ExcelWorkbook>
 <Styles>
    <Style ss:ID="ssCell">
        <Alignment ss:Vertical="Top" ss:WrapText="1"/>
        <Font ss:Bold="1" />
    </Style>
    <Style ss:ID="ssCellBlue">
        <Alignment ss:Vertical="Top" ss:WrapText="1"/>
        <Font ss:Color="#0000FF" />
    </Style>

    <!-- File header -->
    <Style ss:ID="big_header">
        <Font x:Family="Swiss" ss:Size="14" ss:Bold="1"/>
    </Style>
    <Style ss:ID="file_header">
        <Font ss:Size="9" />
        <Interior ss:Color="#F79646" ss:Pattern="Solid"/>
    </Style>

    <!-- Line header -->
    <Style ss:ID="line_header">
        <Borders>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <Font x:Family="Swiss" ss:Size="7" ss:Bold="1"/>
        <Interior ss:Color="#F79646" ss:Pattern="Solid"/>
        <Interior/>
    </Style>

    <!-- Lines -->
    <Style ss:ID="line_left">
        <Alignment ss:Horizontal="Left" ss:Vertical="Bottom"/>
        <Borders>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <Font ss:Size="8" ss:Color="#0000FF"/>
    </Style>
    <Style ss:ID="line_left_green">
        <Alignment ss:Horizontal="Left" ss:Vertical="Bottom"/>
        <Borders>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <Font ss:Size="8" ss:Color="#1A721A"/>
    </Style>
    <Style ss:ID="line_right">
        <Alignment ss:Horizontal="Right" ss:Vertical="Bottom"/>
        <Borders>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <Font ss:Size="8" ss:Color="#0000FF"/>
        <NumberFormat ss:Format="#,##0.00"/>
    </Style>
     <Style ss:ID="line_center">
        <Alignment ss:Horizontal="Center" ss:Vertical="Bottom"/>
         <Borders>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <Font ss:Size="8" ss:Color="#0000FF"/>
        <NumberFormat ss:Format="#,##0.00"/>
    </Style>
    <Style ss:ID="line_left_date">
        <Alignment ss:Horizontal="Right" ss:Vertical="Bottom"/>
        <NumberFormat ss:Format="Short Date" />
        <Borders>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <Font ss:Size="8" ss:Color="#0000FF"/>
    </Style>

    <Style ss:ID="short_date">
        <Alignment ss:Horizontal="Left" ss:Vertical="Center" ss:WrapText="1" />
        <NumberFormat ss:Format="Short Date" />
        <Font ss:Color="#0000FF" />
    </Style>
    <Style ss:ID="short_date_center">
        <Alignment ss:Horizontal="Center" ss:Vertical="Bottom" ss:WrapText="1" />
        <NumberFormat ss:Format="Short Date" />
        <Font ss:Color="#0000FF" />
    </Style>
</Styles>


% for pt in objects:
<ss:Worksheet ss:Name="Pre-Packing Excel Report">
    <Table x:FullColumns="1" x:FullRows="1">
        ## Item
        <Column ss:AutoFitWidth="1" ss:Width="19.0" />
        ## Code
        <Column ss:AutoFitWidth="1" ss:Width="107.25" />
        ## Description
        <Column ss:AutoFitWidth="1" ss:Width="239.25" />
        ## Comment
        <Column ss:AutoFitWidth="1" ss:Width="150.75" />
        ## Total Qty to pack
        <Column ss:AutoFitWidth="1" ss:Width="54.75" />
        ## Batch #
        <Column ss:AutoFitWidth="1" ss:Width="107.25" />
        ## Expiry Date #
        <Column ss:AutoFitWidth="1" ss:Width="55.75" />
        ## KC
        <Column ss:AutoFitWidth="1" ss:Width="19.0" />
        ## DG
        <Column ss:AutoFitWidth="1" ss:Width="19.0" />
        ## CS
        <Column ss:AutoFitWidth="1" ss:Width="19.0" />
        ## Qty Packed
        <Column ss:AutoFitWidth="1" ss:Width="54.75"  />
        ## From pack
        <Column ss:AutoFitWidth="1" ss:Width="54.75"  />
        ## Weight per pack (kg)
        <Column ss:AutoFitWidth="1" ss:Width="54.75"  />
        ## Size (w x l x h) (cm)
        <Column ss:AutoFitWidth="1" ss:Width="54.75"  />
        ## Pack Type
        <Column ss:AutoFitWidth="1" ss:Width="68.25"  />

        ## WORKSHEET HEADER
        <Row>
            <Cell ss:StyleID="file_header" ss:MergeAcross="1"><Data ss:Type="String">${_('Reference*')|x}</Data></Cell>
            <Cell ss:StyleID="line_center"><Data ss:Type="String"></Data>${pt.name|x}</Cell>
            <Cell ss:StyleID="file_header" ss:MergeAcross="2"><Data ss:Type="String">${_('Shipper')|x}</Data></Cell>
            <Cell ss:StyleID="file_header" ss:MergeAcross="4"><Data ss:Type="String">${_('Consignee')|x}</Data></Cell>
        </Row>
        <Row>
            <Cell ss:StyleID="file_header" ss:MergeAcross="1"><Data ss:Type="String">${_('Date')|x}</Data></Cell>
            <Cell ss:StyleID="short_date_center"><Data ss:Type="String"></Data>${formatLang(time.strftime('%Y-%m-%d'), date=True)|x}</Cell>
            <Cell ss:StyleID="ssCell" ss:MergeAcross="2"><Data ss:Type="String">${getShipper.get('shipper_name', '')|x}</Data></Cell>
            <Cell ss:StyleID="ssCell" ss:MergeAcross="4"><Data ss:Type="String">${getConsignee(pt).get('consignee_name', '')|x}</Data></Cell>
        </Row>
        <Row>
            <Cell ss:StyleID="file_header" ss:MergeAcross="1"><Data ss:Type="String">${_('Requester Ref')|x}</Data></Cell>
            <Cell ss:StyleID="line_center"><Data ss:Type="String"></Data>${pt.sale_id and pt.sale_id.client_order_ref or ''|x}</Cell>
            <Cell ss:StyleID="ssCell" ss:MergeAcross="2"><Data ss:Type="String">${getShipper.get('shipper_contact', '')|x}</Data></Cell>
            <Cell ss:StyleID="ssCell" ss:MergeAcross="4"><Data ss:Type="String">${getConsignee(pt).get('consignee_contact', '')|x}</Data></Cell>
        </Row>
        <Row>
            <Cell ss:StyleID="file_header" ss:MergeAcross="1"><Data ss:Type="String">${_('Our Ref*')|x}</Data></Cell>
            <Cell ss:StyleID="line_center"><Data ss:Type="String"></Data>${pt.sale_id and pt.sale_id.name or ''|x}</Cell>
            <Cell ss:StyleID="ssCell" ss:MergeAcross="2"><Data ss:Type="String">${getShipper.get('shipper_address', '')|x}</Data></Cell>
            <Cell ss:StyleID="ssCell" ss:MergeAcross="4"><Data ss:Type="String">${getConsignee(pt).get('consignee_address', '')|x}</Data></Cell>
        </Row>
        <Row>
            <Cell ss:StyleID="file_header" ss:MergeAcross="1"><Data ss:Type="String">${_('FO Date')|x}</Data></Cell>
            <Cell ss:StyleID="short_date_center"><Data ss:Type="String"></Data>${pt.sale_id and formatLang(pt.sale_id.date_order, date=True) or ''|x}</Cell>
            <Cell ss:StyleID="ssCell" ss:MergeAcross="2"><Data ss:Type="String">${getShipper.get('shipper_phone', '')|x}</Data></Cell>
            <Cell ss:StyleID="ssCell" ss:MergeAcross="4"><Data ss:Type="String">${getConsignee(pt).get('consignee_phone', '')|x}</Data></Cell>
        </Row>
        <Row>
            <Cell ss:StyleID="file_header" ss:MergeAcross="1"><Data ss:Type="String">${_('Packing Date')|x}</Data></Cell>
            <Cell ss:StyleID="short_date_center"><Data ss:Type="String"></Data>${pt.sale_id and formatLang(pt.sale_id.delivery_requested_date, date=True) or ''|x}</Cell>
            <Cell ss:StyleID="ssCell" ss:MergeAcross="2"><Data ss:Type="String"></Data></Cell>
            <Cell ss:StyleID="ssCell" ss:MergeAcross="4"><Data ss:Type="String"></Data></Cell>
        </Row>
        <Row>
            <Cell ss:StyleID="file_header" ss:MergeAcross="1"><Data ss:Type="String">${_('RTS Date')|x}</Data></Cell>
            <Cell ss:StyleID="short_date_center"><Data ss:Type="String"></Data>${pt.sale_id and formatLang(pt.sale_id.ready_to_ship_date, date=True)|x}</Cell>
            <Cell ss:StyleID="ssCell" ss:MergeAcross="2"><Data ss:Type="String"></Data></Cell>
            <Cell ss:StyleID="ssCell" ss:MergeAcross="4"><Data ss:Type="String"></Data></Cell>
        </Row>
        <Row>
            <Cell ss:StyleID="file_header" ss:MergeAcross="1"><Data ss:Type="String">${_('Transport mode')|x}</Data></Cell>
            <Cell ss:StyleID="line_center"><Data ss:Type="String"></Data>${pt.sale_id and pt.sale_id.transport_type and getSel(pt.sale_id, 'transport_type') or ''|x}</Cell>
            <Cell ss:StyleID="ssCell" ss:MergeAcross="2"><Data ss:Type="String"></Data></Cell>
            <Cell ss:StyleID="ssCell" ss:MergeAcross="4"><Data ss:Type="String"></Data></Cell>
        </Row>

        <Row></Row>

        <%
            headers_list = [
                _('Item*'),
                _('Code*'),
                _('Description'),
                _('Comment'),
                _('Total Qty to pack*'),
                _('Batch #'),
                _('Expiry Date#'),
                _('KC'),
                _('DG'),
                _('CS'),
                _('Qty Packed'),
                _('From pack*'),
                _('To pack*'),
                _('Weight per pack (kg)*'),
                _('Size (w x l x h) (cm)'),
                _('Pack Type'),
            ]
        %>

        <Row>
        % for h in headers_list:
            <Cell ss:StyleID="line_header"><Data ss:Type="String">${h|x}</Data></Cell>
        % endfor
        </Row>

        % for o in getOrders(r):
            % for line in getLines(o, grouped=True):
            <Row ss:Height="11.25">
                <Cell ss:StyleID="line_left"><Data ss:Type="String">${o.name|x}</Data></Cell>
                <Cell ss:StyleID="line_left"><Data ss:Type="String">${o.client_order_ref or ''|x}</Data></Cell>
                <Cell ss:StyleID="line_left"><Data ss:Type="String">${line.get('po_name', '')|x}</Data></Cell>
                <Cell ss:StyleID="line_left"><Data ss:Type="String">${getSel(o, 'state')|x}</Data></Cell>
                <Cell ss:StyleID="line_left"><Data ss:Type="String">${saleUstr(formatLang(o.date_order, date=True))|x}</Data></Cell>
                <Cell ss:StyleID="line_left"><Data ss:Type="String">${o.delivery_requested_date and saleUstr(formatLang(o.delivery_requested_date, date=True)) or ''|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${line.get('line_number', '-')|x}</Data></Cell>
                <Cell ss:StyleID="line_left"><Data ss:Type="String">${line.get('product_code', '-') or ''|x}</Data></Cell>
                <Cell ss:StyleID="line_left"><Data ss:Type="String">${line.get('product_name', '-') or ''|x}</Data></Cell>
                % if line.get('ordered_qty'):
                <Cell ss:StyleID="line_right"><Data ss:Type="Number">${line.get('ordered_qty')}</Data></Cell>
                % else:
                <Cell ss:StyleID="line_left"><Data ss:Type="String">N/A</Data></Cell>
                % endif
                <Cell ss:StyleID="line_left"><Data ss:Type="String">${line.get('uom_id', '-')|x}</Data></Cell>
                % if line.get('delivered_qty'):
                <Cell ss:StyleID="line_right"><Data ss:Type="Number">${line.get('delivered_qty')}</Data></Cell>
                % else:
                <Cell ss:StyleID="line_left"><Data ss:Type="String">N/A</Data></Cell>
                % endif
                <Cell ss:StyleID="line_left"><Data ss:Type="String">${line.get('delivered_uom', '')|x}</Data></Cell>
                <Cell ss:StyleID="line_left"><Data ss:Type="String">${line.get('packing', '')|x}</Data></Cell>
                % if line.get('extra_qty', False):
                <Cell ss:StyleID="line_left"><Data ss:Type="String">${line.get('backordered_qty', 0.00)} (+${line.get('extra_qty', 0.00)|x})</Data></Cell>
                % else:
                <Cell ss:StyleID="line_right"><Data ss:Type="Number">${line.get('backordered_qty')}</Data></Cell>
                % endif
                % if o.transport_type and o.transport_type not in (False, 'False', ''):
                <Cell ss:StyleID="line_left"><Data ss:Type="String">${getSel(o, 'transport_type')|x}</Data></Cell>
                % else:
                <Cell ss:StyleID="line_left"><Data ss:Type="String"></Data></Cell>
                % endif
                % if line.get('is_delivered'):
                <Cell ss:StyleID="line_left_green"><Data ss:Type="String">${line.get('shipment', '')|x}</Data></Cell>
                % else:
                <Cell ss:StyleID="line_left"><Data ss:Type="String">${line.get('shipment', '')|x}</Data></Cell>
                % endif
                <Cell ss:StyleID="line_left"><Data ss:Type="String">${line.get('cdd', False) not in (False, 'False') and saleUstr(formatLang(line.get('cdd'), date=True)) or ''|x}</Data></Cell>
                <Cell ss:StyleID="line_left"><Data ss:Type="String">${line.get('eta', False) not in (False, 'False') and saleUstr(formatLang(line.get('eta'), date=True)) or ''|x}</Data></Cell>
                <Cell ss:StyleID="line_left"><Data ss:Type="String">${line.get('rts', False) not in (False, 'False') and saleUstr(formatLang(line.get('rts'), date=True)) or ''|x}</Data></Cell>
            </Row>
            % endfor

        % endfor

    </Table>

    <WorksheetOptions xmlns="urn:schemas-microsoft-com:office:excel">
        <PageSetup>
            <Layout x:Orientation="Landscape"/>
            <Footer x:Data="Page &amp;P of &amp;N"/>
        </PageSetup>
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
