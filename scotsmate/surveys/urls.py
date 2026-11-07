from django.urls import path
from . import views

urlpatterns = [
    path('',views.SurveyList,name='MySurvey'),
    path('history/',views.SurveyHistory,name='SurveyHistory'),
    path('temp_detail/',views.SurveyDetail,name='SurveyDetail'), #remember to change input to survey_pk
    path('create/',views.SurveyCreate,name='SurveyCreate'),
    path('approver/list/',views.SurveyApproveList,name='SurveyApproveList'),
    path('approver/list/temp_detail/',views.SurveyApproveDetail,name='SurveyApproveDetail'), #remember to change input to survey_pk
    path('approver/published/',views.SurveyPublished,name='SurveyPublished'),
    path('approver/published/temp_id/overview/',views.ResponseOverview,name='ResponseOverview'), #remember to change input to response_pk
    path('approver/published/temp_id/detail/',views.ResponseDetail,name='ResponseDetail'), #remember to change input to response_pk
]