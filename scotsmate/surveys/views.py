from django.contrib.auth.models import User
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.db.models import Exists, OuterRef, Q
from django.contrib import messages
from django.contrib.auth import login
from django.utils import timezone
from django.core.paginator import Paginator
import json
import collections
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from django.db import transaction
from .models import *
from home.models import *
from .forms import *


# Create your views here.
def SurveyList(request):
    if not request.user.is_authenticated:
        default_user = User.objects.filter(username='minhanh').first()
        if default_user:
            login(request, default_user)

    user = request.user
    query = request.GET.get('q', '').strip()

    # 1. Chọn ra các khảo sát thuộc quyền truy cập của user, đang hiển thị và chưa quá hạn
    surveys_qs = Survey.objects.filter(
        access_permissions__emp=user,
        access_permissions__can_respond=True,
        is_visible=True,
    ).filter(
        Q(response_deadline__isnull=True) | Q(response_deadline__gt=timezone.now())
    ).distinct().select_related('department', 'creator').order_by('-date_created')

    if query:
        surveys_qs = surveys_qs.filter(name__icontains=query)

    # 2. Lấy thông tin các phản hồi của user đối với các khảo sát này để tính số lượt đã nộp & nháp
    user_responses = SurveyResponse.objects.filter(
        survey__in=surveys_qs,
        respondent=user
    ).values('survey_id', 'submission_date')

    submitted_counts = collections.Counter()
    has_draft_map = set()

    for ur in user_responses:
        sid = ur['survey_id']
        if ur['submission_date'] is not None:
            submitted_counts[sid] += 1
        else:
            has_draft_map.add(sid)

    surveys_list = []
    for s in surveys_qs:
        sub_count = submitted_counts[s.id]
        has_draft = (s.id in has_draft_map)
        max_limit = s.response_limit or 1

        # Điều kiện: User chưa trả lời quá số lần được trả lời tối đa (response_limit)
        if sub_count < max_limit:
            s.user_submitted_count = sub_count
            s.has_draft = has_draft
            s.is_submitted = (sub_count > 0)
            s.max_limit = max_limit

            if has_draft:
                s.status_label = 'Lưu nháp'
                s.status_badge_class = 'doc-badge-in-progress'
                s.btn_label = 'Tiếp tục'
            elif sub_count > 0:
                s.status_label = 'Đã thực hiện'
                s.status_badge_class = 'doc-badge-approved'
                s.btn_label = 'Thực hiện lại'
            else:
                s.status_label = 'Chưa thực hiện'
                s.status_badge_class = 'doc-badge-pending'
                s.btn_label = 'Thực hiện'

            surveys_list.append(s)

    context = {
        'surveys': surveys_list,
        'search_query': query,
    }
    return render(request, 'list.html', context)

def SurveyHistory(request):
    if not request.user.is_authenticated:
        default_user = User.objects.filter(username='minhanh').first()
        if default_user:
            login(request, default_user)

    user = request.user
    query = request.GET.get('q', '').strip()

    responses = SurveyResponse.objects.filter(
        respondent=user,
        submission_date__isnull=False
    ).select_related('survey', 'survey__department').order_by('-submission_date')

    if query:
        responses = responses.filter(survey__name__icontains=query)

    total_count = responses.count()
    paginator = Paginator(responses, 10)  # 10 bài trên mỗi trang
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'search_query': query,
        'total_count': total_count,
    }
    return render(request, 'history.html', context)

