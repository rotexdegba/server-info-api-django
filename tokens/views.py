import secrets
from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .models import Token


@login_required
def my_tokens(request, last_edited_id=None):
    today = date.today()
    all_tokens = Token.objects.filter(generators_username=request.user.username).order_by('date_created')
    active = [t for t in all_tokens if not t.is_expired()]
    expired = sorted([t for t in all_tokens if t.is_expired()], key=lambda t: t.expiry_date)
    return render(request, 'tokens/my_tokens.html', {
        'activeTokenRecords': active,
        'expiredTokenRecords': expired,
        'idOfLastEditedToken': last_edited_id,
    })


@login_required
def add_token(request):
    if request.method == 'POST':
        expiry_str = request.POST.get('expiry_date', '')
        try:
            expiry = date.fromisoformat(expiry_str)
        except ValueError:
            expiry = date.today() + timedelta(days=30)
        max_req = int(request.POST.get('max_requests_per_day', 0) or 0)
        ip = (
            request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
            or request.META.get('REMOTE_ADDR', 'NOIP')
        )
        Token.objects.create(
            generators_username=request.user.username,
            token=secrets.token_hex(32),
            max_requests_per_day=max_req,
            expiry_date=expiry,
            creators_ip=ip,
        )
        messages.success(request, 'Token Successfully Created!')
        return redirect('my_tokens')
    default_expiry = (date.today() + timedelta(days=30)).isoformat()
    return render(request, 'tokens/add_edit.html', {
        'form_title': 'Add Token',
        'form_action': '/tokens/add',
        'token_value': secrets.token_hex(32),
        'default_expiry': default_expiry,
        'max_requests_per_day': 0,
    })


@login_required
def edit_token(request, pk):
    token = get_object_or_404(Token, pk=pk)
    if token.generators_username != request.user.username:
        return redirect('my_tokens')

    if request.method == 'POST':
        expiry_str = request.POST.get('expiry_date', '')
        try:
            expiry = date.fromisoformat(expiry_str)
        except ValueError:
            expiry = token.expiry_date
        token.max_requests_per_day = int(request.POST.get('max_requests_per_day', 0) or 0)
        token.expiry_date = expiry
        token.save()
        messages.success(request, 'Token Successfully Updated!')
        return redirect('my_tokens_last_edited', last_edited_id=pk)

    return render(request, 'tokens/add_edit.html', {
        'form_title': 'Edit Token',
        'form_action': f'/tokens/{pk}/edit',
        'token_value': token.token,
        'default_expiry': token.expiry_date.isoformat(),
        'max_requests_per_day': token.max_requests_per_day,
        'token_id': pk,
    })


@login_required
def delete_token(request, pk):
    token = get_object_or_404(Token, pk=pk)
    if token.generators_username != request.user.username:
        return redirect('my_tokens')
    token.delete()
    messages.success(request, 'Token Successfully Deleted!')
    return redirect('my_tokens')
