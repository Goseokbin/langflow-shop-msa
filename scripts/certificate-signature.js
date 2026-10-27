// Read the outer X.509 signature algorithm OID for inventory only; this is not trust validation.
function certificateSignature(bytes) {
    function tlv(offset) {
        if (offset + 2 > bytes.length) throw new Error('Truncated DER header');
        const tag = bytes[offset++]; let length = bytes[offset++];
        if (length & 128) {
            const count = length & 127;
            if (!count || count > 4 || offset + count > bytes.length) throw new Error('Invalid DER length');
            length = 0;
            for (let i = 0; i < count; i++) length = length * 256 + bytes[offset++];
        }
        if (offset + length > bytes.length) throw new Error('Truncated DER value');
        return { tag, start: offset, end: offset + length };
    }
    const root = tlv(0), tbs = tlv(root.start), algorithm = tlv(tbs.end), oid = tlv(algorithm.start);
    if (root.tag !== 48 || tbs.tag !== 48 || algorithm.tag !== 48 || oid.tag !== 6 || oid.end > algorithm.end) throw new Error('Invalid X.509 algorithm structure');
    const key = bytes.slice(oid.start, oid.end).map(n => n.toString(16).padStart(2, '0')).join('');
    return ({'2a864886f70d01010b':'SHA256-RSA','2a864886f70d01010c':'SHA384-RSA','2a864886f70d01010d':'SHA512-RSA',
        '2a864886f70d010105':'SHA1-RSA','2a8648ce3d040302':'SHA256-ECDSA','2a8648ce3d040303':'SHA384-ECDSA','2a8648ce3d040304':'SHA512-ECDSA'})[key] || 'Unknown-OID-' + key;
}
