from django.contrib.auth import get_user_model
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed, InvalidToken
from rest_framework_simplejwt.serializers import TokenRefreshSerializer


SESSION_REPLACED_DETAIL = (
    "This session expired because this account signed in from another browser or device."
)
SESSION_REPLACED_CODE = "session_replaced"


def _coerce_session_version(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _validate_token_session(user, token):
    token_version = _coerce_session_version(token.get("session_version"))
    current_version = _coerce_session_version(getattr(user, "session_version", None))
    if token_version is None or current_version is None or token_version != current_version:
        raise AuthenticationFailed(SESSION_REPLACED_DETAIL, code=SESSION_REPLACED_CODE)


class SessionVersionJWTAuthentication(JWTAuthentication):
    """
    Enforces one active portal session per account.

    SimpleJWT tokens are otherwise stateless, so a previous browser remains valid after
    a new login. This guard makes the database session_version the source of truth.
    """

    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        _validate_token_session(user, validated_token)
        return user


class SessionVersionTokenRefreshSerializer(TokenRefreshSerializer):
    """
    Prevents old refresh tokens from minting new access tokens after a newer login.
    """

    def validate(self, attrs):
        refresh = self.token_class(attrs["refresh"])
        user_id = refresh.get("user_id")
        token_version = _coerce_session_version(refresh.get("session_version"))
        if user_id is None or token_version is None:
            raise InvalidToken(SESSION_REPLACED_DETAIL)

        User = get_user_model()
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist as exc:
            raise InvalidToken("User not found.") from exc

        if not user.is_active:
            raise InvalidToken("User account is disabled.")

        current_version = _coerce_session_version(getattr(user, "session_version", None))
        if current_version is None or token_version != current_version:
            raise InvalidToken(SESSION_REPLACED_DETAIL)

        return super().validate(attrs)
