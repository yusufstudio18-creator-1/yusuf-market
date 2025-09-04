from flask import Flask, request, redirect, render_template_string, session, url_for
import uuid, qrcode, io, base64, sqlite3, os
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.urandom(24)
DATABASE = os.path.join(os.path.dirname(__file__), "market.db")

# --- Database helpers ---
def get_db():
    db = getattr(app, "_database", None)
    if db is None:
        db = app._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

def init_db():
    db = get_db()
    db.execute("""
        CREATE TABLE IF NOT EXISTS saticilar (
            id TEXT PRIMARY KEY,
            kullanici_adi TEXT UNIQUE,
            sifre_hash TEXT
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS urunler (
            id TEXT PRIMARY KEY,
            ad TEXT,
            fiyat REAL,
            aciklama TEXT,
            kategori TEXT,
            link TEXT,
            satici_id TEXT,
            FOREIGN KEY(satici_id) REFERENCES saticilar(id)
        )
    """)
    db.commit()

@app.before_first_request
def initialize():
    init_db()

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(app, "_database", None)
    if db:
        db.close()

# --- Language support ---
def get_text(key):
    lang = session.get("lang","tr")
    texts = {
        "tr": {
            "home":"Ana Sayfa","login":"Giriş","register":"Kayıt","logout":"Çıkış",
            "seller_panel":"Satıcı Paneli","welcome":"Hoşgeldin","search":"Arama",
            "category":"Kategori","filter":"Filtrele","product_page":"Ürün Sayfası",
            "buy":"Satın Al","add_product":"Ürün Ekle","delete":"Sil","price":"Fiyat",
            "description":"Açıklama","payment_link":"Ödeme Linki","product_list":"Ürünleriniz",
            "password":"Şifre","username":"Kullanıcı Adı"
        },
        "en": {
            "home":"Home","login":"Login","register":"Register","logout":"Logout",
            "seller_panel":"Seller Panel","welcome":"Welcome","search":"Search",
            "category":"Category","filter":"Filter","product_page":"Product Page",
            "buy":"Buy","add_product":"Add Product","delete":"Delete","price":"Price",
            "description":"Description","payment_link":"Payment Link","product_list":"Your Products",
            "password":"Password","username":"Username"
        }
    }
    return texts[lang].get(key,key)

@app.route("/switch_lang")
def switch_lang():
    current = session.get("lang","tr")
    session["lang"] = "en" if current=="tr" else "tr"
    return redirect(request.referrer or "/")

# --- CSS ---
BASE_CSS = """
<style>
body { font-family: Arial, sans-serif; background:#f9f9f9; margin:0; padding:0;}
nav { text-align:left; padding:10px;}
button.lang { background:#e67e22; color:white; border:none; padding:5px 10px; border-radius:5px; cursor:pointer; }
button.lang:hover { background:#d35400; }
form { text-align:center; margin:20px; }
button { background:#3498db; color:white; border:none; padding:8px 12px; cursor:pointer; border-radius:5px; }
button:hover { background:#2980b9; }
a { text-decoration:none; color:#3498db; margin-right:10px; }
a:hover { text-decoration:underline; }
.container { display:flex; flex-wrap:wrap; justify-content:center; }
.card { background:white; border:1px solid #ddd; border-radius:8px; padding:15px; margin:10px; width:250px; box-shadow:0 2px 5px rgba(0,0,0,0.1);}
.card h3 { margin-top:0; }
@media(max-width:600px){.card{width:90%;}}
</style>
"""

# --- Templates ---
HOME_HTML = """
<!DOCTYPE html>
<html lang="{{ session.get('lang','tr') }}">
<head><meta charset="UTF-8"><title>Yusuf Market</title>{{ css }}</head>
<body>
<nav>
<a href="{{ url_for('switch_lang') }}"><button class="lang">{{ 'EN' if session.get('lang','tr')=='tr' else 'TR' }}</button></a>
</nav>
<h1 style="text-align:center;">🛍 Yusuf Market</h1>
<nav>
{% if 'satici_id' in session %}
{{ get_text('welcome') }} {{session['kullanici_adi']}} | <a href='/satici/panel'>{{ get_text('seller_panel') }}</a> | <a href='/logout'>{{ get_text('logout') }}</a>
{% else %}
<a href='/login'>{{ get_text('login') }}</a> | <a href='/register'>{{ get_text('register') }}</a>
{% endif %}
</nav>
<form method="get" action="/">
{{ get_text('search') }}: <input name="q" value="{{query}}">
{{ get_text('category') }}:
<select name="kategori">
<option value="">{{ 'All' if session.get('lang','tr')=='en' else 'Tümü' }}</option>
{% for k in kategoriler %}
<option value="{{k}}" {% if k==secili_kategori %}selected{% endif %}>{{k}}</option>
{% endfor %}
</select>
<button type="submit">{{ get_text('filter') }}</button>
</form>
<div class="container">
{% for u in urunler %}
<div class="card">
<h3>{{u['ad']}} - {{u['fiyat']}} TL</h3>
<p>{{u['aciklama']}}</p>
<p>{{ get_text('category') }}: {{u['kategori']}}</p>
<a href='/urun/{{u["id"]}}'><button>{{ get_text('product_page') }}</button></a>
</div>
{% endfor %}
</div>
</body>
</html>
"""

