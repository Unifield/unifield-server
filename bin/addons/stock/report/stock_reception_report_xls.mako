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

    <!-- File header -->
    <Style ss:ID="big_header">
        <Font ss:Size="13" ss:Bold="1" />
    </Style>
    <Style ss:ID="file_header">
        <Font ss:Size="13" ss:Bold="1" />
        <Interior ss:Color="#F79646" ss:Pattern="Solid"/>
    </Style>

    <!-- Line header -->
    <Style ss:ID="line_header">
        <Alignment ss:Horizontal="Left" ss:Vertical="Center" ss:WrapText="1" />
        <Borders>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <Interior ss:Color="#F79646" ss:Pattern="Solid"/>
    </Style>
    <Style ss:ID="line_header_center">
        <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1" />
        <Borders>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <Interior ss:Color="#F79646" ss:Pattern="Solid"/>
    </Style>

    <!-- Lines -->
     <Style ss:ID="line">
        <Alignment ss:Horizontal="Left" ss:Vertical="Center" ss:WrapText="1" />
         <Borders>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <NumberFormat ss:Format="#,##0.00"/>
    </Style>
    <Style ss:ID="line_center">
        <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1" />
         <Borders>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <NumberFormat ss:Format="#0"/>
    </Style>
    <Style ss:ID="line_center_nb">
        <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1" />
         <Borders>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <NumberFormat ss:Format="#,##0.00"/>
    </Style>
    <Style ss:ID="short_date">
        <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1" />
        <Borders>
            <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1"/>
            <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1"/>
        </Borders>
        <NumberFormat ss:Format="Short Date" />
    </Style>
 </Styles>

