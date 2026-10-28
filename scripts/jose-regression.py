"""JWT compatibility and validation checks for the selected authentication dependency."""
from datetime import timedelta
from fastapi import HTTPException
from jose import jwt, jwe
from app.auth import create_access_token, decode_access_token, SECRET_KEY, ALGORITHM

subject='6dd60d43-c851-45c4-b21d-174ea63f3692'
token=create_access_token({'sub':subject})
assert decode_access_token(token).user_id==subject
for bad in [token.rsplit('.',1)[0]+'.invalid', create_access_token({'sub':subject},timedelta(seconds=-60)), jwt.encode({'sub':subject},'different-test-secret',algorithm=ALGORITHM), jwt.encode({'no_subject':True},SECRET_KEY,algorithm=ALGORITHM)]:
    try:decode_access_token(bad)
    except HTTPException as exc:assert exc.status_code==401
    else:raise AssertionError('Invalid JWT accepted')
# Exercise supported bounded JWE compression; the deployed app uses JWT/HS256.
key=b'0123456789abcdef0123456789abcdef'
encrypted=jwe.encrypt(b'bounded regression payload',key,algorithm='dir',encryption='A256GCM',zip='DEF')
assert jwe.decrypt(encrypted,key)==b'bounded regression payload'
print('JWT roundtrip, tampered/expired/wrong-key/missing-sub rejection, bounded JWE: passed')
