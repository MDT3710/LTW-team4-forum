from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Count, Q
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.utils import timezone

from .models import DocumentCategory, Document, DocumentUpdateProposal, DocumentAccess
from .forms import DocumentCreateForm, DocumentCategoryForm, DocumentEditForm
from home.models import Department
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
    if is_it_admin(user) or is_department_manager(user):
        return Document.objects.select_related('category', 'creator').prefetch_related(
            'access_permissions__department',
            'proposals__proposed_category',
            'proposals__submitted_by',
        ).filter(
            Q(status='PENDING') | Q(proposals__is_processed=False)
        ).distinct()
    return Document.objects.none()


def _can_manage_doc(user, doc):
    return _is_manager(user)


def _can_manage_category(user, category=None):
    return _is_manager(user)


def _visible_docs_queryset_for_user(user, category=None, include_hidden_for_manager=False):
    is_mgr = _is_manager(user)
    qs = Document.objects.select_related('creator', 'approver', 'category').prefetch_related(
        'access_permissions__department'
    ).filter(status='APPROVED')
    if category is not None:
        qs = qs.filter(category=category)
    if not (is_mgr and include_hidden_for_manager):
        qs = qs.filter(is_visible=True)
    if not is_mgr:
        user_dept = _get_user_department(user)
        access_filter = Q(access_scope='ALL') | Q(creator=user)
        if user_dept:
            access_filter |= Q(access_scope='DEPARTMENT', access_permissions__department=user_dept)
        qs = qs.filter(access_filter).distinct()
    return qs


def _sync_doc_access(doc, access_scope, selected_departments):
    doc.access_permissions.all().delete()
    if access_scope == 'DEPARTMENT' and selected_departments:
        DocumentAccess.objects.bulk_create([
            DocumentAccess(document=doc, department=dept) for dept in selected_departments
        ])

# 1. Thư viện tài liệu (/documents/)
def document_list(request):
    denied = _require_doc_access(request)
    if denied:
        return denied

    if request.method == 'POST' and 'delete_cat_id' in request.POST:
        cat_to_delete = get_object_or_404(DocumentCategory, id=request.POST.get('delete_cat_id'))
        if not _can_manage_category(request.user, cat_to_delete):
            return redirect_back_with_error(
                request,
                'Chỉ Trưởng phòng hoặc Admin mới có quyền xóa danh mục tài liệu.',
                fallback_url='documents',
            )
        cat_name = cat_to_delete.name
        cat_to_delete.delete()
        messages.success(request, f'Đã xóa danh mục "{cat_name}".')
        return redirect('documents')

    search_query = request.GET.get('q', '').strip()

    categories_qs = DocumentCategory.objects.select_related('creator').all()
    if search_query:
        categories_qs = categories_qs.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query)
        )

    visible_docs = _visible_docs_queryset_for_user(request.user, include_hidden_for_manager=False)
    counts_by_cat = dict(
        visible_docs.values('category_id').annotate(c=Count('id', distinct=True)).values_list('category_id', 'c')
    )

    is_mgr = _is_manager(request.user)
    categories = list(categories_qs)
    for cat in categories:
        cat.can_manage = is_mgr
        cat.doc_count = counts_by_cat.get(cat.id, 0)

    context = {
        'categories': categories,
        'pending_count': _pending_docs_for_user(request.user).count(),
        'search_query': search_query,
        'is_manager': is_mgr,
    }
    return render(request, 'documents.html', context)


