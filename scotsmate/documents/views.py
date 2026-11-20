from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Count, Q
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.utils import timezone

from .models import DocumentCategory, Document, DocumentUpdateProposal, DocumentAccess
from .forms import DocumentCreateForm, DocumentCategoryForm, DocumentEditForm
from home.roles import (
    is_department_manager,
    is_it_admin,
    redirect_back_with_error,
)

User = get_user_model()


def _require_doc_access(request, require_manager=False):
    if not request.user.is_authenticated:
        return redirect('/login/?next=' + request.path)
    if require_manager and not (is_it_admin(request.user) or is_department_manager(request.user)):
        return redirect_back_with_error(
            request,
            'Chỉ Trưởng phòng hoặc Admin mới có quyền thực hiện chức năng quản lý/phê duyệt tài liệu.',
            fallback_url='documents',
        )
    return None


def _get_user_department(user):
    # Lấy phòng ban của user thông qua EmployeeInformation (employee_info.dep)
    if not user or not user.is_authenticated:
        return None
    emp_info = getattr(user, 'employee_info', None)
    if emp_info and getattr(emp_info, 'dep', None):
        return emp_info.dep
    return None


def _is_manager(user):
    return is_it_admin(user) or is_department_manager(user)


def _pending_docs_for_user(user):
    qs = Document.objects.select_related('category', 'creator').filter(status='PENDING')
    if is_it_admin(user):
        return qs
    if not is_department_manager(user):
        return Document.objects.none()
    managed_ids = list(user.managed_departments.values_list('id', flat=True))
    return qs.filter(
        Q(creator=user)
        | Q(creator__employee_info__dep_id__in=managed_ids)
        | Q(access_permissions__department_id__in=managed_ids)
        | Q(creator__employee_info__dep__isnull=True)
    ).distinct()


def _can_manage_doc(user, doc):
    if is_it_admin(user):
        return True
    if not is_department_manager(user):
        return False
    if doc.creator_id == user.id:
        return True
    managed_ids = set(user.managed_departments.values_list('id', flat=True))
    emp_info = getattr(doc.creator, 'employee_info', None)
    creator_dep_id = getattr(emp_info, 'dep_id', None)
    if creator_dep_id is None or creator_dep_id in managed_ids:
        return True
    return doc.access_permissions.filter(department_id__in=managed_ids).exists()


# 1. Thư viện tài liệu (/documents/)
def document_list(request):
    denied = _require_doc_access(request)
    if denied:
        return denied

    search_query = request.GET.get('q', '').strip()

    categories = DocumentCategory.objects.annotate(
        doc_count=Count('documents', filter=Q(documents__status='APPROVED', documents__is_visible=True))
    )

    if search_query:
        categories = categories.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query)
        )

    context = {
        'categories': categories,
        'pending_count': _pending_docs_for_user(request.user).count(),
        'search_query': search_query,
        'is_manager': _is_manager(request.user),
    }
    return render(request, 'documents.html', context)


# 2. Tạo mới tài liệu (/documents/create/)
def document_create(request):
    denied = _require_doc_access(request)
    if denied:
        return denied

    error_message = None

    if request.method == "POST":
        form = DocumentCreateForm(request.POST, request.FILES)
        if form.is_valid():
            title = form.cleaned_data['title']
            category = form.cleaned_data['category']
            description = form.cleaned_data['description']
            access_scope = form.cleaned_data.get('access_scope') or 'ALL'
            selected_departments = form.cleaned_data.get('departments', [])
            uploaded_files = form.cleaned_data['file']

            for index, f in enumerate(uploaded_files, start=1):
                doc_title = title if len(uploaded_files) == 1 else f"{title} ({index})"
                new_doc = Document.objects.create(
                    title=doc_title,
                    category=category,
                    description=description,
                    file=f,
                    access_scope=access_scope,
                    creator=request.user,
                    status='PENDING',
                    request_type='NEW',
                )
                if access_scope == 'DEPARTMENT':
                    for dept in selected_departments:
                        DocumentAccess.objects.create(document=new_doc, department=dept)

            messages.success(
                request,
                f'Tài liệu "{title}" đã được gửi phê duyệt thành công.'
            )
            return redirect("document_my_docs")
        else:
            for field_errors in form.errors.values():
                error_message = field_errors[0]
                break
    else:
        form = DocumentCreateForm()

    acting_user = request.user
    user_dept = _get_user_department(acting_user)
    context = {
        'form': form,
        'pending_count': _pending_docs_for_user(request.user).count(),
        'error_message': error_message,
        'is_manager': _is_manager(request.user),
        'acting_user': acting_user,
        'user_dept': user_dept,
    }
    return render(request, 'documents_create.html', context)


