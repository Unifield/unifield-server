#!/usr/bin/env node

const fs = require("fs");
const axios = require("axios");

const { url, dbname, user, password, api_key } = require('./config.js')
const objectToPull = "res.partner";
// const objectToPull = "account.journal";
// const objectToPull = "hr.employee";

async function main() {
    // login
    const loginResponse = await axios.post(`${url}/common`, {
        method: "login",
        params: [
            dbname,
            user,
            password
        ]
    });

    const uid = loginResponse.data.result;

    if (!uid) {
        console.log(`Wrong ${user} password on ${url} db: ${dbname}`);
        process.exit(1);
    }

    // create a sync session
    // arguments:
    //    'waca.fin.sync': object used to manage the session
    //    'generate_session': method to call
    //    objectToPull: object to retrieve
    //    apiKey: client key
    //    false: incremental sync (true = full sync)
    //
    // returned values:
    //     success: boolean
    //     error: error message if success is false
    //     session: session identifier

    const sessionResponse = await axios.post(`${url}/object`, {
        method: "execute",
        params: [
            dbname,
            uid,
            password,
            "waca.fin.sync",
            "generate_session",
            objectToPull,
            api_key,
            false
        ]
    });

    const sessionData = sessionResponse.data.result;

    if (!sessionData.success) {
        console.log(`New session error: ${sessionData.error}`);
        process.exit(1);
    }

    const session = sessionData.session;

    let csvStream = null;
    let keys = null;
    let line = 0;

    if (process.argv.length > 2) {
        console.log(`Export to file: ${process.argv[2]}`);
        csvStream = fs.createWriteStream(process.argv[2], {
            encoding: "utf8"
        });
    }

    let page = 1;

    while (true) {
        // get the records page by page, limited to 200 records
        const response = await axios.post(`${url}/object`, {
            method: "execute",
            params: [
                dbname,
                uid,
                password,
                "waca.fin.sync",
                "get_record",
                session,
                page
            ]
        });

        const ret = response.data.result;

        if (!ret.success) {
            console.log(`Error ${ret.error}`);
            process.exit(1);
        }

        for (const record of ret.records) {
            if (csvStream) {
                if (!line) {
                    keys = Object.keys(record);
                    csvStream.write(keys.join(",") + "\n");
                }

                const values = keys.map(key => {
                    const value = record[key];

                    if (value === null || value === undefined) {
                        return "";
                    }

                    const str = String(value);

                    // Escape CSV values
                    if (str.includes(",") || str.includes('"') || str.includes("\n")) {
                        return `"${str.replace(/"/g, '""')}"`;
                    }

                    return str;
                });

                csvStream.write(values.join(",") + "\n");
            } else {
                console.log(record);
            }

            line++;
        }

        if (!ret.has_next_page) {
            // has_next_page is a boolean
            // if no new page stop the loop
            break;
        }

        page++;
    }

    if (csvStream) {
        csvStream.end();
    }

    // confirm the session, next call with the same client key will be incremental
    // if the session is not confirmed, UniField considers it as not committed
    // and will send the data again on the next API call
    const confirmResponse = await axios.post(`${url}/object`, {
        method: "execute",
        params: [
            dbname,
            uid,
            password,
            "waca.fin.sync",
            "confirm_session",
            session
        ]
    });

    const confirmResult = confirmResponse.data.result;

    if (!confirmResult.success) {
        console.log(`Error ${confirmResult.error}`);
        process.exit(1);
    }
}

main().catch(err => {
    console.error(err.response?.data || err.message);
    process.exit(1);
});
