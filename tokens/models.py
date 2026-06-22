from datetime import date, datetime, timedelta, timezone

from django.db import models
from django.contrib.auth.models import User


class Token(models.Model):
    generators_username = models.CharField(max_length=255)
    token = models.CharField(max_length=255, unique=True)
    date_created = models.DateTimeField(auto_now_add=True)
    date_last_edited = models.DateTimeField(auto_now=True)
    max_requests_per_day = models.PositiveBigIntegerField(default=0)
    expiry_date = models.DateField()
    creators_ip = models.CharField(max_length=255, default='NOIP')

    class Meta:
        ordering = ['date_created']

    def is_expired(self):
        return date.today() >= self.expiry_date

    def has_exceeded_daily_limit(self):
        if self.max_requests_per_day == 0:
            return False
        since = datetime.now(timezone.utc) - timedelta(days=1)
        count = self.usages.filter(date_time_of_request__gte=since).count()
        return count >= self.max_requests_per_day

    def __str__(self):
        return f'{self.token[:12]}… ({self.generators_username})'


class TokenUsage(models.Model):
    token = models.ForeignKey(Token, on_delete=models.CASCADE, related_name='usages')
    request_uri = models.CharField(max_length=255)
    date_time_of_request = models.DateTimeField(auto_now_add=True)
    request_full_details = models.TextField()
    requesters_ip = models.CharField(max_length=255, default='NOIP')
    http_status_code = models.CharField(max_length=3, default='200')
    request_error_details = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-date_time_of_request']
