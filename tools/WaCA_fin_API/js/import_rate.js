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
                'import_rates',
                [
                    { currency: 'CHF', date: '2026-12-01', rate: 4.46 },
                    { currency: 'AED', date: '2026-12-01', rate: 3.456789 }
                ]
            ]
        })
    });

    const result = (await response.json()).result || {};

    console.log('Result:', result);
}

main().catch(console.error);

// returned value:
// when no error
// {'success': true, 'nb_created': 0, 'nb_updated': 0, 'nb_processed': 2, 'nb_errors': 0}

// in case of errors:
// {
//    'success': false,
//    'nb_errors': 2,
//    'nb_created': 0,
//    'nb_updated': 0,
//    'nb_processed': 3,
//    'error': [
//        {
//            'line': {'currency': 'CHFT', 'date': '2026-12-01', 'rate': 4.44},
//            'error': 'Error: "currency" CHFT does not exist'
//        }, {
//            'line': {'currency': 'ABCD1', 'date': '2026-12-01', 'rate': 1.123456},
//            'error': 'Error: "currency" ABCD1 does not exist'
//        }
//    ]
// }
