'use strict';

const { url, dbname, user, password } = require('./config.js');
const apiUrl = `${url}/jsonrpc`;

async function main() {
    // login
    const loginResponse = await fetch(`${apiUrl}/common`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            method: 'login',
            params: [
                dbname,
                user,
                password
            ]
        })
    });

    const uid = (await loginResponse.json()).result;

    if (!uid) {
        console.log(`Wrong ${user} password on ${apiUrl} db: ${dbname}`);
        process.exit(1);
    }

    const response = await fetch(`${apiUrl}/object`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            method: 'execute',
            params: [
                dbname,
                uid,
                password,
                'waca.fin.sync',
                'import_hq_entries',
                [
                 {
                       description: 'Airport Transfer',
                       reference: 'Ref ZZZ-44-340',
                       document_date: '2026-01-30',
                       posting_date: '2026-01-30',
                       account_code: '64000',
                       amount: 234.56,
                       currency: 'EUR',
                       destination: 'IFRG01',
                       cost_center: 'NEW03',
                       funding_pool: 'PF'
                 }, {
                       description: 'HEPATITIS C TEST (OraQuick HCV)',
                       reference: 'R2D2-6PO',
                       document_date: '2026-01-28',
                       posting_date: '2026-01-28',
                       account_code: '60110',
                       amount: 812.20,
                       currency: 'EUR',
                       destination: 'EQPE01',
                       cost_center: 'MRW01',
                       funding_pool: 'PF'
                 }
                ]
            ]
        })
    });

    const result = (await response.json()).result || {};

    console.log('Result:', JSON.stringify(result, null, 2));
}

main().catch(console.error);
