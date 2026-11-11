from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Count, Q
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.utils import timezone
from django.utils.text import slugify

from .models import DocumentCategory, Document, DocumentUpdateProposal
from .forms import DocumentCreateForm, DocumentCategoryForm, DocumentEditForm

User = get_user_model()


def _get_acting_user(request):
    """Lấy user đang đăng nhập hoặc tạo user mặc định nếu chưa login."""
    if request.user.is_authenticated:
        return request.user
    user = User.objects.first()
    if not user:
        user = User.objects.create_user(
            username='minhanh',
            first_name='Minh Anh',
            last_name='Nguyễn'
        )
    return user

# 1. Thư viện tài liệu (/documents/)
def document_list(request):
    search_query = request.GET.get('q', '').strip()

    categories = DocumentCategory.objects.annotate(
        doc_count=Count('documents', filter=Q(documents__status='APPROVED'))
    )

    if search_query:
        # Đã xóa Q(code__icontains=search_query)
        categories = categories.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query)
        )

    context = {
        'categories': categories,
        'pending_count': Document.objects.filter(status='PENDING').count(),
        'search_query': search_query,
    }
    return render(request, 'documents.html', context)


# 2. Tạo mới tài liệu (/documents/create/)
def document_create(request):
    error_message = None

    if request.method == "POST":
        form = DocumentCreateForm(request.POST, request.FILES)
        if form.is_valid():
            title = form.cleaned_data['title']
            category = form.cleaned_data['category']
            description = form.cleaned_data['description']
            uploaded_files = form.cleaned_data['file']

            for index, f in enumerate(uploaded_files, start=1):
                doc_title = title if len(uploaded_files) == 1 else f"{title} ({index})"
                Document.objects.create(
                    title=doc_title,
                    category=category,
                    description=description,
                    file=f,
                    creator=_get_acting_user(request),
                    status='PENDING',
                    request_type='NEW',
                )

            # Đăng ký thông báo theo mẫu Bài thực hành Chương 4[cite: 51]
            messages.success(
                request,
                'Tài liệu "{}" đã được gửi phê duyệt thành công.'.format(title)
            )

            # Điều hướng về lại trang tạo mới (hoặc đổi thành "document_my_docs" nếu muốn về danh sách Tài liệu của tôi)[cite: 51]
            return redirect("document_my_docs")
        else:
            for field_errors in form.errors.values():
                error_message = field_errors[0]
                break
    else:
        form = DocumentCreateForm()

    context = {
        'form': form,
        'pending_count': Document.objects.filter(status='PENDING').count(),
        'error_message': error_message,
    }
    return render(request, 'documents_create.html', context)


# 3. Tài liệu của tôi (/documents/my_docs/)
def document_my_docs(request):
    search_query = request.GET.get('q', '').strip()
    user = _get_acting_user(request)

    if request.method == 'POST' and 'delete_doc_id' in request.POST:
        doc_to_delete = get_object_or_404(Document, id=request.POST.get('delete_doc_id'))
        doc_to_delete.delete()
        return redirect('document_my_docs')

    my_documents = Document.objects.select_related('category', 'approver').filter(creator=user)

    if search_query:
        my_documents = my_documents.filter(title__icontains=search_query)

    paginator = Paginator(my_documents, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'documents': page_obj,
        'pending_count': Document.objects.filter(status='PENDING').count(),
        'search_query': search_query,
    }
    return render(request, 'documents_my_docs.html', context)

# 4. Cập nhật tài liệu (/documents/my_docs/<id>/edit/)
def document_edit(request, id):
    doc = get_object_or_404(Document, id=id)

    if request.method == 'POST':
        form = DocumentEditForm(request.POST, request.FILES, instance=doc)
        if form.is_valid():
            proposed_title = form.cleaned_data['title']
            proposed_category = form.cleaned_data['category']
            proposed_file = request.FILES.get('file') or doc.file

            DocumentUpdateProposal.objects.create(
                document=doc,
                proposed_title=proposed_title,
                proposed_category=proposed_category,
                proposed_file=proposed_file,
                proposed_scope=doc.access_scope,
                submitted_by=_get_acting_user(request),
                approver=doc.approver,
            )

            doc.status = 'PENDING'
            doc.request_type = 'UPDATE'
            doc.save()

            messages.success(
                request,
                f'Tài liệu "{proposed_title}" đã được lưu và gửi phê duyệt chỉnh sửa thành công.'
            )
            return redirect('document_my_docs')
    else:
        form = DocumentEditForm(instance=doc)

    context = {
        'doc_id': id,
        'doc': doc,
        'form': form,
        'pending_count': Document.objects.filter(status='PENDING').count(),
    }
    return render(request, 'documents_my_docs_edit.html', context)


