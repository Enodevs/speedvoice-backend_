from django.shortcuts import render # type:ignore
from rest_framework_simplejwt.views import TokenObtainPairView # type:ignore
from api import serializer as api_serializer # type:ignore
from rest_framework.decorators import APIView # type:ignore
from rest_framework import generics # type:ignore
from api import models as api_models # type:ignore
from userauth.models import User
from rest_framework.decorators import permission_classes # type:ignore
from rest_framework.permissions import AllowAny, IsAuthenticated # type:ignore
from rest_framework import status # type:ignore
from rest_framework.response import Response # type:ignore
from rest_framework_simplejwt.tokens import RefreshToken # type:ignore
from django.template.loader import render_to_string # type:ignore
from django.conf import settings # type:ignore
from django.utils.html import strip_tags # type:ignore
from django.db.models.functions import ExtractMonth # type:ignore
from django.db.models import Count, Sum, Q # type:ignore
from rest_framework.parsers import MultiPartParser, FormParser # type:ignore
from rest_framework.authtoken.models import Token # type:ignore

from drf_yasg import openapi # type:ignore
from drf_yasg.utils import swagger_auto_schema # type:ignore
from django.core.mail import EmailMultiAlternatives # type:ignore

import random
import json
import secrets

class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = api_serializer.MyTokenObtainPairSerializer

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = api_serializer.RegisterSerializer
    permission_classes = [AllowAny]

    def perform_create(self, serializer):
        # You can customize user creation logic here if necessary
        # For example, you can add custom profile data, etc.
        serializer.save()

class GenerateLoginTokenAPIView(APIView):
    """
    API to generate a passwordless login token for a user.
    """

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['email'],
            properties={
                'email': openapi.Schema(type=openapi.TYPE_STRING, description='User email to check existence'),
            }
        ),
        operation_description="Check if a user exists with the provided email"
    )

    def post(self, request):
        email = request.data.get("email")
        try:
            # Find user by email
            user = User.objects.get(email=email)

            # Generate a secure token
            token = secrets.token_urlsafe(32)

            # Save the token to the database
            api_models.LoginToken.objects.create(user=user, token=token)

            return Response({"token": token}, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({"error": "No user found with this email."}, status=status.HTTP_400_BAD_REQUEST)
        
class CheckUserEmailAPIView(APIView):
    """
    API to check if a user exists with the provided email.
    """
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['email'],
            properties={
                'email': openapi.Schema(type=openapi.TYPE_STRING, description='User email to check existence'),
            }
        ),
        operation_description="Check if a user exists with the provided email"
    )

    def post(self, request):
        email = request.data.get("email")
        if not email:
            return Response({"error": "Email is required."}, status=status.HTTP_400_BAD_REQUEST)

        user_exists = User.objects.filter(email=email).exists()
        return Response({"user_exists": user_exists}, status=status.HTTP_200_OK)


