import json

def sum(event, context):
    body = json.loads(event["body"])
    a = body["a"]
    b = body["b"]
    return {
        "statusCode": 200,
        "body": json.dumps({"sum": a + b})
    }