URUN_HTML = """
<!DOCTYPE html>
<html lang="{{ session.get('lang','tr') }}">
<head><meta charset="UTF-8"><title>{{urun['ad']}} - Yusuf Market</title>{{ css }}</head>
<body>
<a href="{{ url_for('switch_lang') }}"><button class="lang">{{ 'EN' if session.get('lang','tr')=='tr' else 'TR' }}</button></a>
<h2 style="text-align:center;">{{urun['ad']}} - {{urun['fiyat']}} TL</h2>
<p style="text-align:center;">{{urun['aciklama']}}</p>
<p style="text-align:center;">{{ get_text('category') }}: {{urun['kategori']}}</p>
<a href="{{urun['link']}}" target="_blank"><button>{{ get_text('buy') }}</button></a>
<hr>
<p style="text-align:center;">QR Code:</p>
<img style="display:block; margin:auto;" src="data:image/png;base64,{{qr_code}}">
<br><a href="/">{{ get_text('home') }}</a>
</body>
</html>
"""

PANEL_HTML = """
<!DOCTYPE html>
<html lang="{{ session.get('lang','tr') }}">
<head><meta charset="UTF-8"><title>{{ get_text('seller_panel') }}</title>{{ css }}</head>
<body>
<nav>
<a href="{{ url_for('switch_lang') }}"><button class="lang">{{ 'EN' if session.get('lang','tr')=='tr' else 'TR' }}</button></a>
</nav>
<h2>{{ get_text('seller_panel') }} ({{ kullanici_adi }})</h2>
<a href="/satici/ekle">{{ get_text('add_product') }}</a> | <a href="/logout">{{ get_text('logout') }}</a>
<hr>
<h3>{{ get_text('product_list') }}</h3>
<ul>
{% for u in urunler %}
<li>{{u['ad']}} - {{ get_text('price') }}: {{u['fiyat']}} TL - {{ get_text('category') }}: {{u['kategori']}}
<form method="post" action="/satici/delete/{{u['id']}}" style="display:inline">
<button type="submit">{{ get_text('delete') }}</button>
</form>
</li>
{% endfor %}
</ul>
<a href="/">{{ get_text('home') }}</a>
</body>
</html>
"""

EKLE_HTML = """
<!DOCTYPE html>
<html lang="{{ session.get('lang','tr') }}">
<head><meta charset="UTF-8"><title>{{ get_text('add_product') }}</title>{{ css }}</head>
<body>
<a href="{{ url_for('switch_lang') }}"><button class="lang">{{ 'EN' if session.get('lang','tr')=='tr' else 'TR' }}</button></a>
<h2>{{ get_text('add_product') }}</h2>
<form method="post">
{{ get_text('product_page') }}: <input type="text" name="ad"><br><br>
{{ get_text('price') }}: <input type="number" name="fiyat"><br><br>
{{ get_text('description') }}: <input type="text" name="aciklama"><br><br>
{{ get_text('category') }}: <input type="text" name="kategori"><br><br>
{{ get_text('payment_link') }}: <input type="text" name="link"><br><br>
<button type="submit">{{ get_text('add_product') }}</button>
</form>
<a href="/satici/panel">{{ get_text('seller_panel') }}</a> | <a href="/">{{ get_text('home') }}</a>
</body>
</html>
"""

LOGIN_HTML = """
<!DOCTYPE html>
<html lang="{{ session.get('lang','tr') }}">
<head><meta charset="UTF-8"><title>{{ get_text('login') }}</title>{{ css }}</head>
<body>
<h2>{{ get_text('login') }}</h2>
<form method="post">
{{ get_text('username') }}: <input type="text" name="kullanici_adi"><br><br>
{{ get_text('password') }}: <input type="password" name="sifre"><br><br>
<button type="submit">{{ get_text('login') }}</button>
</form>
<a href="/register">{{ get_text('register') }}</a> | <a href="/">{{ get_text('home') }}</a>
</body>
</html>
"""

