from django.urls import path
from . import views

urlpatterns = [
    path('',views.SurveyList,name='MySurvey'),
    path('history/',views.SurveyHistory,name='SurveyHistory'),
    path('<int:survey_pk>/',views.SurveyTake,name='SurveyTake'),
    path('create/',views.SurveyCreate,name='SurveyCreate'),
    path('approve/',views.SurveyApproveList,name='SurveyApproveList'),
    path('approve/<int:survey_pk>/',views.SurveyApproveDetail,name='SurveyApproveDetail'),
    path('published/',views.SurveyPublished,name='SurveyPublished'),
    path('published/<int:survey_pk>/overview/',views.ResponseOverview,name='ResponseOverview'),
    path('published/<int:survey_pk>/export-excel/', views.SurveyExportExcel, name='SurveyExportExcel'), #export ra excel
    path('published/<int:rep_pk>/detail/',views.ResponseDetail,name='ResponseDetail'), #remember to change input to response_pk
]