# 5. Danh sách tài liệu chờ duyệt (/documents/approve/)
def document_approve_list(request):
    search_query = request.GET.get('q', '').strip()
    pending_docs = Document.objects.select_related('category', 'creator').filter(status='PENDING')

    if search_query:
        pending_docs = pending_docs.filter(title__icontains=search_query)

    context = {
        'pending_docs': pending_docs,
        'pending_count': pending_docs.count(),
        'search_query': search_query,
    }
    return render(request, 'documents_approve.html', context)


# 6. Chi tiết duyệt tài liệu (/documents/approve/<id>/)
def document_approve_detail(request, id):
    doc = get_object_or_404(Document, id=id)
    proposal = doc.proposals.filter(is_processed=False).first()

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'approve':
            # Xử lý duyệt
            if proposal:
                doc.title = proposal.proposed_title
                if proposal.proposed_category:
                    doc.category = proposal.proposed_category
                if proposal.proposed_file:
                    doc.file = proposal.proposed_file
                doc.access_scope = proposal.proposed_scope
                proposal.is_processed = True
                proposal.save()

            doc.status = 'APPROVED'
            doc.approver = request.user if request.user.is_authenticated else User.objects.first()
            doc.approved_at = timezone.now()
            doc.save()

            # Thông báo phê duyệt thành công
            messages.success(request, f'Đã phê duyệt thành công tài liệu "{doc.title}".')

        elif action == 'reject':
            # Xử lý từ chối
            doc.status = 'REJECTED'
            doc.rejection_reason = request.POST.get('rejection_reason', '')
            doc.save()

            if proposal:
                proposal.is_processed = True
                proposal.save()

            # Thông báo đã từ chối
            messages.error(request, f'Đã từ chối phê duyệt tài liệu "{doc.title}".')

        # Điều hướng về trang danh sách chờ duyệt
        return redirect('document_approve')

    context = {
        'doc_id': id,
        'doc': doc,
        'proposal': proposal,
        'pending_count': Document.objects.filter(status='PENDING').count(),
    }
    return render(request, 'documents_approve_detail.html', context)


# 7. Chi tiết danh mục (/documents/<int:cate_id>/)
def document_category(request, cate_id):
    search_query = request.GET.get('q', '').strip()
    category = get_object_or_404(DocumentCategory, id=cate_id)

    documents = Document.objects.select_related('creator', 'approver').filter(
        category=category,
        status='APPROVED'
    )

    if search_query:
        documents = documents.filter(title__icontains=search_query)

    context = {
        'cate_id': cate_id,
        'category': category,
        'documents': documents,
        'pending_count': Document.objects.filter(status='PENDING').count(),
        'search_query': search_query,
    }
    return render(request, 'documents_category.html', context)


# 8. Xem trước tài liệu (/documents/<int:cate_id>/preview/)
def document_preview(request, cate_id):
    category = get_object_or_404(DocumentCategory, id=cate_id)

    documents = Document.objects.select_related('creator', 'approver').filter(
        category=category,
        status='APPROVED'
    )

    doc_id = request.GET.get('doc_id')
    preview_doc = documents.filter(id=doc_id).first() if doc_id else documents.first()

    context = {
        'cate_id': cate_id,
        'category': category,
        'documents': documents,
        'preview_doc': preview_doc,
        'show_preview_modal': True,
        'pending_count': Document.objects.filter(status='PENDING').count(),
    }
    return render(request, 'documents_category.html', context)

from django.contrib import messages
# 9. Tạo danh mục tài liệu mới (/documents/category/create/)
def document_category_create(request):
    if request.method == "POST":
        form = DocumentCategoryForm(request.POST)
        if form.is_valid():
            category = form.save(commit=False)
            # Đã xóa toàn bộ phần gán category.code và category.icon_name
            category.display_order = DocumentCategory.objects.count() + 1
            category.save()

            messages.success(
                request,
                f'Danh mục "{category.name}" đã được tạo thành công.'
            )
            return redirect("documents")
    else:
        form = DocumentCategoryForm()

    return render(request, "documents_category_create.html", {
        "form": form,
        "pending_count": Document.objects.filter(status='PENDING').count(),
    })