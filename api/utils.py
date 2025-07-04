def check_response(response):
    content_type = response.headers.get('content-type')
    if content_type not in ["application/json", "application/json; charset=utf-8"]:
        raise ValueError("Unexpected response format, expected JSON.")
