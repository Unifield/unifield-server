'use strict';

const axios = require('axios');

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
 * Export matching report.
 */
async function exportMatchingReport() {

    let page = 0;
    let nbLines = 0;

    while (true) {

        page++;

        let result;

        try {
            const response = await axios.post(`${url}/object`, {
                method: 'execute',
                params: [
                    dbname,
                    uid,
                    password,
                    'waca.export.accounting.lines',
                    'matching_report',
                    period,
                    coordo_code,
                    page
                ]
            });

            result = response.data.result || {};
        } catch (err) {
            console.error(`Error: ${err.message}`);
            process.exit(1);
        }

        if (!result.success) {
            console.error(`Error: ${result.error}`);
            process.exit(1);
        }

        const records = result.records || [];

        nbLines += records.length;

        for (const line of records) {
            console.log(line);
        }

        if (!result.has_next_page) {
            break;
        }
    }

    console.log(`Nb records ${nbLines}`);
}

/**
 * Main entry point.
 */
async function main() {
    await login();
    await exportMatchingReport();
}

main().catch(err => {
    console.error(err);
    process.exit(1);
});
