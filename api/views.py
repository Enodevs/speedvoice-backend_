from rest_framework_simplejwt.views import TokenObtainPairView
from api import serializer as api_serializer
from rest_framework.decorators import APIView
from rest_framework import generics
from api import models as api_models
from userauth.models import User
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import status
from rest_framework.response import Response
from django.db.models.functions import ExtractMonth
from django.db.models import Count, Sum, Q
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import NotFound, ValidationError, APIException

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema

import secrets
import os
import environ
from django.core.cache import cache

env = environ.Env()

class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = api_serializer.MyTokenObtainPairSerializer
    permission_classes = [AllowAny]

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

class UserAPIView(APIView):
    """
    API to retrieve or update user details.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        email = request.query_params.get('email')
        if not email:
            return Response({"error": "Email parameter is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
            serializer = api_serializer.UserSerializer(user)
            return Response(serializer.data)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

    def put(self, request):
        email = request.query_params.get('email')
        
        if not email:
            return Response({"error": "Email parameter is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
            

            for field, value in request.data.items():
                if field in ['fullname', 'email', 'customer_id', 'product_type', 'hasAccess']:
                    setattr(user, field, value)

            user.save()  # Save the updated user object

            return Response({"message": "Updated successfully"}, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": f"Error updating user: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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

            business = api_models.Business.objects.filter(owner=user).first()
            active_business_id = business.id if business else None

            return Response({
                "auth_token": auth_token.key,
                "user_id": user.id,
                "email": user.email,
                "name": user.fullname,
                "active_business": active_business_id,
                "customer_id": user.customer_id,
                "hasAccess": user.hasAccess,
                "product_type": user.product_type,
            }, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class BusinessGetView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = api_serializer.BusinessSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        try:
            business_id = self.kwargs['business_id']
            return api_models.Business.objects.get(id=business_id)
        except api_models.Business.DoesNotExist:
            raise NotFound("Business not found")
        except Exception as e:
            raise APIException(f"Error retrieving business: {str(e)}")
    
    def update(self, request, *args, **kwargs):
        try:
            business_instance = self.get_object()
            
            name = request.data.get('name')
            description = request.data.get('description')
            country = request.data.get('country')
            currency = request.data.get('currency')
            state = request.data.get('state')
            city = request.data.get('city')
            image = request.data.get('image', None)

            if name:
                business_instance.name = name
            if description:
                business_instance.description = description
            if country:
                business_instance.country = country
            if currency:
                business_instance.currency = currency
            if state:
                business_instance.state = state
            if city:
                business_instance.city = city
            if image:
                business_instance.image = image

            business_instance.save()

            # Create notification for business update
            api_models.Notification.objects.create(
                business=business_instance,
                title="Business updated",
                description=f'Business "{business_instance.name}" was updated',
                type="business_updated"
            )

            return Response({
                "message": "Business updated successfully",
                "data": api_serializer.BusinessSerializer(business_instance).data
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {"error": f"Error updating business: {str(e)}"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

class BusinessCreateView(APIView):
    permission_classes = [IsAuthenticated]

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

            # Check user's product plan
            if user.product_type == os.environ.get('BASIC_PLAN') and api_models.Business.objects.filter(owner=user).exists():
                latest_business = api_models.Business.objects.filter(owner=user).latest('id')
                api_models.Notification.objects.create(
                    business=latest_business,
                    title="New business creation failed",
                    description="Your attempt to create a new business has failed because of the current plan you are subscribed to, please upgrade your plan to create a new business.",
                    type="business_created"
                )

                return Response(
                    {"error": "Basic plan users can only create one business. Please upgrade your plan."}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            elif user.product_type == os.environ.get('PREMIUM_PLAN'):
                business = api_models.Business.objects.create(
                    owner=user,
                    name=name,
                    country=country,
                    state=state,
                    city=city,
                    currency=currency,
                    active=True,
                )

                business.save()

                api_models.Notification.objects.create(
                    business=business,
                    title="New business created",
                    description="A new business has been created",
                    type="business_created"
                )
                
                return Response({"message": "Business created successfully", "id": business.id}, status=status.HTTP_201_CREATED)
            elif user.product_type == os.environ.get('BASIC_PLAN') and not api_models.Business.objects.filter(owner=user).exists():
                business = api_models.Business.objects.create(
                    owner=user,
                    name=name,
                    country=country,
                    state=state,
                    city=city,
                    currency=currency,
                    active=True,
                )

                business.save()

                api_models.Notification.objects.create(
                    business=business,
                    title="New business created",
                    description="A new business has been created",
                    type="business_created"
                )
                
                return Response({"message": "Business created successfully", "id": business.id}, status=status.HTTP_201_CREATED)
            else:
                # Handle unknown or unrecognized plan
                return Response(
                    {"error": "Unknown subscription plan. Please contact support."}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": f"Error creating business: {e}"}, status=status.HTTP_400_BAD_REQUEST)

class InvoiceListView(generics.ListAPIView):
    serializer_class = api_serializer.InvoiceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        try:
            business_id = self.kwargs['business_id']
            business = api_models.Business.objects.get(id=business_id)

            # Use prefetch_related to fetch related invoice items in one query
            invoices = api_models.Invoice.objects.filter(business=business).prefetch_related('invoice_item_set')

            # Calculate totals in a single query using aggregate
            for invoice in invoices:
                total_price = api_models.Invoice_item.objects.filter(invoice=invoice).aggregate(
                    total=Sum('quantity') * Sum('product__price')
                )['total'] or 0
                
                if invoice.total != total_price:
                    invoice.total = total_price

                invoice.set_unpaid()
                invoice.save()

            return invoices
        except api_models.Business.DoesNotExist:
            return Response({"error": "Business not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": f"Error retrieving invoices: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class InvoiceCreateView(APIView):
    permission_classes = [IsAuthenticated]

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
        try:
            # Get data from request
            user_id = request.data.get('user_id')
            business_id = request.data.get('business_id')
            title = request.data.get('title')
            description = request.data.get('description')
            customer_name = request.data.get('customer_name')
            date_due = request.data.get('date_due')

            # Validate required fields
            required_fields = {'user_id', 'business_id', 'title', 'customer_name'}
            missing_fields = [field for field in required_fields if not request.data.get(field)]
            if missing_fields:
                return Response(
                    {"error": f"Missing required fields: {', '.join(missing_fields)}"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Get related objects
            try:
                user = User.objects.get(id=user_id)
                business = api_models.Business.objects.get(id=business_id)
                customer = api_models.Customer.objects.get(full_name=customer_name, business=business)
            except User.DoesNotExist:
                return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)
            except api_models.Business.DoesNotExist:
                return Response({"error": "Business not found"}, status=status.HTTP_404_NOT_FOUND)
            except api_models.Customer.DoesNotExist:
                return Response({"error": "Customer not found"}, status=status.HTTP_404_NOT_FOUND)

            # Check invoice limit for basic plan
            invoices_count = api_models.Invoice.objects.filter(owner=user).count()
            INVOICE_LIMIT = 15
            
            if invoices_count >= INVOICE_LIMIT and user.product_type == os.environ.get('BASIC_PLAN'):
                api_models.Notification.objects.create(
                    business=business,
                    title="New invoice creation failed",
                    description=f'Invoice creation for customer "{customer.full_name}" has failed due to your current plan, please upgrade your plan to create more invoices.',
                    type="invoice_creation_failed"
                )
                return Response(
                    {"error": "Maximum invoice limit reached for basic plan"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Create invoice
            invoice = api_models.Invoice(
                owner=user,
                business=business,
                title=title,
                description=description,
                customer=customer,
                date_due=date_due,
            )
            invoice.save()

            # Create notification
            api_models.Notification.objects.create(
                business=business,
                title="New invoice created",
                description=f'A new invoice has been created for customer "{customer.full_name}"',
                type="invoice_created"
            )

            return Response(
                {
                    "message": invoice.Uid,
                }, 
                status=status.HTTP_201_CREATED
            )

        except Exception as e:
            return Response(
                {"error": f"Error creating invoice: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
class InvoiceView(generics.RetrieveAPIView):
    serializer_class = api_serializer.InvoiceSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        try:
            invoice_id = self.kwargs['Uid']
            invoice = api_models.Invoice.objects.get(Uid=invoice_id)

            total_price = api_models.Invoice_item.objects.filter(invoice=invoice).aggregate(
                total=Sum('quantity') * Sum('product__price')
            )['total'] or 0
                
            if invoice.total != total_price:
                invoice.total = total_price

            invoice.set_unpaid()
            invoice.save()

            return invoice
        except api_models.Invoice.DoesNotExist:
            raise NotFound({"error": "Invoice not found"})
        except Exception as e:
            return Response({"error": f"Error retrieving invoice: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get(self, request, *args, **kwargs):
        invoice_instance = self.get_object()
        serializer = self.get_serializer(invoice_instance)
        return Response(serializer.data)

class InvoiceDeleteView(generics.DestroyAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = api_serializer.InvoiceSerializer  # Assuming you have a serializer

    def get_object(self):
        invoice_id = self.kwargs.get('Uid')
        business_id = self.kwargs.get('business_id')

        business = api_models.Business.objects.get(id=business_id)
        invoice = api_models.Invoice.objects.get(Uid=invoice_id, business=business)
        return invoice

    def perform_destroy(self, instance):
        try:
            instance = self.get_object()
            instance.delete()
        except Exception as e:
            return Response({"error": f"Error deleting invoice: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
class InvoiceUpdateView(APIView):
    permission_classes = [IsAuthenticated]

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

            business = api_models.Business.objects.get(id=user_id)
            
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

    
class CategoryListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, business_id):
        try:
            business = api_models.Business.objects.get(id=business_id)
            categories = api_models.Category.objects.filter(business=business)
            serializer = api_serializer.CategorySerializer(categories, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except (api_models.Business.DoesNotExist, api_models.Business.DoesNotExist):
            return Response({"error": "Business not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": f"Error retrieving categories: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class CategoryView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = api_serializer.CategorySerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        try:
            user_id = self.kwargs['business_id']
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
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        try:
            user_id = self.kwargs['business_id']
            business = api_models.Business.objects.get(id=user_id)
            customers = api_models.Customer.objects.filter(business=business)
            return customers
        except (User.DoesNotExist, api_models.Business.DoesNotExist):
            return Response({"error": "Business not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": f"Error retrieving customers: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class CustomerCreateView(APIView):
    permission_classes = [IsAuthenticated]

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
            business = api_models.Business.objects.get(id=user_id)

            customer = api_models.Customer.objects.create(
                full_name=full_name, 
                email=email, 
                phone_number=phone_number, 
                business=business
            )

            customer.save()

            api_models.Notification.objects.create(
                business=business,
                title="New customer created",
                description=f'A new customer has been created "{customer.full_name}"',
                type="customer_added"
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
    permission_classes = [IsAuthenticated]

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

class ProductListView(generics.ListAPIView):
    serializer_class = api_serializer.ProductSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        try:
            user_id = self.kwargs['business_id']
            business = api_models.Business.objects.get(id=user_id)
            products = api_models.Product.objects.filter(owner=business)
            return products
        except (User.DoesNotExist, api_models.Business.DoesNotExist):
            return Response({"error": "Business not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": f"Error retrieving products: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ProductCreateView(APIView):
    permission_classes = [IsAuthenticated]

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

            business = api_models.Business.objects.get(id=user_id)
            category = api_models.Category.objects.get(name=category, business=business)

            product = api_models.Product.objects.create(name=name, category=category, price=price, owner=business)

            if image:
                product.image = image

            product.save()

            api_models.Notification.objects.create(
                business=business,
                title="New product created",
                description=f'A new product has been created "{product.name}"',
                type="product_added"
            )

            return Response({"message": "Product created successfully"}, status=status.HTTP_201_CREATED)
        except (User.DoesNotExist, api_models.Business.DoesNotExist, api_models.Category.DoesNotExist):
            return Response({"error": "Related object not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            print(e)
            return Response({"error": f"Error creating product: {e}"}, status=status.HTTP_400_BAD_REQUEST)

class ProductView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = api_serializer.ProductSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        try:
            user_id = self.kwargs['business_id']
            product_id = self.kwargs['id']
            business = api_models.Business.objects.get(id=user_id)
            product = api_models.Product.objects.get(id=product_id, owner=business)
            return product
        except (User.DoesNotExist, api_models.Business.DoesNotExist, api_models.Product.DoesNotExist):
            raise NotFound({"error": "Product not found"})
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
        
    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            instance.delete()
            return Response({"message": "Product deleted successfully"}, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            return Response({"error": f"Error deleting product: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
class InvoiceItemListView(generics.ListAPIView):
    serializer_class = api_serializer.InvoiceItemSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        try:
            invoice_id = self.kwargs['invoice_id']
            invoice = api_models.Invoice.objects.get(Uid=invoice_id)
            invoice_items = api_models.Invoice_item.objects.filter(invoice=invoice)

            total_price = api_models.Invoice_item.objects.filter(invoice=invoice).aggregate(
                total=Sum('quantity') * Sum('product__price')
            )['total'] or 0

            if invoice.total != total_price:
                invoice.total = total_price
                invoice.save()

            return invoice_items
        except api_models.Invoice.DoesNotExist:
            return Response({"error": "Invoice not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": f"Error retrieving invoice items: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
class InvoiceItemCreateView(APIView):
    permission_classes = [IsAuthenticated]

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

            business = api_models.Business.objects.get(id=user_id)
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
    permission_classes = [IsAuthenticated]

    def get_object(self):
        try:
            invoice_item_id = self.kwargs['id']
            invoice_id = self.kwargs['invoice_id']
            invoice = api_models.Invoice.objects.get(Uid=invoice_id)
            invoice_item = api_models.Invoice_item.objects.get(id=invoice_item_id, invoice=invoice)
            return invoice_item
        except api_models.Invoice_item.DoesNotExist:
            return Response({"error": "Invoice item not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": f"Error retrieving invoice item: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def update(self, request, *args, **kwargs):
        try:
            invoice_item_instance = self.get_object()
            
            # Validate quantity exists in request data
            if "quantity" not in request.data:
                return Response(
                    {"error": "Quantity is required"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            quantity = request.data["quantity"]
            
            # Validate quantity is positive integer
            try:
                quantity = int(quantity)
                if quantity <= 0:
                    raise ValueError
            except (TypeError, ValueError):
                return Response(
                    {"error": "Quantity must be a positive integer"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            invoice_item_instance.quantity = quantity
            invoice_item_instance.save()

            return Response(
                {"message": "Invoice item updated successfully"}, 
                status=status.HTTP_200_OK
            )
            
        except api_models.Invoice_item.DoesNotExist:
            return Response(
                {"error": "Invoice item not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": f"Error updating invoice item: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class AdminView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = api_serializer.InvoiceAdminSerializer

    def get_queryset(self):
        user_id = self.kwargs['business_id']
        business = api_models.Business.objects.get(id=user_id)

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
    permission_classes = [IsAuthenticated]
    serializer_class = api_serializer.DashboardStatsSerializer

    def get_queryset(self):
        user_id = self.kwargs["business_id"]
        business = api_models.Business.objects.get(id=user_id)

        invoiceData = api_models.Invoice.objects.filter(business=business).annotate(month=ExtractMonth("date_created")).values("month").annotate(invoices=Count("id")).values("month", "invoices")

        return invoiceData

class InvoiceStatsView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = api_serializer.InvoiceStatsSerializer

    def get_queryset(self):
        user_id = self.kwargs["business_id"]
        business = api_models.Business.objects.get(id=user_id)

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
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user_id = self.kwargs['business_id']
        business = api_models.Business.objects.get(id=user_id)
        receipts = api_models.Receipt.objects.filter(business=business)
        return receipts

class ReceiptGetView(generics.RetrieveAPIView):
    serializer_class = api_serializer.ReceiptSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        user_id = self.kwargs['business_id']
        Uid = self.kwargs['Uid']

        try:
            business = api_models.Business.objects.get(id=user_id)
            receipt = api_models.Receipt.objects.get(business=business, Uid=Uid)
            return receipt
        except (User.DoesNotExist, api_models.Business.DoesNotExist, api_models.Receipt.DoesNotExist):
            return Response({"error": "Receipt not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": f"Error retrieving receipt: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class ReceiptCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        try:
            user_id = request.data['user_id']
            business_id = request.data['business_id']
            customer_id = request.data['customer_id']
            uid = request.data['uid']

            user = User.objects.get(id=user_id)
            business = api_models.Business.objects.get(id=business_id)
            customer = api_models.Customer.objects.get(id=customer_id)
            invoice = api_models.Invoice.objects.get(Uid=uid, business=business)
                
            receipt = api_models.Receipt.objects.create(
                owner=user,
                business=business,
                customer=customer,
                invoice=invoice,
            )

            receipt.save()

            api_models.Notification.objects.create(
                business=business,
                title='New receipt created',
                description="A new receipt has been created",
                type="receipt_created"
            )
                
            return Response({"Uid": receipt.Uid}, status=status.HTTP_201_CREATED)
        except api_models.Business.DoesNotExist:
            return Response({"error": "Business not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": f"Error creating receipt: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CategoryCreateView(generics.CreateAPIView):
    permission_classes = [IsAuthenticated]

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

        api_models.Notification.objects.create(
            business=business,
            title=f'New category created "{name}"',
            description="A new category has been created",
            type="category_created"
        )

        return Response({"message": "Category created successfully"}, status=status.HTTP_201_CREATED)
    
class NotificationListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                name='business_id',
                in_=openapi.IN_QUERY,
                type=openapi.TYPE_INTEGER,
                description='ID of the business'
            ),
        ],
        operation_description="List notifications for a business"
    )

    def get(self, request,):
        business_id = request.query_params.get('business_id')
        
        if business_id:
            try:
                business = api_models.Business.objects.get(id=business_id)
                notifications = api_models.Notification.objects.filter(business=business)
                serializer = api_serializer.NotificationSerializer(notifications, many=True)
                return Response(serializer.data, status=status.HTTP_200_OK)
            except api_models.Business.DoesNotExist:
                return Response({"error": "Business not found"}, status=status.HTTP_404_NOT_FOUND)
        else:
            return Response({"error": "Business ID is required"}, status=status.HTTP_400_BAD_REQUEST)

class NotificationMarkAllReadAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                name='business_id',
                in_=openapi.IN_QUERY,
                type=openapi.TYPE_INTEGER,
                description='ID of the business'
            ),
        ],
        operation_description="Mark all notifications for a business as read"
    )

    def put(self, request):
        business_id = request.query_params.get('business_id')

        if business_id:
            try:
                business = api_models.Business.objects.get(id=business_id)
                notifications = api_models.Notification.objects.filter(business=business)
                notifications.update(seen=True)
                return Response({"message": "Notifications marked as read successfully"}, status=status.HTTP_200_OK)
            except api_models.Business.DoesNotExist:
                return Response({"error": "Business not found"}, status=status.HTTP_404_NOT_FOUND)
        else:
            return Response({"error": "Business ID is required"}, status=status.HTTP_400_BAD_REQUEST)

class InvoiceAccessTokenCreateView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['email', 'Uid'],
            properties={
                'email': openapi.Schema(type=openapi.TYPE_STRING, description='Customer email'),
                'Uid': openapi.Schema(type=openapi.TYPE_STRING, description='Invoice UID'),
            }
        ),
        operation_description="Create an invoice access token for a customer"
    )

    def post(self, request):
        try:
            email = request.data["email"]
            invoice_id = request.data["Uid"]
            invoice = api_models.Invoice.objects.get(Uid=invoice_id)

            if invoice.customer.email != email:
                return Response({"error": "No invoice found with the provided email"}, status=status.HTTP_400_BAD_REQUEST)

            existing_token = api_models.InvoiceAccessToken.objects.filter(
                invoice=invoice,
            ).first()

            if existing_token and existing_token.is_valid():
                return Response({
                    "token": existing_token.token,
                    "message": "Using existing valid token"
                }, status=status.HTTP_200_OK)

            # Create new token and delete the old one if no valid one exists
            if existing_token:
                existing_token.delete()
            token = api_models.InvoiceAccessToken.create_token(invoice)
            return Response({"token": token}, status=status.HTTP_201_CREATED)

        except api_models.Invoice.DoesNotExist:
            return Response({"error": "Invoice not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class VerifyInvoiceTokenView(APIView):
    """
    API to retrieve the invoice related with an invoice view token
    """
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['token'],
            properties={
                'token': openapi.Schema(type=openapi.TYPE_STRING, description='Invoice access token'),
            }
        ),
        responses={
            200: openapi.Response('Success', api_serializer.InvoiceSerializer),
            400: 'Invalid token',
            404: 'Token not found',
            500: 'Server error'
        },
        operation_description="Verify an invoice access token and return invoice details"
    )
    def post(self, request):
        try:
            # Validate token
            token_serializer = api_serializer.InvoiceAccessTokenSerializer(data=request.data)
            if not token_serializer.is_valid():
                return Response({
                    "error": "Invalid token",
                    "details": token_serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)

            # Get invoice from validated token
            invoice = token_serializer.invoice
            
            # Serialize invoice data
            invoice_serializer = api_serializer.InvoiceSerializer(invoice)
            
            # Create notification for invoice view
            api_models.Notification.objects.create(
                business=invoice.business,
                title="Invoice viewed",
                description=f'Invoice {invoice.Uid} has been viewed by customer',
                type="invoice_viewed"
            )
            
            return Response({
                "invoice": invoice_serializer.data,
                "message": "Token verified successfully"
            }, status=status.HTTP_200_OK)
            
        except api_models.InvoiceAccessToken.DoesNotExist:
            return Response({
                "error": "Token not found"
            }, status=status.HTTP_404_NOT_FOUND)
            
        except api_models.Invoice.DoesNotExist:
            return Response({
                "error": "Invoice not found"
            }, status=status.HTTP_404_NOT_FOUND)
            
        except Exception as e:
            return Response({
                "error": "An error occurred while verifying the token",
                "details": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class BusinessGetByNameView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                'name', 
                openapi.IN_QUERY,
                description="Business name to search for",
                type=openapi.TYPE_STRING,
                required=True
            )
        ],
        responses={
            200: openapi.Response('Success', api_serializer.BusinessSerializer),
            400: 'Bad Request',
            404: 'Business not found'
        }
    )
    def get(self, request):
        name = request.query_params.get('name')
        if not name:
            return Response({"error": "Name parameter is required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            business = api_models.Business.objects.get(name=name)
            serializer = api_serializer.BusinessSerializer(business)

            # Create notification for business search
            api_models.Notification.objects.create(
                business=business,
                title="Business searched",
                description=f'Business "{business.name}" was searched',
                type="business_searched"
            )

            return Response({"data": serializer.data}, status=status.HTTP_200_OK)
        except api_models.Business.DoesNotExist:
            return Response({"error": "Business not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": f"Error retrieving business: {str(e)}"}, 
                          status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class UserBusinessListView(APIView):
    """
    API to list all businesses owned by a user
    """
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                'user_id',
                openapi.IN_QUERY,
                description="ID of the user",
                type=openapi.TYPE_INTEGER,
                required=True
            ),
        ],
        responses={
            200: openapi.Response('Success', api_serializer.BusinessSerializer(many=True)),
            400: 'Bad Request',
            404: 'User not found'
        },
        operation_description="List all businesses owned by a user"
    )
    def get(self, request):
        try:
            user_id = request.query_params.get('user_id')
            if not user_id:
                return Response(
                    {"error": "User ID is required"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            cache_key = f'user_businesses_{user_id}'
            businesses = cache.get(cache_key)

            if businesses is None:
                user = User.objects.get(id=user_id)
                businesses = api_models.Business.objects.filter(owner=user)
                cache.set(cache_key, businesses, timeout=60 * 15)  # Cache for 15 minutes

            serializer = api_serializer.BusinessSerializer(businesses, many=True)
            return Response({
                "data": serializer.data,
                "message": "Businesses retrieved successfully"
            }, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            return Response(
                {"error": "User not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": f"An error occurred: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


