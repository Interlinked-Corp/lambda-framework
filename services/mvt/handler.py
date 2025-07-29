import json
import base64
import requests
import time
import boto3
import hashlib
import os

def create_response(status_code, body, content_type="application/json", is_base64=True):
    """Create a standardized Lambda response"""
    headers = {
        "Content-Type": content_type,
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "*",
        "Access-Control-Allow-Methods": "*"
    }
    
    response = {
        "statusCode": status_code,
        "headers": headers,
        "body": body
    }
    
    if is_base64:
        response["isBase64Encoded"] = True
    
    return response

def handler(event, context):
    """Main Lambda handler function"""
    try:
        # Parse the HTTP method and path
        http_method = event.get('httpMethod', 'GET')
        path = event.get('path', '')
        
        # Handle CORS preflight requests
        if http_method == 'OPTIONS':
            return create_response(200, "")
        
        # Parse query parameters
        query_params = event.get('queryStringParameters', {}) or {}
        
        # Route to appropriate handler based on path
        if path == '/api/' or path == '/api':
            return handle_root()
        elif path == '/api/mvt':
            return handle_mvt(query_params)
        else:
            return create_response(404, json.dumps({"error": "Endpoint not found"}))
            
    except Exception as error:
        print(f'Lambda handler error: {error}')
        return create_response(500, json.dumps({"error": "Internal server error"}))

def handle_root():
    """Handle the root endpoint /api/"""
    return create_response(200, json.dumps({"message": "Welcome to the MVT API"}))

def handle_mvt(query_params):
    """Handle the MVT endpoint /api/mvt"""
    try:
        # Extract required parameters
        layer = query_params.get('layer')
        tile_matrix = query_params.get('tileMatrix')
        tile_col = query_params.get('tileCol')
        tile_row = query_params.get('tileRow')
        cache_version = query_params.get('cacheVersion')
        use_local = query_params.get('use_local', 'false').lower() == 'true'
        
        # Validate required parameters
        if not all([layer, tile_matrix, tile_col, tile_row]):
            return create_response(400, json.dumps({
                "error": "Missing required parameters: layer, tileMatrix, tileCol, tileRow"
            }))
        
        # Parse zoom level from tile matrix
        zoom_level = tile_matrix.split(":")[-1]
        
        # Generate cache version if not provided
        if not cache_version:
            cache_version = str(int(time.time() * 1000))
        
        # Create S3 key for the tile
        s3_key = f"mvt-tiles/{layer}/{zoom_level}/{tile_col}/{tile_row}.pbf"
        
        # Initialize S3 client
        s3_client = boto3.client('s3')
        bucket_name = 'mvt-tile-bucket'
        
        # Check if tile exists in S3
        try:
            s3_client.get_object(Bucket=bucket_name, Key=s3_key)
            print(f"Tile found in S3: {s3_key}")
            
            # Generate presigned URL for direct access
            presigned_url = s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': bucket_name, 'Key': s3_key},
                ExpiresIn=3600  # 1 hour
            )
            
            return create_response(200, json.dumps({
                "tileUrl": presigned_url,
                "source": "cache"
            }))
            
        except s3_client.exceptions.NoSuchKey:
            print(f"Tile not found in S3, fetching from ZoneHaven: {s3_key}")
            
            # Construct ZoneHaven URL (matching FastAPI exactly)
            zone_haven_url = (
                f"https://cdngeospatialcei.zonehaven.com/geoserver/gwc/service/wmts?REQUEST=GetTile&SERVICE=WMTS&VERSION=1.0.0"
                f"&LAYER={layer}"
                f"&STYLE="
                f"&TILEMATRIX=EPSG:900913:{zoom_level}"
                f"&TILEMATRIXSET=EPSG:900913"
                f"&FORMAT=application/vnd.mapbox-vector-tile"
                f"&TILECOL={tile_col}"
                f"&TILEROW={tile_row}"
                f"&caheVersion={cache_version}"
            )
            
            print(f"ZoneHaven URL: {zone_haven_url}")
            
            # Make request to ZoneHaven
            headers = {
                'Authorization': 'Basic dWktY2xpZW50OlFjZUo2MnpzWTRmYg=='
            }
            
            resp = requests.get(zone_haven_url, headers=headers)
            
            if not resp.ok:
                print(f'ZoneHaven API error: {resp.status_code} {resp.reason}')
                return create_response(
                    resp.status_code, 
                    json.dumps({"error": f"ZoneHaven API error: {resp.status_code}"})
                )
            
            # Check if we actually got MVT data
            if not resp.content or len(resp.content) == 0:
                return create_response(500, json.dumps({"error": "Empty response from ZoneHaven"}))
            
            # Upload tile to S3
            try:
                s3_client.put_object(
                    Bucket=bucket_name,
                    Key=s3_key,
                    Body=resp.content,
                    ContentType='application/vnd.mapbox-vector-tile',
                    CacheControl='max-age=3600'  # Cache for 1 hour
                )
                print(f"Tile uploaded to S3: {s3_key}")
                
                # Generate presigned URL for the newly uploaded tile
                presigned_url = s3_client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': bucket_name, 'Key': s3_key},
                    ExpiresIn=3600  # 1 hour
                )
                
                return create_response(200, json.dumps({
                    "tileUrl": presigned_url,
                    "source": "zonehaven"
                }))
                
            except Exception as s3_error:
                print(f"S3 upload error: {s3_error}")
                return create_response(500, json.dumps({"error": "Failed to upload tile to S3"}))
        
    except Exception as error:
        print(f'MVT API error: {error}')
        return create_response(500, json.dumps({"error": "Internal server error"}))