# 3. Tài liệu của tôi (/documents/my_docs/)
def document_my_docs(request):
    denied = _require_doc_access(request)
    if denied:
        return denied

    search_query = request.GET.get('q', '').strip()
    user = request.user

    if request.method == 'POST' and 'delete_doc_id' in request.POST:
        doc_to_delete = get_object_or_404(Document, id=request.POST.get('delete_doc_id'), creator=user)
        doc_to_delete.delete()
        messages.success(request, 'Đã xóa tài liệu của bạn.')
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
        'pending_count': _pending_docs_for_user(request.user).count(),
        'search_query': search_query,
        'is_manager': _is_manager(request.user),
    }
    return render(request, 'documents_my_docs.html', context)


# 4. Cập nhật tài liệu (/documents/my_docs/<id>/edit/)
def document_edit(request, id):
    denied = _require_doc_access(request)
    if denied:
        return denied

    doc = get_object_or_404(Document, id=id)
    can_manage = _can_manage_doc(request.user, doc)
    if doc.creator_id != request.user.id and not can_manage:
        return redirect_back_with_error(
            request,
            'Bạn không có quyền chỉnh sửa tài liệu ngoài phạm vi quản lý.',
            fallback_url='document_my_docs',
        )

    if request.method == 'POST':
        form = DocumentEditForm(request.POST, request.FILES, instance=doc)
        if form.is_valid():
            proposed_title = form.cleaned_data['title']
            proposed_category = form.cleaned_data['category']
            proposed_file = request.FILES.get('file') or doc.file

            if can_manage:
                doc.title = proposed_title
                doc.category = proposed_category
                doc.file = proposed_file
                doc.approver = request.user
                doc.approved_at = timezone.now()
                doc.status = 'APPROVED'
                doc.save()
                messages.success(request, f'Đã cập nhật tài liệu "{doc.title}".')
                return redirect('document_category', cate_id=doc.category_id)

            DocumentUpdateProposal.objects.create(
                document=doc,
                proposed_title=proposed_title,
                proposed_category=proposed_category,
                proposed_file=proposed_file,
                proposed_scope=doc.access_scope,
                submitted_by=request.user,
                approver=doc.approver,
            )

            # Chỉ cập nhật trạng thái, giữ nguyên dữ liệu gốc cho tới khi Trưởng phòng phê duyệt
            Document.objects.filter(id=doc.id).update(
                status='PENDING',
                request_type='UPDATE',
                updated_at=timezone.now(),
            )

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
        'pending_count': _pending_docs_for_user(request.user).count(),
        'is_manager': _is_manager(request.user),
    }
    return render(request, 'documents_my_docs_edit.html', context)


# 5. Danh sách tài liệu chờ duyệt (/documents/approve/)
def document_approve_list(request):
    denied = _require_doc_access(request, require_manager=True)
    if denied:
        return denied

    search_query = request.GET.get('q', '').strip()
    pending_docs = _pending_docs_for_user(request.user)

    if search_query:
        pending_docs = pending_docs.filter(title__icontains=search_query)

    context = {
        'pending_docs': pending_docs,
        'pending_count': pending_docs.count(),
        'search_query': search_query,
        'is_manager': True,
    }
    return render(request, 'documents_approve.html', context)


# 6. Chi tiết duyệt tài liệu (/documents/approve/<id>/)
def document_approve_detail(request, id):
    denied = _require_doc_access(request, require_manager=True)
    if denied:
        return denied

    doc = get_object_or_404(Document, id=id)
    if not _can_manage_doc(request.user, doc):
        return redirect_back_with_error(
            request,
            'Bạn chỉ được phê duyệt tài liệu thuộc phòng ban mình quản lý.',
            fallback_url='document_approve',
        )
    proposal = doc.proposals.filter(is_processed=False).first()

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'approve':
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
            doc.approver = request.user
            doc.approved_at = timezone.now()
            doc.save()

            messages.success(request, f'Đã phê duyệt thành công tài liệu "{doc.title}".')

        elif action == 'reject':
            doc.status = 'REJECTED'
            doc.rejection_reason = request.POST.get('rejection_reason', '')
            doc.save()

            if proposal:
                proposal.is_processed = True
                proposal.save()

            messages.error(request, f'Đã từ chối phê duyệt tài liệu "{doc.title}".')

        return redirect('document_approve')

    context = {
        'doc_id': id,
        'doc': doc,
        'proposal': proposal,
        'pending_count': _pending_docs_for_user(request.user).count(),
        'is_manager': True,
    }
    return render(request, 'documents_approve_detail.html', context)


