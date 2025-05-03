from flask import Flask, render_template, request
import requests

app = Flask(__name__)

# TDX 憑證
client_id = 'ae100890-ae89c86e-9a76-46e1'
client_secret = '47c01c48-19ce-4d60-94e8-c72ca8eed731'

# 取得 TDX token
def get_tdx_token():
    url = "https://tdx.transportdata.tw/auth/realms/TDXConnect/protocol/openid-connect/token"
    headers = { "Content-Type": "application/x-www-form-urlencoded" }
    data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret
    }
    response = requests.post(url, headers=headers, data=data)
    return response.json().get("access_token")

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
            metro_stations.append({"name": name})
    return metro_stations

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


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

@app.route("/get_stations", methods=["POST"])
def get_stations():
    lat = request.form.get("lat")
    lon = request.form.get("lon")
    radius = request.form.get("radius", 500)

    stations = get_nearby_stations(lat, lon, radius)
    metro_stations = get_nearby_metro_stations(lat, lon, radius)

    return render_template(
        "index.html",
        stations=stations,
        metro_stations=metro_stations
    )

if __name__ == "__main__":
    app.run(debug=True)
