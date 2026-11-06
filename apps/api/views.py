from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework.exceptions import AuthenticationFailed

from apps.users.services import send_verification_email

from .serializers import RegisterSerializer, UserSerializer


class MeView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request):
        data = UserSerializer(request.user).data
        account = getattr(request, "cuenta", None) or getattr(
            request._request, "cuenta", None
        )
        if account:
            data["account"] = {
                "id": account.pk,
                "name": account.nombre,
                "plan": account.plan,
                "plan_display": account.get_plan_display(),
                "tenant_limit": account.limite_inquilinos,
                "tenant_count": account.inquilinos_utilizados,
                "tenant_slots_available": account.inquilinos_disponibles,
                "requested_plan": account.plan_solicitado or None,
            }
        return Response(data)


@method_decorator(
    ratelimit(key="ip", rate="5/m", method="POST", block=True), name="dispatch"
)
class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = (permissions.AllowAny,)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        send_verification_email(user, request)
        return Response(
            {"detail": "Cuenta creada. Revisá tu correo para verificar la cuenta."},
            status=status.HTTP_201_CREATED,
        )


class PasswordAwareTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        from apps.users.models import UserSecurityState

        if UserSecurityState.objects.filter(
            user=self.user, must_change_password=True
        ).exists():
            raise AuthenticationFailed(
                "Debe cambiar la contraseña temporal antes de usar la API.",
                code="password_change_required",
            )
        return data


@method_decorator(
    ratelimit(key="ip", rate="10/m", method="POST", block=True), name="dispatch"
)
class RateLimitedTokenObtainPairView(TokenObtainPairView):
    serializer_class = PasswordAwareTokenObtainPairSerializer
