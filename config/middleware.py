
import time


class NoCacheMiddleware:
    COOKIE_NAME = 'canastra_last_auth_activity'
    SESSION_TIMEOUT = 900  # 15 minutos em segundos

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        cookie = request.COOKIES.get(self.COOKIE_NAME)
        expirou = False

        if not request.user.is_authenticated and cookie:
            try:
                ultima_atividade = int(cookie)
                expirou = (
                    time.time() - ultima_atividade > self.SESSION_TIMEOUT
                )
            except (ValueError, TypeError):
                pass

        if expirou:
            request.session['session_expired'] = True

        response = self.get_response(request)

        if expirou:
            response.delete_cookie(self.COOKIE_NAME)

        elif request.resolver_match and request.resolver_match.url_name == 'logout':
            response.delete_cookie(self.COOKIE_NAME)

        elif request.user.is_authenticated:
            response.set_cookie(
                self.COOKIE_NAME,
                str(int(time.time())),
                max_age=86400,
                httponly=True,
                secure=request.is_secure(),
                samesite='Lax'
            )

        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'

        return response
