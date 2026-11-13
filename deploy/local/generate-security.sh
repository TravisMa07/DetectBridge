#!/usr/bin/env bash
# Runs as the host UID in the locked OpenSearch image. Never trace secret values.
set -euo pipefail
cd /output/security
export KS_PASS
KS_PASS=$(cat keystore-password)
KEYTOOL=/usr/share/opensearch/jdk/bin/keytool
"$KEYTOOL" -genkeypair -alias ca -dname CN=DetectBridge-Local-CA -keyalg RSA -keysize 3072 -validity 3650 -ext bc:c -ext KeyUsage=keyCertSign,cRLSign -storetype PKCS12 -keystore ca.p12 -storepass:env KS_PASS >/dev/null 2>&1
"$KEYTOOL" -exportcert -rfc -alias ca -keystore ca.p12 -storepass:env KS_PASS -file ca.pem >/dev/null 2>&1
"$KEYTOOL" -importcert -noprompt -alias ca -file ca.pem -keystore truststore.p12 -storetype PKCS12 -storepass:env KS_PASS >/dev/null 2>&1
for name in node admin; do
  "$KEYTOOL" -genkeypair -alias "$name" -dname "CN=detectbridge-$name" -keyalg RSA -keysize 3072 -validity 825 -keystore "$name.p12" -storetype PKCS12 -storepass:env KS_PASS >/dev/null 2>&1
  "$KEYTOOL" -certreq -alias "$name" -keystore "$name.p12" -storepass:env KS_PASS -file "$name.csr" >/dev/null 2>&1
  if [ "$name" = node ]; then
    "$KEYTOOL" -gencert -rfc -alias ca -keystore ca.p12 -storepass:env KS_PASS -infile "$name.csr" -outfile "$name.pem" -validity 825 -ext SAN=dns:opensearch,dns:localhost,ip:127.0.0.1 -ext EKU=serverAuth,clientAuth >/dev/null 2>&1
  else
    "$KEYTOOL" -gencert -rfc -alias ca -keystore ca.p12 -storepass:env KS_PASS -infile "$name.csr" -outfile "$name.pem" -validity 825 -ext EKU=clientAuth >/dev/null 2>&1
  fi
  "$KEYTOOL" -importcert -noprompt -alias ca -file ca.pem -keystore "$name.p12" -storepass:env KS_PASS >/dev/null 2>&1
  "$KEYTOOL" -importcert -noprompt -alias "$name" -file "$name.pem" -keystore "$name.p12" -storepass:env KS_PASS >/dev/null 2>&1
  rm "$name.csr"
done
for role in operator health; do
  export HASH_PASSWORD
  HASH_PASSWORD=$(cat "$role-password")
  /usr/share/opensearch/plugins/opensearch-security/tools/hash.sh -env HASH_PASSWORD > "$role-hash"
done
# Preserve the upstream licensed role/action definitions, replacing all users and authentication.
cp /usr/share/opensearch/config/opensearch-security/*.yml .
chmod 600 ./*
