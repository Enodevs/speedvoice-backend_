from django.db import models # type:ignore
from userauth.models import User # type:ignore
from django.utils.timezone import now # type:ignore
from datetime import timedelta # type:ignore
from shortuuid.django_fields import ShortUUIDField # type:ignore

INVOICE_STATUS = (
    ("paid", "Paid"),
    ("pending", "Pending"),
    ("unpaid", "Unpaid"),
    ("draft", "Draft")
)

CURRENCY = (
    ("USD", "USD"),
    ("EUR", "EUR"),
    ("NGN", "NGN"),
    ("YEN", "YEN"),
)

def user_directory_path(instance, filename):
    ext = filename.split(".")[-1]
    filename = "%s_%s" % (instance.id, ext)
    return "user_{0}/{1}".format(instance.user_id, filename)


class LoginToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    token = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def is_valid(self):
        return now() < self.created_at + timedelta(minutes=15)   

    def __str__(self):
        return self.token

class Business(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    currency = models.CharField(choices=CURRENCY, default="USD", max_length=100)
    description = models.CharField(max_length=100, default="")
    image = models.FileField(null=True, blank=True, upload_to="media")
    active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = "Businesses"

    def __str__(self):
        return self.name

class Signature(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE)
    text = models.CharField(max_length=100)
    font = models.CharField(max_length=50)

    def __str__(self):
        return self.text

class Category(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)

    class Meta:
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name

class Customer(models.Model):
    business = models.ForeignKey(Business, on_delete=models.CASCADE)
    full_name = models.CharField(max_length=100)
    email = models.CharField(max_length=100, blank=True)
    phone_number = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return self.full_name

class Product(models.Model):
    owner = models.ForeignKey(Business, on_delete=models.CASCADE)
    name = models.CharField(max_length=100, null=False, blank=False)
    category = models.ForeignKey(Category, on_delete=models.DO_NOTHING, null=True, blank=True, related_name="category")
    price = models.DecimalField(decimal_places=2, default=0.00, max_digits=15)
    image = models.FileField(upload_to="media", null=True, blank=True)
    date_added = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-date_added']

    def __str__(self):
        return self.name 
        

class Invoice(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="user")
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="business")
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, related_name="customer")
    signature = models.ForeignKey(Signature, on_delete=models.DO_NOTHING, null=True, blank=True)
    Uid = ShortUUIDField(unique=True, max_length=17, length=12, alphabet="abcdefghijklmnopqrstuvwxyz", prefix="Inv-")
    title = models.CharField(max_length=50)
    description = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=100, choices=INVOICE_STATUS, default="pending")
    total = models.DecimalField(default=0.00, decimal_places=2, max_digits=15)
    discount = models.DecimalField(default=0.00, decimal_places=2, max_digits=15)
    grand_total = models.DecimalField(default=0.00, decimal_places=2, max_digits=15)
    is_recurring = models.BooleanField(default=False)
    date_created = models.DateTimeField(auto_now_add=True)
    date_due = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-date_created']

    def __str__(self):
        return self.business.name

    def save(self):
        self.grand_total = float(self.total) - float(self.discount)
        return super(Invoice, self).save()

    def set_unpaid(self):
        if self.date_due is not None and now() < self.date_due and self.status != "paid":
            self.status = "unpaid"
            return "done"
        else:
            self.status = "pending"
            return "done"

class Invoice_item(models.Model):
    # id = ShortUUIDField(length=1, max_length=2, primary_key=True, unique=True, alphabet="1234567890")
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=0)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Sale Items"

    def price(self):
        return self.product.price * self.quantity
    
    def removeQuantity(self):
        self.product.quantity -= 1
        self.product.save()
        return "saved"
    
class Receipt(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="user_receipt")
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="business_receipt")
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, related_name="customer_receipt")
    signature = models.ForeignKey(Signature, on_delete=models.DO_NOTHING, null=True, blank=True)
    invoice = models.OneToOneField(Invoice, on_delete=models.CASCADE, related_name="invoice_receipt")
    Uid = ShortUUIDField(unique=True, max_length=15, length=10, alphabet="abcdefghijklmnopqrstuvwxyz#1234567890", prefix="Rcpt-")
    date_created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date_created']

    def __str__(self):
        return self.invoice.title

