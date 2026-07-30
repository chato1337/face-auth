from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema


class HealthView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(tags=["system"], summary="Health check", responses={200: {"type": "object"}})
    def get(self, request):
        return Response({"status": "ok"})