REGISTER_HTML = """
<!DOCTYPE html>
<html lang="{{ session.get('lang','tr') }}">
<head><meta charset="UTF-8"><title>{{ get_text('register') }}</title>{{ css }}</head>
<body>
<h2>{{ get_text('register') }}</h2>
<form method="post">
{{ get_text('username') }}: <input type="text" name="kullanici_adi"><br><br>
{{ get_text('password') }}: <input type="password" name="sifre"><br><br>
<button type="submit">{{ get_text('register') }}</button>
</form>
<a href="/login">{{ get_text('login') }}</a> | <a href="/">{{ get_text('home') }}</a>
</body>
</html>
"""

# --- Routes ---
@app.route("/", methods=["GET"])
def home():
    query = request.args.get("q","")
    kategori = request.args.get("kategori","")
    db = get_db()
    sql = "SELECT * FROM urunler WHERE 1=1"
    params=[]
    if query:
        sql += " AND ad LIKE ?"
        params.append(f"%{query}%")
    if kategori:
        sql += " AND kategori=?"
        params.append(kategori)
    urunler = db.execute(sql, params).fetchall()
    kategoriler = [u['kategori'] for u in db.execute("SELECT DISTINCT kategori FROM urunler").fetchall()]
    return render_template_string(HOME_HTML, urunler=urunler, query=query, kategoriler=kategoriler, secili_kategori=kategori, css=BASE_CSS, get_text=get_text)

@app.route("/urun/<urun_id>")
def urun(urun_id):
    db = get_db()
    u = db.execute("SELECT * FROM urunler WHERE id=?",(urun_id,)).fetchone()
    if not u:
        return "Ürün bulunamadı"
    qr = qrcode.make(u['link'])
    buf = io.BytesIO()
    qr.save(buf, format='PNG')
    qr_b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return render_template_string(URUN_HTML, urun=u, qr_code=qr_b64, css=BASE_CSS, get_text=get_text)

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        kullanici = request.form["kullanici_adi"]
        sifre = request.form["sifre"]
        db = get_db()
        u = db.execute("SELECT * FROM saticilar WHERE kullanici_adi=?",(kullanici,)).fetchone()
        if u and check_password_hash(u['sifre_hash'],sifre):
            session['satici_id']=u['id']
            session['kullanici_adi']=u['kullanici_adi']
            return redirect("/")
        else:
            return "Hatalı giriş"
    return render_template_string(LOGIN_HTML, css=BASE_CSS, get_text=get_text)

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method=="POST":
        kullanici = request.form["kullanici_adi"]
        sifre = request.form["sifre"]
        db = get_db()
        try:
            db.execute("INSERT INTO saticilar (id,kullanici_adi,sifre_hash) VALUES (?,?,?)",
                       (str(uuid.uuid4()), kullanici, generate_password_hash(sifre)))
            db.commit()
            return redirect("/login")
        except:
            return "Kullanıcı mevcut"
    return render_template_string(REGISTER_HTML, css=BASE_CSS, get_text=get_text)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/satici/panel")
def panel():
    if 'satici_id' not in session:
        return redirect("/login")
    db = get_db()
    urunler = db.execute("SELECT * FROM urunler WHERE satici_id=?",(session['satici_id'],)).fetchall()
    return render_template_string(PANEL_HTML, urunler=urunler, kullanici_adi=session['kullanici_adi'], css=BASE_CSS, get_text=get_text)

@app.route("/satici/ekle", methods=["GET","POST"])
def ekle():
    if 'satici_id' not in session:
        return redirect("/login")
    if request.method=="POST":
        ad = request.form["ad"]
        fiyat = request.form["fiyat"]
        aciklama = request.form["aciklama"]
        kategori = request.form["kategori"]
        link = request.form["link"]
        db = get_db()
        db.execute("INSERT INTO urunler (id,ad,fiyat,aciklama,kategori,link,satici_id) VALUES (?,?,?,?,?,?,?)",
                   (str(uuid.uuid4()),ad,fiyat,aciklama,kategori,link,session['satici_id']))
        db.commit()
        return redirect("/satici/panel")
    return render_template_string(EKLE_HTML, css=BASE_CSS, get_text=get_text)

@app.route("/satici/delete/<urun_id>", methods=["POST"])
def delete(urun_id):
    if 'satici_id' not in session:
        return redirect("/login")
    db = get_db()
    db.execute("DELETE FROM urunler WHERE id=? AND satici_id=?",(urun_id, session['satici_id']))
    db.commit()
    return redirect("/satici/panel")

if __name__=="__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",8080)))