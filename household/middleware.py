from django.contrib.auth import logout


class PrivateResponsesMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and request.session.get('access_version') != request.user.access_version:
            logout(request)
        response = self.get_response(request)
        # Generated appearance stylesheets are cacheable and cached by the
        # display's service worker; everything else stays private and fresh.
        is_cached_asset = request.path.startswith('/static/') or request.path in ('/appearance.css', '/appearance-display.css')
        if not is_cached_asset:
            response['Cache-Control'] = 'no-store, private'
        response['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; worker-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        return response

