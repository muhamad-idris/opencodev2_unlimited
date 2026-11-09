"""TLS fingerprint that reproduces Bun 1.4.4's ClientHello.

Captured from /tmp/opencode/hello.pcap (opencode.ai):

  ciphers    : 17 suites, order below
  extensions : 0-23-65281-10-11-35-16-5-13-18-51-45-43 (fresh connection)
  groups     : X25519MLKEM768, x25519, P-256, P-384
  ALPN       : http/1.1 only
  JA3        : 1523504b38f0fae0d881d4b6554aac1b (fresh)
               ae5f2d34331c18f27df379f7d4b72e35 (with pre_shared_key)

curl_cffi is backed by BoringSSL, the same TLS library Bun uses. The custom
`ja3` string sets cipher order, extension order and curves; the two CurlOpt
values below add extensions 5 (status_request) and 18 (SCT), which BoringSSL
does not send by default.
"""

from curl_cffi.const import CurlOpt

JA3 = (
    "771,"
    "4865-4866-4867-49195-49199-49196-49200-52393-52392-"
    "49161-49171-49162-49172-156-157-47-53,"
    "0-23-65281-10-11-35-16-5-13-18-51-45-43,"
    "4588-29-23-24,"
    "0"
)

# Order matters: BoringSSL keeps the list as given.
SIGNATURE_ALGORITHMS = [
    "ecdsa_secp256r1_sha256",
    "rsa_pss_rsae_sha256",
    "rsa_pkcs1_sha256",
    "ecdsa_secp384r1_sha384",
    "rsa_pss_rsae_sha384",
    "rsa_pkcs1_sha384",
    "rsa_pss_rsae_sha512",
    "rsa_pkcs1_sha512",
    "ed25519",
    "ecdsa_secp521r1_sha512",
    "rsa_pkcs1_sha1",
]

EXTRA_FP = {
    "tls_grease": False,
    "tls_signature_algorithms": SIGNATURE_ALGORITHMS,
}

CURL_OPTIONS = {
    CurlOpt.TLS_STATUS_REQUEST: 1,
    CurlOpt.TLS_SIGNED_CERT_TIMESTAMPS: 1,
}
