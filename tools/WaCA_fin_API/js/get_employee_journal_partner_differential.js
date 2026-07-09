#!/usr/bin/env node

const { url, dbname, user, password, api_key } = require('./config.js')

async function post(endpoint, body) {
    const response = await fetch(`${url}/${endpoint}`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify(body)
    });

    return response.json();
}

async function main() {
    try {
        // Login
        const loginResponse = await post("common", {
            method: "login",
            params: [
                dbname,
                user,
                password
            ]
        });

        const uid = loginResponse.result;

        if (!uid) {
            console.error(`Wrong ${user} password on ${url} db: ${dbname}`);
            process.exit(1);
        }

        // Create sync session


        // objectToPull: can be
        // res.partner for UP02-Partners
        // hr.employee for UP03-NationalStaf
        // account.journal for UP04-Journals

        const objectToPull = "account.journal";
        //const objectToPull = "res.partner";
        //const objectToPull = "hr.employee";


        // params:
        //    'waca.fin.sync': object used to manage the session
        //    'generate_session': string, method to call
        //    object_to_pull: string, res.partner, hr.employee or account.journal
        //    'client_string': string, client key, any string, to distinguish tests from production,
        //       the next call with the same client string will send the differences since the last *confirmed* session
        //    full_sync: boolean, True to retrieve all data, False to retrieve only the differences, default value: False

        // returned values:
        //     success: boolean
        //     error: if success is False, error message
        //    session: string, session identifier

        const sessionResponse = await post("object", {
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

        const sessionData = sessionResponse.result;

        if (!sessionData.success) {
            console.error(`New session error: ${sessionData.error}`);
            process.exit(1);
        }

        const session = sessionData.session;

        let page = 1;

        while (true) {

            // Retrieve records page by page, maximum 200 records
            const recordResponse = await post("object", {
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

            const ret = recordResponse.result;

            if (!ret.success) {
                console.error(`Error ${ret.error}`);
                process.exit(1);
            }

            for (const record of ret.records) {
                console.log(record);
            }

            if (!ret.has_next_page) {
                break;
            }

            page++;
        }

        // Confirm session, the next call with the same "client key" will be incremental
        // if the session is not confirmed, UniField considers it as not committed and will send again the data on the next API call

        const confirmResponse = await post("object", {
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

        const confirm = confirmResponse.result;

        if (!confirm.success) {
            console.error(`Error ${confirm.error}`);
            process.exit(1);
        }

        console.log("Session confirmed.");

    } catch (err) {
        console.error("Unexpected error:", err);
        process.exit(1);
    }
}

main();