def SurveyTake(request, survey_pk):
    if not request.user.is_authenticated:
        default_user = User.objects.filter(username='minhanh').first()
        if default_user:
            login(request, default_user)

    current_user = request.user
    survey = get_object_or_404(Survey, pk=survey_pk)

    # Kiểm tra quyền truy cập: nếu không phải creator / manager / admin thì phải có SurveyAccess
    has_access = SurveyAccess.objects.filter(survey=survey, emp=current_user, can_respond=True).exists()
    is_admin = current_user.is_staff or current_user.is_superuser
    is_creator = (survey.creator_id == current_user.id)
    is_manager = bool(survey.department and survey.department.manager_id == current_user.id)

    if not (has_access or is_admin or is_creator or is_manager):
        messages.error(request, 'Bạn không có quyền tham gia trả lời bài khảo sát này.')
        return redirect('MySurvey')

    # Thống kê số lần user đã nộp khảo sát này và giới hạn cho phép
    user_submitted_qs = SurveyResponse.objects.filter(
        survey=survey,
        respondent=current_user,
        submission_date__isnull=False
    ).order_by('-submission_date')
    user_submitted_count = user_submitted_qs.count()
    max_limit = survey.response_limit or 1
    can_retake = (user_submitted_count < max_limit)

    view_mode_param = request.GET.get('mode')
    view_response_id = request.GET.get('response_id')

    draft_response = SurveyResponse.objects.filter(
        survey=survey,
        respondent=current_user,
        submission_date__isnull=True
    ).first()

    # Xác định view_mode:
    # 1. Nếu có tham số mode='view' hoặc response_id (ví dụ bấm từ Lịch sử khảo sát)
    # 2. Hoặc nếu user đã trả lời đủ/quá số lần tối đa quy định (không được làm lại nữa)
    if view_mode_param == 'view' or view_response_id or (not can_retake and user_submitted_count > 0):
        is_view_mode = True
        if view_response_id:
            existing_response = SurveyResponse.objects.filter(pk=view_response_id, survey=survey, respondent=current_user).first()
            if not existing_response:
                existing_response = user_submitted_qs.first()
        else:
            existing_response = user_submitted_qs.first()
        is_submitted = True
        is_draft = False
    else:
        # Chế độ làm bài / làm lại (thực hiện hoặc thực hiện lại)
        is_view_mode = False
        is_submitted = False
        existing_response = draft_response
        is_draft = bool(draft_response)

        # Kiểm tra thời hạn và trạng thái nhận phản hồi
        if survey.response_deadline and survey.response_deadline < timezone.now():
            messages.error(request, 'Khảo sát này đã hết hạn nhận phản hồi.')
            return redirect('MySurvey')

        if not survey.is_respondable:
            messages.error(request, 'Khảo sát này hiện đang tạm ngưng nhận phản hồi.')
            return redirect('MySurvey')

        if not can_retake:
            messages.info(request, f'Bạn đã hoàn thành đủ {max_limit} lần cho khảo sát này.')
            return redirect('MySurvey')

    # Lấy danh sách câu hỏi
    details = list(survey.details.select_related('question_type').all().order_by('id'))

    # Lấy câu trả lời đã lưu (nếu có bản nháp hoặc xem lại bài nộp)
    user_answers = {}
    if existing_response:
        for rd in existing_response.details.all():
            user_answers[rd.question_id] = rd.answer

    # Chuẩn bị dữ liệu MC và Essay
    mc_ids = [d.object_id for d in details if d.question_type_id == 26]
    essay_ids = [d.object_id for d in details if d.question_type_id == 25]

    mc_map = {
        mc.id: mc
        for mc in SurveyMultipleChoiceQuestion.objects.filter(id__in=mc_ids).prefetch_related('choices')
    }
    essay_map = {
        eq.id: eq
        for eq in SurveyEssayQuestion.objects.filter(id__in=essay_ids)
    }

    questions_data = []
    answered_count = 0

    for idx, d in enumerate(details, start=1):
        raw_ans = user_answers.get(d.id, '')
        q_item = {
            'id': d.id,
            'index': idx,
            'caption': d.caption,
            'is_required': d.is_required,
            'is_mc': (d.question_type_id == 26),
            'is_essay': (d.question_type_id == 25),
            'user_answer': raw_ans,
            'selected_choice_ids': [],
            'choices': [],
            'max_choice': 1,
            'max_character': None,
            'is_grid': False,
            'error_msg': None,
        }

        if d.question_type_id == 26:
            mc_obj = mc_map.get(d.object_id)
            if mc_obj:
                q_item['max_choice'] = mc_obj.max_choice
                q_item['choices'] = list(mc_obj.choices.all())
                # Bố trí dạng lưới nếu các nhãn ngắn (<= 25 ký tự) và ít hơn hoặc bằng 5 lựa chọn
                if len(q_item['choices']) <= 5 and all(len(c.content) <= 25 for c in q_item['choices']):
                    q_item['is_grid'] = True

            if raw_ans:
                try:
                    parsed = json.loads(raw_ans)
                    if isinstance(parsed, list):
                        q_item['selected_choice_ids'] = [str(x) for x in parsed]
                    else:
                        q_item['selected_choice_ids'] = [str(parsed)]
                except Exception:
                    q_item['selected_choice_ids'] = [x.strip() for x in raw_ans.split(',') if x.strip()]

            if q_item['selected_choice_ids']:
                answered_count += 1

        elif d.question_type_id == 25:
            eq_obj = essay_map.get(d.object_id)
            if eq_obj:
                q_item['max_character'] = eq_obj.max_character
            if raw_ans and raw_ans.strip():
                answered_count += 1

        questions_data.append(q_item)

    # Xử lý khi người dùng gửi form (POST)
    if request.method == 'POST':
        if is_view_mode:
            messages.warning(request, 'Khảo sát này đã được gửi trước đó, bạn không thể gửi lại.')
            return redirect('SurveyTake', survey_pk=survey_pk)

        action = request.POST.get('action', 'submit')  # 'draft' hoặc 'submit'
        form_errors = {}
        new_answers = {}
        recalculated_answered = 0

        for q in questions_data:
            qid = q['id']
            field_name = f'question_{qid}'

            if q['is_mc']:
                selected = request.POST.getlist(field_name)
                selected = [str(s).strip() for s in selected if str(s).strip()]
                new_answers[qid] = json.dumps(selected)
                q['selected_choice_ids'] = selected

                if selected:
                    recalculated_answered += 1

                if action == 'submit':
                    if q['is_required'] and not selected:
                        form_errors[qid] = 'Vui lòng chọn câu trả lời cho câu hỏi bắt buộc này.'
                    elif q['max_choice'] and len(selected) > q['max_choice']:
                        form_errors[qid] = f'Bạn chỉ được chọn tối đa {q["max_choice"]} phương án.'
            elif q['is_essay']:
                text_val = request.POST.get(field_name, '').strip()
                new_answers[qid] = text_val
                q['user_answer'] = text_val

                if text_val:
                    recalculated_answered += 1

                if action == 'submit':
                    if q['is_required'] and not text_val:
                        form_errors[qid] = 'Vui lòng nhập nội dung cho câu hỏi bắt buộc này.'
                    elif q['max_character'] and len(text_val) > q['max_character']:
                        form_errors[qid] = f'Nội dung không được vượt quá {q["max_character"]} ký tự (hiện có {len(text_val)} ký tự).'

            if qid in form_errors:
                q['error_msg'] = form_errors[qid]

        # Nếu có lỗi khi submit thì trả về template kèm thông báo lỗi tại chỗ
        if action == 'submit' and form_errors:
            messages.error(request, 'Vui lòng hoàn thành các câu hỏi được cảnh báo trước khi gửi bài.')
            total_q = len(questions_data)
            progress_pct = int((recalculated_answered / total_q) * 100) if total_q > 0 else 0
            return render(request, 'detail.html', {
                'survey': survey,
                'questions': questions_data,
                'is_view_mode': False,
                'is_draft': is_draft,
                'existing_response': existing_response,
                'user_submitted_count': user_submitted_count,
                'max_limit': max_limit,
                'total_questions': total_q,
                'answered_count': recalculated_answered,
                'progress_percent': progress_pct,
            })

        # Lưu vào Database
        with transaction.atomic():
            if not existing_response:
                existing_response = SurveyResponse.objects.create(
                    survey=survey,
                    respondent=current_user,
                    submission_date=timezone.now() if action == 'submit' else None
                )
            else:
                if action == 'submit':
                    existing_response.submission_date = timezone.now()
                    existing_response.save()

            for qid, ans_val in new_answers.items():
                detail_obj = next((d for d in details if d.id == qid), None)
                if detail_obj:
                    SurveyResponseDetail.objects.update_or_create(
                        survey_response=existing_response,
                        question=detail_obj,
                        defaults={'answer': ans_val}
                    )

        if action == 'draft':
            messages.success(request, 'Đã lưu bản nháp thành công! Bạn có thể tiếp tục thực hiện sau.')
            return redirect('MySurvey')
        else:
            messages.success(request, 'Gửi bài khảo sát thành công! Cảm ơn bạn đã tham gia đóng góp ý kiến.')
            return redirect('SurveyHistory')

    total_q = len(questions_data)
    progress_pct = int((answered_count / total_q) * 100) if total_q > 0 else 0

    return render(request, 'detail.html', {
        'survey': survey,
        'questions': questions_data,
        'is_view_mode': is_view_mode,
        'is_draft': is_draft,
        'existing_response': existing_response,
        'user_submitted_count': user_submitted_count,
        'max_limit': max_limit,
        'total_questions': total_q,
        'answered_count': answered_count,
        'progress_percent': progress_pct,
    })