# 2. Tạo mới tài liệu (/documents/create/)
def document_create(request):
    denied = _require_doc_access(request)
    if denied:
        return denied

    error_message = None
    is_mgr = _is_manager(request.user)

    # Kiểm tra hệ thống đã có danh mục chưa
    if not DocumentCategory.objects.exists():
        if is_mgr:
            messages.error(
                request,
                'Chưa có danh mục nào trong hệ thống. Vui lòng tạo ít nhất một danh mục trước khi đăng tài liệu.'
            )
            return redirect('document_category_create')
        messages.error(
            request,
            'Hệ thống hiện chưa có danh mục tài liệu nào. Vui lòng liên hệ Trưởng phòng để tạo danh mục trước khi đăng tải.'
        )
        return redirect('documents')

    if request.method == "POST":
        form = DocumentCreateForm(request.POST, request.FILES)
        if form.is_valid():
            title = form.cleaned_data['title']
            category = form.cleaned_data['category']
            description = form.cleaned_data['description']
            access_scope = form.cleaned_data.get('access_scope') or 'ALL'
            selected_departments = form.cleaned_data.get('departments', [])
            uploaded_files = form.cleaned_data['file']

            doc_status = 'APPROVED' if is_mgr else 'PENDING'
            approver_user = request.user if is_mgr else None
            approved_time = timezone.now() if is_mgr else None

            for index, f in enumerate(uploaded_files, start=1):
                doc_title = title if len(uploaded_files) == 1 else f"{title} ({index})"
                new_doc = Document.objects.create(
                    title=doc_title,
                    category=category,
                    description=description,
                    file=f,
                    access_scope=access_scope,
                    creator=request.user,
                    approver=approver_user,
                    approved_at=approved_time,
                    status=doc_status,
                    request_type='NEW',
                    is_visible=True,
                )
                if access_scope == 'DEPARTMENT':
                    _sync_doc_access(new_doc, access_scope, selected_departments)

            if is_mgr:
                messages.success(
                    request,
                    f'Tài liệu "{title}" đã được đăng tải trực tiếp lên thư viện thành công.'
                )
                return redirect('document_category', cate_id=category.id)

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
        'is_manager': is_mgr,
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
        doc_to_delete = get_object_or_404(Document, id=request.POST.get('delete_doc_id'))
        if doc_to_delete.creator_id != user.id and not _is_manager(user):
            return redirect_back_with_error(
                request,
                'Bạn chỉ được phép xóa tài liệu do mình đăng tải.',
                fallback_url='document_my_docs',
            )
        doc_to_delete.delete()
        messages.success(request, 'Đã xóa tài liệu của bạn.')
        return redirect('document_my_docs')

    my_documents = Document.objects.select_related('category', 'approver', 'creator').prefetch_related(
        'access_permissions__department',
        'proposals',
    ).filter(creator=user)

    if search_query:
        my_documents = my_documents.filter(
            Q(title__icontains=search_query) | Q(description__icontains=search_query)
        )

    paginator = Paginator(my_documents, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    docs_list = list(page_obj)
    for d in docs_list:
        d.has_pending_update = any(not p.is_processed for p in d.proposals.all())

    context = {
        'page_obj': page_obj,
        'documents': docs_list,
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
            'Bạn chỉ có quyền chỉnh sửa tài liệu do mình tạo hoặc thuộc phạm vi quản lý.',
            fallback_url='document_my_docs',
        )

    active_proposal = doc.proposals.filter(is_processed=False).first()
    error_message = None

    if request.method == 'POST':
        form = DocumentEditForm(request.POST, request.FILES, instance=doc)
        if form.is_valid():
            proposed_title = form.cleaned_data['title']
            proposed_category = form.cleaned_data['category']
            proposed_description = form.cleaned_data.get('description', '')
            proposed_scope = form.cleaned_data.get('access_scope') or doc.access_scope or 'ALL'
            selected_departments = form.cleaned_data.get('departments', [])

            if can_manage:
                doc.title = proposed_title
                doc.category = proposed_category
                doc.description = proposed_description
                doc.access_scope = proposed_scope
                doc.file = request.FILES.get('file') or doc.file
                doc.approver = request.user
                doc.approved_at = timezone.now()
                doc.status = 'APPROVED'
                doc.rejection_reason = ''
                doc.save()
                _sync_doc_access(doc, proposed_scope, selected_departments)
                doc.proposals.filter(is_processed=False).update(is_processed=True)
                messages.success(request, f'Đã cập nhật tài liệu "{doc.title}".')
                return redirect('document_category', cate_id=doc.category_id)

            if doc.status == 'APPROVED':
                proposed_file = request.FILES.get('file') or (
                    active_proposal.proposed_file
                    if active_proposal and active_proposal.proposed_file
                    else doc.file
                )
                doc.proposals.filter(is_processed=False).update(is_processed=True)
                DocumentUpdateProposal.objects.create(
                    document=doc,
                    proposed_title=proposed_title,
                    proposed_category=proposed_category,
                    proposed_description=proposed_description,
                    proposed_file=proposed_file,
                    proposed_scope=proposed_scope,
                    proposed_department_ids=[d.id for d in selected_departments] if proposed_scope == 'DEPARTMENT' else [],
                    submitted_by=request.user,
                    approver=doc.approver,
                )
                Document.objects.filter(id=doc.id).update(
                    request_type='UPDATE',
                    rejection_reason='',
                    updated_at=timezone.now(),
                )
                messages.success(
                    request,
                    f'Đề xuất chỉnh sửa tài liệu "{proposed_title}" đã được gửi phê duyệt. Bản gốc vẫn hiển thị cho đến khi được duyệt.'
                )
            else:
                doc.proposals.filter(is_processed=False).update(is_processed=True)
                doc.title = proposed_title
                doc.category = proposed_category
                doc.description = proposed_description
                doc.access_scope = proposed_scope
                doc.file = request.FILES.get('file') or doc.file
                doc.status = 'PENDING'
                doc.request_type = 'NEW'
                doc.rejection_reason = ''
                doc.save()
                _sync_doc_access(doc, proposed_scope, selected_departments)
                messages.success(
                    request,
                    f'Đã cập nhật tài liệu "{doc.title}" và giữ trạng thái chờ phê duyệt.'
                )
            return redirect('document_my_docs')
        else:
            for field_errors in form.errors.values():
                error_message = field_errors[0]
                break
    else:
        initial_data = {}
        if active_proposal and not can_manage:
            initial_data = {
                'title': active_proposal.proposed_title,
                'category': active_proposal.proposed_category_id or doc.category_id,
                'description': active_proposal.proposed_description,
                'access_scope': active_proposal.proposed_scope,
                'departments': active_proposal.proposed_department_ids or [],
            }
        form = DocumentEditForm(instance=doc, initial=initial_data)

    context = {
        'doc_id': id,
        'doc': doc,
        'active_proposal': active_proposal,
        'form': form,
        'error_message': error_message,
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
    pending_qs = _pending_docs_for_user(request.user)
    total_pending = pending_qs.count()

    filtered_qs = pending_qs
    if search_query:
        filtered_qs = filtered_qs.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(proposals__is_processed=False, proposals__proposed_title__icontains=search_query) |
            Q(proposals__is_processed=False, proposals__proposed_description__icontains=search_query)
        ).distinct()

    paginator = Paginator(filtered_qs, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    docs_list = list(page_obj)
    all_proposed_dept_ids = set()
    for d in docs_list:
        d.active_proposal = next((p for p in d.proposals.all() if not p.is_processed), None)
        if d.active_proposal and d.active_proposal.proposed_scope == 'DEPARTMENT':
            all_proposed_dept_ids.update(d.active_proposal.proposed_department_ids or [])

    dept_map = {}
    if all_proposed_dept_ids:
        dept_map = {
            dept.id: dept.name
            for dept in Department.objects.filter(id__in=all_proposed_dept_ids)
        }

    for d in docs_list:
        if d.active_proposal:
            if d.active_proposal.proposed_scope == 'DEPARTMENT':
                names = [dept_map[did] for did in (d.active_proposal.proposed_department_ids or []) if did in dept_map]
                d.display_scope = ', '.join(names) if names else 'Giới hạn phòng ban'
            else:
                d.display_scope = 'Toàn hệ thống'
        else:
            if d.access_scope == 'DEPARTMENT':
                names = [perm.department.name for perm in d.access_permissions.all()]
                d.display_scope = ', '.join(names) if names else 'Giới hạn phòng ban'
            else:
                d.display_scope = 'Toàn hệ thống'

    context = {
        'page_obj': page_obj,
        'pending_docs': docs_list,
        'pending_count': total_pending,
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
            'Bạn không có quyền phê duyệt tài liệu này.',
            fallback_url='document_approve',
        )

    proposal = doc.proposals.filter(is_processed=False).first()
    if doc.status != 'PENDING' and not proposal:
        messages.error(request, 'Tài liệu này không ở trạng thái chờ duyệt hoặc đã được xử lý trước đó.')
        return redirect('document_approve')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'approve':
            if proposal:
                doc.title = proposal.proposed_title
                if proposal.proposed_category:
                    doc.category = proposal.proposed_category
                if proposal.proposed_description is not None:
                    doc.description = proposal.proposed_description
                if proposal.proposed_file:
                    doc.file = proposal.proposed_file
                doc.access_scope = proposal.proposed_scope
                selected_depts = (
                    Department.objects.filter(id__in=proposal.proposed_department_ids)
                    if proposal.proposed_scope == 'DEPARTMENT' else []
                )
                _sync_doc_access(doc, proposal.proposed_scope, selected_depts)
                doc.proposals.filter(is_processed=False).update(is_processed=True)
            else:
                doc.is_visible = True

            doc.status = 'APPROVED'
            doc.approver = request.user
            doc.approved_at = timezone.now()
            doc.rejection_reason = ''
            doc.save()

            messages.success(request, f'Đã phê duyệt thành công tài liệu "{doc.title}".')

        elif action == 'reject':
            rejection_reason = (request.POST.get('rejection_reason') or '').strip()
            if not rejection_reason:
                messages.error(request, 'Vui lòng nhập lý do từ chối phê duyệt trước khi xác nhận.')
                return redirect('document_approve_detail', id=doc.id)

            if proposal:
                doc.proposals.filter(is_processed=False).update(is_processed=True)
                doc.rejection_reason = rejection_reason
                doc.save(update_fields=['rejection_reason', 'updated_at'])
                messages.error(
                    request,
                    f'Đã từ chối đề xuất chỉnh sửa tài liệu "{doc.title}". Bản gốc đã duyệt vẫn được giữ nguyên.'
                )
            else:
                doc.status = 'REJECTED'
                doc.rejection_reason = rejection_reason
                doc.save(update_fields=['status', 'rejection_reason', 'updated_at'])
                messages.error(request, f'Đã từ chối phê duyệt tài liệu "{doc.title}".')

        return redirect('document_approve')

    proposed_departments = (
        list(Department.objects.filter(id__in=proposal.proposed_department_ids))
        if (proposal and proposal.proposed_scope == 'DEPARTMENT') else []
    )

    context = {
        'doc_id': id,
        'doc': doc,
        'proposal': proposal,
        'proposed_departments': proposed_departments,
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

    # Xử lý xóa (người tạo hoặc Trưởng phòng/Admin) hoặc ẩn/hiện (Trưởng phòng/Admin)
    if request.method == 'POST':
        if 'delete_doc_id' in request.POST:
            doc_to_delete = get_object_or_404(Document, id=request.POST.get('delete_doc_id'), category=category)
            if doc_to_delete.creator_id != user.id and not is_mgr:
                return redirect_back_with_error(
                    request,
                    'Bạn chỉ được phép xóa tài liệu do mình đăng tải.',
                    fallback_url=f'/documents/{cate_id}/',
                )
            doc_title = doc_to_delete.title
            doc_to_delete.delete()
            messages.success(request, f'Đã xóa thành công tài liệu "{doc_title}".')
            return redirect('document_category', cate_id=cate_id)
        if 'toggle_visibility_id' in request.POST:
            if not is_mgr:
                return redirect_back_with_error(
                    request,
                    'Chỉ Trưởng phòng hoặc Admin mới có quyền ẩn/hiện tài liệu.',
                    fallback_url=f'/documents/{cate_id}/',
                )
            doc_to_toggle = get_object_or_404(Document, id=request.POST.get('toggle_visibility_id'), category=category)
            doc_to_toggle.is_visible = not doc_to_toggle.is_visible
            doc_to_toggle.save(update_fields=['is_visible'])
            state_txt = 'hiển thị lại' if doc_to_toggle.is_visible else 'ẩn'
            messages.success(request, f'Đã {state_txt} tài liệu "{doc_to_toggle.title}".')
            return redirect('document_category', cate_id=cate_id)

    documents = _visible_docs_queryset_for_user(user, category=category, include_hidden_for_manager=True)

    if search_query:
        documents = documents.filter(
            Q(title__icontains=search_query) | Q(description__icontains=search_query)
        )

    paginator = Paginator(documents, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    docs_list = list(page_obj)
    for d in docs_list:
        d.can_manage = is_mgr
        d.can_edit_delete = (d.creator_id == user.id or is_mgr)

    context = {
        'cate_id': cate_id,
        'category': category,
        'can_manage_category': _can_manage_category(user, category),
        'page_obj': page_obj,
        'documents': docs_list,
        'pending_count': _pending_docs_for_user(user).count(),
        'search_query': search_query,
        'is_manager': is_mgr,
    }
    return render(request, 'documents_category.html', context)


# 8. Tạo danh mục tài liệu mới (/documents/category/create/)
def document_category_create(request):
    denied = _require_doc_access(request, require_manager=True)
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
                category.creator = request.user
                category.display_order = DocumentCategory.objects.count() + 1
                category.save()
                messages.success(request, f'Danh mục "{category.name}" đã được tạo thành công.')
                return redirect('documents')
    else:
        form = DocumentCategoryForm()

    context = {
        'form': form,
        'pending_count': _pending_docs_for_user(request.user).count(),
        'is_manager': True,
    }
    return render(request, 'documents_category_create.html', context)


# 9. Chỉnh sửa danh mục tài liệu (/documents/category/<cate_id>/edit/)
def document_category_edit(request, cate_id):
    denied = _require_doc_access(request, require_manager=True)
    if denied:
        return denied

    category = get_object_or_404(DocumentCategory, id=cate_id)

    if request.method == 'POST':
        form = DocumentCategoryForm(request.POST, instance=category)
        if form.is_valid():
            name = form.cleaned_data['name'].strip()
            if DocumentCategory.objects.filter(name__iexact=name).exclude(id=category.id).exists():
                messages.error(request, f"Danh mục '{name}' đã tồn tại trong hệ thống.")
            else:
                form.save()
                messages.success(request, f'Đã cập nhật danh mục "{category.name}" thành công.')
                return redirect('documents')
    else:
        form = DocumentCategoryForm(instance=category)

    context = {
        'form': form,
        'editing_category': category,
        'pending_count': _pending_docs_for_user(request.user).count(),
        'is_manager': True,
    }
    return render(request, 'documents_category_create.html', context)