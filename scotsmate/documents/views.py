from django.shortcuts import render
from django.http import HttpResponse

def document_list(request, *args, **kwargs):
    return render(request, 'documents.html') if request else HttpResponse("Document List")

def document_create(request, *args, **kwargs):
    return HttpResponse("Document Create")

def document_my_docs(request, *args, **kwargs):
    return render(request, 'documents_my_docs.html') if request else HttpResponse("My Docs")

def document_edit(request, *args, **kwargs):
    return HttpResponse("Document Edit")

def document_approve_list(request, *args, **kwargs):
    return HttpResponse("Document Approve List")

def document_approve_detail(request, *args, **kwargs):
    return HttpResponse("Document Approve Detail")

def document_category(request, *args, **kwargs):
    return HttpResponse("Document Category")

def document_preview(request, *args, **kwargs):
    return HttpResponse("Document Preview")
