#!/bin/bash
# setup certificates required for spinning up 
# backup jobs via NBDS
set -e
SYSTEM_PKIDIR=/etc/pki/qemu/
USER_PKIDIR=$HOME/.pki/libnbd/

mkdir -p ${SYSTEM_PKIDIR} ${USER_PKIDIR}
cat <<EOF >  certificate_authority_template.info
cn = virtnbdbackup
ca
cert_signing_key
EOF
certtool --generate-privkey > ca_key.pem
certtool --generate-self-signed \
            --template certificate_authority_template.info \
            --load-privkey ca_key.pem \
            --outfile ca-cert.pem

cp  ca-cert.pem ${SYSTEM_PKIDIR}/ca-cert.pem

cat <<EOF >  host1_server_template.info
organization = virtnbdbackup
cn = server.example.com
tls_www_server
encryption_key
signing_key
EOF

certtool --generate-privkey > host1_server_key.pem
certtool --generate-certificate \
            --template host1_server_template.info \
            --load-privkey host1_server_key.pem \
            --load-ca-certificate ca-cert.pem \
            --load-ca-privkey ca_key.pem \
            --outfile host1_server_certificate.pem

cp host1_server_key.pem ${SYSTEM_PKIDIR}/server-key.pem
cp host1_server_certificate.pem ${SYSTEM_PKIDIR}/server-cert.pem


cat <<EOF >  host1_client_template.info
country = Country
state = State
locality = City
organization = Name of your organization
cn = client.example.com
tls_www_client
encryption_key
signing_key
EOF
certtool --generate-privkey > host1_client_key.pem
certtool --generate-certificate \
            --template host1_client_template.info \
            --load-privkey host1_client_key.pem \
            --load-ca-certificate ca-cert.pem \
            --load-ca-privkey ca_key.pem \
            --outfile host1_client_certificate.pem

cp host1_client_certificate.pem ${USER_PKIDIR}/client-cert.pem
cp host1_client_key.pem ${USER_PKIDIR}/client-key.pem
cp ca-cert.pem ${USER_PKIDIR}/ca-cert.pem


sed -i 's/#backup_tls_x509_verify.*/backup_tls_x509_verify=0/' /etc/libvirt/qemu.conf
systemctl restart libvirtd
