from django.db import models


class Supplier(models.Model):
    name = models.CharField(max_length=255, help_text="Supplier company or individual name")
    contact_number = models.CharField(max_length=50, blank=True, help_text="Contact phone number")
    email = models.EmailField(blank=True, help_text="Contact email address")
    address = models.TextField(blank=True, help_text="Physical or postal address")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name = "Supplier"
        verbose_name_plural = "Suppliers"

    def __str__(self):
        return self.name
