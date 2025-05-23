import eventlet
eventlet.monkey_patch()
import os, json, requests, time, random, psycopg2,decimal  
from flask import Flask, render_template, redirect, url_for, session, jsonify,request
from flask_socketio import SocketIO
from flask_socketio import emit
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_cors import CORS
from datetime import datetime
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from decimal import Decimal
from requests.adapters import HTTPAdapter
import ssl
from urllib.parse import urlparse


app = Flask(__name__)
app.secret_key = 'key'
CORS(app)
socketio = SocketIO(app)

UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'pic') 
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER  
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
load_dotenv() 
url = urlparse(os.getenv("DATABASE_URL"))
db_config = {
    'host': os.getenv('DB_HOST'),
    'database': os.getenv('DB_NAME'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'port': int(os.getenv('DB_PORT', 5432)),
    'sslmode': os.getenv('DB_SSLMODE', 'require')
}
ORS_API_KEY = os.getenv("ORS_API_KEY")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")
CLIENT_ID = "ae100890-ae89c86e-9a76-46e1"
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
TDX_BASE_URL = "https://tdx.transportdata.tw/api/basic/v2/Bus"

CITY_NAME = "NewTaipei"
DISTRICT_NAME = "淡水區"

DEEPL_API_KEY = os.getenv("DEEPL_API_KEY")
DEEPL_URL = "https://api-free.deepl.com/v2/translate"

@app.route('/index')
def index():
    formatted_itineraries = [] 
    connection = None
    cursor = None
    try:
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()
        sql = """
            SELECT i.id, i.itinerary_name, i.start_time, i.end_time, i.description, 
                i.price, i.locations, i.photos, i.userid, u.username, 
                i.latitude, i.longitude 
            FROM itineraries i
            LEFT JOIN users u ON i.userid = u.user_id
            ORDER BY i.id DESC
        """
        cursor.execute(sql)
        itineraries = cursor.fetchall()

        for itinerary in itineraries:

            id, name, start, end, desc, price, locations, photos, userid, username, latitude, longitude = itinerary
            try:
                locations_data = json.loads(locations)
                if isinstance(locations_data, list):
                    locations_list = [loc.get("name", "") for loc in locations_data]
                else:
                    locations_list = [locations]
            except Exception:
                locations_list = [loc.strip() for loc in locations.split(",")] if locations else []
            try:
                photos_list = json.loads(photos) if photos else []
            except json.JSONDecodeError:
                photos_list = []

            formatted_itineraries.append({
                'id': id,
                'name': name,
                'start': start,
                'end': end,
                'desc': desc,
                'price': price,
                'locations': locations_list,
                'photos': photos_list,
                'userid': userid,
                'username': username,
                'latitude': latitude,
                'longitude': longitude
            })

    except psycopg2.Error as err:
        print(f"Database Error: {err}")
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

    return render_template('index2.html', itineraries=formatted_itineraries)

@app.route('/search')
def search():
    query = request.args.get('q', '').lower()
    if not query:
        return jsonify([])
    connection = None
    cursor = None
    try:
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()

        sql = """
        SELECT id, itinerary_name, locations
        FROM itineraries
        WHERE LOWER(itinerary_name) LIKE %s
           OR LOWER(locations) LIKE %s
           OR LOWER(description) LIKE %s
        ORDER BY id DESC
        """
        keyword = f"%{query}%"
        cursor.execute(sql, (keyword, keyword, keyword))
        raw_results = cursor.fetchall()
        results = []

        for row in raw_results:
            try:
                locs = json.loads(row["locations"])
                if isinstance(locs, list):
                    parsed_locations = [loc.get("name", "") for loc in locs]
                else:
                    parsed_locations = [row["locations"]]
            except:
                parsed_locations = row["locations"].split(",") if row["locations"] else []

            results.append({
                "id": row["id"],
                "itinerary_name": row["itinerary_name"], 
                "locations": parsed_locations
            })

        return jsonify(results)

    except psycopg2.Error as err:
        print(f"Database Error: {err}")
        return jsonify([])

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

@app.route('/user', methods=['GET', 'POST'], endpoint='user_page')
def user_page():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    success_message = None
    error_message = None
    user_comments = []
    user_itineraries = []
    user_info = None
    connection = None
    cursor = None

    def safe_int(value, default=0):
        try:
            return int(value)
        except (ValueError, TypeError):
            return default

    try:
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        
        # 撈使用者資料
        user_sql = """
            SELECT name, username, birth_year, birth_month, birth_day, phone 
            FROM users WHERE user_id = %s
        """
        cursor.execute(user_sql, (session['user_id'],))
        user_info = cursor.fetchone()

        if not user_info:
            return render_template('error.html', error_message="使用者資料不存在"), 404

        # 更新個資
        if request.method == 'POST':
            print("收到 POST 請求")
            name = request.form['name']
            phone = request.form['phone']
            birth_year = request.form['birth_year']
            birth_month = request.form['birth_month']
            birth_day = request.form['birth_day']
            print("更新內容：", name, phone, birth_year, birth_month, birth_day)

            update_sql = """
                UPDATE users
                SET name = %s, phone = %s, birth_year = %s, birth_month = %s, birth_day = %s
                WHERE user_id = %s
            """
            values = (name, phone, safe_int(birth_year), safe_int(birth_month), safe_int(birth_day), session['user_id'])
            cursor.execute(update_sql, values)
            connection.commit()
            success_message = '資料更新成功'

            # 更新後重新抓一次個資
            cursor.execute(user_sql, (session['user_id'],))
            user_info = cursor.fetchone()

        # 撈使用者的留言
        comments_sql = """
            SELECT uc.comment_text, uc.timestamp, u.username
            FROM user_comments uc
            JOIN users u ON uc.user_id = u.user_id
            WHERE u.username = %s
            ORDER BY uc.timestamp
        """
        cursor.execute(comments_sql, (user_info['username'],))
        user_comments = cursor.fetchall()

        # 撈自己刊登的行程
        itineraries_sql = """
            SELECT id, itinerary_name
            FROM itineraries
            WHERE userid = %s
            ORDER BY id DESC
        """
        cursor.execute(itineraries_sql, (session['user_id'],))
        user_itineraries = cursor.fetchall()

    except psycopg2.Error as err:
        print(f"資料庫錯誤內容: {err}")
        error_message = f"資料庫錯誤: {err}"
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

    return render_template('user_page.html',
                           user_info=user_info,
                           success_message=success_message,
                           error_message=error_message,
                           user_comments=user_comments,
                           user_itineraries=user_itineraries)

@app.route('/edit_user', methods=['GET', 'POST'])
def edit_user():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    connection = None
    cursor = None
    try:
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()

        if request.method == 'POST':
            name = request.form.get('name', '')
            birth_year = request.form.get('birth_year', 0)
            birth_month = request.form.get('birth_month', 0)
            birth_day = request.form.get('birth_day', 0)
            phone = request.form.get('phone', '')

            update_sql = """
                UPDATE users
                SET name = %s, birth_year = %s, birth_month = %s, birth_day = %s, phone = %s
                WHERE user_id = %s
            """
            cursor.execute(update_sql, (name, birth_year, birth_month, birth_day, phone, session['user_id']))
            connection.commit()

            return redirect(url_for('user_page'))

        # GET 載入表單資料
        user_sql = "SELECT name, username, birth_year, birth_month, birth_day, phone FROM users WHERE user_id = %s"
        cursor.execute(user_sql, (session['user_id'],))
        user_info = cursor.fetchone()

        if not user_info:
            return render_template('error.html', error_message="使用者資料不存在"), 404

        return render_template('edit_user.html', user_info=user_info)

    except psycopg2.Error as err:
        print(f"Database Error: {err}")
        return render_template('error.html', error_message='資料庫錯誤'), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

@app.route('/user/<username>')
def public_user_page(username):
    user_info = None
    user_comments = []
    user_itineraries = []
    connection = None
    cursor = None
    try:
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()

        user_sql = "SELECT name, username, birth_year, birth_month, birth_day, phone FROM users WHERE username = %s"
        cursor.execute(user_sql, (username,))
        user_info = cursor.fetchone()

        if user_info is None:
            return render_template('error.html', error_message=f"使用者 '{username}' 不存在")

        comments_sql = """
            SELECT uc.comment_text, uc.timestamp, u.username
            FROM user_comments uc
            JOIN users u ON uc.user_id = u.user_id
            WHERE uc.username = %s
            ORDER BY uc.timestamp
        """
        cursor.execute(comments_sql, (username,))
        user_comments = cursor.fetchall()

        itineraries_sql = """
            SELECT id, itinerary_name
            FROM itineraries
            WHERE userid = (SELECT user_id FROM users WHERE username = %s)
            ORDER BY id DESC
        """
        cursor.execute(itineraries_sql, (username,))
        user_itineraries = cursor.fetchall()

    except psycopg2.Error as err:
        print(f"Error: {err}")
        return render_template('error.html', error_message='資料庫錯誤'), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

    return render_template('public_user_page.html',
                           user_info=user_info,
                           user_comments=user_comments,
                           user_itineraries=user_itineraries)

@app.route('/search_usernames')
def search_usernames():
    keyword = request.args.get('q', '').strip().lower()
    if not keyword:
        return jsonify([])
    connection = None
    cursor = None
    try:
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        sql = """
            SELECT username, name FROM users
            WHERE LOWER(username) LIKE %s OR LOWER(name) LIKE %s
            LIMIT 10
        """
        like_kw = f"%{keyword}%"
        cursor.execute(sql, (like_kw, like_kw))
        users = cursor.fetchall()
        return jsonify(users)

    except psycopg2.Error as err:
        print(f"Search error: {err}")
        return jsonify([])

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()
            
@app.route('/', methods=['GET', 'POST'])
def login():
    connection = None
    cursor = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        print("db_config =", db_config)
        try:
            
            connection = psycopg2.connect(**db_config)
            cursor = connection.cursor()

            sql = "SELECT user_id, password FROM users WHERE username = %s"
            cursor.execute(sql, (username,))
            user = cursor.fetchone()

            if user and check_password_hash(user[1], password):
                session['user_id'] = user[0]
                session['username'] = username
                return redirect(url_for('index'))
            else:
                return render_template('login2.html', error_message='帳號或密碼錯誤')
        
        except psycopg2.Error as err:
            print(f"Error: {err}")
            return render_template('login2.html', error_message='資料庫錯誤，請稍後再試')
        
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()

    return render_template('login2.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        username = request.form['username']
        password = request.form['password']
        birth_year = request.form['birth_year']
        birth_month = request.form['birth_month']
        birth_day = request.form['birth_day']
        phone = request.form['phone']
        connection = None
        cursor = None
        
        try:
            connection = psycopg2.connect(**db_config)
            cursor = connection.cursor()
            

            sql_check = "SELECT COUNT(*) FROM users WHERE username = %s"
            cursor.execute(sql_check, (username,))
            user_exists = cursor.fetchone()[0]

            if user_exists > 0:
                return render_template('register2.html', error_message='Username already exists')
            
            sql = """
            INSERT INTO users (name, username, password, birth_year, birth_month, birth_day, phone)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            values = (name, username, generate_password_hash(password), int(birth_year), int(birth_month), int(birth_day), phone)
            cursor.execute(sql, values)
            connection.commit()
        except psycopg2.Error as err:
            return render_template('register2.html', error_message=f'Database error: {err}')
        except Exception as e:
            return render_template('register2.html', error_message=f'Registration failed: {e}')
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()

        return redirect(url_for('login'))
        
    return render_template('register2.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/post', methods=['GET', 'POST'])
def post():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    connection = None
    cursor = None
    try:
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()


        sql = "SELECT name, username, birth_year, birth_month, birth_day, phone FROM users WHERE user_id = %s"
        cursor.execute(sql, (session['user_id'],))
        user_info = cursor.fetchone()

        if request.method == 'POST':
            
            title = request.form.get('title', '').strip()
            description = request.form.get('description', '').strip()
            location = request.form.get('location', '').strip()
            price = request.form.get('price', '0.00').strip()
            photos = request.form.get('photos', '').strip()

            
            if not title or not description or not location:
                return render_template('error.html', error_message='標題、描述和地點不能為空'), 400

            try:
                price = float(price)
            except ValueError:
                return render_template('error.html', error_message='價格必須是數字'), 400

           
            sql_insert = """
                INSERT INTO posts (user_id, title, description, location, price, photos, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
            """
            cursor.execute(sql_insert, (session['user_id'], title, description, location, price, photos))
            connection.commit()

            return redirect(url_for('index')) 

    except psycopg2.Error as err:
        print(f"Database Error: {err}")
        return render_template('error.html', error_message='資料庫錯誤，請稍後再試'), 500

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

    return render_template('post2.html', user_info=user_info)

@app.route('/submit_post', methods=['POST'])
def submit_post():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    connection = None
    cursor = None
    try:
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()
        user_id = session['user_id']
        itinerary_name = request.form['itinerary_name']
        start_time = request.form['start_time']
        end_time = request.form['end_time']
        description = request.form['description']
        price = request.form['price']
        location = request.form['location']
        latitude = float(request.form['latitude'])
        longitude = float(request.form['longitude'])
        photos = request.files.getlist('photos')
        photo_paths = []

        for photo in photos:
            if photo and photo.filename:
                filename = secure_filename(photo.filename)
                save_path = os.path.join('static', 'pic', filename)
                photo.save(save_path)
                photo_paths.append(f"pic/{filename}") 

        if not photo_paths:
            photo_paths.append("pic/default.jpg")  
        
        sql_insert = """
            INSERT INTO itineraries (itinerary_name, start_time, end_time, locations,latitude, longitude, description, price, photos, userid)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(sql_insert, (
            itinerary_name,start_time,end_time,location,latitude,longitude,description,price,json.dumps(photo_paths),user_id
        ))
        connection.commit()
        return redirect(url_for('index'))

    except psycopg2.Error as err:
        print(f"Database Error: {err}")
        return render_template('error.html', error_message="刊登失敗，請稍後再試"), 500

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

@app.route('/cus')
def cus():
    return render_template('cus.html')

@app.route('/cus/AddItinerary/<string:name>')
def cus_AddItinerary(name):
    connection = None
    cursor = None
    try:
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()

        sql = """
            SELECT id, itinerary_name, start_time, end_time, description, price, 
                   locations, latitude, longitude, photos, userid 
            FROM itineraries WHERE itinerary_name = %s
        """
        cursor.execute(sql, (name,))
        itinerary = cursor.fetchone()

        if itinerary:
            id, name, start, end, desc, price, locations, latitude, longitude, photos, userid = itinerary
            locations_list = locations.split(",") if locations else []
            itinerary_data = {
                'id': id,
                'name': name,
                'start': start,
                'end': end,
                'desc': desc,
                'price': price,
                'locations': [location.strip() for location in locations_list],
                'photos': json.loads(photos) if photos not in [None, ''] else [],
                'userid': userid,
                'latitude': latitude,
                'longitude': longitude
            }
            return jsonify(itinerary_data)
        else:
            return jsonify({'error': '行程未找到'}), 404

    except psycopg2.Error as err:
        print(f"Error: {err}")
        return jsonify({'error': '資料庫錯誤'}), 500

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


class TLSAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context()
        #ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        kwargs['ssl_context'] = ctx
        return super().init_poolmanager(*args, **kwargs)

@app.route("/cus/ScheduleItinerary", methods=["POST"])
def cus_ScheduleItinerary():
    data = request.get_json(silent=True) or {}
    start_lat = data.get("start_latitude")
    start_lng = data.get("start_longitude")
    itineraries = data.get("itineraries", [])

    if start_lat is None or start_lng is None or not itineraries:
        return jsonify({"error": "缺少必要的資料：出發點經緯度或方案資料"}), 400

    try:
        coords = [[float(Decimal(start_lng)), float(Decimal(start_lat))]]
    except (decimal.InvalidOperation, ValueError):
        return jsonify({"error": "出發點經緯度格式錯誤"}), 400

    id_mapping = []
    for it in itineraries:
        lat, lng = it.get("latitude"), it.get("longitude")
        try:
            if lat is None or lng is None:
                continue
            coords.append([float(Decimal(lng)), float(Decimal(lat))])
            id_mapping.append(it.get("id"))
        except (decimal.InvalidOperation, ValueError):
            continue

    if len(coords) <= 1:
        return jsonify({"error": "沒有有效的行程經緯度資料"}), 400

    body = {
        "jobs": [
            {"id": idx + 1, "location": loc}
            for idx, loc in enumerate(coords[1:])
        ],
        "vehicles": [{
            "id": 0,
            "profile": "driving-car",
            "start": coords[0],
            "end": coords[0]
        }]
    }

    print("ORS Request body:\n", json.dumps(body, indent=2, ensure_ascii=False))

    url = "https://api.openrouteservice.org/optimization"
    headers = {"Authorization": ORS_API_KEY, "Content-Type": "application/json"}

    try:
        session = requests.Session()
        session.mount("https://", TLSAdapter())

        response = session.post(
            url,
            json=body,
            headers=headers,
            timeout=15
        )
        print("🔑 ORS_API_KEY:", ORS_API_KEY)
        response.raise_for_status()
    except requests.RequestException as e:
        print("OpenRouteService API 錯誤：", e)
        return jsonify({"error": "OpenRouteService API 呼叫失敗"}), 502

    result = response.json()
    steps = result.get("routes", [{}])[0].get("steps", [])
    sorted_ids = [id_mapping[st["job"] - 1] for st in steps if st.get("job")]

    return jsonify({
        "sorted_itinerary_ids": sorted_ids,
        "raw_steps": steps 
    })

@app.route('/cus/search_itineraries')
def search_itineraries():
    keyword = request.args.get('q', '').strip()
    if not keyword:
        return jsonify([])
    connection = None
    cursor = None
    try:
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()
        sql = """
            SELECT itinerary_name FROM itineraries 
            WHERE itinerary_name ILIKE %s 
            LIMIT 10
        """
        cursor.execute(sql, (f'%{keyword}%',))
        results = [row[0] for row in cursor.fetchall()]
        return jsonify(results)

    except Exception as e:
        print("Search error:", e)
        return jsonify([])

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

@app.route('/case/<int:id>')
def case(id):
    itinerary = None
    try:
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()
        sql = """
            SELECT i.id, i.itinerary_name, i.start_time, i.end_time, i.description, 
                   i.price, i.locations, i.photos, i.userid, u.username, 
                   i.latitude, i.longitude 
            FROM itineraries i
            LEFT JOIN users u ON i.userid = u.user_id
            WHERE i.id = %s
        """
        cursor.execute(sql, (id,))
        itinerary = cursor.fetchone()

        if itinerary:
            id, name, start, end, desc, price, locations, photos, userid, username, latitude, longitude = itinerary

            try:
                locations_data = json.loads(locations)
                if isinstance(locations_data, list):
                    locations_list = [loc.get("name", "") for loc in locations_data]
                else:
                    locations_list = [locations]
            except:
                locations_list = [loc.strip() for loc in locations.split(",")] if locations else []


            try:
                photos_list = json.loads(photos) if photos else []
            except json.JSONDecodeError:
                photos_list = []

            return render_template('case.html', itinerary=(
                id, name, start, end, desc, price,
                locations_list, photos_list, username,
                latitude, longitude
            ))
        else:
            return render_template('error.html', error_message="未找到該行程"), 404

    except psycopg2.Error as err:
        print(f"Database Error: {err}")
        return render_template('error.html', error_message='資料庫錯誤，請稍後再試'), 500

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

@app.route('/edit_case/<int:id>', methods=['GET', 'POST'])
def edit_case(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    connection = None
    cursor = None
    try:
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()
        cursor.execute("SELECT userid FROM itineraries WHERE id = %s", (id,))
        result = cursor.fetchone()

        if not result:
            return render_template('error.html', error_message='行程未找到'), 404

        itinerary_owner_id = result[0]
        current_user_id = session.get('user_id')
        if current_user_id != itinerary_owner_id:
            return render_template('error.html', error_message='您沒有權限編輯此行程'), 403

        if request.method == 'POST':
            itinerary_name = request.form.get('itinerary_name', '')
            start_time = request.form.get('start_time', '')
            end_time = request.form.get('end_time', '')
            locations = request.form.get('locations', '')
            description = request.form.get('description', '')
            price = request.form.get('price', '0.00')
            longitude = request.form.get('longitude', '0.0')
            latitude = request.form.get('latitude', '0.0')

            try:
                longitude = float(longitude)
                latitude = float(latitude)

                if not (-180 <= longitude <= 180):
                    return render_template('error.html', error_message='經度必須在 -180 到 180 之間'), 400
                if not (-90 <= latitude <= 90):
                    return render_template('error.html', error_message='緯度必須在 -90 到 90 之間'), 400

                keep_photos = request.form.getlist('keep_photos')
                new_photos = request.files.getlist('new_photos')
                new_photo_paths = []

                for photo in new_photos:
                    if photo and photo.filename:
                        try:
                            timestamp = int(time.time() * 1000)
                            filename = f"{timestamp}_{random.randint(1000,9999)}_{secure_filename(photo.filename)}"
                            save_path = os.path.join('static', 'pic', filename)
                            photo.save(save_path)
                            new_photo_paths.append(f"pic/{filename}")
                        except Exception as e:
                            print(f"新照片儲存失敗: {e}")

                final_photos = keep_photos + new_photo_paths


                try:
                    photos_json = json.dumps(final_photos, ensure_ascii=False)
                except Exception as e:
                    print("JSON 轉換錯誤:", e)
                    photos_json = "[]"

                sql_update = """
                    UPDATE itineraries
                    SET itinerary_name = %s, start_time = %s, end_time = %s, 
                        locations = %s, longitude = %s, latitude = %s,
                        description = %s, price = %s, photos = %s 
                    WHERE id = %s
                """
                print("更新的行程 ID:", id)
                cursor.execute(sql_update, (
                    itinerary_name, start_time, end_time, locations,
                    longitude, latitude, description, price,
                    photos_json,
                    id
                ))
                print("更新的資料列數:", cursor.rowcount)
                connection.commit()
                return redirect(url_for('index'))

            except ValueError:
                return render_template('error.html', error_message='經度或緯度無法轉換為數字'), 400
            except psycopg2.Error as err:
                print(f"Database Error: {err}")
                return render_template('error.html', error_message='更新行程時出錯'), 500

        cursor.execute("""
            SELECT itinerary_name, start_time, end_time, locations, description, 
                   price, photos, longitude, latitude 
            FROM itineraries WHERE id = %s
        """, (id,))
        itinerary_data = cursor.fetchone()

        itinerary = {
            'itinerary_name': itinerary_data[0],
            'start_time': itinerary_data[1],
            'end_time': itinerary_data[2],
            'locations': itinerary_data[3],
            'description': itinerary_data[4],
            'price': itinerary_data[5],
            'photos': json.loads(itinerary_data[6]) if itinerary_data[6] else [],
            'longitude': itinerary_data[7],
            'latitude': itinerary_data[8]
        }

        return render_template('edit.html', itinerary=itinerary)

    except psycopg2.Error as err:
        print(f"Error: {err}")
        return render_template('error.html', error_message='資料庫錯誤'), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

@app.route('/chat/<username>', methods=['GET', 'POST'])
def chat(username):
    if 'user_id' not in session or 'username' not in session:
        return redirect(url_for('login'))

    user_messages = []
    contacts = []
    user_id = session['user_id'] 
    self_username = session['username'] 
    connection = None
    cursor = None
    try:
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor(cursor_factory=RealDictCursor)

        cursor.execute("SELECT user_id FROM users WHERE username = %s", (username,))
        result = cursor.fetchone()

        if result:
            recipient_id = result['user_id']
            recipient_username = username

            sql = """SELECT userid, receiver, message, timestamp, u.username
                    FROM messages
                    JOIN users u ON userid = u.user_id
                    WHERE (userid = %s AND receiver = %s)
                        OR (userid = %s AND receiver = %s)
                    ORDER BY timestamp"""
            cursor.execute(sql, (
                user_id, recipient_username,
                recipient_id, self_username
            ))
            user_messages = cursor.fetchall()

            sql_contacts = """
                SELECT DISTINCT CASE
                    WHEN messages.userid = %s THEN messages.receiver
                    ELSE CAST(messages.userid AS TEXT)
                END AS contact_id
                FROM messages
                WHERE messages.userid = %s OR messages.receiver = %s
            """
            cursor.execute(sql_contacts, (user_id, user_id, self_username))
            contacts = [row['contact_id'] for row in cursor.fetchall() if str(row['contact_id']) != self_username]

        else:
            return render_template('error.html', error_message=f"使用者 '{username}' 不存在")
    except psycopg2.Error as err:
        print(f"Database Error: {err}")
        return render_template('error.html', error_message='資料庫錯誤')

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

    return render_template(
        'chat2.html',
        chat_messages=user_messages,
        recipient_id=recipient_id,
        contacts=contacts,
        recipient_username=username
    )

@app.route('/chat_list')
def chat_list():
    try:
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()
        sql = "SELECT username ,name FROM users"
        cursor.execute(sql)
        users = cursor.fetchall()
        connection = None
        cursor = None
    except psycopg2.Error as err:
        return render_template('error.html', error_message=f"資料庫錯誤: {err}")
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()
    return render_template('chat_list.html', users=users)

@socketio.on('send_message')
def handle_send_message(data):
    message = data.get('message')
    recipient_id = data.get('recipient_id')
    user_id = session.get('user_id')
    sender_username = session.get('username')
    connection = None
    cursor = None
    if not message or not recipient_id or not user_id:
        print("資料不完整，無法處理訊息")
        return

    try:
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()

        # 先查出對方 username，因為 receiver 欄位存的是 username 而不是 user_id
        cursor.execute("SELECT username FROM users WHERE user_id = %s", (recipient_id,))
        result = cursor.fetchone()
        if not result:
            print("找不到接收者 username")
            return
        recipient_username = result[0]

        # 寫入訊息
        timestamp = datetime.now()
        sql = """
            INSERT INTO messages (userid, receiver, message, timestamp)
            VALUES (%s, %s, %s, %s)
        """
        cursor.execute(sql, (user_id, recipient_username, message, timestamp))
        connection.commit()

        # 發送訊息給雙方（房間以 username 為識別）
        emit('receive_message', {
            'message': message,
            'user_id': user_id,
            'recipient_id': recipient_id,
            'timestamp': timestamp.strftime('%Y-%m-%d %H:%M:%S')
        }, room=recipient_username)

        emit('receive_message', {
            'message': message,
            'user_id': user_id,
            'recipient_id': recipient_id,
            'timestamp': timestamp.strftime('%Y-%m-%d %H:%M:%S')
        }, room=sender_username)

    except Exception as err:
        print(f"SocketIO message insert error: {err}")
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

@app.route('/add_comment/<int:itinerary_id>', methods=['POST'])
def add_comment(itinerary_id):
    connection = None
    cursor = None
    try:
        if 'user_id' not in session:
            return jsonify({'error': '未登入'}), 401

        if request.is_json:
            data = request.get_json()
        else:
            data = request.form

        # 再從 data 拿 comment、rating
        comment = data.get('comment')
        rating = data.get('rating')
        
        if not comment or comment.strip() == "":
            return jsonify({'error': '留言內容不能為空'}), 400

        user_id = session['user_id']
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()
        query = "INSERT INTO itinerary_comments (itinerary_id, user_id, comment_text, rating) VALUES (%s, %s, %s, %s)"
        cursor.execute(query, (itinerary_id, user_id, comment, rating))
        connection.commit()
        return jsonify({'message': '留言成功'})
    except psycopg2.Error as err:
        print(f"Error adding comment: {err}")
        return jsonify({'error': '資料庫錯誤'}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

@app.route('/get_comments/<int:itinerary_id>')
def get_comments(itinerary_id):
    connection = None
    cursor = None
    try:
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        query = """
            SELECT u.username, ic.comment_text, ic.rating, ic.timestamp
            FROM itinerary_comments ic
            JOIN users u ON ic.user_id = u.user_id
            WHERE ic.itinerary_id = %s
            ORDER BY ic.timestamp
        """
        cursor.execute(query, (itinerary_id,))
        comments = cursor.fetchall()

        for comment in comments:
            if comment.get('timestamp'):
                comment['timestamp'] = comment['timestamp'].isoformat()
        return jsonify(comments)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

@app.route('/add_user_comment/<username>', methods=['POST'])
def add_user_comment(username):
    if 'user_id' not in session:
        return jsonify({'error': '未登入'}), 401 

    comment = request.json.get('comment')
    user_id = session['user_id'] 
    connection = None
    cursor = None
    try:
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()

        sql = "INSERT INTO user_comments (username, user_id, comment_text) VALUES (%s, %s, %s)"
        cursor.execute(sql, (username, user_id, comment))
        connection.commit()
        return jsonify({'message': '留言成功'})
    except psycopg2.Error as err:
        print(f"Error adding comment: {err}")
        return jsonify({'error': '資料庫錯誤'}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

@app.route('/get_user_comments/<username>', methods=['GET'])
def get_user_comments(username):
    try:
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        connection = None
        cursor = None

        sql = """
            SELECT uc.comment_text, uc.timestamp, u.username
            FROM user_comments uc
            JOIN users u ON uc.user_id = u.user_id
            WHERE uc.username = %s
            ORDER BY uc.timestamp DESC
        """
        cursor.execute(sql, (username,))
        comments = cursor.fetchall()
        return jsonify(comments)
    except psycopg2.Error as err:
        print(f"Error fetching comments: {err}")
        return jsonify({'error': '資料庫錯誤'}), 500
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

def get_tdx_token():
    url = "https://tdx.transportdata.tw/auth/realms/TDXConnect/protocol/openid-connect/token"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET
    }
    
    response = requests.post(url, headers=headers, data=data)
    if response.status_code == 200:
        return response.json()["access_token"]
    else:
        return None

@app.route('/weather', methods=['POST'])
def get_weather():
    city = request.form.get("city", "Taipei")  
    url = f"https://api.openweathermap.org/data/2.5/weather?q={city},TW&appid={WEATHER_API_KEY}&lang=zh_tw&units=metric"
    response = requests.get(url)
    weather_data = response.json()

    if weather_data.get("cod") != 200:
        return jsonify({"error": weather_data.get('message', '查詢失敗')})

    return jsonify({
        "city": weather_data['name'],
        "temp": weather_data['main']['temp'],
        "description": weather_data['weather'][0]['description'],
        "humidity": weather_data['main']['humidity'],
        "wind_speed": weather_data['wind']['speed']
    })

@app.route("/bus/search", methods=["POST"])
def search_bus_routes():
    start_stop = request.form.get("start_stop")
    end_stop = request.form.get("end_stop")
    
    if not start_stop or not end_stop:
        return jsonify({"error": "請輸入起點與終點站"}), 400

    token = get_tdx_token()
    if not token:
        return jsonify({"error": "無法取得 Token"}), 500

    url = "https://tdx.transportdata.tw/api/basic/v2/Bus/StopOfRoute/City/NewTaipei?%24format=JSON"
    headers = {"Authorization": f"Bearer {token}"}
    
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return jsonify({"error": "無法取得公車路線資訊"}), 500

    bus_data = response.json()
    available_buses = []

    # 篩選有經過起點與終點的公車
    for bus in bus_data:
        stops = [stop["StopName"]["Zh_tw"] for stop in bus["Stops"]]
        if start_stop in stops and end_stop in stops:
            available_buses.append(bus["RouteName"]["Zh_tw"])

    if not available_buses:
        return jsonify({"error": "沒有找到可以直達的公車"}), 404

    return jsonify({"buses": available_buses})

@app.route("/bus/eta/by-route", methods=["GET"])
def get_eta_by_route():
    route = request.args.get("bus_number", "").strip()
    if not route:
        return jsonify({"error": "請輸入公車號碼"}), 400

    token = get_tdx_token()
    if not token:
        return jsonify({"error": "無法取得 Token"}), 500

    url = f"https://tdx.transportdata.tw/api/basic/v2/Bus/EstimatedTimeOfArrival/City/NewTaipei/{route}?$format=JSON"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        return jsonify({"error": "無法取得資料"}), 500

    data = response.json()
    result = []

    for item in data:
        est = item.get("EstimateTime")
        if est is not None:
            result.append({
                "StopName": item["StopName"]["Zh_tw"],
                "EstimateTime": est // 60
            })

    return jsonify({"route": route, "etas": result})

@app.route("/bus/eta/by-stop", methods=["GET"])
def get_eta_by_stop():
    stop_name = request.args.get("stop_name", "").strip()
    if not stop_name:
        return jsonify({"error": "請輸入站名"}), 400

    token = get_tdx_token()
    if not token:
        return jsonify({"error": "無法取得 Token"}), 500

    url = "https://tdx.transportdata.tw/api/basic/v2/Bus/EstimatedTimeOfArrival/City/NewTaipei?$format=JSON"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        return jsonify({"error": "無法取得資料"}), 500

    data = response.json()
    result = []

    for item in data:
        if item["StopName"]["Zh_tw"] == stop_name:
            est = item.get("EstimateTime")
            if est is not None:
                result.append({
                    "RouteName": item["RouteName"]["Zh_tw"],
                    "EstimateTime": est // 60
                })

    return jsonify({"stop": stop_name, "etas": result})

@app.route("/bus/suggestions", methods=["GET"])
def get_bus_suggestions():
    start_stop = request.args.get("start", "").strip()
    end_stop = request.args.get("end", "").strip()
    if not start_stop or not end_stop:
        return jsonify({"error": "請輸入起點與終點站"}), 400

    token = get_tdx_token()
    if not token:
        return jsonify({"error": "無法取得 Token"}), 500

    url = f"{TDX_BASE_URL}/StopOfRoute/City/{CITY_NAME}?%24format=JSON"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        return jsonify({"error": "無法取得公車路線資訊"}), 500

    bus_data = response.json()
    buses_via_start = set()
    buses_via_end = set()
    direct_buses = []
    transfer_buses = []

    for bus in bus_data:
        route_name = bus["RouteName"]["Zh_tw"]
        stops = [stop["StopName"]["Zh_tw"] for stop in bus["Stops"]]

        if start_stop in stops and end_stop in stops:
            direct_buses.append(route_name)
        if start_stop in stops:
            buses_via_start.add(route_name)
        if end_stop in stops:
            buses_via_end.add(route_name)

    MAX_RESULTS = 10
    for bus1 in buses_via_start:
        for bus2 in buses_via_end:
            if bus1 != bus2:
                transfer_buses.append((bus1, bus2))
                if len(transfer_buses) >= MAX_RESULTS:
                    break
        if len(transfer_buses) >= MAX_RESULTS:
            break

    return jsonify({
        "direct_buses": direct_buses,
        "transfer_buses": transfer_buses
    })

# 查詢附近公車站
def get_nearby_stations(lat, lon, radius):
    token = get_tdx_token()
    headers = { "Authorization": f"Bearer {token}" }
    url = f"https://tdx.transportdata.tw/api/advanced/v2/Bus/Station/NearBy?$spatialFilter=nearby({lat},{lon},{radius})&$format=JSON"
    response = requests.get(url, headers=headers)

    stations = []
    if response.status_code == 200:
        data = response.json()
        for s in data:
            name = s["StationName"]["Zh_tw"]
            addr = s.get("StationAddress", "無地址")
            stations.append({"name": name, "addr": addr})
    return stations

# 查詢附近捷運站
def get_nearby_metro_stations(lat, lon, radius):
    token = get_tdx_token()
    headers = { "Authorization": f"Bearer {token}" }
    url = f"https://tdx.transportdata.tw/api/basic/v2/Rail/Metro/Station/NearBy?$spatialFilter=nearby({lat},{lon},{radius})&$format=JSON"
    response = requests.get(url, headers=headers)

    metro_stations = []
    if response.status_code == 200:
        data = response.json()
        for s in data:
            name = s["StationName"]["Zh_tw"]
            operator = s.get("OperatorID", "")
            metro_stations.append({"name": name, "operator": operator})
    return metro_stations


@app.route("/get_stations", methods=["POST"])
def get_stations():
    lat = request.form.get("lat")
    lon = request.form.get("lon")
    radius = request.form.get("radius", 500)

    stations = get_nearby_stations(lat, lon, radius)
    metro_stations = get_nearby_metro_stations(lat, lon, radius)

    return render_template(
        "cus.html",  # ⚠️ 根據你使用的模板檔名修改
        stations=stations,
        metro_stations=metro_stations
    )
def translate_text_from_api(text, target_lang):
    params = {
        'auth_key': DEEPL_API_KEY,
        'text': text,
        'target_lang': target_lang
    }

    response = requests.post(DEEPL_URL, data=params)

    if response.status_code != 200:
        print("❌ DeepL API 錯誤:", response.status_code)
        print("🔍 回傳內容:", response.text)
        return None

    try:
        result = response.json()
        if 'translations' in result:
            return result['translations'][0]['text']
        else:
            print("❗️解析成功但找不到 'translations':", result)
            return None
    except Exception as e:
        print("❌ JSON 解析錯誤:", e)
        print("⚠️ 原始內容:", response.text)
        return None

@app.route("/translate", methods=["POST"])
def translate_text_route():
    data = request.get_json()
    text = data.get("text", "")
    target_lang = data.get("target_lang", "EN")

    if not text:
        return jsonify({"error": "未提供文本進行翻譯"}), 400

    texts = text.split("\n___SPLIT___\n")  # 分段

    translations = []
    for text_chunk in texts:
        translated_text = translate_text_from_api(text_chunk, target_lang)
        if translated_text:
            translations.append(translated_text)
        else:
            translations.append("")  # 保持對齊

    final_translation = "\n___SPLIT___\n".join(translations)
    return jsonify({"translation": final_translation})


#if __name__ == '__main__':
#   socketio.run(app, debug=True) 