def assign_survey_permissions(survey, branches, departments, manager):
    """
    Hàm hỗ trợ: Cấp quyền trả lời và quyền xem kết quả khảo sát.
    """
    respondents = User.objects.filter(employee_info__status='ACTIVE')

    if branches and branches.exists():
        respondents = respondents.filter(employee_info__branch__in=branches)

    if departments and departments.exists():
        respondents = respondents.filter(employee_info__dep__in=departments)

    access_dict = {}
    for u in respondents:
        access_dict[u.id] = {
            'can_respond': True,
            'can_view_responses': False
        }

    # Cấp quyền cho trưởng phòng
    if manager:
        if manager.id in access_dict:
            access_dict[manager.id]['can_view_responses'] = True
        else:
            access_dict[manager.id] = {
                'can_respond': False,
                'can_view_responses': True
            }

    access_objs = [
        SurveyAccess(
            emp_id=uid,
            survey=survey,
            can_respond=perms['can_respond'],
            can_view_responses=perms['can_view_responses']
        )
        for uid, perms in access_dict.items()
    ]

    if access_objs:
        SurveyAccess.objects.bulk_create(access_objs)


def process_survey_questions(survey, raw_json):
    """
    Hàm hỗ trợ: Parse JSON và tạo các object câu hỏi (trắc nghiệm, tự luận, chi tiết).
    """
    if not raw_json:
        return

    questions_list = json.loads(raw_json)
    for q in questions_list:
        caption = q.get('caption', '').strip()
        if not caption:
            continue

        q_type = int(q.get('question_type_id'))
        is_req = q.get('is_required')

        if q_type == 26:  # Trắc nghiệm
            max_c = int(q.get('max_choice', 1))
            choices = q.get('choices', [])

            mc_q = SurveyMultipleChoiceQuestion.objects.create(max_choice=max_c)

            choice_objs = [
                SurveyQuestionChoice(question=mc_q, content=str(c).strip())
                for c in choices if str(c).strip()
            ]
            if choice_objs:
                SurveyQuestionChoice.objects.bulk_create(choice_objs)

            # Lưu ý: Đảm bảo model được gọi đúng (không bị trùng tên với view)
            SurveyDetail.objects.create(
                survey=survey,
                question_type_id=26,
                object_id=mc_q.id,
                caption=caption,
                is_required=is_req
            )

        elif q_type == 25:  # Tự luận
            essay_q = SurveyEssayQuestion.objects.create(
                max_character=int(q['max_character']) if q.get('max_character') else None
            )

            SurveyDetail.objects.create(
                survey=survey,
                question_type_id=25,
                object_id=essay_q.id,
                caption=caption,
                is_required=is_req
            )


def SurveyCreate(request):
    if request.method == 'POST':
        survey_info = Create(request.POST)
        if survey_info.is_valid():
            with transaction.atomic():
                # 1. Lưu thông tin cơ bản của khảo sát
                survey = survey_info.save(commit=False)
                survey.creator = request.user
                survey.department = request.user.employee_info.dep

                manager = survey.department.manager
                if manager == request.user:
                    survey.is_approved = True
                else:
                    survey.approver = manager
                    survey.is_approved = False
                survey.save()

                # 2. Gọi hàm gán quyền truy cập
                branches = survey_info.cleaned_data.get('branches')
                departments = survey_info.cleaned_data.get('departments')
                assign_survey_permissions(survey, branches, departments, manager)

                # 3. Gọi hàm xử lý và lưu câu hỏi
                raw_json = survey_info.cleaned_data.get('questions_data')
                process_survey_questions(survey, raw_json)

            return redirect('MySurvey')
    else:
        survey_info = Create()

    context = {
        'survey_info': survey_info,
    }
    return render(request, 'create.html', context)

def SurveyApproveList(request):
    if not request.user.is_authenticated:
        default_user = User.objects.filter(username='minhanh').first()
        if default_user:
            login(request, default_user)

    user = request.user
    managed_departments = user.managed_departments.all()
    is_admin = user.is_staff or user.is_superuser

    # Kiểm tra quyền: Chỉ Trưởng phòng (hoặc Admin/Superuser) mới được truy cập
    if not (managed_departments.exists() or is_admin):
        messages.error(request, 'Bạn không có quyền truy cập trang phê duyệt khảo sát.')
        return redirect('MySurvey')

    query = request.GET.get('q', '').strip()

    # Lọc khảo sát:
    # 1. Thuộc các phòng ban do user làm trưởng phòng
    # 2. Chưa duyệt (is_approved=False)
    # 3. Chưa quá hạn (response_deadline > now() hoặc không đặt hạn)
    if is_admin and not managed_departments.exists():
        surveys_qs = Survey.objects.filter(is_approved=False)
    else:
        surveys_qs = Survey.objects.filter(
            department__in=managed_departments,
            is_approved=False
        )

    surveys_qs = surveys_qs.filter(
        Q(response_deadline__isnull=True) | Q(response_deadline__gt=timezone.now())
    ).select_related('creator', 'department').order_by('-date_created')

    if query:
        surveys_qs = surveys_qs.filter(
            Q(name__icontains=query) |
            Q(creator__first_name__icontains=query) |
            Q(creator__last_name__icontains=query) |
            Q(creator__username__icontains=query) |
            Q(department__name__icontains=query)
        )

    total_count = surveys_qs.count()
    paginator = Paginator(surveys_qs, 10)  # 10 bài trên mỗi trang
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'search_query': query,
        'total_count': total_count,
    }
    return render(request, 'approve_list.html', context)

