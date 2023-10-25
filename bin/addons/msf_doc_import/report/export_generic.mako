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
        <Style ss:ID="header">
            <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
            <Interior ss:Color="#ffcc99" ss:Pattern="Solid"/>
            <Font ss:Bold="1" ss:Color="#000000" />
            <Protection />
        </Style>
        <Style ss:ID="String">
            <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
            <NumberFormat ss:Format="@"/>
            <Protection ss:Protected="0" />
        </Style>
        <Style ss:ID="StringProtected">
            <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
            <Interior ss:Color="#A9A9A9" ss:Pattern="Solid"/>
            <NumberFormat ss:Format="@"/>
            <Protection />
        </Style>
        <Style ss:ID="Boolean">
            <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
            <Protection ss:Protected="0" />
        </Style>
        <Style ss:ID="Float">
            <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
            <NumberFormat ss:Format="Fixed" />
            <Protection ss:Protected="0" />
        </Style>
        <Style ss:ID="Number">
            <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
            <NumberFormat ss:Format="Fixed" />
            <Protection ss:Protected="0" />
        </Style>
        <Style ss:ID="DateTime">
            <Alignment ss:Horizontal="Center" ss:Vertical="Center" ss:WrapText="1"/>
            <NumberFormat ss:Format="Short Date" />
            <Protection ss:Protected="0" />
        </Style>
    </Styles>

    <ss:Worksheet ss:Name="${data.get('model_name', _('Sheet 1'))|x}" ss:Protected="1">

        <Table x:FullColumns="1" x:FullRows="1">
            <% rows = getRows(data) %>
            <% headers = getHeaders(data['model'], data['fields'], rows, data['selection'], data['context']) %>
            % for col in headers:
            <Column ss:AutoFitWidth="1" ss:Width="${col[2] or 70|x}" ss:StyleID="${col[1]|x}" />
            % endfor

            <% header_info_data = getHeaderInfo(data['model'], data['selection'], data['prod_list_id'], data['supp_cata_id'], data['context']) %>
            % for header_info in header_info_data:
                <Row>
                    <Cell ss:StyleID="header">
                        <Data ss:Type="String">${header_info[0]}</Data>
                    </Cell>
                    <Cell ss:StyleID="header">
                        <Data ss:Type="String">${header_info[1]}</Data>
                    </Cell>
                </Row>
            % endfor


            <Row>
            % for col in headers:
                <Cell ss:StyleID="header">
                    <Data ss:Type="String">${col[0]|x}</Data>
                </Cell>
            % endfor
            </Row>

            % if not data.get('template_only', False):
                % for row in rows:
                <Row>
                    % for index, cell in enumerate(row):
                    % if data['selection'] == 'cost_centers_update' and index not in (1, 4, 5):
                    <Cell ss:StyleID="StringProtected">
                    % if headers[index][1] == 'String' and not cell:
                            <Data ss:Type="String"></Data>
                        % else:
                            <Data ss:Type="String">${cell|x}</Data>
                        % endif
                    </Cell>
                    % else:
                    <Cell ss:StyleID="${headers[index][1]|x}">
                        % if headers[index][1] == 'String' and not cell:
                            <Data ss:Type="String"></Data>
                        % else:
                            <Data ss:Type="String">${cell|x}</Data>
                        % endif
                    </Cell>
                    % endif
                    % endfor
                </Row>
                % endfor
            % else:
                <!-- template export: generate 10 empty lines with the correct cell type -->
                % for x in range(0, 10):
                    <Row>
                        % for h in headers:
                           <Cell ss:StyleID="${h[1]|x}">
                                <Data ss:Type="String"></Data>
                            </Cell>
                        % endfor
                    </Row>
                % endfor
            % endif
        </Table>

        <x:WorksheetOptions xmlns="urn:schemas-microsoft-com:office:excel">
            <ProtectScenarios>False</ProtectScenarios>
            <EnableSelection>UnlockedCells</EnableSelection>
            <AllowInsertRows />
        </x:WorksheetOptions>

    </ss:Worksheet>

</Workbook>
