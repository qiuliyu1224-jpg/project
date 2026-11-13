"""Validated image storage, structured entry editing and application review."""
import io
import secrets
import time
import warnings
from datetime import datetime, timezone, timedelta
from email.parser import BytesParser
from email.policy import default
from urllib.parse import parse_qs
from PIL import Image, UnidentifiedImageError
from app import Problem, scalar

MAX_IMAGE=5*1024*1024
MAX_REQUEST=24*1024*1024
MAX_DAYS=30  # Implementation assumption, not a confirmed course requirement.
TZ=timezone(timedelta(hours=8))


def read_form(env):
    try: size=int(env.get('CONTENT_LENGTH') or 0)
    except ValueError: raise Problem('Invalid request length.')
    if not 0<=size<=MAX_REQUEST: raise Problem('Request too large; maximum 24 MB / 总上传不能超过24MB。',413)
    raw=env['wsgi.input'].read(size)
    content_type=env.get('CONTENT_TYPE','application/x-www-form-urlencoded')
    if not content_type.startswith('multipart/form-data'):
        try: return parse_qs(raw.decode('utf-8'),keep_blank_values=True),{}
        except UnicodeError: raise Problem('Invalid text encoding.')
    if '\r' in content_type or '\n' in content_type: raise Problem('Invalid upload format.')
    message=BytesParser(policy=default).parsebytes(('Content-Type: '+content_type+'\r\nMIME-Version: 1.0\r\n\r\n').encode()+raw)
    if not message.is_multipart(): raise Problem('Invalid multipart form.')
    fields,files={},{}
    for part in message.iter_parts():
        name=part.get_param('name',header='content-disposition')
        if not name or len(name)>100: raise Problem('Invalid form field.')
        data=part.get_payload(decode=True) or b''
        if part.get_filename() is not None:
            if name in files: raise Problem('Repeated upload field.')
            if data: files[name]=data
        else:
            try: text=data.decode('utf-8')
            except UnicodeError: raise Problem('Invalid text encoding.')
            fields.setdefault(name,[]).append(text)
    return fields,files


def save_image(con,data):
    if not data: return None
    if len(data)>MAX_IMAGE: raise Problem('Image exceeds 5 MB / 单张图片不能超过5MB。')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error',Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as image:
                if image.format not in ('PNG','JPEG','WEBP'): raise Problem('Use JPEG, PNG or WebP images / 仅支持JPEG、PNG、WebP图片。')
                if image.width*image.height>16000000: raise Problem('Image resolution is too large / 图片不能超过1600万像素。')
                image.load()
                # Re-encode to remove metadata, active payloads and animation.
                from PIL import ImageOps
                image=ImageOps.exif_transpose(image).convert('RGB')
                image.thumbnail((1600,1600))
                out=io.BytesIO(); image.save(out,format='JPEG',quality=88)
    except Problem: raise
    except (UnidentifiedImageError,OSError,ValueError,Image.DecompressionBombWarning,Image.DecompressionBombError):
        raise Problem('The file is not a valid supported image / 文件不是有效图片。')
    image_id=secrets.token_hex(20)
    con.execute('INSERT INTO images VALUES(?,?,?)',(image_id,out.getvalue(),int(time.time())))
    return image_id


def validate_event(form):
    title=scalar(form,'title').strip(); method=scalar(form,'method'); visibility=scalar(form,'visibility')
    if not 1<=len(title)<=100: raise Problem('Title must be 1–100 characters / 活动名称需1–100字。')
    if method not in ('SINGLE','SCORE','MAJORITY','RCV') or visibility not in ('PUBLIC','PRIVATE'): raise Problem('Invalid event settings / 活动设置无效。')
    try: end=int(datetime.strptime(scalar(form,'deadline'),'%Y-%m-%dT%H:%M').replace(tzinfo=TZ).timestamp())
    except ValueError: raise Problem('Choose a valid end date and time / 请选择有效的截止日期时间。')
    if not time.time()+60<end<=time.time()+MAX_DAYS*86400: raise Problem('End time must be more than one minute ahead and within 30 days / 截止时间须在1分钟后、30天内。')
    return title,method,visibility,end,1 if scalar(form,'submissions_open')=='1' else 0


