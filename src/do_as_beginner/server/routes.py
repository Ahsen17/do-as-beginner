from django.contrib import admin
from django.urls import path

from do_as_beginner.http import BaseController

urlpatterns = [
    path("admin/", admin.site.urls),
    *[
        path(
            f"{cls.path}/",
            cls().urls,
        )
        for cls in BaseController.__subclasses__()
    ],
]