def SurveyApproveDetail(request, survey_pk=None):
    if not request.user.is_authenticated:
        default_user = User.objects.filter(username='minhanh').first()
        if default_user:
            login(request, default_user)

    current_user = request.user
    survey = get_object_or_404(
        Survey.objects.select_related('creator', 'department', 'department__manager'),
        pk=survey_pk
    )

    # Kiểm tra quyền: phải là Trưởng phòng của phòng ban khảo sát hoặc Admin/Superuser
    is_manager = current_user.managed_departments.filter(id=survey.department_id).exists()
    is_admin = current_user.is_staff or current_user.is_superuser

    if not (is_manager or is_admin):
        messages.error(request, 'Bạn không có quyền thẩm định bài khảo sát này.')
        return redirect('SurveyApproveList')

    # Xử lý POST (Từ chối xóa khảo sát, hoặc Phê duyệt & Phát hành)
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'reject':
            survey_name = survey.name
            survey.delete()
            messages.success(request, f'Đã từ chối và xóa thành công khảo sát "{survey_name}".')
            return redirect('SurveyApproveList')

        elif action == 'approve':
            survey.is_approved = True
            survey.approver = current_user
            survey.save()
            messages.success(request, f'Đã phê duyệt và phát hành khảo sát "{survey.name}" thành công.')
            return redirect('SurveyApproveList')

    # Lấy danh sách câu hỏi
    details = list(survey.details.select_related('question_type').all().order_by('id'))
    mc_ids = [d.object_id for d in details if d.question_type_id == 26]
    essay_ids = [d.object_id for d in details if d.question_type_id == 25]

    mc_map = {
        mc.id: mc
        for mc in SurveyMultipleChoiceQuestion.objects.filter(id__in=mc_ids).prefetch_related('choices')
    }
    essay_map = {
        eq.id: eq
        for eq in SurveyEssayQuestion.objects.filter(id__in=essay_ids)
    }

    questions_data = []
    for idx, d in enumerate(details, start=1):
        q_item = {
            'id': d.id,
            'index': idx,
            'caption': d.caption,
            'is_required': d.is_required,
            'is_mc': (d.question_type_id == 26),
            'is_essay': (d.question_type_id == 25),
            'choices': [],
            'max_choice': 1,
            'max_character': None,
        }
        if d.question_type_id == 26:
            mc_obj = mc_map.get(d.object_id)
            if mc_obj:
                q_item['max_choice'] = mc_obj.max_choice
                q_item['choices'] = list(mc_obj.choices.all())
        elif d.question_type_id == 25:
            eq_obj = essay_map.get(d.object_id)
            if eq_obj:
                q_item['max_character'] = eq_obj.max_character

        questions_data.append(q_item)

    # Lấy danh sách phân quyền từ SurveyAccess
    accesses = SurveyAccess.objects.filter(survey=survey).select_related(
        'emp', 'emp__employee_info', 'emp__employee_info__dep'
    )

    def get_initials(user):
        fn = user.get_full_name().strip()
        if fn:
            pts = fn.split()
            if len(pts) >= 2:
                return (pts[0][0] + pts[-1][0]).upper()
            return fn[:2].upper()
        return user.username[:2].upper()

    def get_dep_name(user):
        if hasattr(user, 'employee_info') and user.employee_info and user.employee_info.dep:
            return user.employee_info.dep.name
        return survey.department.name if survey.department else 'Chưa phân bổ'

    participants_map = {}
    managers_map = {}

    for acc in accesses:
        u = acc.emp
        initials = get_initials(u)
        full_name = u.get_full_name() or u.username
        email = u.email or (u.employee_info.email if hasattr(u, 'employee_info') and u.employee_info and u.employee_info.email else '') or f'{u.username}@scotsenglish.edu.vn'
        dep_name = get_dep_name(u)

        user_info = {
            'username': u.username,
            'full_name': full_name,
            'initials': initials,
            'email': email,
            'department_name': dep_name,
        }

        if acc.can_respond:
            participants_map[u.username] = user_info
        if acc.can_view_responses:
            managers_map[u.username] = user_info

    # Đảm bảo nếu trưởng phòng phụ trách chưa có trong danh sách managers thì bổ sung vào
    if survey.department and survey.department.manager:
        mgr = survey.department.manager
        if mgr.username not in managers_map:
            managers_map[mgr.username] = {
                'username': mgr.username,
                'full_name': mgr.get_full_name() or mgr.username,
                'initials': get_initials(mgr),
                'email': mgr.email or f'{mgr.username}@scotsenglish.edu.vn',
                'department_name': survey.department.name,
            }

    context = {
        'survey': survey,
        'questions': questions_data,
        'participants': list(participants_map.values()),
        'managers': list(managers_map.values()),
    }
    return render(request, 'approve_detail.html', context)

