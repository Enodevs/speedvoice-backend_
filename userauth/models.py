from django.db import models # type:ignore
from django.contrib.auth.models import AbstractUser # type:ignore

def user_directory_path(instance, filename):
    ext = filename.split(".")[-1]
    filename = "%s_%s" % (instance.id, ext)
    return "user_{0}/{1}".format(instance.user_id, filename)

class User(AbstractUser):
    email = models.EmailField(unique=True)
    username = models.CharField(max_length=100)
    fullname = models.CharField(max_length=100, blank=True)
    image = models.FileField(upload_to="image", blank=True)
    hasAccess = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    customer_id = models.CharField(max_length=100, null=True, blank=True)
    product_type = models.CharField(max_length=100, null=True, blank=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['fullname', 'username']

    def __str__(self):
        return self.fullname