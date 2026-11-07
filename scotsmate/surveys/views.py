from django.shortcuts import render

# Create your views here.
def SurveyList(request):
    return render(request, 'list.html')

def SurveyHistory(request):
    return render(request, 'history.html')

def SurveyDetail(request):
    return render(request, 'detail.html')

def SurveyCreate(request):
    return render(request, 'create.html')

def SurveyApproveList(request):
    return render(request, 'approve_list.html')

def SurveyApproveDetail(request):
    return render(request, 'approve_detail.html')

def SurveyPublished(request):
    return render(request, 'published.html')

def ResponseOverview(request):
    return render(request, 'responses_overview.html')

def ResponseDetail(request):
    return render(request, 'responses_detail.html')
