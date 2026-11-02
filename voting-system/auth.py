"""Local demo verification codes; no SMS service is connected."""
import hmac,re,secrets,time
import app as core
from app import Problem

def now():
    return int(time.time())


def stamp(value):
    return datetime.fromtimestamp(value, timezone.utc).astimezone().strftime('%m/%d %H:%M %Z') if value else 'Not started / 尚未开始'


def issue_code(con, phone, browser, purpose):
    if not re.fullmatch(r'[0-9]{8,15}',phone) or purpose not in ('login','register'):
        raise Problem('Enter an 8–15 digit phone account / 手机号需为8–15位数字。')
    row=con.execute('SELECT * FROM verification_codes WHERE phone=? AND browser=? AND purpose=?',(phone,browser,purpose)).fetchone()
    if row and now()-row['created']<60:
        raise Problem('Please wait 60 seconds before requesting another code / 请等待60秒后再获取。',429)
    code=f'{secrets.randbelow(1000000):06d}'
    digest=hmac.new(core.CSRF_KEY,(phone+browser+purpose+code).encode(),'sha256').hexdigest()
    with con:
        con.execute('INSERT OR REPLACE INTO verification_codes VALUES(?,?,?,?,?,?,0)',(phone,browser,purpose,digest,now()+300,now()))
    return code


def consume_code(con,phone,browser,purpose,code):
    row=con.execute('SELECT * FROM verification_codes WHERE phone=? AND browser=? AND purpose=?',(phone,browser,purpose)).fetchone()
    if not row or row['expires']<=now() or row['attempts']>=5:
        raise Problem('Code expired or too many attempts. Request a new code / 验证码过期或尝试过多，请重新获取。')
    digest=hmac.new(core.CSRF_KEY,(phone+browser+purpose+code).encode(),'sha256').hexdigest()
    if not hmac.compare_digest(row['code_hash'],digest):
        with con:
            con.execute('UPDATE verification_codes SET attempts=attempts+1 WHERE phone=? AND browser=? AND purpose=?',(phone,browser,purpose))
        raise Problem('Incorrect verification code / 验证码不正确。')
    with con:
        con.execute('DELETE FROM verification_codes WHERE phone=? AND browser=? AND purpose=?',(phone,browser,purpose))


