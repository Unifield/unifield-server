'use strict';

const axios = require('axios');
const fs = require('fs');

const { url, dbname, user, password, period, coordo_code } = require('./config.js')

let uid = null;

/**
 * Login to the JSON-RPC server.
 */
async function login() {
    try {
        const response = await axios.post(`${url}/common`, {
            method: 'login',
            params: [
                dbname,
                user,
                password
            ]
        });

        uid = response.data.result;

        if (!uid) {
            console.error(`Wrong ${user} password on ${url} db: ${dbname}`);
            process.exit(1);
        }
    } catch (err) {
        console.error(`Login error: ${err.message}`);
        process.exit(1);
    }
}

/**
 * Escape CSV values.
 */
function csvEscape(value) {
    if (value === null || value === undefined) {
        return '';
    }

    const str = String(value);

    if (/[",\r\n]/.test(str)) {
        return `"${str.replace(/"/g, '""')}"`;
    }

    return str;
}

/**
 * Export records into a CSV file.
 */
async function exportToFile(object, method, args, page, fileName) {

    const file = fs.createWriteStream(fileName, {
        encoding: 'utf8'
    });

    let nbLines = 0;
    let headers = [];

    while (true) {

        const params = [
            dbname,
            uid,
            password,
            object,
            method,
            ...args
        ];

        if (page !== null && page !== undefined) {
            params.push(page);
        }

        let result;

        try {
            const response = await axios.post(`${url}/object`, {
                method: 'execute',
                params
            });

            result = response.data.result || {};
        } catch (err) {
            console.error(`${object} ${method} error: ${err.message}`);
            process.exit(1);
        }

        if (!result.success) {
            console.error(`${object} ${method} error: ${result.error}`);
            process.exit(1);
        }

        const records = result.records || [];

        for (const record of records) {

            if (nbLines === 0) {
                headers = Object.keys(record);
                file.write(headers.map(csvEscape).join(',') + '\n');
            }

            nbLines++;

            const row = headers.map(key => csvEscape(record[key]));
            file.write(row.join(',') + '\n');
        }

        if (!result.has_next_page) {
            break;
        }

        page++;
    }

    file.end();

    await new Promise(resolve => file.on('finish', resolve));

    console.log(`${object} ${method} ${nbLines} records to ${fileName}`);
}

/**
 * Main entry point.
 */
async function main() {

    await login();

    await exportToFile(
        'waca.export.accounting.lines',
        'export',
        [period, coordo_code],
        1,
        `${period}_${coordo_code}_accounting_entries.csv`
    );

    await exportToFile(
        'waca.export.accounting.lines',
        'matching_report',
        [period, coordo_code],
        1,
        `${period}_${coordo_code}_matching_report.csv`
    );

    await exportToFile(
        'waca.export.balances',
        'export',
        [period, coordo_code],
        1,
        `${period}_${coordo_code}_balances.csv`
    );
}

main().catch(err => {
    console.error(err);
    process.exit(1);
});