# 7. Chi tiết danh mục (/documents/<int:cate_id>/)
def document_category(request, cate_id):
    denied = _require_doc_access(request)
    if denied:
        return denied

    search_query = request.GET.get('q', '').strip()
    category = get_object_or_404(DocumentCategory, id=cate_id)
    user = request.user
    is_mgr = _is_manager(user)
    is_admin = is_it_admin(user)

    # Xử lý xoá hoặc ẩn/hiện tài liệu (Trưởng phòng trong phạm vi phòng ban hoặc Admin)
    if request.method == 'POST':
        if not is_mgr:
            return redirect_back_with_error(
                request,
                'Chỉ Trưởng phòng hoặc Admin mới có quyền xóa hoặc ẩn/hiện tài liệu.',
                fallback_url=f'/documents/{cate_id}/',
            )
        if 'delete_doc_id' in request.POST:
            doc_to_delete = get_object_or_404(Document, id=request.POST.get('delete_doc_id'), category=category)
            if not _can_manage_doc(user, doc_to_delete):
                return redirect_back_with_error(
                    request,
                    'Bạn chỉ được xóa tài liệu thuộc phòng ban mình quản lý.',
                    fallback_url=f'/documents/{cate_id}/',
                )
            doc_title = doc_to_delete.title
            doc_to_delete.delete()
            messages.success(request, f'Đã xoá thành công tài liệu "{doc_title}".')
            return redirect('document_category', cate_id=cate_id)
        if 'toggle_visibility_id' in request.POST:
            doc_to_toggle = get_object_or_404(Document, id=request.POST.get('toggle_visibility_id'), category=category)
            if not _can_manage_doc(user, doc_to_toggle):
                return redirect_back_with_error(
                    request,
                    'Bạn chỉ được ẩn/hiện tài liệu thuộc phòng ban mình quản lý.',
                    fallback_url=f'/documents/{cate_id}/',
                )
            doc_to_toggle.is_visible = not doc_to_toggle.is_visible
            doc_to_toggle.save(update_fields=['is_visible'])
            state_txt = 'hiển thị lại' if doc_to_toggle.is_visible else 'ẩn'
            messages.success(request, f'Đã {state_txt} tài liệu "{doc_to_toggle.title}".')
            return redirect('document_category', cate_id=cate_id)

    documents = Document.objects.select_related('creator', 'approver').prefetch_related(
        'access_permissions__department'
    ).filter(
        category=category,
        status='APPROVED'
    )

    if not is_mgr:
        documents = documents.filter(is_visible=True)

    if not is_admin:
        user_dept = _get_user_department(user)
        access_filter = Q(access_scope='ALL') | Q(creator=user)
        if user_dept:
            access_filter |= Q(access_scope='DEPARTMENT', access_permissions__department=user_dept)
        if is_department_manager(user):
            managed_ids = list(user.managed_departments.values_list('id', flat=True))
            access_filter |= (
                Q(creator__employee_info__dep_id__in=managed_ids)
                | Q(access_permissions__department_id__in=managed_ids)
                | Q(creator__employee_info__dep__isnull=True)
            )
        documents = documents.filter(access_filter).distinct()

    if search_query:
        documents = documents.filter(title__icontains=search_query)

    docs_list = list(documents)
    for d in docs_list:
        d.can_manage = _can_manage_doc(user, d)

    context = {
        'cate_id': cate_id,
        'category': category,
        'documents': docs_list,
        'pending_count': _pending_docs_for_user(user).count(),
        'search_query': search_query,
        'is_manager': is_mgr,
    }
    return render(request, 'documents_category.html', context)


# 8. Tạo danh mục tài liệu mới (/documents/category/create/)
def document_category_create(request):
    denied = _require_doc_access(request)
    if denied:
        return denied

    if request.method == 'POST':
        form = DocumentCategoryForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data['name'].strip()
            if DocumentCategory.objects.filter(name__iexact=name).exists():
                messages.error(request, f"Danh mục '{name}' đã tồn tại trong hệ thống.")
            else:
                category = form.save(commit=False)
                category.display_order = DocumentCategory.objects.count() + 1
                category.save()
                messages.success(request, f'Danh mục "{category.name}" đã được tạo thành công.')
                return redirect('documents')
    else:
        form = DocumentCategoryForm()

    context = {
        'form': form,
        'pending_count': _pending_docs_for_user(request.user).count(),
        'is_manager': _is_manager(request.user),
    }
    return render(request, 'documents_category_create.html', context)
