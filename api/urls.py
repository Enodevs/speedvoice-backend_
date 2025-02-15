from api import views as api_views
from django.urls import path # type:ignore
from rest_framework_simplejwt.views import TokenRefreshView # type:ignore

urlpatterns = [
    path('user/token/', api_views.MyTokenObtainPairView.as_view()),
    path('user/token/refresh/', TokenRefreshView.as_view()),
    path('user/register/', api_views.RegisterView.as_view()),
    path('user/', api_views.UserAPIView.as_view()),

    path('auth/generate-login-token/', api_views.GenerateLoginTokenAPIView.as_view(), name='generate_login_token'),
    path('auth/token-login/', api_views.TokenLoginAPIView.as_view(), name='token_login'),
    path('auth/business-create/', api_views.BusinessCreateView.as_view()),
    path('auth/business/<int:business_id>/', api_views.BusinessGetView.as_view()),
    path('auth/check-user-email/', api_views.CheckUserEmailAPIView.as_view(), name='check_user_email'),

    ########### Invoice ###########
    path('dashboard/invoices/<business_id>/', api_views.InvoiceListView.as_view(), name='invoices_list'),
    path('dashboard/invoices-create/', api_views.InvoiceCreateView.as_view()),
    path('dashboard/invoice-update/', api_views.InvoiceUpdateView.as_view()),
    path('dashboard/invoice/<Uid>/', api_views.InvoiceView.as_view()),
    path('dashboard/invoice/delete/<business_id>/<Uid>/', api_views.InvoiceDeleteView.as_view()),

    ###########  Category ###########
    path('dashboard/categories/<int:business_id>/', api_views.CategoryListView.as_view(), name='categories_list'),
    path('dashboard/categories-create/', api_views.CategoryCreateView.as_view()),
    path('dashboard/categories/<int:business_id>/<name>/', api_views.CategoryView.as_view()),
    path('dashboard/categories/<int:business_id>/', api_views.CategoryListView.as_view(), name="Category_list"),
    path('dashboard/categories-create/', api_views.CategoryCreateView.as_view()),

    ###########  Customer ###########
    path('dashboard/customers/<int:business_id>/', api_views.CustomerListView.as_view(), name='customers_list'),
    path('dashboard/customers-create/', api_views.CustomerCreateView.as_view()),
    path('dashboard/customer/<id>/', api_views.CustomerView.as_view()),

    ###########  Invoice item ###########
    path('dashboard/invoice-items/<invoice_id>/', api_views.InvoiceItemListView.as_view(), name='invoice_items_list'),
    path('dashboard/invoice-items-create/', api_views.InvoiceItemCreateView.as_view()),
    path('dashboard/invoice-item/<id>/', api_views.InvoiceItemView.as_view()),

    ###########  Product ###########
    path('dashboard/products/<int:business_id>/', api_views.ProductListView.as_view(), name='products_list'),
    path('dashboard/products-create/', api_views.ProductCreateView.as_view()),
    path('dashboard/product/<int:business_id>/<id>/', api_views.ProductView.as_view()),

    ###########  Invoice Admin ###########
    path('dashboard/admin/<int:business_id>/', api_views.AdminView.as_view()),
    path('dashboard/admin/stats/<int:business_id>/', api_views.DashboardStatsView.as_view()),
    path('dashboard/invoice/admin/stats/<int:business_id>/', api_views.InvoiceStatsView.as_view(), name='dashboard_stats'),

    ###########  Receipts ###########
    path('dashboard/receipts/<int:business_id>/', api_views.ReceiptListView.as_view()),
    path('dashboard/receipt/<int:business_id>/<Uid>/', api_views.ReceiptGetView.as_view(), name='receipt_get'),
]