from django.urls import path
from . import views

urlpatterns = [
    path("merchants", views.merchant_list, name="merchant_list"),
    path("payouts", views.create_payout, name="create_payout"),
    path("payouts/history", views.payout_history, name="payout_history"),
    path("dashboard", views.merchant_dashboard, name="merchant_dashboard"),
]
