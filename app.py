#!/usr/bin/env python3
"""家庭点菜系统 v3 - 多家庭 + 多人协作 + 食材管理"""

import os, json, time
from datetime import date, datetime, timedelta
from functools import wraps
from flask import Flask, render_template, request, jsonify, send_from_directory, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, join_room
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(BASE_DIR, 'menu.db')}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.urandom(24).hex()

db = SQLAlchemy(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent')
login_manager = LoginManager(app)
login_manager.login_view = "login_page"

@socketio.on('connect')
def handle_connect():
    try:
        if current_user.is_authenticated:
            join_room(f"family_{current_user.family_id}")
    except:
        pass

# ════════════════════════════════════════════
# 模型
# ════════════════════════════════════════════

class Family(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, default="我的家庭")
    created_at = db.Column(db.DateTime, default=datetime.now)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    family_id = db.Column(db.Integer, db.ForeignKey("family.id"), nullable=False)
    display_name = db.Column(db.String(50), default="")
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    family = db.relationship("Family", backref="users")

    def set_password(self, pwd):
        self.password_hash = generate_password_hash(pwd)
    def check_password(self, pwd):
        return check_password_hash(self.password_hash, pwd)

class Dish(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    family_id = db.Column(db.Integer, db.ForeignKey("family.id"), nullable=False, index=True)
    name = db.Column(db.String(50), nullable=False)
    category = db.Column(db.String(20), nullable=False)
    description = db.Column(db.String(200), default="")
    image_url = db.Column(db.String(300), default="")
    available = db.Column(db.Boolean, default=True)

    def to_dict(self):
        return {"id":self.id,"name":self.name,"category":self.category,
                "description":self.description,"image_url":self.image_url,
                "available":self.available}

class Ingredient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    dish_id = db.Column(db.Integer, db.ForeignKey("dish.id"), nullable=False)
    name = db.Column(db.String(50), nullable=False)
    quantity = db.Column(db.String(30), default="")
    dish = db.relationship("Dish", backref="ingredients")

    def to_dict(self):
        return {"id":self.id,"dish_id":self.dish_id,"name":self.name,"quantity":self.quantity}

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    family_id = db.Column(db.Integer, db.ForeignKey("family.id"), nullable=False, index=True)
    dish_id = db.Column(db.Integer, db.ForeignKey("dish.id"), nullable=True)
    custom_name = db.Column(db.String(100), default="")
    order_date = db.Column(db.Date, nullable=False, default=date.today)
    created_at = db.Column(db.DateTime, default=datetime.now)
    dish = db.relationship("Dish", backref="orders")

    def to_dict(self):
        nm = self.custom_name or (self.dish.name if self.dish else "")
        ct = "自定义" if self.custom_name else (self.dish.category if self.dish else "")
        did = self.dish_id or 0
        return {"id":self.id,"dish_id":did,"dish_name":nm,"category":ct,
                "custom":bool(self.custom_name),
                "order_date":self.order_date.strftime("%Y-%m-%d")}

class Note(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    family_id = db.Column(db.Integer, db.ForeignKey("family.id"), nullable=False, index=True)
    order_date = db.Column(db.Date, nullable=False)
    content = db.Column(db.String(500), default="")
    created_at = db.Column(db.DateTime, default=datetime.now)

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    family_id = db.Column(db.Integer, db.ForeignKey("family.id"), nullable=False, index=True)
    name = db.Column(db.String(20), nullable=False)
    icon = db.Column(db.String(10), default="\U0001f37d\ufe0f")
    sort_order = db.Column(db.Integer, default=0)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ════════════════════════════════════════════
# 辅助函数
# ════════════════════════════════════════════

CACHE_HDR = {"Cache-Control": "no-cache, no-store, must-revalidate"}
STATIC_DIR = os.path.join(BASE_DIR, "static")

_ratelimit = {}
def rate_limit(mpm=120):
    def deco(f):
        @wraps(f)
        def wrap(*a, **kw):
            ip = request.remote_addr or "unk"
            now = time.time()
            key = f"{ip}:{f.__name__}"
            win = _ratelimit.get(key, [])
            win = [t for t in win if now - t < 60]
            if len(win) >= mpm:
                return jsonify({"error":"过于频繁"}), 429
            win.append(now)
            _ratelimit[key] = win
            return f(*a, **kw)
        return wrap
    return deco

def _sanitize_custom_name(nm):
    if not nm or not nm.strip():
        return None
    nm = nm.strip()
    return nm[:100]

# ════════════════════════════════════════════
# 页面路由
# ════════════════════════════════════════════

@app.route("/")
def index():
    if current_user.is_authenticated:
        r = app.make_response(render_template("index.html", user=current_user))
        r.headers.update(CACHE_HDR)
        return r
    return redirect(url_for("login_page"))

@app.route("/admin")
@login_required
def admin_page():
    if not current_user.is_admin:
        return redirect(url_for("index"))
    r = app.make_response(render_template("admin.html", user=current_user))
    r.headers.update(CACHE_HDR)
    return r

@app.route("/static/<path:fp>")
def static_files(fp):
    return send_from_directory(STATIC_DIR, fp)

# ════════════════════════════════════════════
# 认证
# ════════════════════════════════════════════

@app.route("/login", methods=["GET","POST"])
def login_page():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    if request.method == "POST":
        data = request.get_json(silent=True) or request.form
        email = (data.get("email") or "").strip().lower()
        pwd = data.get("password","")
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(pwd):
            login_user(user, remember=True)
            if request.is_json:
                return jsonify({"ok":True,"redirect":url_for("index")})
            return redirect(url_for("index"))
        if request.is_json:
            return jsonify({"error":"邮箱或密码错误"}), 401
        flash("邮箱或密码错误")
    return render_template("login.html")

@app.route("/register", methods=["GET","POST"])
def register_page():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    if request.method == "POST":
        data = request.get_json(silent=True) or request.form
        email = (data.get("email") or "").strip().lower()
        pwd = data.get("password","")
        name = (data.get("family_name") or "").strip() or "我的家庭"
        if not email or "@" not in email:
            return jsonify({"error":"请输入有效邮箱"}), 400
        if len(pwd) < 4:
            return jsonify({"error":"密码至少4位"}), 400
        if User.query.filter_by(email=email).first():
            return jsonify({"error":"该邮箱已注册"}), 400
        try:
            fam = Family(name=name)
            db.session.add(fam)
            db.session.flush()
            user = User(email=email, password_hash="", family_id=fam.id, is_admin=True)
            user.set_password(pwd)
            db.session.add(user)
            db.session.commit()
            login_user(user, remember=True)
            if request.is_json:
                return jsonify({"ok":True,"redirect":url_for("index")})
            return redirect(url_for("index"))
        except Exception as e:
            db.session.rollback()
            return jsonify({"error":"注册失败，请重试"}), 500
    return render_template("register.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login_page"))

# ════════════════════════════════════════════
# API: 菜品
# ════════════════════════════════════════════

@app.route("/api/dishes", methods=["GET"])
@rate_limit()
def get_dishes():
    fid = current_user.family_id if current_user.is_authenticated else 1
    ds = Dish.query.filter_by(family_id=fid, available=True).order_by(Dish.id).all()
    r = jsonify([d.to_dict() for d in ds])
    r.headers.update(CACHE_HDR)
    return r

@app.route("/api/dishes/all", methods=["GET"])
@rate_limit()
@login_required
def get_all_dishes():
    ds = Dish.query.filter_by(family_id=current_user.family_id).order_by(Dish.id).all()
    r = jsonify([d.to_dict() for d in ds])
    r.headers.update(CACHE_HDR)
    return r

@app.route("/api/dishes", methods=["POST"])
@rate_limit(30)
@login_required
def add_dish():
    d = request.get_json()
    dish = Dish(family_id=current_user.family_id, name=d["name"],category=d["category"],
                description=d.get("description",""),image_url=d.get("image_url",""))
    db.session.add(dish); db.session.commit()
    return jsonify({"ok":True,"id":dish.id})

@app.route("/api/dishes/<int:did>", methods=["PUT"])
@rate_limit(30)
@login_required
def upd_dish(did):
    dish = Dish.query.filter_by(id=did, family_id=current_user.family_id).first_or_404()
    for k in request.get_json():
        if k in ("name","category","description","image_url","available"):
            setattr(dish, k, request.get_json()[k])
    db.session.commit()
    return jsonify({"ok":True})

@app.route("/api/dishes/<int:did>", methods=["DELETE"])
@rate_limit(30)
@login_required
def del_dish(did):
    dish = Dish.query.filter_by(id=did, family_id=current_user.family_id).first_or_404()
    db.session.delete(dish)
    db.session.commit()
    return jsonify({"ok":True})

# ─── API: 食材 ────────────────────────────────

@app.route("/api/dishes/<int:did>/ingredients", methods=["GET"])
@rate_limit()
def get_ingredients(did):
    its = Ingredient.query.filter_by(dish_id=did).all()
    return jsonify([i.to_dict() for i in its])

@app.route("/api/dishes/<int:did>/ingredients", methods=["POST"])
@rate_limit(30)
@login_required
def add_ingredient(did):
    d = request.get_json()
    ing = Ingredient(dish_id=did, name=d["name"], quantity=d.get("quantity",""))
    db.session.add(ing); db.session.commit()
    return jsonify({"ok":True,"id":ing.id})

@app.route("/api/ingredients/<int:iid>", methods=["PUT"])
@rate_limit(30)
@login_required
def upd_ingredient(iid):
    ing = Ingredient.query.get_or_404(iid)
    d = request.get_json()
    if "name" in d: ing.name = d["name"]
    if "quantity" in d: ing.quantity = d["quantity"]
    db.session.commit()
    return jsonify({"ok":True})

@app.route("/api/ingredients/<int:iid>", methods=["DELETE"])
@rate_limit(30)
@login_required
def del_ingredient(iid):
    db.session.delete(Ingredient.query.get_or_404(iid))
    db.session.commit()
    return jsonify({"ok":True})

# ─── API: 订单 ────────────────────────────────

def _fid():
    return current_user.family_id if current_user.is_authenticated else 1

@app.route("/api/orders", methods=["GET"])
@rate_limit()
def get_orders():
    d = request.args.get("date", date.today().strftime("%Y-%m-%d"))
    try:
        qd = datetime.strptime(d, "%Y-%m-%d").date()
    except:
        return jsonify({"error":"日期格式错误"}), 400
    fid = _fid()
    os = Order.query.filter_by(family_id=fid, order_date=qd).all()
    r = jsonify({"date":d,"orders":[o.to_dict() for o in os]})
    r.headers.update(CACHE_HDR)
    return r

@app.route("/api/orders/week", methods=["GET"])
@rate_limit()
def get_week_orders():
    t = date.today()
    m = t - timedelta(days=t.weekday())
    fid = _fid()
    os = Order.query.filter(Order.family_id==fid, Order.order_date>=m).order_by(Order.order_date).all()
    r = jsonify({"week_start":m.strftime("%Y-%m-%d"),"orders":[o.to_dict() for o in os]})
    r.headers.update(CACHE_HDR)
    return r

@app.route("/api/orders/toggle", methods=["POST"])
@rate_limit(30)
def toggle_order():
    d = request.get_json()
    did = d.get("dish_id")
    cn = d.get("custom_name") if "custom_name" in d else None
    ods = d.get("order_date", date.today().strftime("%Y-%m-%d"))
    fid = _fid()
    try:
        od = datetime.strptime(ods, "%Y-%m-%d").date()
    except:
        return jsonify({"error":"日期格式错误"}), 400

    if cn is not None:
        cn = _sanitize_custom_name(cn)
        if not cn:
            return jsonify({"error":"菜名不能为空"}), 400
        try:
            exist = Order.query.filter_by(family_id=fid, custom_name=cn, order_date=od).first()
            if exist:
                db.session.delete(exist); db.session.commit()
                try: socketio.emit('order_updated',{'date':ods,'action':'toggle'}, room=f'family_{fid}')
                except: pass
                return jsonify({"ok":True,"selected":False})
            else:
                db.session.add(Order(family_id=fid, custom_name=cn, order_date=od))
                db.session.commit()
                try: socketio.emit('order_updated',{'date':ods,'action':'toggle'}, room=f'family_{fid}')
                except: pass
                return jsonify({"ok":True,"selected":True})
        except Exception:
            db.session.rollback()
            return jsonify({"error":"操作失败，请重试"}), 500

    if not did:
        return jsonify({"error":"缺少菜品"}), 400
    dish = Dish.query.get(did)
    if not dish: return jsonify({"error":"菜品不存在"}), 400
    if not dish.available: return jsonify({"error":"菜品已下架"}), 400

    try:
        exist = Order.query.filter_by(family_id=fid, dish_id=did, order_date=od).first()
        if exist:
            db.session.delete(exist); db.session.commit()
            try: socketio.emit('order_updated',{'date':ods,'action':'toggle'}, room=f'family_{fid}')
            except: pass
            return jsonify({"ok":True,"selected":False})
        else:
            db.session.add(Order(family_id=fid, dish_id=did, order_date=od))
            db.session.commit()
            try: socketio.emit('order_updated',{'date':ods,'action':'toggle'}, room=f'family_{fid}')
            except: pass
            return jsonify({"ok":True,"selected":True})
    except Exception:
        db.session.rollback()
        return jsonify({"error":"操作失败，请重试"}), 500

@app.route("/api/orders/batch", methods=["POST"])
@rate_limit(30)
def batch_orders():
    d = request.get_json()
    dids = d.get("dish_ids",[])
    cns = d.get("custom_names",[])
    ods = d.get("order_date", date.today().strftime("%Y-%m-%d"))
    fid = _fid()
    try:
        od = datetime.strptime(ods, "%Y-%m-%d").date()
    except:
        return jsonify({"error":"日期格式错误"}), 400
    try:
        Order.query.filter_by(family_id=fid, order_date=od).delete()
        for did in dids:
            dish = Dish.query.get(did)
            if dish and dish.available:
                db.session.add(Order(family_id=fid, dish_id=did, order_date=od))
        for nm in cns:
            snm = _sanitize_custom_name(nm)
            if snm:
                db.session.add(Order(family_id=fid, custom_name=snm, order_date=od))
        db.session.commit()
        try: socketio.emit('order_updated',{'date':ods,'action':'batch'}, room=f'family_{fid}')
        except: pass
        return jsonify({"ok":True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error":str(e)}), 500

# ─── API: 购物清单 ────────────────────────────

@app.route("/api/shopping", methods=["GET"])
@rate_limit()
def get_shopping():
    d = request.args.get("date", date.today().strftime("%Y-%m-%d"))
    try:
        qd = datetime.strptime(d, "%Y-%m-%d").date()
    except:
        return jsonify({"error":"日期格式错误"}), 400
    fid = _fid()
    orders = Order.query.filter_by(family_id=fid, order_date=qd).all()
    items = []; done = set()
    for o in orders:
        if o.dish_id and o.dish_id not in done:
            done.add(o.dish_id)
            ings = Ingredient.query.filter_by(dish_id=o.dish_id).all()
            for i in ings:
                items.append({"name":i.name,"quantity":i.quantity,"dish":o.dish.name})
    return jsonify({"date":d,"items":items})

# ─── API: 统计 ────────────────────────────────

@app.route("/api/stats", methods=["GET"])
@rate_limit()
def get_stats():
    from sqlalchemy import func as f
    fid = _fid()
    rows = db.session.query(Order.dish_id, f.count(Order.id).label("cnt")).filter(
        Order.family_id==fid, Order.dish_id.isnot(None)).group_by(Order.dish_id).order_by(
        f.count(Order.id).desc()).limit(20).all()
    top = []
    for r in rows:
        dish = Dish.query.get(r.dish_id)
        if dish:
            top.append({"id":dish.id,"name":dish.name,"category":dish.category,"count":r.cnt})
    total = Order.query.filter_by(family_id=fid).count()
    return jsonify({"total_orders":total,"top_dishes":top})

# ─── API: 笔记 ────────────────────────────────

@app.route("/api/notes", methods=["GET"])
@rate_limit()
def get_notes():
    d = request.args.get("date", date.today().strftime("%Y-%m-%d"))
    try:
        qd = datetime.strptime(d, "%Y-%m-%d").date()
    except:
        return jsonify({"error":"日期格式错误"}), 400
    fid = _fid()
    note = Note.query.filter_by(family_id=fid, order_date=qd).first()
    if note:
        return jsonify({"date":d,"content":note.content,"id":note.id})
    return jsonify({"date":d,"content":"","id":None})

@app.route("/api/notes", methods=["POST"])
@rate_limit(30)
def save_note():
    d = request.get_json()
    ods = d.get("date", date.today().strftime("%Y-%m-%d"))
    content = d.get("content","")
    fid = _fid()
    try:
        od = datetime.strptime(ods, "%Y-%m-%d").date()
    except:
        return jsonify({"error":"日期格式错误"}), 400
    note = Note.query.filter_by(family_id=fid, order_date=od).first()
    if note:
        note.content = content
    else:
        note = Note(family_id=fid, order_date=od, content=content)
        db.session.add(note)
    db.session.commit()
    return jsonify({"ok":True})

# ─── API: 分类 ────────────────────────────────

@app.route("/api/categories", methods=["GET"])
@rate_limit()
def get_categories():
    fid = _fid()
    cats = Category.query.filter_by(family_id=fid).order_by(Category.sort_order).all()
    if not cats:
        defaults = [("荤菜","\U0001f969"),("素菜","\U0001f966"),("汤","\U0001f372"),("主食","\U0001f95e"),("凉菜","\U0001f96c")]
        for i, (n, ic) in enumerate(defaults):
            c = Category(family_id=fid, name=n, icon=ic, sort_order=i)
            db.session.add(c)
        db.session.commit()
        cats = Category.query.filter_by(family_id=fid).order_by(Category.sort_order).all()
    return jsonify([{"id":c.id,"name":c.name,"icon":c.icon} for c in cats])

@app.route("/api/categories", methods=["POST"])
@rate_limit(10)
@login_required
def add_category():
    d = request.get_json()
    name = (d.get("name") or "").strip()
    icon = (d.get("icon") or "\U0001f37d").strip()
    if not name: return jsonify({"error":"请输入分类名称"}), 400
    cat = Category(family_id=current_user.family_id, name=name, icon=icon)
    db.session.add(cat)
    db.session.commit()
    return jsonify({"ok":True,"id":cat.id})

@app.route("/api/categories/<int:cid>", methods=["PUT"])
@rate_limit(10)
@login_required
def upd_category(cid):
    cat = Category.query.filter_by(id=cid, family_id=current_user.family_id).first_or_404()
    d = request.get_json()
    if "name" in d: cat.name = d["name"].strip()
    if "icon" in d: cat.icon = d["icon"].strip()
    db.session.commit()
    return jsonify({"ok":True})

@app.route("/api/categories/<int:cid>", methods=["DELETE"])
@rate_limit(10)
@login_required
def del_category(cid):
    cat = Category.query.filter_by(id=cid, family_id=current_user.family_id).first_or_404()
    cnt = Dish.query.filter_by(family_id=current_user.family_id, category=cat.name).count()
    if cnt > 0:
        return jsonify({"error":f"还有 {cnt} 道菜使用了「{cat.name}」分类，请先修改或删除这些菜品"}), 400
    db.session.delete(cat)
    db.session.commit()
    return jsonify({"ok":True})


# ─── API: 修改密码 ────────────────────────────

@app.route("/api/settings/password", methods=["POST"])
@rate_limit(10)
@login_required
def change_password():
    d = request.get_json()
    old_pwd = d.get("old_password","")
    new_pwd = d.get("new_password","").strip()
    if not current_user.check_password(old_pwd):
        return jsonify({"error":"当前密码错误"}), 400
    if len(new_pwd) < 4:
        return jsonify({"error":"新密码至少4位"}), 400
    current_user.set_password(new_pwd)
    db.session.commit()
    return jsonify({"ok":True})


# ─── API: 提醒 ────────────────────────────────

@app.route("/api/reminder", methods=["POST"])
@rate_limit(10)
def set_reminder():
    import os as _os
    secret = _os.environ.get("FAMILY_MENU_SECRET", "")
    if secret and request.json.get("token","") != secret:
        return jsonify({"error":"未授权"}), 401
    rf = os.path.join(BASE_DIR, ".reminder")
    with open(rf, "w") as f:
        json.dump({"date":date.today().strftime("%Y-%m-%d"),"fired":True}, f)
    return jsonify({"ok":True})

@app.route("/api/reminder", methods=["GET"])
@rate_limit()
def check_reminder():
    rf = os.path.join(BASE_DIR, ".reminder")
    if not os.path.exists(rf):
        return jsonify({"remind":False})
    with open(rf) as f:
        data = json.load(f)
    if data.get("date") == date.today().strftime("%Y-%m-%d") and data.get("fired"):
        cnt = Order.query.filter_by(order_date=date.today()).count()
        if cnt == 0:
            return jsonify({"remind":True})
    return jsonify({"remind":False})

@app.route("/api/reminder/dismiss", methods=["POST"])
def dismiss_reminder():
    rf = os.path.join(BASE_DIR, ".reminder")
    with open(rf, "w") as f:
        json.dump({"date":date.today().strftime("%Y-%m-%d"),"fired":False}, f)
    return jsonify({"ok":True})

# ─── API: 内测预约 ──────────────────────────────

WAITLIST_FILE = os.path.join(BASE_DIR, ".waitlist_emails.txt")

@app.route("/api/waitlist", methods=["POST"])
@rate_limit(10)
def waitlist():
    d = request.get_json()
    email = (d.get("email") or "").strip().lower()
    if not email or "@" not in email:
        return jsonify({"error":"无效邮箱"}), 400
    try:
        exists = False
        if os.path.exists(WAITLIST_FILE):
            with open(WAITLIST_FILE) as f:
                exists = email in f.read()
        if not exists:
            with open(WAITLIST_FILE, "a") as f:
                f.write(email + "\n")
            os.chmod(WAITLIST_FILE, 0o600)
        return jsonify({"ok":True, "new": not exists})
    except Exception as e:
        return jsonify({"error":str(e)}), 500

# ─── API: 设置（旧版密码，保持兼容）──────────────



# ─── API: 当前用户信息 ──────────────────────────

@app.route("/api/me", methods=["GET"])
@login_required
def get_me():
    return jsonify({
        "id": current_user.id,
        "email": current_user.email,
        "display_name": current_user.display_name or current_user.email.split("@")[0],
        "is_admin": current_user.is_admin,
        "family_id": current_user.family_id
    })

# ─── 忘记密码 ────────────────────────────────
@app.route("/forgot", methods=["GET","POST"])
def forgot_page():
    if request.method == "POST":
        data = request.get_json(silent=True) or request.form
        email = (data.get("email") or "").strip().lower()
        user = User.query.filter_by(email=email).first()
        if user:
            import secrets
            new_pwd = secrets.token_hex(6)  # 12位随机密码
            user.set_password(new_pwd)
            db.session.commit()
            if request.is_json:
                return jsonify({"ok":True, "new_password": new_pwd})
            return render_template("forgot.html", sent=True, new_password=new_pwd, email=email)
        if request.is_json:
            return jsonify({"error":"该邮箱未注册"}), 404
        return render_template("forgot.html", sent=True, new_password=None, email=email or "该邮箱")
    email = request.args.get("email", "")
    return render_template("forgot.html", sent=False, email=email)


# ════════════════════════════════════════════
# 启动
# ════════════════════════════════════════════

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    socketio.run(app, host="0.0.0.0", port=5000)
