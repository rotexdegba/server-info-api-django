from django.urls import path
from . import views

urlpatterns = [
    path('my-tokens', views.my_tokens, name='my_tokens'),
    path('my-tokens/<int:last_edited_id>', views.my_tokens, name='my_tokens_last_edited'),
    path('add', views.add_token, name='add_token'),
    path('<int:pk>/edit', views.edit_token, name='edit_token'),
    path('<int:pk>/delete', views.delete_token, name='delete_token'),
]