def save_event(con,uid,form,files,eid=None):
    title,method,visibility,end,accepting=validate_event(form)
    old=con.execute('SELECT * FROM elections WHERE id=?',(eid,)).fetchone() if eid else None
    if eid and (not old or old['creator_id']!=uid): raise Problem('Not the event owner / 仅创建者可操作。',403)
    if old and old['status']!='DRAFT': raise Problem('Published entries and rules are locked / 已开票，名单与规则锁定。',409)
    if not eid:
        eid=con.execute('INSERT INTO elections(creator_id,title,method,visibility,duration,planned_end,allow_submissions) VALUES(?,?,?,?,?,?,?)',(uid,title,'SCORE' if method=='SCORE' else 'SINGLE',visibility,60,end,accepting)).lastrowid
        con.execute('INSERT INTO rounds(election_id) VALUES(?)',(eid,))
    current={str(r['id']):r for r in con.execute('SELECT * FROM candidates WHERE election_id=? AND active=1',(eid,))}
    tokens=form.get('entry_key',[])
    if len(tokens)>20 or len(set(tokens))!=len(tokens): raise Problem('Use at most 20 entries / 最多20个选项。')
    keep=set()
    for key in tokens:
        if not __import__('re').fullmatch('[a-zA-Z0-9_-]{1,40}',key): raise Problem('Invalid entry key.')
        cid=scalar(form,'entry_id_'+key)
        name=scalar(form,'entry_name_'+key).strip(); description=scalar(form,'entry_description_'+key).strip()
        if not 1<=len(name)<=80 or len(description)>1000: raise Problem('Entry name: 1–80 characters; description: at most 1000 / 名称1–80字，介绍最多1000字。')
        row=current.get(cid) if cid else None
        if cid and (not row or row['submitter_id'] not in (None,uid)): raise Problem('Cannot edit another entrant’s submission / 不能改写其他人的报名作品。',403)
        image=save_image(con,files.get('entry_image_'+key))
        if not image and scalar(form,'remove_image_'+key)!='1': image=row['image_id'] if row else None
        if cid:
            con.execute('UPDATE candidates SET name=?,description=?,image_id=? WHERE id=?',(name,description,image,int(cid))); keep.add(cid)
        else:
            cid=con.execute("INSERT INTO candidates(election_id,name,description,image_id,submitter_id,review_status) VALUES(?,?,?,?,?,'APPROVED')",(eid,name,description,image,uid)).lastrowid
            keep.add(str(cid))
    for cid,row in current.items():
        if row['submitter_id'] in (None,uid) and cid not in keep:
            if con.execute('SELECT 1 FROM choices WHERE candidate_id=? UNION SELECT 1 FROM preferences WHERE candidate_id=?',(int(cid),int(cid))).fetchone():
                con.execute('UPDATE candidates SET active=0 WHERE id=?',(int(cid),))
            else: con.execute('DELETE FROM candidates WHERE id=?',(int(cid),))
    allrows=con.execute('SELECT name FROM candidates WHERE election_id=? AND active=1',(eid,)).fetchall()
    names=[r['name'].casefold() for r in allrows]
    if len(names)>20 or len(names)!=len(set(names)): raise Problem('Entry names must be distinct; at most 20 / 选项不能重名，最多20个。')
    if not accepting and len(names)<2: raise Problem('Add at least two entries, or enable applications / 请添加至少2项，或开启报名征集。')
    try: limit=int(scalar(form,'max_choices','1')) if method=='SINGLE' else 1
    except ValueError: raise Problem('Selection limit must be an integer / 可选数量必须为整数。')
    if not 1<=limit<=20: raise Problem('Selection limit must be 1–20 / 最多可选数量须为1～20。')
    con.execute('UPDATE elections SET title=?,method=?,voting_mode=?,max_choices=?,score_optional=1,visibility=?,planned_end=?,allow_submissions=?,submissions_open=CASE WHEN ?=0 THEN 0 ELSE submissions_open END WHERE id=?',(title,'SCORE' if method=='SCORE' else 'SINGLE',method,limit,visibility,end,accepting,accepting,eid))
    invite=scalar(form,'invite_code').strip()
    tags=scalar(form,'tags').strip()
    if len(tags)>120: raise Problem('Tags must be at most 120 characters / 标签最多120字。')
    con.execute('UPDATE elections SET tags=? WHERE id=?',(tags,eid))
    # An explicit save selects the new publication policy; untouched legacy
    # activities retain their previous manual-publication setting.
    con.execute('UPDATE elections SET auto_publish=? WHERE id=?',(1 if visibility=='PUBLIC' else 0,eid))
    if invite:
        if not 4<=len(invite)<=64: raise Problem('Invitation code must be 4–64 characters / 邀请码须为4～64个字符。')
        from app import password_hash
        salt=secrets.token_hex(16)
        con.execute('UPDATE elections SET invite_salt=?,invite_hash=? WHERE id=?',(salt,password_hash(invite,salt),eid))
        con.execute('DELETE FROM event_access WHERE election_id=?',(eid,))
    elif scalar(form,'remove_invite')=='1':
        con.execute("UPDATE elections SET invite_salt='',invite_hash='' WHERE id=?",(eid,))
        con.execute('DELETE FROM event_access WHERE election_id=?',(eid,))
    return eid


def apply_entry(con,eid,uid,form,files):
    event=con.execute('SELECT * FROM elections WHERE id=?',(eid,)).fetchone()
    if not event: raise Problem('Event not found.',404)
    if event['status']!='DRAFT' or not event['submissions_open'] or not event['planned_end'] or event['planned_end']<=time.time(): raise Problem('Applications are closed / 报名已关闭。',409)
    if event['creator_id']==uid: raise Problem('Use the event editor for your own entries / 创建者请在活动编辑页添加。')
    previous=con.execute('SELECT * FROM candidates WHERE election_id=? AND submitter_id=? AND active=1',(eid,uid)).fetchone()
    if previous and previous['review_status']!='REJECTED': raise Problem('You have already submitted an entry / 本活动你已提交过作品。',409)
    name=scalar(form,'name').strip(); description=scalar(form,'description').strip()
    if not 1<=len(name)<=80 or len(description)>1000: raise Problem('Entry name: 1–80 characters; description: at most 1000 / 名称1–80字，介绍最多1000字。')
    rows=con.execute('SELECT name FROM candidates WHERE election_id=? AND active=1 AND id<>?',(eid,previous['id'] if previous else -1)).fetchall()
    if len(rows)>=20 or name.casefold() in [r['name'].casefold() for r in rows]: raise Problem('Entry name is taken or event is full / 名称已存在或报名已满。')
    image=save_image(con,files.get('image'))
    if not image and previous and scalar(form,'remove_image')!='1': image=previous['image_id']
    if previous:
        con.execute("UPDATE candidates SET name=?,description=?,image_id=?,review_status='PENDING',review_reason='' WHERE id=?",(name,description,image,previous['id']))
        return previous['id']
    return con.execute("INSERT INTO candidates(election_id,name,description,image_id,submitter_id,review_status) VALUES(?,?,?,?,?,'PENDING')",(eid,name,description,image,uid)).lastrowid