class TokenLoginAPIView(APIView):
    """
    API to verify a login token and return an authentication token.
    """

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['email'],
            properties={
                'token': openapi.Schema(type=openapi.TYPE_STRING, description='User token to check existence'),
            }
        ),
        operation_description="Check if a user exists with the provided token"
    )

    def post(self, request):
        serializer = api_serializer.TokenLoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.user

            # Create or retrieve the API token
            try:
                auth_token, _ = Token.objects.get_or_create(user=user)
            except Exception as e:
                return Response({"error": f"Error creating or retrieving token: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # Optionally delete the one-time login token after successful login
            try:
                api_models.LoginToken.objects.filter(token=request.data.get("token")).delete()
            except Exception as e:
                return Response({"warning": f"Error deleting login token: {e}"}, status=status.HTTP_200_OK) #Non-critical error

            return Response({
                "auth_token": auth_token.key,
                "user_id": user.id,
                "email": user.email,
                "name": user.fullname
            }, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class BusinessGetView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = api_serializer.BusinessSerializer
    permission_classes = [AllowAny]

    def get_object(self):
        try:
            owner_id = self.kwargs['owner_id']
            owner = User.objects.get(id=owner_id)
            business = api_models.Business.objects.get(owner=owner, active=True)
            return business
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)
        except api_models.Business.DoesNotExist:
            return Response({"error": "Business not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": f"An unexpected error occurred: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    
    def update(self, request, *args, **kwargs):
        try:
            business_instance = self.get_object()

            name = request.data.get('name')
            country = request.data.get('country')
            state = request.data.get('state')
            city = request.data.get('city')

            business_instance.name = name
            business_instance.country = country
            business_instance.state = state
            business_instance.city = city

            business_instance.save()

            return Response({"message": "Business updated successfully"}, status=status.HTTP_200_OK)    
        except Exception as e:
            return Response({"error": f"Error updating business: {e}"}, status=status.HTTP_400_BAD_REQUEST)

class BusinessCreateView(APIView):
    permission_classes = (AllowAny,)

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['owner', 'name', 'country', 'state', 'city'],
            properties={
                'owner': openapi.Schema(type=openapi.TYPE_INTEGER, description='User ID'),
                'name': openapi.Schema(type=openapi.TYPE_STRING, description='Business name'),
                'country': openapi.Schema(type=openapi.TYPE_STRING, description='Business country'),
                'state': openapi.Schema(type=openapi.TYPE_STRING, description='Business state'),
                'city': openapi.Schema(type=openapi.TYPE_STRING, description='Business city'),
                'currency': openapi.Schema(type=openapi.TYPE_STRING, description='Business currency'),
            }   
        ),
        operation_description="Create a new business for a user"
    )

    def post(self, request):
        try:
            user_id = request.data.get('owner')
            name = request.data.get('name')
            country = request.data.get('country')
            state = request.data.get('state')
            city = request.data.get('city')
            currency = request.data.get('currency')

            user = User.objects.get(id=user_id)

            try:
                active_business = api_models.Business.objects.get(owner=user, active=True)
                active_business.active = False
                active_business.save()
            except api_models.Business.DoesNotExist:
                pass #No active business found, do nothing


            api_models.Business.objects.create(
                owner=user,
                name=name,
                country=country,
                state=state,
                city=city,
                currency=currency,
                active=True,
            )
            
            return Response({"message": "Business created successfully"}, status=status.HTTP_201_CREATED)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": f"Error creating business: {e}"}, status=status.HTTP_400_BAD_REQUEST)

class InvoiceListView(generics.ListAPIView):
    serializer_class = api_serializer.InvoiceSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        try:
            business_id = self.kwargs['business_id']
            business = api_models.Business.objects.get(id=business_id)

            invoices = api_models.Invoice.objects.filter(business=business)

            return invoices
        except api_models.Business.DoesNotExist:
            return Response({"error": "Business not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": f"Error retrieving invoices: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class InvoiceCreateView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['user', 'title', 'description', 'customer_name',],
            properties={
                'user_id': openapi.Schema(type=openapi.TYPE_INTEGER, description='User ID'),
                'title': openapi.Schema(type=openapi.TYPE_STRING, description='Invoice title'),
                'description': openapi.Schema(type=openapi.TYPE_STRING, description='Invoice description'),
                'customer_name': openapi.Schema(type=openapi.TYPE_STRING, description='Customer name'),
                'date_due': openapi.Schema(type=openapi.TYPE_STRING, description='Date due'),
            }
        ),
        operation_description="Create a new invoice for a user"
    )

    def post(self, request):
        # Get data from request
        user_id = request.data.get('user_id')
        title = request.data.get('title')
        description = request.data.get('description')
        customer_name = request.data.get('customer_name')
        date_due = request.data.get('date_due')

        try:
            # Get the user instance
            user = User.objects.get(id=user_id)
            # Get the business instance associated with the user
            business = api_models.Business.objects.get(owner=user, active=True)
            customer = api_models.Customer.objects.get(full_name=customer_name, business=business)

            # Create the invoice
            invoice = api_models.Invoice(
                owner=user,
                business=business,
                title=title,
                description=description,
                customer=customer,
                date_due=date_due,
            )

            invoice.save()

            return Response({"message": f"{invoice.Uid}"}, status=status.HTTP_201_CREATED)

        except User.DoesNotExist:
            return Response(
                {"error": "User not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except api_models.Business.DoesNotExist:
            return Response(
                {"error": "Business not found for this user"}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except api_models.Customer.DoesNotExist:
            return Response(
                {"error": "Customer not found for this business"}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    
class InvoiceView(generics.RetrieveAPIView):
    serializer_class = api_serializer.InvoiceSerializer
    permission_classes = [AllowAny]

    def get_object(self):
        try:
            invoice_id = self.kwargs['Uid']
            invoice = api_models.Invoice.objects.get(Uid=invoice_id)
            return invoice
        except api_models.Invoice.DoesNotExist:
            return Response({"error": "Invoice not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": f"Error retrieving invoice: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class InvoiceDeleteView(generics.DestroyAPIView):
    serializer_class = api_serializer.InvoiceSerializer
    permission_classes = [AllowAny] #Corrected missing brackets

    def get_object(self):
        try:
            invoice_id = self.kwargs['Uid']
            user_id = self.kwargs['id']
            user = User.objects.get(id=user_id)
            owner = api_models.Business.objects.get(owner=user, active=True) #More efficient to use get instead of filter.first()
            invoice = api_models.Invoice.objects.get(Uid=invoice_id, business=owner)
            self.check_object_permissions(self.request, invoice) #Add permission check
            return invoice
        except (api_models.Invoice.DoesNotExist, api_models.Business.DoesNotExist, User.DoesNotExist):
            return Response({"error": "Invoice not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
             return Response({"error": f"Error retrieving invoice: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


    def delete(self, request, *args, **kwargs):
        invoice = self.get_object()
        invoice.delete()
        return Response({"message": "Deleted successfully"}, status=status.HTTP_200_OK)

    
class InvoiceUpdateView(APIView):
    permission_classes = [AllowAny]

    def put(self, request):
        try:
            Uid = request.data["Uid"]
            invoice_instance = api_models.Invoice.objects.get(Uid=Uid)

            user_id = request.data["user_id"]
            title = request.data["title"]
            description = request.data["description"]
            customer_name = request.data["customer"]
            date_due = request.data["date_due"]
            discount = request.data["discount"]
            is_recurring = request.data["is_recurring"]
            _status = request.data["status"]

            user = User.objects.get(id=user_id)
            business = api_models.Business.objects.get(owner=user, active=True)
            
            customer = api_models.Customer.objects.get(full_name=customer_name, business=business)

            invoice_instance.title = title
            invoice_instance.description = description
            invoice_instance.customer = customer
            invoice_instance.date_due = date_due
            invoice_instance.discount = discount
            invoice_instance.is_recurring = is_recurring
            invoice_instance.status = _status

            invoice_instance.save()
            return Response({"message": "Invoice updated successfully"}, status=status.HTTP_200_OK)
        except api_models.Invoice.DoesNotExist:
            return Response({"error": "Invoice not found"}, status=status.HTTP_404_NOT_FOUND)
        except (User.DoesNotExist, api_models.Business.DoesNotExist, api_models.Customer.DoesNotExist):
            return Response({"error": "Related object not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": f"Error updating invoice: {e}"}, status=status.HTTP_400_BAD_REQUEST)

    
class CategoryListView(generics.ListAPIView):
    serializer_class = api_serializer.CategorySerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        try:
            user_id = self.kwargs['user_id']
            user = User.objects.get(id=user_id)
            business = api_models.Business.objects.get(owner=user, active=True)
            categories = api_models.Category.objects.filter(business=business)
            return categories
        except (User.DoesNotExist, api_models.Business.DoesNotExist):
            return Response({"error": "Business not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": f"Error retrieving categories: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class CategoryCreateView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['user_id', 'name'],
            properties={
                'user_id': openapi.Schema(type=openapi.TYPE_INTEGER, description='User ID'),
                'name': openapi.Schema(type=openapi.TYPE_STRING, description='Category name'),
            }
        ),
        operation_description="Create a new category for a user"
    )

    def post(self, request, *args, **kwargs):
        try:
            user_id = request.data["user_id"]
            name = request.data["name"]
            user = User.objects.get(id=user_id)
            business = api_models.Business.objects.get(owner=user, active=True)

            api_models.Category.objects.create(
                name=name, 
                business=business
            )

            return Response({"message": "Category created successfully"}, status=status.HTTP_201_CREATED)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)
        except api_models.Business.DoesNotExist:
            return Response({"error": "Business not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": f"Error creating category: {e}"}, status=status.HTTP_400_BAD_REQUEST)

class CategoryView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = api_serializer.CategorySerializer
    permission_classes = [AllowAny]

    def get_object(self):
        try:
            user_id = self.kwargs['user_id']
            user = User.objects.get(id=user_id)
            business = api_models.Business.objects.get(owner=user, active=True)
            category_name = self.kwargs['name']
            category = api_models.Category.objects.get(name=category_name, business=business)
            return category
        except (User.DoesNotExist, api_models.Business.DoesNotExist, api_models.Category.DoesNotExist):
            return Response({"error": "Category not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": f"Error retrieving category: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def update(self, request, *args, **kwargs):
        try:
            category_instance = self.get_object()
            name = request.data["name"]
            category_instance.name = name
            category_instance.save()
            return Response({"message": "Category updated successfully"}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": f"Error updating category: {e}"}, status=status.HTTP_400_BAD_REQUEST)

class CustomerListView(generics.ListAPIView):
    serializer_class = api_serializer.CustomerSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        try:
            user_id = self.kwargs['user_id']
            user = User.objects.get(id=user_id)
            business = api_models.Business.objects.get(owner=user, active=True)
            customers = api_models.Customer.objects.filter(business=business)
            return customers
        except (User.DoesNotExist, api_models.Business.DoesNotExist):
            return Response({"error": "Business not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": f"Error retrieving customers: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class CustomerCreateView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['user_id', 'full_name', 'email', 'phone_number'],
            properties={
                'user_id': openapi.Schema(type=openapi.TYPE_INTEGER, description='User ID'),
                'full_name': openapi.Schema(type=openapi.TYPE_STRING, description='Customer full name'),
                'email': openapi.Schema(type=openapi.TYPE_STRING, description='Customer email'),
                'phone_number': openapi.Schema(type=openapi.TYPE_STRING, description='Customer phone number'),
            }
        ),
        operation_description="Create a new customer for a user"
    )

    def post(self, request, *args, **kwargs):
        try:
            full_name = request.data["full_name"]
            email = request.data["email"]
            phone_number = request.data["phone_number"]
            user_id = request.data["user_id"]
            user = User.objects.get(id=user_id)
            business = api_models.Business.objects.get(owner=user, active=True)

            api_models.Customer.objects.create(
                full_name=full_name, 
                email=email, 
                phone_number=phone_number, 
                business=business
            )

            return Response({"message": "Customer created successfully"}, status=status.HTTP_201_CREATED)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)
        except api_models.Business.DoesNotExist:
            return Response({"error": "Business not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": f"Error creating customer: {e}"}, status=status.HTTP_400_BAD_REQUEST)

class CustomerView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = api_serializer.CustomerSerializer
    permission_classes = [AllowAny]

    def get_object(self):
        try:
            customer_id = self.kwargs['id']
            customer = api_models.Customer.objects.get(id=customer_id)
            return customer
        except api_models.Customer.DoesNotExist:
            return Response({"error": "Customer not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": f"Error retrieving customer: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def update(self, request, *args, **kwargs):
        try:
            customer_instance = self.get_object()
            full_name = request.data["full_name"]
            email = request.data["email"]
            phone_number = request.data["phone_number"]

            customer_instance.full_name = full_name
            customer_instance.email = email
            customer_instance.phone_number = phone_number

            customer_instance.save()

            return Response({"message": "Customer updated successfully"}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": f"Error updating customer: {e}"}, status=status.HTTP_400_BAD_REQUEST)
    
class CustomerListView(generics.ListAPIView):
    serializer_class = api_serializer.CustomerSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        try:
            user_id = self.kwargs['user_id']
            user = User.objects.get(id=user_id)
            business = api_models.Business.objects.get(owner=user, active=True)
            customers = api_models.Customer.objects.filter(business=business)
            return customers
        except (User.DoesNotExist, api_models.Business.DoesNotExist):
            return Response({"error": "Business not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": f"Error retrieving customers: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ProductListView(generics.ListAPIView):
    serializer_class = api_serializer.ProductSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        try:
            user_id = self.kwargs['user_id']
            user = User.objects.get(id=user_id)
            business = api_models.Business.objects.get(owner=user)
            products = api_models.Product.objects.filter(owner=business)
            return products
        except (User.DoesNotExist, api_models.Business.DoesNotExist):
            return Response({"error": "Business not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": f"Error retrieving products: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ProductCreateView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(   
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['user_id', 'name', 'category', 'price',],
            properties={
                'user_id': openapi.Schema(type=openapi.TYPE_INTEGER, description='User ID'),
                'name': openapi.Schema(type=openapi.TYPE_STRING, description='Product name'),
                'category': openapi.Schema(type=openapi.TYPE_STRING, description='Product category'),
                'price': openapi.Schema(type=openapi.TYPE_NUMBER, description='Product price'),
                'image': openapi.Schema(type=openapi.TYPE_STRING, description='Product image', nullable=True),  # Made image optional
            }
        ),
        operation_description="Create a new product for a user"
    )

    def post(self, request, *args, **kwargs):
        try:
            name = request.data["name"]
            category = request.data["category"]
            price = request.data["price"]
            user_id = request.data["user_id"]
            image = request.data.get("image", None)  # Changed to use get for optional image

            user = User.objects.get(id=user_id)

            business = api_models.Business.objects.get(owner=user, active=True)
            category = api_models.Category.objects.get(name=category, business=business)

            product = api_models.Product.objects.create(name=name, category=category, price=price, owner=business)

            if image:
                product.image = image

            product.save()

            return Response({"message": "Product created successfully"}, status=status.HTTP_201_CREATED)
        except (User.DoesNotExist, api_models.Business.DoesNotExist, api_models.Category.DoesNotExist):
            return Response({"error": "Related object not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            print(e)
            return Response({"error": f"Error creating product: {e}"}, status=status.HTTP_400_BAD_REQUEST)

class ProductView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = api_serializer.ProductSerializer
    permission_classes = [AllowAny]

    def get_object(self):
        try:
            user_id = self.kwargs['user_id']
            product_id = self.kwargs['id']
            user = User.objects.get(id=user_id)
            business = api_models.Business.objects.get(owner=user, active=True)
            product = api_models.Product.objects.get(id=product_id, owner=business)
            return product
        except (User.DoesNotExist, api_models.Business.DoesNotExist, api_models.Product.DoesNotExist):
            return Response({"error": "Product not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": f"Error retrieving product: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def update(self, request, *args, **kwargs):
        try:
            product_instance = self.get_object()

            name = request.data["name"]
            category_name = request.data["category"]
            price = request.data["price"]
            image = request.data.get("image", None)

            business = product_instance.owner
            category = api_models.Category.objects.get(name=category_name, business=business)

            product_instance.name = name
            product_instance.category = category
            product_instance.price = price

            if image:
                product_instance.image = image

            product_instance.save()
            return Response({"message": "Product updated successfully"}, status=status.HTTP_200_OK)
        except (api_models.Category.DoesNotExist) as e:
            return Response({"error": "Category not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": f"Error updating product: {e}"}, status=status.HTTP_400_BAD_REQUEST)
    
class InvoiceItemListView(generics.ListAPIView):
    serializer_class = api_serializer.InvoiceItemSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        try:
            invoice_id = self.kwargs['invoice_id']
            invoice = api_models.Invoice.objects.get(Uid=invoice_id)
            invoice_items = api_models.Invoice_item.objects.filter(invoice=invoice)

            total_price = 0

            for item in invoice_items:
                total_price += item.price()
                invoice.total = total_price
                invoice.save()

            return invoice_items
        except api_models.Invoice.DoesNotExist:
            return Response({"error": "Invoice not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": f"Error retrieving invoice items: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
class InvoiceItemCreateView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['user_id', 'invoice_Uid', 'product_id', 'quantity'],
            properties={
                'user_id': openapi.Schema(type=openapi.TYPE_INTEGER, description='User ID'),
                'invoice_Uid': openapi.Schema(type=openapi.TYPE_STRING, description='Invoice UID'),
                'product_id': openapi.Schema(type=openapi.TYPE_INTEGER, description='Product ID'),
                'quantity': openapi.Schema(type=openapi.TYPE_INTEGER, description='Quantity'),
            }
        ),
        operation_description="Create a new invoice item for a user"
    )

    def post(self, request, *args, **kwargs):
        try:
            user_id = request.data["user_id"]
            invoice_Uid = request.data["invoice_Uid"]
            product_id = request.data["product_id"]
            quantity = request.data["quantity"]

            user = User.objects.get(id=user_id)
            business = api_models.Business.objects.get(owner=user, active=True)
            invoice = api_models.Invoice.objects.get(Uid=invoice_Uid)  # Using Uid field instead of id
            product = api_models.Product.objects.get(id=product_id, owner=business)

            api_models.Invoice_item.objects.create(
                invoice=invoice,
                product=product,
                quantity=quantity
            )
            
            return Response({"message": "Invoice item created successfully"}, status=status.HTTP_201_CREATED)
            
        except ValueError as e:
            return Response({"error": "Invalid input data. Please ensure product_id and quantity are valid numbers."}, status=status.HTTP_400_BAD_REQUEST)

        except (User.DoesNotExist, api_models.Business.DoesNotExist, api_models.Invoice.DoesNotExist, api_models.Product.DoesNotExist) as e:
            return Response( {"error": str(e)}, status=status.HTTP_404_NOT_FOUND )
        except Exception as e:
            return Response({"error": f"Error creating invoice item: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class InvoiceItemView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = api_serializer.InvoiceItemSerializer
    permission_classes = [AllowAny]

    def get_object(self):
        try:
            invoice_item_id = self.kwargs['id']
            invoice_item = api_models.Invoice_item.objects.get(id=invoice_item_id)
            return invoice_item
        except api_models.Invoice_item.DoesNotExist:
            return Response({"error": "Invoice item not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": f"Error retrieving invoice item: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def update(self, request, *args, **kwargs):
        invoice_item_instance = self.get_object()
        quantity = request.data["quantity"]
        user_id = request.data["user_id"]
        product_id = request.data["product_id"]
        user = User.objects.get(id=user_id)
        business = api_models.Business.objects.get(owner=user, active=True)
        product = api_models.Product.objects.get(id=product_id, owner=business)
        invoice_item_instance.quantity = quantity
        invoice_item_instance.product = product
        invoice_item_instance.save()

        return Response({"message": "Invoice item updated successfully"}, status=status.HTTP_200_OK)
    

class CategoryListView(generics.ListAPIView):
    serializer_class = api_serializer.CategorySerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        user_id = self.kwargs['user_id']
        user = User.objects.get(id=user_id)
        business = api_models.Business.objects.get(owner=user, active=True)
        return api_models.Category.objects.filter(business=business)

class CategoryCreateView(generics.CreateAPIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['user_id', 'name'],
            properties={
                'user_id': openapi.Schema(type=openapi.TYPE_INTEGER, description='User ID'),
                'name': openapi.Schema(type=openapi.TYPE_STRING, description='Category Name'),
            }
        ),
        operation_description="Create a new category for a business"
    )
    
    def post(self, request, *args, **kwargs):
        user_id = request.data["user_id"]
        name = request.data["name"]

        user = User.objects.get(id=user_id)
        business = api_models.Business.objects.get(owner=user, active=True)

        api_models.Category.objects.create(business=business, name=name)
        return Response({"message": "Category created successfully"}, status=status.HTTP_201_CREATED)

class AdminView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = api_serializer.InvoiceAdminSerializer

    def get_queryset(self):
        user_id = self.kwargs['user_id']
        user = User.objects.get(id=user_id)
        business = api_models.Business.objects.get(owner=user, active=True)

        invoices = api_models.Invoice.objects.filter(business=business)
        customers = api_models.Customer.objects.filter(business=business)
        products = api_models.Product.objects.filter(owner=business)

        for invoice in invoices:
            invoice.set_unpaid()

        unpaid_invoices = api_models.Invoice.objects.filter(business=business, status="unpaid")
        draft_invoices = api_models.Invoice.objects.filter(business=business, status="draft")
        paid_invoices = api_models.Invoice.objects.filter(business=business, status="paid")
        pending_invoices = api_models.Invoice.objects.filter(business=business, status="pending")

        return [{
            "invoices": invoices.count(),
            "draft_invoices": draft_invoices.count(),
            "paid_invoices": paid_invoices.count(),
            "unpaid_invoices": unpaid_invoices.count(),
            "pending_invoices": pending_invoices.count(),
            "customers": customers.count(),
            "products": products.count(),
        }]
    
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)

        return Response(serializer.data, status=status.HTTP_200_OK)
    
class DashboardStatsView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = api_serializer.DashboardStatsSerializer

    def get_queryset(self):
        user_id = self.kwargs["user_id"]
        user = User.objects.get(id=user_id)
        business = api_models.Business.objects.get(owner=user, active=True)

        invoiceData = api_models.Invoice.objects.filter(business=business).annotate(month=ExtractMonth("date_created")).values("month").annotate(invoices=Count("id")).values("month", "invoices")

        return invoiceData

class InvoiceStatsView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = api_serializer.InvoiceStatsSerializer

    def get_queryset(self):
        user_id = self.kwargs["user_id"]
        user = User.objects.get(id=user_id)
        business = api_models.Business.objects.get(owner=user, active=True)

        invoiceData = (
            api_models.Invoice.objects.filter(business=business).annotate(month=ExtractMonth("date_created")).values("month")
            .annotate(
                invoices=Count("id"),
                paid=Count('id', filter=Q(status='paid'))
            )
            .values("month", "invoices", "paid")
        )

        return invoiceData
    
class ReceiptListView(generics.ListAPIView):
    serializer_class = api_serializer.ReceiptSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        user_id = self.kwargs['user_id']
        user = User.objects.get(id=user_id)
        business = api_models.Business.objects.get(owner=user, active=True)
        receipts = api_models.Receipt.objects.filter(business=business)
        return receipts

class CategoryCreateView(generics.CreateAPIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['user_id', 'name'],
            properties={
                'user_id': openapi.Schema(type=openapi.TYPE_INTEGER, description='User ID'),
                'name': openapi.Schema(type=openapi.TYPE_STRING, description='Category Name'),
            }
        ),
        operation_description="Create a new category for a business"
    )
    
    def post(self, request, *args, **kwargs):
        user_id = request.data["user_id"]
        name = request.data["name"]

        user = User.objects.get(id=user_id)
        business = api_models.Business.objects.get(owner=user, active=True)

        api_models.Category.objects.create(business=business, name=name)
        return Response({"message": "Category created successfully"}, status=status.HTTP_201_CREATED)

class AdminView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = api_serializer.InvoiceAdminSerializer

    def get_queryset(self):
        user_id = self.kwargs['user_id']
        user = User.objects.get(id=user_id)
        business = api_models.Business.objects.get(owner=user, active=True)

        invoices = api_models.Invoice.objects.filter(business=business)
        customers = api_models.Customer.objects.filter(business=business)
        products = api_models.Product.objects.filter(owner=business)

        for invoice in invoices:
            invoice.set_unpaid()

        unpaid_invoices = api_models.Invoice.objects.filter(business=business, status="unpaid")
        draft_invoices = api_models.Invoice.objects.filter(business=business, status="draft")
        paid_invoices = api_models.Invoice.objects.filter(business=business, status="paid")
        pending_invoices = api_models.Invoice.objects.filter(business=business, status="pending")

        return [{
            "invoices": invoices.count(),
            "draft_invoices": draft_invoices.count(),
            "paid_invoices": paid_invoices.count(),
            "unpaid_invoices": unpaid_invoices.count(),
            "pending_invoices": pending_invoices.count(),
            "customers": customers.count(),
            "products": products.count(),
        }]
    
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)

        return Response(serializer.data, status=status.HTTP_200_OK)
    
class DashboardStatsView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = api_serializer.DashboardStatsSerializer

    def get_queryset(self):
        user_id = self.kwargs["user_id"]
        user = User.objects.get(id=user_id)
        business = api_models.Business.objects.get(owner=user, active=True)

        invoiceData = api_models.Invoice.objects.filter(business=business).annotate(month=ExtractMonth("date_created")).values("month").annotate(invoices=Count("id")).values("month", "invoices")

        return invoiceData

class InvoiceStatsView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = api_serializer.InvoiceStatsSerializer

    def get_queryset(self):
        user_id = self.kwargs["user_id"]
        user = User.objects.get(id=user_id)
        business = api_models.Business.objects.get(owner=user, active=True)

        invoiceData = (
            api_models.Invoice.objects.filter(business=business).annotate(month=ExtractMonth("date_created")).values("month")
            .annotate(
                invoices=Count("id"),
                paid=Count('id', filter=Q(status='paid'))
            )
            .values("month", "invoices", "paid")
        )

        return invoiceData
    
class ReceiptGetView(generics.RetrieveAPIView):
    serializer_class = api_serializer.ReceiptSerializer
    permission_classes = [AllowAny]

    def get_object(self):
        user_id = self.kwargs['user_id']
        Uid = self.kwargs['Uid']

        try:
            user = User.objects.get(id=user_id)
            business = api_models.Business.objects.get(owner=user, active=True)
            receipt = api_models.Receipt.objects.get(business=business, Uid=Uid)
            return receipt
        except (User.DoesNotExist, api_models.Business.DoesNotExist, api_models.Receipt.DoesNotExist):
            return Response({"error": "Receipt not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": f"Error retrieving receipt: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



# class InvoiceStatsView(generics.ListAPIView):
#     permission_classes = [AllowAny]
#     serializer_class

    permission_classes = [AllowAny]

    def get_queryset(self):
        user_id = self.kwargs['user_id']
        user = User.objects.get(id=user_id)
        business = api_models.Business.objects.get(owner=user)
        return api_models.Category.objects.filter(business=business)

class CategoryCreateView(generics.CreateAPIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['user_id', 'name'],
            properties={
                'user_id': openapi.Schema(type=openapi.TYPE_INTEGER, description='User ID'),
                'name': openapi.Schema(type=openapi.TYPE_STRING, description='Category Name'),
            }
        ),
        operation_description="Create a new category for a business"
    )
    
    def post(self, request, *args, **kwargs):
        user_id = request.data["user_id"]
        name = request.data["name"]

        user = User.objects.get(id=user_id)
        business = api_models.Business.objects.get(owner=user)

        api_models.Category.objects.create(business=business, name=name)
        return Response({"message": "Category created successfully"}, status=status.HTTP_201_CREATED)

class AdminView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = api_serializer.InvoiceAdminSerializer

    def get_queryset(self):
        user_id = self.kwargs['user_id']
        user = User.objects.get(id=user_id)
        business = api_models.Business.objects.get(owner=user)

        invoices = api_models.Invoice.objects.filter(business=business)
        customers = api_models.Customer.objects.filter(business=business)
        products = api_models.Product.objects.filter(owner=business)

        for invoice in invoices:
            invoice.set_unpaid()

        unpaid_invoices = api_models.Invoice.objects.filter(business=business, status="unpaid")
        draft_invoices = api_models.Invoice.objects.filter(business=business, status="draft")
        paid_invoices = api_models.Invoice.objects.filter(business=business, status="paid")
        pending_invoices = api_models.Invoice.objects.filter(business=business, status="pending")

        return [{
            "invoices": invoices.count(),
            "draft_invoices": draft_invoices.count(),
            "paid_invoices": paid_invoices.count(),
            "unpaid_invoices": unpaid_invoices.count(),
            "pending_invoices": pending_invoices.count(),
            "customers": customers.count(),
            "products": products.count(),
        }]
    
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)

        return Response(serializer.data, status=status.HTTP_200_OK)
    
class DashboardStatsView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = api_serializer.DashboardStatsSerializer

    def get_queryset(self):
        user_id = self.kwargs["user_id"]
        user = User.objects.get(id=user_id)
        business = api_models.Business.objects.get(owner=user)

        invoiceData = api_models.Invoice.objects.filter(business=business).annotate(month=ExtractMonth("date_created")).values("month").annotate(invoices=Count("id")).values("month", "invoices")

        return invoiceData

class InvoiceStatsView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = api_serializer.InvoiceStatsSerializer

    def get_queryset(self):
        user_id = self.kwargs["user_id"]
        user = User.objects.get(id=user_id)
        business = api_models.Business.objects.get(owner=user)

        invoiceData = (
            api_models.Invoice.objects.filter(business=business).annotate(month=ExtractMonth("date_created")).values("month")
            .annotate(
                invoices=Count("id"),
                paid=Count('id', filter=Q(status='paid'))
            )
            .values("month", "invoices", "paid")
        )

        return invoiceData
    
class ReceiptListView(generics.ListAPIView):
    serializer_class = api_serializer.ReceiptSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        user_id = self.kwargs['user_id']
        user = User.objects.get(id=user_id)
        business = api_models.Business.objects.get(owner=user)
        receipts = api_models.Receipt.objects.filter(business=business)
        return receipts


# class InvoiceStatsView(generics.ListAPIView):
#     permission_classes = [AllowAny]
#     serializer_class

    permission_classes = [AllowAny]

    def get_queryset(self):
        user_id = self.kwargs['user_id']
        user = User.objects.get(id=user_id)
        business = api_models.Business.objects.get(owner=user)
        return api_models.Category.objects.filter(business=business)

class CategoryCreateView(generics.CreateAPIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['user_id', 'name'],
            properties={
                'user_id': openapi.Schema(type=openapi.TYPE_INTEGER, description='User ID'),
                'name': openapi.Schema(type=openapi.TYPE_STRING, description='Category Name'),
            }
        ),
        operation_description="Create a new category for a business"
    )
    
    def post(self, request, *args, **kwargs):
        user_id = request.data["user_id"]
        name = request.data["name"]

        user = User.objects.get(id=user_id)
        business = api_models.Business.objects.get(owner=user)

        api_models.Category.objects.create(business=business, name=name)
        return Response({"message": "Category created successfully"}, status=status.HTTP_201_CREATED)

class AdminView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = api_serializer.InvoiceAdminSerializer

    def get_queryset(self):
        user_id = self.kwargs['user_id']
        user = User.objects.get(id=user_id)
        business = api_models.Business.objects.get(owner=user)

        invoices = api_models.Invoice.objects.filter(business=business)
        customers = api_models.Customer.objects.filter(business=business)
        products = api_models.Product.objects.filter(owner=business)

        for invoice in invoices:
            invoice.set_unpaid()

        unpaid_invoices = api_models.Invoice.objects.filter(business=business, status="unpaid")
        draft_invoices = api_models.Invoice.objects.filter(business=business, status="draft")
        paid_invoices = api_models.Invoice.objects.filter(business=business, status="paid")
        pending_invoices = api_models.Invoice.objects.filter(business=business, status="pending")

        return [{
            "invoices": invoices.count(),
            "draft_invoices": draft_invoices.count(),
            "paid_invoices": paid_invoices.count(),
            "unpaid_invoices": unpaid_invoices.count(),
            "pending_invoices": pending_invoices.count(),
            "customers": customers.count(),
            "products": products.count(),
        }]
    
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)

        return Response(serializer.data, status=status.HTTP_200_OK)
    
class DashboardStatsView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = api_serializer.DashboardStatsSerializer

    def get_queryset(self):
        user_id = self.kwargs["user_id"]
        user = User.objects.get(id=user_id)
        business = api_models.Business.objects.get(owner=user)

        invoiceData = api_models.Invoice.objects.filter(business=business).annotate(month=ExtractMonth("date_created")).values("month").annotate(invoices=Count("id")).values("month", "invoices")

        return invoiceData

class InvoiceStatsView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = api_serializer.InvoiceStatsSerializer

    def get_queryset(self):
        user_id = self.kwargs["user_id"]
        user = User.objects.get(id=user_id)
        business = api_models.Business.objects.get(owner=user)

        invoiceData = (
            api_models.Invoice.objects.filter(business=business).annotate(month=ExtractMonth("date_created")).values("month")
            .annotate(
                invoices=Count("id"),
                paid=Count('id', filter=Q(status='paid'))
            )
            .values("month", "invoices", "paid")
        )

        return invoiceData
    
class ReceiptListView(generics.ListAPIView):
    serializer_class = api_serializer.ReceiptSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        user_id = self.kwargs['user_id']
        user = User.objects.get(id=user_id)
        business = api_models.Business.objects.get(owner=user)
        receipts = api_models.Receipt.objects.filter(business=business)
        return receipts
