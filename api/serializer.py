from . import models as api_models
from userauth.models import User
from django.contrib.auth.password_validation import validate_password # type:ignore
from rest_framework import serializers # type:ignore
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer # type:ignore
from rest_framework.authtoken.models import Token # type:ignore


class UserSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = ['id', 'fullname', 'email', 'otp', 'email_token', 'customer_id', 'hasAccess', 'product_type']

class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        auth_token, _ = Token.objects.get_or_create(user=user)

        print(auth_token)

        token['email'] = user.email
        token['fullname'] = user.fullname
        token['auth_token'] = str(auth_token)

        return token

class RegisterSerializer(serializers.ModelSerializer):
    fullname = serializers.CharField(write_only=True, required=True)
    email = serializers.EmailField(write_only=True, required=True)
    customer_id = serializers.CharField(write_only=True, required=True)
    product_type = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = ['email', 'fullname', 'customer_id', 'product_type']

    def validate_fullname(self, value):
        """
        Ensure fullname contains at least a first and last name.
        """
        fullname_parts = value.split()
        if len(fullname_parts) < 2:
            raise serializers.ValidationError("Fullname must include at least first and last names.")
        return value

    def create(self, validated_data):
        """
        Create a new user with the provided data.
        """
        fullname_parts = validated_data['fullname'].split()
        username = fullname_parts[0]  # Use the first part of the name as the username

        # Create the user instance
        user = User.objects.create(
            fullname=validated_data['fullname'],
            email=validated_data['email'],
            username=username,  # Assign username
        )

        # Handle additional fields (customer_id, product_type, and hasAccess)
        user.customer_id = validated_data['customer_id']
        user.product_type = validated_data['product_type']

        # Set a random password for the user
        user.set_password("pass1000")
        user.save()
        return user

class TokenLoginSerializer(serializers.Serializer):
    token = serializers.CharField()

    def validate(self, data):
        """
        Ensure the provided token is valid.
        """
        token = data.get("token")
        try:
            login_token = api_models.LoginToken.objects.get(token=token)
        except api_models.LoginToken.DoesNotExist:
            raise serializers.ValidationError("Invalid token.")

        if not login_token.is_valid():
            raise serializers.ValidationError("Token has expired.")

        self.user = login_token.user
        return data        

class BusinessSerializer(serializers.ModelSerializer):
    class Meta:
        model = api_models.Business
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super(BusinessSerializer, self).__init__(*args, **kwargs)
        request = self.context.get('request')
        if request and request.method == "POST":
            self.Meta.depth = 0
        else:
            self.Meta.depth = 1                

class InvoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = api_models.Invoice
        fields = "__all__"
        read_only_fields = ['id', 'Uid', 'date_created',]

    def __init__(self, *args, **kwargs):
        super(InvoiceSerializer, self).__init__(*args, **kwargs)
        request = self.context.get('request')
        if request and request.method == "POST":
            self.Meta.depth = 0
        else:
            self.Meta.depth = 1       

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = api_models.Category
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super(CategorySerializer, self).__init__(*args, **kwargs)
        request = self.context.get('request')
        if request and request.method == "POST":
            self.Meta.depth = 0
        else:
            self.Meta.depth = 1

class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = api_models.Customer
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super(CustomerSerializer, self).__init__(*args, **kwargs)
        request = self.context.get('request')
        if request and request.method == "POST":
            self.Meta.depth = 0
        else:
            self.Meta.depth = 1

class InvoiceItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = api_models.Invoice_item
        fields = "__all__"  

    def __init__(self, *args, **kwargs):
        super(InvoiceItemSerializer, self).__init__(*args, **kwargs)
        request = self.context.get('request')
        if request and request.method == "POST":
            self.Meta.depth = 0
        else:
            self.Meta.depth = 1

class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = api_models.Product
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super(ProductSerializer, self).__init__(*args, **kwargs)
        request = self.context.get('request')
        if request and request.method == "POST":
            self.Meta.depth = 0
        else:
            self.Meta.depth = 1

class InvoiceAdminSerializer(serializers.Serializer):
    invoices = serializers.IntegerField(default=0)
    draft_invoices = serializers.IntegerField(default=0)
    paid_invoices = serializers.IntegerField(default=0)
    unpaid_invoices = serializers.IntegerField(default=0)
    pending_invoices = serializers.IntegerField(default=0)
    customers = serializers.IntegerField(default=0)
    products = serializers.IntegerField(default=0)

class DashboardStatsSerializer(serializers.Serializer):
    month = serializers.CharField()
    invoices = serializers.IntegerField(default=0)

class InvoiceStatsSerializer(serializers.Serializer):
    month = serializers.CharField()
    invoices = serializers.IntegerField(default=0)
    paid = serializers.IntegerField(default=0)

class ReceiptSerializer(serializers.ModelSerializer):
    class Meta:
        model = api_models.Receipt
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super(ReceiptSerializer, self).__init__(*args, **kwargs)
        request = self.context.get('request')
        if request and request.method == "POST":
            self.Meta.depth = 0
        else:
            self.Meta.depth = 1
