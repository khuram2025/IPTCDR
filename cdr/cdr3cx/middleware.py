class CDRRequestMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == 'POST' and request.path == '/receive_cdr/':  # Adjust path as needed
            try:
                # Convert the non-standard request to a proper POST
                request.META['REQUEST_METHOD'] = 'POST'
                request.META['CONTENT_TYPE'] = 'text/plain'
                request._body = request.META['RAW_URI'].encode('utf-8')
                request._post = request._files = None
            except Exception as e:
                print(f"Middleware error: {e}")
        return self.get_response(request)