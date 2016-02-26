#!/bin/sh

echo "generating SSL keys"

openssl genrsa -des3 -out server.pkey 2048

openssl req -new -key server.pkey -out server.csr

openssl genrsa -des3 -out ca.pkey 2048

openssl req -new -x509 -days 365 -key ca.pkey -out ca.crt

openssl x509 -req -in server.csr -out server.crt -CA ca.crt -CAkey ca.pkey -CAcreateserial -CAserial ca.srl

# decrypt private key to avoid typing passphrase at each client connection
openssl rsa -in server.pkey -out server.pkey

#start openerp server with --cert-file=YOUR .crt FILE PATH --pkey-file=YOUR pkey FILE PATH

#./openerp-server --addons-path=../openobject-addons/ --cert-file=bin/ssl/server.crt --pkey-file=bin/ssl/server.pkey