% for r in objects:
<ss:Worksheet ss:Name="${_('Receptions Report')|x}">
    <Table x:FullColumns="1" x:FullRows="1">
        ## Reference
        <Column ss:AutoFitWidth="1" ss:Width="80.0" />
        ## Reason Type
        <Column ss:AutoFitWidth="1" ss:Width="100.0" />
        ## Purchase Order
        <Column ss:AutoFitWidth="1" ss:Width="120.0" />
        ## Supplier
        <Column ss:AutoFitWidth="1" ss:Width="110.0" />
        ## IN Details
        <Column ss:AutoFitWidth="1" ss:Width="240.0" />
        ## Order Type
        <Column ss:AutoFitWidth="1" ss:Width="60.0" />
        ## Order Category
        <Column ss:AutoFitWidth="1" ss:Width="60.0" />
        ## Order Priority
        <Column ss:AutoFitWidth="1" ss:Width="60.0" />
        ## Delivery Requested Date
        <Column ss:AutoFitWidth="1" ss:Width="60.0" />
        ## Delivery Confirmed Date
        <Column ss:AutoFitWidth="1" ss:Width="60.0" />
        ## Origin
        <Column ss:AutoFitWidth="1" ss:Width="240.0" />
        ## Backorder of
        <Column ss:AutoFitWidth="1" ss:Width="80.0" />
        ## Line
        <Column ss:AutoFitWidth="1" ss:Width="30.0" />
        ## Product Code
        <Column ss:AutoFitWidth="1" ss:Width="90.0" />
        ## Product Description
        <Column ss:AutoFitWidth="1" ss:Width="240.0" />
        ## UoM
        <Column ss:AutoFitWidth="1" ss:Width="40.0" />
        ## Qty Ordered
        <Column ss:AutoFitWidth="1" ss:Width="70.0" />
        ## Qty Received
        <Column ss:AutoFitWidth="1" ss:Width="70.0" />
        ## Batch Number
        <Column ss:AutoFitWidth="1" ss:Width="90.0" />
        ## Expiry Date
        <Column ss:AutoFitWidth="1" ss:Width="60.0" />
        ## Unit Price
        <Column ss:AutoFitWidth="1" ss:Width="60.0" />
        ## Currency
        <Column ss:AutoFitWidth="1" ss:Width="45.0" />
        ## Ave. Cost Price (Functional currency)
        <Column ss:AutoFitWidth="1" ss:Width="60.0" />
        ## Total Cost (PO currency)
        <Column ss:AutoFitWidth="1" ss:Width="80.0" />
        ## Total Cost (Functional currency)
        <Column ss:AutoFitWidth="1" ss:Width="80.0" />
        ## Ave. Cost Price Total Cost (Functional currency)
        <Column ss:AutoFitWidth="1" ss:Width="80.0" />
        ## Line Comment
        <Column ss:AutoFitWidth="1" ss:Width="200.0" />
        ## Reception Destination
        <Column ss:AutoFitWidth="1" ss:Width="90.0" />
        ## Final Destination Location
        <Column ss:AutoFitWidth="1" ss:Width="90.0" />
        ## Final Dest. Partner
        <Column ss:AutoFitWidth="1" ss:Width="90.0" />
        ## Expected Receipt Date
        <Column ss:AutoFitWidth="1" ss:Width="60.0" />
        ## Actual Receipt Date
        <Column ss:AutoFitWidth="1" ss:Width="60.0" />
        ## Physical Reception Date
        <Column ss:AutoFitWidth="1" ss:Width="60.0" />
        ## INT Ref.
        <Column ss:AutoFitWidth="1" ss:Width="80.0" />

        ## WORKSHEET HEADER
        <Row>
            <Cell ss:StyleID="file_header" ss:MergeAcross="1"><Data ss:Type="String">${_('RECEPTIONS REPORT')|x}</Data></Cell>
        </Row>
        <Row>
            <Cell ss:StyleID="line"><Data ss:Type="String">${_('DB/Instance name')|x}</Data></Cell>
            <Cell ss:StyleID="line_center"><Data ss:Type="String">${r.company_id and r.company_id.name or ''|x}</Data></Cell>
        </Row>
        <Row>
            <Cell ss:StyleID="line"><Data ss:Type="String">${_('Generated on')|x}</Data></Cell>
            % if isDateTime(r.report_date):
            <Cell ss:StyleID="short_date"><Data ss:Type="DateTime">${parseDateXls(r.report_date)|n}</Data></Cell>
            % else:
            <Cell ss:StyleID="line_center"><Data ss:Type="String"></Data></Cell>
            % endif
        </Row>

        <Row></Row>

        <Row>
            <Cell ss:StyleID="big_header" ss:MergeAcross="1"><Data ss:Type="String">${_('FILTERS')|x}</Data></Cell>
        </Row>
        <Row>
            <Cell ss:StyleID="line"><Data ss:Type="String">${_('Actual Receipt Date from')|x}</Data></Cell>
            % if r.start_date and isDate(r.start_date):
            <Cell ss:StyleID="short_date"><Data ss:Type="DateTime">${parseDateXls(r.start_date)|n}</Data></Cell>
            % else:
            <Cell ss:StyleID="line_center"><Data ss:Type="String"></Data></Cell>
            % endif
        </Row>
        <Row>
            <Cell ss:StyleID="line"><Data ss:Type="String">${_('Actual Receipt Date to')|x}</Data></Cell>
            % if r.end_date and isDate(r.end_date):
            <Cell ss:StyleID="short_date"><Data ss:Type="DateTime">${parseDateXls(r.end_date)|n}</Data></Cell>
            % else:
            <Cell ss:StyleID="line_center"><Data ss:Type="String"></Data></Cell>
            % endif
        </Row>
        <Row>
            <Cell ss:StyleID="line"><Data ss:Type="String">${_('Reason Type')|x}</Data></Cell>
            <Cell ss:StyleID="line_center"><Data ss:Type="String">${r.reason_type_id and r.reason_type_id.name or ''|x}</Data></Cell>
        </Row>
        <Row>
            <Cell ss:StyleID="line"><Data ss:Type="String">${_('Partner')|x}</Data></Cell>
            <Cell ss:StyleID="line_center"><Data ss:Type="String">${r.partner_id and r.partner_id.name or ''|x}</Data></Cell>
        </Row>
        <Row>
            <Cell ss:StyleID="line"><Data ss:Type="String">${_('Order Category')|x}</Data></Cell>
            <Cell ss:StyleID="line_center"><Data ss:Type="String">${getSel(r, 'order_category') or ''|x}</Data></Cell>
        </Row>
        <Row>
            <Cell ss:StyleID="line"><Data ss:Type="String">${_('Order Type')|x}</Data></Cell>
            <Cell ss:StyleID="line_center"><Data ss:Type="String">${getSel(r, 'order_type') or ''|x}</Data></Cell>
        </Row>
        <Row>
            <Cell ss:StyleID="line"><Data ss:Type="String">${_('Product Main Type')|x}</Data></Cell>
            <Cell ss:StyleID="line_center"><Data ss:Type="String">${r.nomen_manda_0 and r.nomen_manda_0.name or ''|x}</Data></Cell>
        </Row>
        <Row>
            <Cell ss:StyleID="line"><Data ss:Type="String">${_('Reception Destination')|x}</Data></Cell>
            <Cell ss:StyleID="line_center"><Data ss:Type="String">${r.location_dest_id and r.location_dest_id.name or ''|x}</Data></Cell>
        </Row>
        <Row>
            <Cell ss:StyleID="line"><Data ss:Type="String">${_('Final Destination Location')|x}</Data></Cell>
            <Cell ss:StyleID="line_center"><Data ss:Type="String">${r.final_dest_id and r.final_dest_id.name or ''|x}</Data></Cell>
        </Row>
        <Row>
            <Cell ss:StyleID="line"><Data ss:Type="String">${_('Final Dest. Partner')|x}</Data></Cell>
            <Cell ss:StyleID="line_center"><Data ss:Type="String">${r.final_partner_id and r.final_partner_id.name or ''|x}</Data></Cell>
        </Row>

        <Row></Row>

        ## DATA HEADERS
        <%
        headers_list = [
            _('Reference'),
            _('Reason Type'),
            _('Purchase Order'),
            _('Supplier'),
            _('IN Details'),
            _('Order Type'),
            _('Order Category'),
            _('Order Priority'),
            _('Delivery Requested Date'),
            _('Delivery Confirmed Date'),
            _('Origin'),
            _('Backorder of'),
            _('Line'),
            _('Product Code'),
            _('Product Description'),
            _('UoM'),
            _('Qty Ordered'),
            _('Qty Received'),
            _('Batch Number'),
            _('Expiry Date'),
            _('Unit Price'),
            _('Currency'),
            _('Ave. Cost Price (Functional currency)'),
            _('Total Cost (PO currency)'),
            _('Total Cost (Functional currency)'),
            _('Ave. Cost Price Total Cost (Functional currency)'),
            _('Line Comment'),
            _('Reception Destination'),
            _('Final Destination Location'),
            _('Final Dest. Partner'),
            _('Expected Receipt Date'),
            _('Actual Receipt Date'),
            _('Physical Reception Date'),
            _('INT Ref.'),
        ]
        %>
        <Row>
        % for h in headers_list:
            <Cell ss:StyleID="line_header_center"><Data ss:Type="String">${h|x}</Data></Cell>
        % endfor
        </Row>

        % for move in getMoves(r['id'], r.company_id.partner_id, r.nb):
            <Row ss:Height="12.0">
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${move['ref']|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${move['reason_type']|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${move['purchase_order']|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${move['supplier']|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${move['details']|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${move['purchase_id'] and getSel(move['purchase_id'], 'order_type') or ''|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${move['purchase_id'] and getSel(move['purchase_id'], 'categ') or ''|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${move['purchase_id'] and getSel(move['purchase_id'], 'priority') or ''|x}</Data></Cell>
                % if move['dr_date'] and isDate(move['dr_date']):
                <Cell ss:StyleID="short_date"><Data ss:Type="DateTime">${parseDateXls(move['dr_date'])|n}</Data></Cell>
                % else:
                <Cell ss:StyleID="line_center"><Data ss:Type="String"></Data></Cell>
                % endif
                % if move['dc_date'] and isDate(move['dc_date']):
                <Cell ss:StyleID="short_date"><Data ss:Type="DateTime">${parseDateXls(move['dc_date'])|n}</Data></Cell>
                % else:
                <Cell ss:StyleID="line_center"><Data ss:Type="String"></Data></Cell>
                % endif
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${move['origin']|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${move['backorder']|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="Number">${move['line']|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${move['product_code']|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${move['product_desc']|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${move['uom']|x}</Data></Cell>
                % if move['purchase_id']:
                <Cell ss:StyleID="line_center"><Data ss:Type="Number">${move['qty_ordered']|x}</Data></Cell>
                % else:
                <Cell ss:StyleID="line_center"><Data ss:Type="String"></Data></Cell>
                % endif
                <Cell ss:StyleID="line_center"><Data ss:Type="Number">${move['qty_received']|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${move['prodlot']|x}</Data></Cell>
                % if move['expiry_date'] and isDate(move['expiry_date']):
                <Cell ss:StyleID="short_date"><Data ss:Type="DateTime">${parseDateXls(move['expiry_date'])|n}</Data></Cell>
                % else:
                <Cell ss:StyleID="line_center"><Data ss:Type="String"></Data></Cell>
                % endif
                <Cell ss:StyleID="line_center_nb"><Data ss:Type="Number">${move['unit_price']|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${move['currency']|x}</Data></Cell>
                <Cell ss:StyleID="line_center_nb"><Data ss:Type="Number">${move['ave_price_func']|x}</Data></Cell>
                % if move['purchase_id']:
                <Cell ss:StyleID="line_center_nb"><Data ss:Type="Number">${move['total_cost']|x}</Data></Cell>
                % else:
                <Cell ss:StyleID="line_center"><Data ss:Type="String"></Data></Cell>
                % endif
                <Cell ss:StyleID="line_center_nb"><Data ss:Type="Number">${move['total_cost_func']|x}</Data></Cell>
                <Cell ss:StyleID="line_center_nb"><Data ss:Type="Number">${move['ave_total_cost_func']|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${move['comment']|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${move['dest_loc']|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${move['final_dest_loc']|x}</Data></Cell>
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${move['final_dest_partner']|x}</Data></Cell>
                % if move['exp_receipt_date'] and isDateTime(move['exp_receipt_date']):
                <Cell ss:StyleID="short_date"><Data ss:Type="DateTime">${parseDateXls(move['exp_receipt_date'])|n}</Data></Cell>
                % else:
                <Cell ss:StyleID="line_center"><Data ss:Type="String"></Data></Cell>
                % endif
                % if move['actual_receipt_date'] and isDateTime(move['actual_receipt_date']):
                <Cell ss:StyleID="short_date"><Data ss:Type="DateTime">${parseDateXls(move['actual_receipt_date'])|n}</Data></Cell>
                % else:
                <Cell ss:StyleID="line_center"><Data ss:Type="String"></Data></Cell>
                % endif
                % if move['phys_recep_date'] and isDateTime(move['phys_recep_date']):
                <Cell ss:StyleID="short_date"><Data ss:Type="DateTime">${parseDateXls(move['phys_recep_date'])|n}</Data></Cell>
                % else:
                <Cell ss:StyleID="line_center"><Data ss:Type="String"></Data></Cell>
                % endif
                <Cell ss:StyleID="line_center"><Data ss:Type="String">${move['int_name']|x}</Data></Cell>
            </Row>
        % endfor

    </Table>
<AutoFilter x:Range="R17C1:R17C33" xmlns="urn:schemas-microsoft-com:office:excel">
</AutoFilter>
</ss:Worksheet>
% endfor
</Workbook>