def SurveyPublished(request):
    if not request.user.is_authenticated:
        default_user = User.objects.filter(username='minhanh').first()
        if default_user:
            login(request, default_user)

    current_user = request.user
    is_admin = current_user.is_staff or current_user.is_superuser

    # 1. Chỉ khảo sát mình được gán quyền xem kết quả (can_view_responses=True) và admin/superadmin mới được xem
    # Lưu ý: Hiển thị cả các khảo sát đã ẩn (is_visible=False) để người quản lý/Admin theo dõi và có thể Bỏ ẩn
    if is_admin:
        surveys_qs = Survey.objects.filter(is_approved=True)
    else:
        surveys_qs = Survey.objects.filter(
            is_approved=True,
            access_permissions__emp=current_user,
            access_permissions__can_view_responses=True
        ).distinct()

    # Tìm kiếm theo tiêu đề
    query = request.GET.get('q', '').strip()
    if query:
        surveys_qs = surveys_qs.filter(name__icontains=query)

    surveys_qs = surveys_qs.select_related('department', 'creator').order_by('-date_created')

    total_count = surveys_qs.count()
    paginator = Paginator(surveys_qs, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Tính toán số liệu thống kê cho các khảo sát trong trang hiện tại
    now = timezone.now()
    enriched_items = []

    def get_initials(user):
        fn = user.get_full_name().strip()
        if fn:
            pts = fn.split()
            if len(pts) >= 2:
                return (pts[0][0] + pts[-1][0]).upper()
            return fn[:2].upper()
        return user.username[:2].upper()

    for s in page_obj:
        submitted_responses_qs = SurveyResponse.objects.filter(survey=s, submission_date__isnull=False)
        submitted_count = submitted_responses_qs.count()
        submitted_user_ids = set(submitted_responses_qs.values_list('respondent_id', flat=True))

        participants_qs = SurveyAccess.objects.filter(survey=s, can_respond=True).select_related(
            'emp', 'emp__employee_info', 'emp__employee_info__dep'
        )
        target_count = participants_qs.count()

        if target_count > 0:
            completion_pct = int((submitted_count / target_count) * 100)
            response_display = f"{submitted_count} / {target_count}"
        elif s.response_limit:
            completion_pct = int((submitted_count / s.response_limit) * 100)
            response_display = f"{submitted_count} / {s.response_limit}"
        else:
            completion_pct = 100 if submitted_count > 0 else 0
            response_display = f"{submitted_count} lượt"

        completion_pct = min(completion_pct, 100)

        # Trạng thái: Đang mở nếu is_respondable=True và chưa quá hạn
        is_open = s.is_respondable and (s.response_deadline is None or s.response_deadline > now)

        # Danh sách người được gán quyền tham gia
        participants_list = []
        for acc in participants_qs:
            u = acc.emp
            full_name = u.get_full_name() or u.username
            email = u.email or (u.employee_info.email if hasattr(u, 'employee_info') and u.employee_info and u.employee_info.email else '') or f'{u.username}@scotsenglish.edu.vn'
            dep_name = (
                u.employee_info.dep.name
                if hasattr(u, 'employee_info') and u.employee_info and u.employee_info.dep
                else (s.department.name if s.department else 'Chưa phân bổ')
            )
            has_submitted = (u.id in submitted_user_ids)

            participants_list.append({
                'username': u.username,
                'full_name': full_name,
                'initials': get_initials(u),
                'email': email,
                'department_name': dep_name,
                'has_submitted': has_submitted,
            })

        enriched_items.append({
            'survey': s,
            'submitted_count': submitted_count,
            'target_count': target_count,
            'response_display': response_display,
            'completion_pct': completion_pct,
            'is_open': is_open,
            'participants': participants_list,
            'participants_json': json.dumps(participants_list, ensure_ascii=False),
        })

    page_obj.object_list = enriched_items

    context = {
        'page_obj': page_obj,
        'search_query': query,
        'total_count': total_count,
    }
    return render(request, 'published.html', context)

def ResponseOverview(request, rep_pk=None, survey_pk=None):
    if not request.user.is_authenticated:
        default_user = User.objects.filter(username='minhanh').first()
        if default_user:
            login(request, default_user)

    current_user = request.user
    survey_id = rep_pk or survey_pk
    survey = get_object_or_404(
        Survey.objects.select_related('department', 'creator'),
        pk=survey_id
    )

    # 1. Kiểm tra quyền truy cập: Chỉ admin/superadmin hoặc người được gán quyền can_view_responses
    is_admin = current_user.is_staff or current_user.is_superuser
    has_access = SurveyAccess.objects.filter(survey=survey, emp=current_user, can_view_responses=True).exists()

    if not (is_admin or has_access):
        messages.error(request, 'Bạn không có quyền xem báo cáo phản hồi của khảo sát này.')
        return redirect('SurveyPublished')

    # Xử lý POST điều chỉnh is_visible hoặc is_respondable
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'toggle_visible':
            survey.is_visible = not survey.is_visible
            survey.save(update_fields=['is_visible'])
            status_text = 'hiển thị trở lại' if survey.is_visible else 'ẩn khỏi danh sách chung'
            messages.success(request, f'Đã {status_text} bài khảo sát "{survey.name}".')
            return redirect('ResponseOverview', survey_pk=survey.id)

        elif action == 'toggle_respondable':
            survey.is_respondable = not survey.is_respondable
            survey.save(update_fields=['is_respondable'])
            status_text = 'tiếp tục mở nhận phản hồi' if survey.is_respondable else 'ngưng nhận phản hồi'
            messages.success(request, f'Đã {status_text} cho bài khảo sát "{survey.name}".')
            return redirect('ResponseOverview', survey_pk=survey.id)

    # 2. Thống kê số lượng phản hồi và chỉ tiêu
    submitted_responses = SurveyResponse.objects.filter(
        survey=survey,
        submission_date__isnull=False
    ).select_related('respondent', 'respondent__employee_info', 'respondent__employee_info__dep')

    total_responses = submitted_responses.count()
    target_count = SurveyAccess.objects.filter(survey=survey, can_respond=True).count()

    if target_count > 0:
        completion_pct = min(100, int((total_responses / target_count) * 100))
    elif survey.response_limit:
        completion_pct = min(100, int((total_responses / survey.response_limit) * 100))
    else:
        completion_pct = 100 if total_responses > 0 else 0

    now = timezone.now()
    is_open = survey.is_respondable and (survey.response_deadline is None or survey.response_deadline > now)

    # 3. Lấy danh sách câu hỏi và phân tích kết quả từng câu
    details = list(survey.details.select_related('question_type').all().order_by('id'))
    mc_ids = [d.object_id for d in details if d.question_type_id == 26]
    essay_ids = [d.object_id for d in details if d.question_type_id == 25]

    mc_map = {
        mc.id: mc
        for mc in SurveyMultipleChoiceQuestion.objects.filter(id__in=mc_ids).prefetch_related('choices')
    }
    essay_map = {
        eq.id: eq
        for eq in SurveyEssayQuestion.objects.filter(id__in=essay_ids)
    }

    # Gom các câu trả lời theo question_id
    response_details = SurveyResponseDetail.objects.filter(
        survey_response__in=submitted_responses,
        question__in=details
    ).select_related('survey_response__respondent', 'survey_response__respondent__employee_info', 'survey_response__respondent__employee_info__dep')

    rd_by_question = collections.defaultdict(list)
    for rd in response_details:
        rd_by_question[rd.question_id].append(rd)

    questions_data = []
    for idx, d in enumerate(details, start=1):
        q_item = {
            'id': d.id,
            'index': idx,
            'caption': d.caption,
            'is_required': d.is_required,
            'is_mc': (d.question_type_id == 26),
            'is_essay': (d.question_type_id == 25),
            'choices': [],
            'answers': [],
            'max_choice': 1,
            'max_character': None,
        }

        if d.question_type_id == 26:
            mc_obj = mc_map.get(d.object_id)
            if mc_obj:
                q_item['max_choice'] = mc_obj.max_choice
                all_choices = list(mc_obj.choices.all())

                # Đếm số phiếu cho từng phương án
                votes = collections.Counter()
                for rd in rd_by_question[d.id]:
                    try:
                        parsed = json.loads(rd.answer)
                        if isinstance(parsed, list):
                            for cid in parsed:
                                votes[str(cid)] += 1
                        elif parsed is not None:
                            votes[str(parsed)] += 1
                    except Exception:
                        if rd.answer and str(rd.answer).strip():
                            votes[str(rd.answer).strip()] += 1

                for c in all_choices:
                    cnt = votes.get(str(c.id), 0)
                    pct = int(round((cnt / total_responses) * 100)) if total_responses > 0 else 0
                    q_item['choices'].append({
                        'id': c.id,
                        'content': c.content,
                        'count': cnt,
                        'pct': pct,
                    })

        elif d.question_type_id == 25:
            eq_obj = essay_map.get(d.object_id)
            if eq_obj:
                q_item['max_character'] = eq_obj.max_character

            ans_list = []
            for rd in rd_by_question[d.id]:
                text = (rd.answer or '').strip()
                if text:
                    # Cơ chế bảo mật ẩn danh đa lớp:
                    # Nếu khảo sát là ẩn danh, triệt để KHÔNG lấy hay truyền thông tin người dùng (Họ tên, phòng ban) sang context
                    if survey.anonymous:
                        ans_list.append({
                            'text': text,
                            'respondent_name': 'Người phản hồi ẩn danh',
                            'department': None,
                            'submission_date': rd.survey_response.submission_date,
                            'is_anonymous': True,
                        })
                    else:
                        resp_user = rd.survey_response.respondent
                        dep_name = (
                            resp_user.employee_info.dep.name
                            if hasattr(resp_user, 'employee_info') and resp_user.employee_info and resp_user.employee_info.dep
                            else (survey.department.name if survey.department else '')
                        )
                        ans_list.append({
                            'text': text,
                            'respondent_name': resp_user.get_full_name() or resp_user.username,
                            'department': dep_name,
                            'submission_date': rd.survey_response.submission_date,
                            'is_anonymous': False,
                        })

            q_item['answers'] = ans_list

        questions_data.append(q_item)

    context = {
        'survey': survey,
        'total_responses': total_responses,
        'target_count': target_count,
        'completion_pct': completion_pct,
        'is_open': is_open,
        'questions': questions_data,
    }
    return render(request, 'responses_overview.html', context)

def ResponseDetail(request, rep_pk=None, survey_pk=None):
    if not request.user.is_authenticated:
        default_user = User.objects.filter(username='minhanh').first()
        if default_user:
            login(request, default_user)

    current_user = request.user
    survey_id = rep_pk or survey_pk
    survey = get_object_or_404(
        Survey.objects.select_related('department', 'creator'),
        pk=survey_id
    )

    # 1. Kiểm tra quyền truy cập: Chỉ admin/superadmin hoặc người được gán quyền can_view_responses
    is_admin = current_user.is_staff or current_user.is_superuser
    has_access = SurveyAccess.objects.filter(survey=survey, emp=current_user, can_view_responses=True).exists()

    if not (is_admin or has_access):
        messages.error(request, 'Bạn không có quyền xem chi tiết phản hồi của khảo sát này.')
        return redirect('SurveyPublished')

    # 2. Lấy danh sách câu hỏi trong khảo sát và map lựa chọn trắc nghiệm
    details = list(survey.details.select_related('question_type').all().order_by('id'))
    mc_ids = [d.object_id for d in details if d.question_type_id == 26]

    mc_choices_map = collections.defaultdict(dict)
    for mc in SurveyMultipleChoiceQuestion.objects.filter(id__in=mc_ids).prefetch_related('choices'):
        for c in mc.choices.all():
            mc_choices_map[mc.id][str(c.id)] = c.content

    # 3. Lấy danh sách các bài nộp đã hoàn thành
    responses_qs = SurveyResponse.objects.filter(
        survey=survey,
        submission_date__isnull=False
    ).select_related(
        'respondent', 'respondent__employee_info', 'respondent__employee_info__dep'
    ).order_by('-submission_date')

    # Tìm kiếm (chỉ tìm theo tên/phòng ban nếu khảo sát công khai)
    query = request.GET.get('q', '').strip()
    if query:
        if not survey.anonymous:
            responses_qs = responses_qs.filter(
                Q(respondent__first_name__icontains=query) |
                Q(respondent__last_name__icontains=query) |
                Q(respondent__username__icontains=query) |
                Q(respondent__employee_info__dep__name__icontains=query)
            )

    total_responses = responses_qs.count()
    paginator = Paginator(responses_qs, 10)  # 10 bài nộp trên mỗi trang
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Đánh số ẩn danh cố định theo thứ tự id bài nộp
    all_submitted_ids = list(SurveyResponse.objects.filter(survey=survey, submission_date__isnull=False).order_by('id').values_list('id', flat=True))
    anon_map = {rid: idx for idx, rid in enumerate(all_submitted_ids, start=1)}

    # Lấy toàn bộ chi tiết câu trả lời của các bài nộp trong trang hiện tại
    page_resp_ids = [r.id for r in page_obj]
    resp_details = SurveyResponseDetail.objects.filter(
        survey_response_id__in=page_resp_ids
    ).select_related('question')

    answers_map = collections.defaultdict(dict)
    for rd in resp_details:
        answers_map[rd.survey_response_id][rd.question_id] = rd.answer

    def get_initials(user):
        fn = user.get_full_name().strip()
        if fn:
            pts = fn.split()
            if len(pts) >= 2:
                return (pts[0][0] + pts[-1][0]).upper()
            return fn[:2].upper()
        return user.username[:2].upper()

    enriched_responses = []
    for resp in page_obj:
        u = resp.respondent
        resp_answers = answers_map[resp.id]

        qa_list = []
        for idx, d in enumerate(details, start=1):
            raw_ans = resp_answers.get(d.id, '')
            ans_display = []

            if d.question_type_id == 26:  # Trắc nghiệm
                mc_choice_dict = mc_choices_map.get(d.object_id, {})
                selected_ids = []
                if raw_ans:
                    try:
                        parsed = json.loads(raw_ans)
                        if isinstance(parsed, list):
                            selected_ids = [str(x) for x in parsed]
                        elif parsed is not None:
                            selected_ids = [str(parsed)]
                    except Exception:
                        selected_ids = [str(raw_ans).strip()]

                for cid in selected_ids:
                    choice_text = mc_choice_dict.get(cid, f"Lựa chọn #{cid}")
                    ans_display.append(choice_text)

            elif d.question_type_id == 25:  # Tự luận
                if raw_ans and str(raw_ans).strip():
                    ans_display.append(str(raw_ans).strip())

            qa_list.append({
                'index': idx,
                'caption': d.caption,
                'is_mc': (d.question_type_id == 26),
                'is_essay': (d.question_type_id == 25),
                'is_required': d.is_required,
                'answers': ans_display,
                'has_answered': bool(ans_display),
            })

        if survey.anonymous:
            anon_no = anon_map.get(resp.id, resp.id)
            item_data = {
                'id': resp.id,
                'respondent_name': f"Người phản hồi ẩn danh #{anon_no}",
                'initials': f"#{anon_no}",
                'department_name': None,
                'submission_date_display': resp.submission_date.strftime("%d/%m/%Y"),
                'is_anonymous': True,
                'qa_list': qa_list,
                'qa_json': json.dumps(qa_list, ensure_ascii=False),
            }
        else:
            full_name = u.get_full_name() or u.username
            dep_name = (
                u.employee_info.dep.name
                if hasattr(u, 'employee_info') and u.employee_info and u.employee_info.dep
                else 'Chưa phân bổ'
            )
            item_data = {
                'id': resp.id,
                'respondent_name': full_name,
                'initials': get_initials(u),
                'department_name': dep_name,
                'email': u.email or (u.employee_info.email if hasattr(u, 'employee_info') and u.employee_info and u.employee_info.email else '') or f'{u.username}@scotsenglish.edu.vn',
                'submission_date_display': resp.submission_date.strftime("%H:%M %d/%m/%Y"),
                'is_anonymous': False,
                'qa_list': qa_list,
                'qa_json': json.dumps(qa_list, ensure_ascii=False),
            }

        enriched_responses.append(item_data)

    page_obj.object_list = enriched_responses

    context = {
        'survey': survey,
        'page_obj': page_obj,
        'search_query': query,
        'total_responses': total_responses,
    }
    return render(request, 'responses_detail.html', context)

def SurveyExportExcel(request, survey_pk):
    if not request.user.is_authenticated:
        default_user = User.objects.filter(username='minhanh').first()
        if default_user:
            login(request, default_user)

    current_user = request.user
    survey = get_object_or_404(
        Survey.objects.select_related('department', 'creator'),
        pk=survey_pk
    )

    is_admin = current_user.is_staff or current_user.is_superuser
    has_access = SurveyAccess.objects.filter(survey=survey, emp=current_user, can_view_responses=True).exists()

    if not (is_admin or has_access):
        messages.error(request, 'Bạn không có quyền xuất báo cáo khảo sát này.')
        return redirect('SurveyPublished')

    wb = openpyxl.Workbook()

    # Styling constants
    header_fill = PatternFill(start_color="134C81", end_color="134C81", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    title_font = Font(name="Calibri", size=15, bold=True, color="134C81")
    bold_font = Font(name="Calibri", size=11, bold=True)
    normal_font = Font(name="Calibri", size=11)
    center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    left_align = Alignment(horizontal="left", vertical="center", wrap_text=True)
    thin_border_side = Side(border_style="thin", color="CBD5E1")
    thin_border = Border(left=thin_border_side, right=thin_border_side, top=thin_border_side, bottom=thin_border_side)

    # Sheet 1: Tổng quan phân tích
    ws_summary = wb.active
    ws_summary.title = "Tổng quan"
    ws_summary.views.sheetView[0].showGridLines = True

    # Title block
    ws_summary["A1"] = f"BÁO CÁO KẾT QUẢ KHẢO SÁT: {survey.name.upper()}"
    ws_summary["A1"].font = title_font
    ws_summary.row_dimensions[1].height = 28

    ws_summary["A3"] = "Đơn vị phụ trách:"
    ws_summary["A3"].font = bold_font
    ws_summary["B3"] = survey.department.name if survey.department else "Chưa phân bổ"

    ws_summary["A4"] = "Người tạo:"
    ws_summary["A4"].font = bold_font
    ws_summary["B4"] = survey.creator.get_full_name() or survey.creator.username

    ws_summary["A5"] = "Hình thức:"
    ws_summary["A5"].font = bold_font
    ws_summary["B5"] = "Ẩn danh" if survey.anonymous else "Công khai"

    submitted_responses = SurveyResponse.objects.filter(
        survey=survey,
        submission_date__isnull=False
    ).select_related('respondent', 'respondent__employee_info', 'respondent__employee_info__dep').order_by('id')
    total_responses = submitted_responses.count()
    target_count = SurveyAccess.objects.filter(survey=survey, can_respond=True).count()

    ws_summary["D3"] = "Tổng lượt phản hồi:"
    ws_summary["D3"].font = bold_font
    ws_summary["E3"] = f"{total_responses} / {target_count}" if target_count > 0 else f"{total_responses} lượt"

    ws_summary["D4"] = "Tỷ lệ hoàn thành:"
    ws_summary["D4"].font = bold_font
    pct_val = min(100, int((total_responses / target_count) * 100)) if target_count > 0 else (100 if total_responses > 0 else 0)
    ws_summary["E4"] = f"{pct_val}%"

    ws_summary["D5"] = "Ngày xuất báo cáo:"
    ws_summary["D5"].font = bold_font
    ws_summary["E5"] = timezone.localtime(timezone.now()).strftime("%H:%M %d/%m/%Y")

    # Section 2: Questions analysis
    row_num = 8
    ws_summary.cell(row=row_num, column=1, value="BẢNG TỔNG HỢP KẾT QUẢ THEO CÂU HỎI").font = Font(name="Calibri", size=13, bold=True, color="134C81")
    row_num += 1

    details = list(survey.details.select_related('question_type').all().order_by('id'))
    mc_ids = [d.object_id for d in details if d.question_type_id == 26]
    essay_ids = [d.object_id for d in details if d.question_type_id == 25]

    mc_map = {
        mc.id: mc
        for mc in SurveyMultipleChoiceQuestion.objects.filter(id__in=mc_ids).prefetch_related('choices')
    }
    essay_map = {
        eq.id: eq
        for eq in SurveyEssayQuestion.objects.filter(id__in=essay_ids)
    }

    response_details = SurveyResponseDetail.objects.filter(
        survey_response__in=submitted_responses,
        question__in=details
    ).select_related('survey_response__respondent', 'survey_response__respondent__employee_info', 'survey_response__respondent__employee_info__dep')

    rd_by_question = collections.defaultdict(list)
    for rd in response_details:
        rd_by_question[rd.question_id].append(rd)

    for idx, d in enumerate(details, start=1):
        ws_summary.cell(row=row_num, column=1, value=f"Câu {idx}: {d.caption}").font = bold_font
        row_num += 1

        if d.question_type_id == 26:
            mc_obj = mc_map.get(d.object_id)
            choices = list(mc_obj.choices.all()) if mc_obj else []

            votes = collections.Counter()
            for rd in rd_by_question[d.id]:
                try:
                    parsed = json.loads(rd.answer)
                    if isinstance(parsed, list):
                        for cid in parsed:
                            votes[str(cid)] += 1
                    elif parsed is not None:
                        votes[str(parsed)] += 1
                except Exception:
                    if rd.answer and str(rd.answer).strip():
                        votes[str(rd.answer).strip()] += 1

            headers = ["STT", "Phương án lựa chọn", "Số lượt chọn", "Tỷ lệ (%)"]
            for col_idx, h in enumerate(headers, start=1):
                cell = ws_summary.cell(row=row_num, column=col_idx, value=h)
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = center_align
                cell.border = thin_border
            row_num += 1

            for c_idx, c in enumerate(choices, start=1):
                cnt = votes.get(str(c.id), 0)
                pct = int(round((cnt / total_responses) * 100)) if total_responses > 0 else 0
                r_cells = [
                    ws_summary.cell(row=row_num, column=1, value=c_idx),
                    ws_summary.cell(row=row_num, column=2, value=c.content),
                    ws_summary.cell(row=row_num, column=3, value=cnt),
                    ws_summary.cell(row=row_num, column=4, value=f"{pct}%")
                ]
                r_cells[0].alignment = center_align
                r_cells[1].alignment = left_align
                r_cells[2].alignment = center_align
                r_cells[3].alignment = center_align
                for cell in r_cells:
                    cell.border = thin_border
                    cell.font = normal_font
                row_num += 1

        elif d.question_type_id == 25:
            essay_answers = [rd.answer.strip() for rd in rd_by_question[d.id] if rd.answer and rd.answer.strip()]
            cell_ans = ws_summary.cell(row=row_num, column=1, value=f"(Dạng tự luận: Đã thu thập được {len(essay_answers)} ý kiến phản hồi - Xem chi tiết tại Sheet 'Ý kiến tự luận')")
            cell_ans.font = Font(name="Calibri", italic=True, color="64748B")
            row_num += 1

        row_num += 1  # Dòng trống giữa các câu hỏi

    # Sheet 2: Danh sách câu trả lời tự luận
    has_essay = any(d.question_type_id == 25 for d in details)
    if has_essay:
        ws_essay = wb.create_sheet(title="Ý kiến tự luận")
        ws_essay.views.sheetView[0].showGridLines = True
        essay_headers = ["STT", "Câu hỏi", "Người phản hồi", "Phòng ban", "Thời gian gửi", "Nội dung phản hồi"]
        for col_idx, h in enumerate(essay_headers, start=1):
            cell = ws_essay.cell(row=1, column=col_idx, value=h)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = center_align
            cell.border = thin_border
        ws_essay.row_dimensions[1].height = 24

        e_row = 2
        stt = 1
        for d in details:
            if d.question_type_id == 25:
                for rd in rd_by_question[d.id]:
                    text = (rd.answer or '').strip()
                    if text:
                        if survey.anonymous:
                            r_name = f"Người phản hồi ẩn danh #{stt}"
                            r_dep = "-"
                            r_time = timezone.localtime(rd.survey_response.submission_date).strftime("%d/%m/%Y") if rd.survey_response.submission_date else "-"
                        else:
                            resp_user = rd.survey_response.respondent
                            r_name = resp_user.get_full_name() or resp_user.username
                            r_dep = resp_user.employee_info.dep.name if hasattr(resp_user, 'employee_info') and resp_user.employee_info and resp_user.employee_info.dep else (survey.department.name if survey.department else "-")
                            r_time = timezone.localtime(rd.survey_response.submission_date).strftime("%H:%M %d/%m/%Y") if rd.survey_response.submission_date else "-"

                        row_cells = [
                            ws_essay.cell(row=e_row, column=1, value=stt),
                            ws_essay.cell(row=e_row, column=2, value=d.caption),
                            ws_essay.cell(row=e_row, column=3, value=r_name),
                            ws_essay.cell(row=e_row, column=4, value=r_dep),
                            ws_essay.cell(row=e_row, column=5, value=r_time),
                            ws_essay.cell(row=e_row, column=6, value=text),
                        ]
                        row_cells[0].alignment = center_align
                        row_cells[1].alignment = left_align
                        row_cells[2].alignment = left_align
                        row_cells[3].alignment = center_align
                        row_cells[4].alignment = center_align
                        row_cells[5].alignment = left_align
                        for c in row_cells:
                            c.font = normal_font
                            c.border = thin_border
                        e_row += 1
                        stt += 1

    # Tự động canh độ rộng cột
    for sheet in wb.worksheets:
        for col in sheet.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = get_column_letter(col[0].column)
            sheet.column_dimensions[col_letter].width = min(max(max_len + 4, 12), 60)

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    filename = f"Bao_cao_khao_sat_{survey.id}.xlsx"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    wb.save(response)
    return response
