from fastapi import FastAPI, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum
import requests
import time

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for now
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)

@app.get("/api/mvt")
def get_mvt(
    layer: str = Query(...),
    tileMatrix: str = Query(...),
    tileCol: int = Query(...),
    tileRow: int = Query(...),
    cacheVersion: str = Query(None),
    use_local: bool = Query(False)
):
    try:
        zoomLevel = tileMatrix.split(":")[-1]
        cache_version = cacheVersion if cacheVersion else str(int(time.time() * 1000))
        zoneHavenUrl = (
            f"https://cdngeospatialcei.zonehaven.com/geoserver/gwc/service/wmts"
            f"?REQUEST=GetTile&SERVICE=WMTS&VERSION=1.0.0"
            f"&LAYER={layer}"
            f"&STYLE="
            f"&TILEMATRIX=EPSG:900913:{zoomLevel}"
            f"&TILEMATRIXSET=EPSG:900913"
            f"&FORMAT=application/vnd.mapbox-vector-tile"
            f"&TILECOL={tileCol}"
            f"&TILEROW={tileRow}"
            f"&caheVersion={cache_version}"
        )
        print(f"ZoneHaven URL: {zoneHavenUrl}")
        headers = {
            'Authorization': 'Basic dWktY2xpZW50OlFjZUo2MnpzWTRmYg=='
        }
        resp = requests.get(zoneHavenUrl, headers=headers)
        if not resp.ok:
            print(f'ZoneHaven API error: {resp.status_code} {resp.reason}')
            return Response(
                content=f'{{"error": "ZoneHaven API error: {resp.status_code}"}}',
                status_code=resp.status_code,
                media_type="application/json"
            )
        return Response(content=resp.content, media_type="application/vnd.mapbox-vector-tile")
    except Exception as error:
        print(f'MVT API error: {error}')
        return Response(
            content='{"error": "Internal server error"}',
            status_code=500,
            media_type="application/json"
        )

# This is the Lambda handler
handler = Mangum(app)
