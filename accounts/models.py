from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


class UserProfile(models.Model):
    ROLE_USER = "user"
    ROLE_TRUSTED = "trusted_reporter"
    ROLE_ADMIN = "admin"

    ROLE_CHOICES = [
        (ROLE_USER, "Regular User"),
        (ROLE_TRUSTED, "Trusted Reporter"),
        (ROLE_ADMIN, "Admin"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    role = models.CharField(max_length=32, choices=ROLE_CHOICES, default=ROLE_USER)
    trust_score = models.PositiveIntegerField(
        default=50,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-trust_score", "user__username"]

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"

    @property
    def is_admin_role(self):
        return self.role == self.ROLE_ADMIN or self.user.is_staff or self.user.is_superuser

    @property
    def is_trusted_reporter(self):
        return self.role == self.ROLE_TRUSTED

    def save(self, *args, **kwargs):
        self.trust_score = max(0, min(100, int(self.trust_score)))
        if self.user_id and (self.user.is_staff or self.user.is_superuser):
            self.role = self.ROLE_ADMIN
        elif self.role == self.ROLE_USER and self.trust_score >= 85:
            self.role = self.ROLE_TRUSTED
        elif self.role == self.ROLE_TRUSTED and self.trust_score < 70:
            self.role = self.ROLE_USER
        super().save(*args, **kwargs)


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)
    elif hasattr(instance, "profile"):
        instance.profile.save()
