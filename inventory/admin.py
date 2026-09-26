

# Register your models here.
from django.contrib import admin
from .models import Category, Warehouse, Location, Product, Stock


admin.site.register(Category)
admin.site.register(Warehouse)
admin.site.register(Location)
admin.site.register(Product)
admin.site.register(Stock)