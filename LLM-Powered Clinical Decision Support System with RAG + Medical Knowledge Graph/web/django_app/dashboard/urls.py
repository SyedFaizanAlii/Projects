from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r"queries", views.ClinicalQueryViewSet)
router.register(r"responses", views.QueryResponseViewSet)

urlpatterns = [
    path("", views.index, name="dashboard-home"),
    path("api/", include(router.urls)),
]
