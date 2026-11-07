from django.shortcuts import render

# Create your views here.
def messages_list(request):
    return render(request, 'messages.html')

def group_create(request):
    return render(request, 'group-create.html')

def group_detail(request, group_id=1):
    return render(request, 'group.html', {'group_id': group_id})

def inbox_detail(request, user_id=1):
    return render(request, 'inbox.html', {'user_id': user_id})