import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.db import transaction
from django.db.models import Q, Count
from datetime import datetime, date
from .models import (
    Course,
    CourseAccess,
    CourseMaterial,
    CourseExam,
    CourseExamQuestion,
    CourseQuestionChoice,
    CourseEnrollment,
    CourseExamResponse,
    CourseExamResponseDetail,
)
from home.models import Department, EmployeeInformation
from .forms import (
    CourseForm,
    CourseUpdateForm,
    CourseMaterialForm,
    CourseExamConfigForm,
    UserRegisterForm,
    UserLoginForm,
)


def get_course_exam(course):
    """Lấy bài thi an toàn của khóa học, tránh lỗi RelatedObjectDoesNotExist"""
    if not course:
        return None
    try:
        return course.exam
    except Exception:
        return None


def get_user_role(user):
    """
    Xác định vai trò THỰC TẾ của tài khoản người dùng:
    - 'trainer': Giảng viên / Quản lý đào tạo (is_staff=True, is_superuser=True, hoặc có quyền CourseAccess/creator)
    - 'trainee': Học viên / Giáo viên / Nhân viên (is_staff=False)
    """
    if not user or not user.is_authenticated:
        return None
    if user.is_staff or user.is_superuser:
        return 'trainer'
    if CourseAccess.objects.filter(emp=user, role__in=['trainer', 'assistant', 'manager']).exists():
        return 'trainer'
    if Course.objects.filter(creator=user).exists():
        return 'trainer'
    return 'trainee'


# ============================================================
# XÁC THỰC NGƯỜI DÙNG THẬT (REAL AUTHENTICATION)
# ============================================================

def login_view(request):
    """
    Trang đăng nhập thật của hệ thống:
    Tiếp nhận tài khoản và mật khẩu, kiểm tra qua UserLoginForm và authenticate() (Chương 04 & 07 - Built-in Auth).
    """
    next_url = request.GET.get('next') or request.POST.get('next')
    if request.user.is_authenticated:
        return redirect(next_url or 'courses_home')

    error_msg = None
    form = UserLoginForm()

    if request.method == 'POST':
        form = UserLoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                if next_url and next_url not in ['/', '/home/', '/courses/']:
                    role = get_user_role(user)
                    if role == 'trainee' and '/trainer/' in next_url:
                        return redirect('trainee_courses')
                    if role == 'trainer' and '/trainee/' in next_url:
                        return redirect('trainer_courses')
                    return redirect(next_url)
                role = get_user_role(user)
                if role == 'trainer':
                    return redirect('trainer_courses')
                return redirect('home')
            else:
                error_msg = 'Tên đăng nhập hoặc mật khẩu không chính xác. Vui lòng kiểm tra lại!'
        else:
            error_msg = 'Vui lòng điền đầy đủ tên đăng nhập và mật khẩu!'

    return render(request, 'login.html', {'form': form, 'error_msg': error_msg, 'next': next_url or ''})


def register_view(request):
    """
    Trang đăng ký tài khoản thật của hệ thống ScotsMate:
    Sử dụng UserRegisterForm (Chương 04 & Chương 07 - Built-in Auth).
    Mặc định tạo tài khoản Học viên (is_staff=False).
    """
    if request.user.is_authenticated:
        return redirect('courses_home')

    error_msg = None
    form = UserRegisterForm()

    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            new_user = form.save()

            # Tự động phân công các khóa học nhập môn cho nhân viên mới
            default_courses = Course.objects.filter(code__in=['KH-1026', 'KH-1028', 'KH-0925'])
            if not default_courses.exists():
                default_courses = Course.objects.all()[:3]
            for c in default_courses:
                CourseEnrollment.objects.get_or_create(
                    course=c,
                    emp=new_user,
                    defaults={
                        'study_process': 10,
                        'is_completed': False,
                        'is_pass': False,
                    }
                )

            # Tự động đăng nhập người dùng vừa đăng ký và vào thẳng Cổng học viên
            login(request, new_user)
            return redirect('trainee_courses')
        else:
            for field, err_list in form.errors.items():
                if err_list:
                    error_msg = err_list[0]
                    break

    return render(request, 'register.html', {'form': form, 'error_msg': error_msg})


def logout_view(request):
    """Đăng xuất người dùng thật và chuyển về trang đăng nhập"""
    logout(request)
    return redirect('/login/')


def courses_home(request):
    """
    Cửa ngõ /courses/ tự động phân quyền theo tài khoản đăng nhập thật:
    - Nếu chưa đăng nhập: Chuyển hướng tới /login/?next=/courses/
    - Nếu là Trainer: Chuyển vào /courses/trainer/courses/
    - Nếu là Trainee: Chuyển vào /courses/trainee/courses/
    """
    if not request.user.is_authenticated:
        return redirect('/login/?next=/courses/')

    role = get_user_role(request.user)
    if role == 'trainer':
        return redirect('trainer_courses')
    else:
        return redirect('trainee_courses')


# ============================================================
# PHÂN HỆ GIẢNG VIÊN / QUẢN LÝ (TRAINER VIEWS)
# Bảo vệ nghiêm ngặt: Chỉ tài khoản Trainer mới được truy cập
# ============================================================

def trainer_courses(request):
    """
    Quản lý danh sách khóa học nội bộ
    """
    if not request.user.is_authenticated:
        return redirect('/login/?next=' + request.path)
    if get_user_role(request.user) != 'trainer':
        return redirect('trainee_courses')

    tab = request.GET.get('tab', 'all')
    search_query = request.GET.get('q', '').strip()

    courses = Course.objects.all().select_related('creator').annotate(
        annotated_total_enrolled=Count('enrollments', distinct=True),
        annotated_total_completed=Count('enrollments', filter=Q(enrollments__is_completed=True), distinct=True)
    ).order_by('-date_start', '-id')

    if tab == 'ongoing':
        courses = courses.filter(status='ongoing')
    elif tab == 'draft':
        courses = courses.filter(status='draft')
    elif tab == 'completed':
        courses = courses.filter(status='completed')

    if search_query:
        courses = courses.filter(
            Q(title__icontains=search_query) |
            Q(code__icontains=search_query) |
            Q(creator__first_name__icontains=search_query) |
            Q(creator__last_name__icontains=search_query)
        )

    # Thống kê tổng số lượng theo trạng thái
    total_count = Course.objects.count()
    ongoing_count = Course.objects.filter(status='ongoing').count()
    draft_count = Course.objects.filter(status='draft').count()
    completed_count = Course.objects.filter(status='completed').count()
    trainers = User.objects.filter(is_staff=True).order_by('first_name')

    context = {
        'courses': courses,
        'current_tab': tab,
        'search_query': search_query,
        'total_count': total_count,
        'ongoing_count': ongoing_count,
        'draft_count': draft_count,
        'completed_count': completed_count,
        'trainers': trainers,
    }
    return render(request, 'trainer_courses.html', context)


def trainer_course_detail(request, course_id=1):
    """Chi tiết khóa học phía quản trị (Hỗ trợ xem, cập nhật và xuất bản)"""
    if not request.user.is_authenticated:
        return redirect('/login/?next=' + request.path)
    if get_user_role(request.user) != 'trainer':
        return redirect('trainee_courses')

    course = get_object_or_404(Course.objects.select_related('creator', 'exam'), id=course_id)

    materials = course.materials.all().order_by('order')
    exam = get_course_exam(course)
    enrollments = list(course.enrollments.select_related('emp', 'emp__employee_info__dep', 'emp__employee_info__branch').all().order_by('-is_assigned', 'emp__last_name', 'emp__first_name'))
    total_enrolled = len(enrollments)
    total_completed = sum(1 for e in enrollments if e.is_completed)

    # Xử lý các thao tác quản trị học viên từ trang chi tiết
    if request.method == 'POST':
        action = request.POST.get('action', '')
        if action == 'publish':
            course.status = 'ongoing'
            course.save()
            messages.success(request, f'Khóa học "{course.title}" đã được xuất bản thành công! Học viên đã có thể tham gia học tập.')
            return redirect('trainer_course_detail', course_id=course.id)
        elif action == 'update_info':
            # Sử dụng CourseUpdateForm chuẩn ModelForm (Chương 04)
            form = CourseUpdateForm(request.POST, instance=course)
            if form.is_valid():
                form.save()
                messages.success(request, f'Đã cập nhật thông tin khóa học "{course.title}" thành công!')
            else:
                messages.error(request, 'Cập nhật thất bại. Ngày kết thúc phải diễn ra sau ngày bắt đầu hoặc dữ liệu không hợp lệ.')
            return redirect('trainer_course_detail', course_id=course.id)
        elif action == 'remove_trainee':
            emp_id = request.POST.get('emp_id')
            if emp_id:
                deleted, _ = CourseEnrollment.objects.filter(course=course, emp_id=emp_id).delete()
                if deleted:
                    messages.success(request, 'Đã xóa học viên khỏi danh sách khóa học thành công.')
            return redirect('trainer_course_detail', course_id=course.id)

    form = CourseUpdateForm(instance=course)
    context = {
        'course': course,
        'materials': materials,
        'materials_count': materials.count(),
        'exam': exam,
        'enrollments': enrollments,
        'total_enrolled': total_enrolled,
        'total_completed': total_completed,
        'form': form,
    }
    return render(request, 'trainer_courses_{id}.html', context)


def trainer_course_assign(request, course_id=1):
    """
    [CHƯƠNG 02, 06 & 07 - MIS3010] Giao diện phân công & ghi danh học viên vào khóa học:
    - Cho phép Giảng viên (Trainer) lọc nhân viên theo từng phòng ban, cơ sở.
    - Học viên do Trainer phân công sẽ được đánh dấu is_assigned=True (BẮT BUỘC).
    - Hỗ trợ thêm hàng loạt (save_assign) và hủy ghi danh (remove_trainee).
    """
    if not request.user.is_authenticated:
        return redirect('/login/?next=' + request.path)
    if get_user_role(request.user) != 'trainer':
        return redirect('trainee_courses')

    course = get_object_or_404(Course.objects.select_related('creator'), id=course_id)
    departments = Department.objects.all().order_by('id')
    trainees = User.objects.filter(is_staff=False).select_related('employee_info__dep', 'employee_info__branch').order_by('last_name', 'first_name')

    if request.method == 'POST':
        action = request.POST.get('action', '')
        if action == 'save_assign':
            trainee_ids = request.POST.getlist('trainee_ids')
            count_new = 0
            with transaction.atomic():
                for tid in trainee_ids:
                    try:
                        t_user = User.objects.get(id=int(tid))
                        enr, created = CourseEnrollment.objects.get_or_create(
                            emp=t_user,
                            course=course,
                            defaults={'study_process': 0, 'is_assigned': True}
                        )
                        # Nếu học viên trước đó tự đăng ký hoặc đã có, cập nhật thành Bắt buộc (Trainer chỉ định)
                        if not created and not enr.is_assigned:
                            enr.is_assigned = True
                            enr.save()
                        if created:
                            count_new += 1
                    except (User.DoesNotExist, ValueError):
                        continue

            messages.success(request, f'Đã cập nhật danh sách phân công học viên bắt buộc cho khóa học "{course.title}" ({len(trainee_ids)} học viên được chọn).')
            return redirect('trainer_course_detail', course_id=course.id)

        elif action == 'remove_trainee':
            emp_id = request.POST.get('emp_id')
            if emp_id:
                deleted, _ = CourseEnrollment.objects.filter(course=course, emp_id=emp_id).delete()
                if deleted:
                    messages.success(request, 'Đã hủy ghi danh học viên khỏi khóa học.')
                else:
                    messages.info(request, 'Học viên không tồn tại trong danh sách khóa học.')
            return redirect('trainer_course_assign', course_id=course.id)

    # Lấy danh sách ghi danh hiện có để đánh dấu checkbox và hiển thị bảng phân loại
    enrollments = list(course.enrollments.select_related('emp', 'emp__employee_info__dep', 'emp__employee_info__branch').all().order_by('-is_assigned', 'emp__last_name'))
    enrolled_map = {e.emp_id: e for e in enrollments}
    enrolled_ids = list(enrolled_map.keys())

    # Gắn thông tin ghi danh trực tiếp vào từng đối tượng nhân viên để template render tối ưu
    for t in trainees:
        t.enrollment = enrolled_map.get(t.id)
        t.is_enrolled = bool(t.enrollment is not None)

    context = {
        'course': course,
        'departments': departments,
        'trainees': trainees,
        'enrollments': enrollments,
        'enrolled_ids': enrolled_ids,
        'total_enrolled': len(enrollments),
        'materials_count': course.materials.count(),
        'exam': get_course_exam(course),
    }
    return render(request, 'trainer_course_{id}_assign.html', context)


def trainer_course_dashboard(request, course_id=1):
    """
    [CHƯƠNG 02, 06 & 07 - MIS3010] Báo cáo tiến độ & Phân tích chi tiết bài thi khóa học:
    - Thống kê tỷ lệ hoàn thành, đỗ/trượt, phổ điểm (trung bình, cao nhất, thấp nhất).
    - Kết quả bài kiểm tra của chính Giảng viên (Trainer) khi thi thử nghiệm.
    - Phân tích chi tiết từng câu hỏi (Item Analysis): câu nào học viên hay sai nhất, thống kê phương án chọn A/B/C/D.
    - Xem chi tiết từng câu trả lời bài làm của từng học viên.
    """
    if not request.user.is_authenticated:
        return redirect('/login/?next=' + request.path)
    if get_user_role(request.user) != 'trainer':
        return redirect('trainee_courses')

    course = get_object_or_404(Course.objects.select_related('creator', 'exam'), id=course_id)
    if course.status == 'draft':
        messages.info(request, f'Khóa học "{course.title}" đang ở trạng thái Bản nháp và chưa xuất bản. Báo cáo tiến độ học viên chỉ hiển thị sau khi khóa học được xuất bản.')
        return redirect('trainer_course_detail', course_id=course.id)

    exam = get_course_exam(course)
    enrollments = list(course.enrollments.select_related(
        'emp', 'emp__employee_info__dep', 'emp__employee_info__branch'
    ).all().order_by('-study_process', 'emp__last_name'))

    total_enrolled = len(enrollments)
    total_completed = sum(1 for e in enrollments if e.is_completed)
    total_passed = sum(1 for e in enrollments if e.is_pass)

    all_responses = list(
        CourseExamResponse.objects.filter(exam=exam)
        .select_related('emp', 'emp__employee_info__dep')
        .order_by('-submission_date')
    ) if exam else []

    # Phân tách lượt nộp bài của học viên và bài kiểm tra thử nghiệm của Giảng viên (Trainer)
    trainee_responses = [r for r in all_responses if not r.emp.is_staff]
    trainer_response = next((r for r in all_responses if r.emp_id == request.user.id), None)
    if not trainer_response and request.user.is_staff:
        trainer_response = next((r for r in all_responses if r.emp.is_staff), None)

    # Thống kê phổ điểm bài thi
    submitted_count = len(trainee_responses)
    scores = [r.score for r in trainee_responses]
    avg_score = round(sum(scores) / len(scores), 1) if scores else 0.0
    max_score = max(scores) if scores else 0.0
    min_score = min(scores) if scores else 0.0
    pass_count = sum(1 for r in trainee_responses if r.is_passed)
    pass_rate = round(pass_count / submitted_count * 100, 1) if submitted_count > 0 else 0.0

    choice_letters = {1: 'A', 2: 'B', 3: 'C', 4: 'D', 5: 'E'}

    # Gắn bài nộp thi và câu trả lời chi tiết vào từng học viên
    response_by_user = {r.emp_id: r for r in all_responses}
    for en in enrollments:
        en.exam_response = response_by_user.get(en.emp_id)
        if en.exam_response:
            en.details_list = list(
                en.exam_response.details.select_related('question')
                .prefetch_related('question__choices')
                .all().order_by('question__question_number')
            )
            en.correct_count = sum(1 for d in en.details_list if d.is_correct)
            for d in en.details_list:
                d.choice_letter = choice_letters.get(d.answer, str(d.answer) if d.answer else 'Bỏ trống')
                d.correct_letter = choice_letters.get(d.question.correct_choice, str(d.question.correct_choice))
                user_c = next((c for c in d.question.choices.all() if c.choice_number == d.answer), None)
                correct_c = next((c for c in d.question.choices.all() if c.choice_number == d.question.correct_choice), None)
                d.user_choice_content = user_c.content if user_c else 'Không chọn'
                d.correct_choice_content = correct_c.content if correct_c else ''
        else:
            en.correct_count = 0
            en.details_list = []

    # Thống kê bài làm của Trainer
    trainer_details = []
    trainer_correct_count = 0
    total_questions = 0
    if exam:
        total_questions = exam.questions.count()
    if trainer_response:
        trainer_details = list(
            trainer_response.details.select_related('question')
            .prefetch_related('question__choices')
            .all().order_by('question__question_number')
        )
        trainer_correct_count = sum(1 for d in trainer_details if d.is_correct)
        for d in trainer_details:
            d.choice_letter = choice_letters.get(d.answer, str(d.answer) if d.answer else 'Bỏ trống')
            d.correct_letter = choice_letters.get(d.question.correct_choice, str(d.question.correct_choice))
            user_c = next((c for c in d.question.choices.all() if c.choice_number == d.answer), None)
            correct_c = next((c for c in d.question.choices.all() if c.choice_number == d.question.correct_choice), None)
            d.user_choice_content = user_c.content if user_c else 'Không chọn'
            d.correct_choice_content = correct_c.content if correct_c else ''

    # PHÂN TÍCH TỪNG CÂU HỎI (ITEM ANALYSIS) - GIẢI ĐÁP HỌC VIÊN ĐA SỐ SAI Ở ĐÂU
    questions_analysis = []
    most_missed_questions = []
    if exam:
        active_responses = trainee_responses if trainee_responses else all_responses
        questions = exam.questions.prefetch_related('choices').all().order_by('question_number')
        for q in questions:
            q_details = list(CourseExamResponseDetail.objects.filter(
                question=q, response__in=active_responses
            ))
            q_total = len(q_details)
            q_correct = sum(1 for d in q_details if d.is_correct)
            q_wrong = q_total - q_correct
            q_correct_pct = round(q_correct / q_total * 100, 1) if q_total > 0 else 0.0
            q_wrong_pct = round(q_wrong / q_total * 100, 1) if q_total > 0 else 0.0

            choices_stats = []
            for c in q.choices.all().order_by('choice_number'):
                c_chosen = sum(1 for d in q_details if d.answer == c.choice_number)
                c_pct = round(c_chosen / q_total * 100, 1) if q_total > 0 else 0.0
                is_correct_choice = (c.choice_number == q.correct_choice)
                choices_stats.append({
                    'letter': choice_letters.get(c.choice_number, str(c.choice_number)),
                    'content': c.content,
                    'count': c_chosen,
                    'pct': c_pct,
                    'is_correct': is_correct_choice,
                    'is_trap': (not is_correct_choice and c_chosen > 0),
                })

            is_hard = (q_wrong_pct >= 30.0 and q_total > 0)
            analysis_item = {
                'question_number': q.question_number,
                'caption': q.caption,
                'correct_choice': q.correct_choice,
                'correct_letter': choice_letters.get(q.correct_choice, str(q.correct_choice)),
                'total_answers': q_total,
                'correct_answers': q_correct,
                'wrong_answers': q_wrong,
                'correct_pct': q_correct_pct,
                'wrong_pct': q_wrong_pct,
                'is_hard': is_hard,
                'choices_stats': choices_stats,
            }
            questions_analysis.append(analysis_item)
            if is_hard:
                most_missed_questions.append(analysis_item)

        most_missed_questions = sorted(most_missed_questions, key=lambda x: x['wrong_pct'], reverse=True)

    not_submitted_count = max(0, total_enrolled - submitted_count)

    context = {
        'course': course,
        'exam': exam,
        'enrollments': enrollments,
        'total_enrolled': total_enrolled,
        'materials_count': course.materials.count(),
        'total_completed': total_completed,
        'total_passed': total_passed,
        'submitted_count': submitted_count,
        'not_submitted_count': not_submitted_count,
        'avg_score': avg_score,
        'max_score': max_score,
        'min_score': min_score,
        'pass_rate': pass_rate,
        'trainer_response': trainer_response,
        'trainer_details': trainer_details,
        'trainer_correct_count': trainer_correct_count,
        'total_questions': total_questions,
        'questions_analysis': questions_analysis,
        'most_missed_questions': most_missed_questions,
    }
    return render(request, 'trainer_courses_{id}_dashboard.html', context)


def trainer_course_materials(request, course_id=1):
    """
    [CHƯƠNG 04 & 06 - MIS3010] Quản lý tài liệu & bài giảng khóa học:
    - Tiếp nhận yêu cầu GET (hiển thị danh mục, xem chi tiết bài học) và POST (thêm mới, chỉnh sửa, xóa bài học).
    - Phân quyền: Chỉ cho phép người dùng có vai trò Giảng viên (Trainer, is_staff=True) truy cập.
    - Xử lý tải lên tập tin đính kèm (FileField) thông qua request.FILES và lưu trữ trong media/courses/materials/.
    """
    # Bước 1: Kiểm tra trạng thái đăng nhập của người dùng (Chương 07)
    if not request.user.is_authenticated:
        return redirect('/login/?next=' + request.path)
    
    # Bước 2: Kiểm tra phân quyền truy cập - Chỉ Giảng viên (Trainer) mới có quyền quản lý bài giảng
    if get_user_role(request.user) != 'trainer':
        return redirect('trainee_courses')

    # Bước 3: Lấy đối tượng khóa học tương ứng theo ID, tối ưu truy vấn kết hợp thông tin người tạo (Chương 02)
    course = get_object_or_404(Course.objects.select_related('creator'), id=course_id)
    # Lấy danh sách toàn bộ bài giảng đã tạo trong khóa học theo thứ tự tăng dần
    materials = course.materials.all().order_by('order')
    exam = get_course_exam(course)

    # Bước 4: Kiểm tra xem người dùng có đang yêu cầu mở chế độ chỉnh sửa bài giảng cụ thể không (?edit=<id>)
    edit_id = request.GET.get('edit')
    editing_material = None
    if edit_id:
        editing_material = CourseMaterial.objects.filter(id=edit_id, course=course).first()

    # Bước 5: Xử lý dữ liệu khi người dùng gửi form bằng phương thức HTTP POST
    if request.method == 'POST':
        action = request.POST.get('action', '')
        
        # 5.1. Thao tác xóa bài giảng
        if action == 'delete':
            material_id = request.POST.get('material_id')
            if material_id:
                CourseMaterial.objects.filter(id=material_id, course=course).delete()
                # Tự động đánh lại số thứ tự tăng dần liên tục cho các bài giảng còn lại
                for idx, m in enumerate(course.materials.all().order_by('order', 'id'), start=1):
                    if m.order != idx:
                        m.order = idx
                        m.save(update_fields=['order'])
                messages.success(request, 'Đã xóa bài giảng khỏi khóa học thành công.')
            return redirect('trainer_course_materials', course_id=course.id)

        # 5.2. Thao tác thêm mới hoặc cập nhật bài giảng
        target_material = editing_material
        material_id = request.POST.get('material_id')
        if material_id and not target_material:
            target_material = CourseMaterial.objects.filter(id=material_id, course=course).first()

        # Khởi tạo ModelForm với dữ liệu từ request.POST và request.FILES (Chương 04 & Chương 06)
        form = CourseMaterialForm(request.POST, request.FILES, instance=target_material)
        if form.is_valid():
            mat = form.save(commit=False)
            mat.course = course

            # [CHƯƠNG 04 - MIS3010] Đồng bộ tình huống thực hành mẫu:
            # Cho phép Giảng viên nhập riêng "Đề bài tình huống" và "Cách xử lý chuẩn (Đáp án giấu đi)",
            # hệ thống tự động ghép định dạng chuẩn để học viên vừa có đề bài vừa giấu được đáp án.
            scenario_prob = request.POST.get('scenario_problem', '').strip()
            scenario_sol = request.POST.get('scenario_solution', '').strip()
            if scenario_prob or scenario_sol:
                if scenario_prob and scenario_sol:
                    mat.scenario_content = f"Tình huống: {scenario_prob}\nCách xử lý: {scenario_sol}"
                elif scenario_sol:
                    mat.scenario_content = scenario_sol
                else:
                    mat.scenario_content = scenario_prob

            # Tự động trích đoạn tóm tắt nếu chưa có
            if not mat.summary and mat.content:
                mat.summary = mat.content[:150]
            # Tự động gán số thứ tự tăng dần tiếp theo nếu là bài giảng mới
            if not target_material:
                max_order = course.materials.aggregate(models.Max('order'))['order__max'] or 0
                mat.order = max_order + 1
            mat.save()
            
            if target_material:
                messages.success(request, f'Đã cập nhật bài giảng "{mat.name}" thành công!')
            else:
                messages.success(request, f'Đã thêm bài giảng "{mat.name}" vào khóa học thành công!')
            return redirect('trainer_course_materials', course_id=course.id)
        else:
            # Thu thập lỗi đầu tiên từ form để phản hồi thông báo thân thiện cho người dùng
            first_err = ''
            for field, errors in form.errors.items():
                if errors:
                    first_err = errors[0]
                    break
            error_msg = f'Dữ liệu bài giảng không hợp lệ: {first_err}' if first_err else 'Dữ liệu bài giảng không hợp lệ. Vui lòng kiểm tra lại thông tin.'
            messages.error(request, error_msg)
    else:
        form = CourseMaterialForm(instance=editing_material)

    # Bước 6: Đóng gói context và truyền dữ liệu ra template giao diện
    context = {
        'course': course,
        'materials': materials,
        'materials_count': materials.count(),
        'total_enrolled': course.enrollments.count(),
        'exam': exam,
        'editing_material': editing_material,
        'form': form,
    }
    return render(request, 'trainer_courses_{id}_materials.html', context)


def trainer_course_exam_setup(request, course_id=1):
    """
    [CHƯƠNG 02, 04 & 07 - MIS3010] Thiết lập quy chuẩn bài thi và ngân hàng câu hỏi trắc nghiệm:
    - Lưu thông tin quy chuẩn phòng thi: thời gian làm bài, điểm đạt yêu cầu, mã passcode mở đề thi.
    - Quản lý ngân hàng câu hỏi trắc nghiệm động: hỗ trợ từ 2 đến 5 phương án A-E và xác định đáp án đúng.
    - Áp dụng transaction.atomic() đảm bảo tính toàn vẹn dữ liệu (ACID) khi lưu đồng thời bài thi, câu hỏi và đáp án.
    """
    # Bước 1: Kiểm tra đăng nhập và phân quyền Giảng viên
    if not request.user.is_authenticated:
        return redirect('/login/?next=' + request.path)
    if get_user_role(request.user) != 'trainer':
        return redirect('trainee_courses')

    # Bước 2: Lấy thông tin khóa học và đề thi hiện có (nếu đã tạo trước đó)
    course = get_object_or_404(Course.objects.select_related('creator'), id=course_id)
    exam = get_course_exam(course)
    questions = []
    if exam:
        # Tối ưu truy vấn prefetch_related lấy sẵn các phương án lựa chọn, tránh lỗi N+1 queries (Chương 02)
        questions = exam.questions.prefetch_related('choices').all().order_by('question_number')

    # Bước 3: Tiếp nhận và xử lý dữ liệu cấu hình khi Giảng viên gửi form POST
    if request.method == 'POST':
        title = request.POST.get('title', '').strip() or f'Bài thi đánh giá: {course.title}'
        passcode = request.POST.get('passcode', 'SCOTS2026').strip().upper()
        duration = int(request.POST.get('duration', 45) or 45)
        passing_score = float(request.POST.get('passing_score', 80.0) or 80.0)
        is_active = True  # Luôn tự động kích hoạt đề thi khi giảng viên thiết lập đề thi

        # Đảm bảo tính toàn vẹn cơ sở dữ liệu: Nếu một bước thất bại, toàn bộ giao dịch sẽ được Rollback
        with transaction.atomic():
            # 3.1. Tạo mới hoặc cập nhật thông tin bài thi (CourseExam)
            exam, created = CourseExam.objects.update_or_create(
                course=course,
                defaults={
                    'title': title,
                    'passcode': passcode,
                    'duration': duration,
                    'passing_score': passing_score,
                    'is_active': is_active,
                }
            )

            # 3.2. Thu thập và cập nhật danh sách câu hỏi trắc nghiệm động từ form gửi lên
            total_questions = int(request.POST.get('total_questions', 0) or 0)
            max_q = 0

            for n in range(1, total_questions + 1):
                caption = request.POST.get(f'question_{n}_caption', '').strip()
                if not caption:
                    continue

                # Thu thập các phương án hợp lệ (m = 1 đến 5 đại diện cho A, B, C, D, E)
                valid_choices = []
                for m in range(1, 6):
                    val = request.POST.get(f'question_{n}_choice_{m}', '').strip()
                    if val:
                        valid_choices.append(val)

                # Mỗi câu hỏi hợp lệ bắt buộc cần có tối thiểu 2 phương án (ví dụ Đúng/Sai hoặc trắc nghiệm A, B)
                if len(valid_choices) < 2:
                    continue

                raw_correct = int(request.POST.get(f'question_{n}_correct', 1) or 1)
                correct_choice = min(max(1, raw_correct), len(valid_choices))

                max_q += 1

                # Lưu hoặc cập nhật câu hỏi vào bảng CourseExamQuestion
                question, _ = CourseExamQuestion.objects.update_or_create(
                    exam=exam,
                    question_number=max_q,
                    defaults={
                        'caption': caption,
                        'correct_choice': correct_choice,
                    }
                )

                # Lưu từng phương án trả lời vào bảng CourseQuestionChoice
                for idx, c_text in enumerate(valid_choices, start=1):
                    CourseQuestionChoice.objects.update_or_create(
                        question=question,
                        choice_number=idx,
                        defaults={'content': c_text}
                    )

                # Dọn dẹp phương án thừa nếu người dùng xóa bớt phương án (ví dụ từ 4 phương án giảm xuống 3)
                question.choices.filter(choice_number__gt=len(valid_choices)).delete()

            # Dọn dẹp câu hỏi thừa nếu số lượng câu hỏi bị giảm sau khi sửa
            if exam:
                exam.questions.filter(question_number__gt=max_q).delete()

        messages.success(request, f'Đã lưu thành công cấu hình bài thi và {max_q} câu hỏi trắc nghiệm!')
        return redirect('trainer_course_exam_setup', course_id=course.id)

    # Nạp lại danh sách câu hỏi mới nhất sau khi lưu để hiển thị lên giao diện
    if exam:
        questions = exam.questions.prefetch_related('choices').all().order_by('question_number')

    context = {
        'course': course,
        'exam': exam,
        'questions': questions,
        'materials_count': course.materials.count(),
        'total_enrolled': course.enrollments.count(),
    }
    return render(request, 'trainer_courses_{id}_exam_setup.html', context)


def trainer_courses_dashboard(request):
    """
    [CHƯƠNG 02, 06 & 07 - MIS3010] Báo cáo tổng quan đào tạo toàn hệ thống với biểu đồ trực quan:
    - Thống kê tỷ lệ hoàn thành theo khóa học và phân bổ trạng thái.
    - Phân tích hiệu suất đào tạo theo từng Phòng ban.
    - Cung cấp dữ liệu JSON sẵn sàng để vẽ biểu đồ tương tác thời gian thực.
    """
    if not request.user.is_authenticated:
        return redirect('/login/?next=' + request.path)
    if get_user_role(request.user) != 'trainer':
        return redirect('trainee_courses')

    courses = list(Course.objects.all().select_related('creator').annotate(
        annotated_total_enrolled=Count('enrollments', distinct=True),
        annotated_total_completed=Count('enrollments', filter=Q(enrollments__is_completed=True), distinct=True)
    ).order_by('-date_start', '-id'))

    total_courses = len(courses)
    ongoing_courses = sum(1 for c in courses if c.status == 'ongoing')
    draft_courses = sum(1 for c in courses if c.status == 'draft')
    completed_courses = sum(1 for c in courses if c.status == 'completed')

    total_enrollments = CourseEnrollment.objects.count()
    total_completed = CourseEnrollment.objects.filter(is_completed=True).count()
    overall_progress = round((total_completed / total_enrollments * 100), 1) if total_enrollments > 0 else 0

    # Dữ liệu cho Biểu đồ 1: Tiến độ hoàn thành theo từng khóa học
    active_courses = [c for c in courses if c.status != 'draft']
    chart_course_labels = [c.code for c in active_courses]
    chart_course_names = [f"{c.code}: {c.title}" for c in active_courses]
    chart_course_rates = [
        round(c.annotated_total_completed / c.annotated_total_enrolled * 100, 1) if c.annotated_total_enrolled > 0 else 0
        for c in active_courses
    ]
    chart_course_enrolled = [c.annotated_total_enrolled for c in active_courses]
    chart_course_completed = [c.annotated_total_completed for c in active_courses]

    # Dữ liệu cho Biểu đồ 2: Cơ cấu trạng thái khóa học
    status_distribution = [ongoing_courses, completed_courses, draft_courses]

    # Dữ liệu cho Biểu đồ 3: Phân bổ nhân sự và hoàn thành theo Phòng ban
    departments = Department.objects.all().order_by('id')
    dept_stats = []
    for d in departments:
        emp_ids = list(EmployeeInformation.objects.filter(dep=d).values_list('emp_id', flat=True))
        dept_enr = CourseEnrollment.objects.filter(emp_id__in=emp_ids).count()
        dept_done = CourseEnrollment.objects.filter(emp_id__in=emp_ids, is_completed=True).count()
        rate = round(dept_done / dept_enr * 100, 1) if dept_enr > 0 else 0
        dept_stats.append({
            'id': d.id,
            'name': d.name,
            'total_emp': len(emp_ids),
            'total_enrollments': dept_enr,
            'completed_count': dept_done,
            'rate': rate,
        })

    trainers = User.objects.filter(is_staff=True).order_by('first_name')

    # Bóc tách dữ liệu chi tiết từng khóa học kèm phòng ban để lọc động thời gian thực (Reactive Filtering)
    all_enrs = list(CourseEnrollment.objects.select_related('emp__employee_info__dep').all())
    course_enr_map = {}
    for en in all_enrs:
        course_enr_map.setdefault(en.course_id, []).append(en)

    courses_data = []
    for c in courses:
        dept_map = {}
        dept_ids_set = set()
        for en in course_enr_map.get(c.id, []):
            emp_info = getattr(en.emp, 'employee_info', None)
            dep = getattr(emp_info, 'dep', None) if emp_info else None
            if dep:
                dept_ids_set.add(dep.id)
                if dep.id not in dept_map:
                    dept_map[dep.id] = {'enrolled': 0, 'completed': 0}
                dept_map[dep.id]['enrolled'] += 1
                if en.is_completed:
                    dept_map[dep.id]['completed'] += 1

        tr_name = c.creator.get_full_name() if c.creator else ''
        if not tr_name and c.creator:
            tr_name = c.creator.username

        courses_data.append({
            'id': c.id,
            'code': c.code,
            'title': c.title,
            'status': c.status,
            'trainer_id': c.creator_id,
            'trainer_name': tr_name,
            'total_enrolled': c.annotated_total_enrolled,
            'total_completed': c.annotated_total_completed,
            'dept_ids': list(dept_ids_set),
            'dept_data': dept_map,
            'search_text': f"{c.code} {c.title} {tr_name}".lower(),
        })

    context = {
        'total_courses': total_courses,
        'ongoing_courses': ongoing_courses,
        'draft_courses': draft_courses,
        'completed_courses': completed_courses,
        'total_enrollments': total_enrollments,
        'total_completed': total_completed,
        'overall_progress': overall_progress,
        'courses': courses,
        'trainers': trainers,
        'departments': departments,
        'dept_stats': dept_stats,
        'chart_course_labels_json': json.dumps(chart_course_labels),
        'chart_course_names_json': json.dumps(chart_course_names),
        'chart_course_rates_json': json.dumps(chart_course_rates),
        'chart_course_enrolled_json': json.dumps(chart_course_enrolled),
        'chart_course_completed_json': json.dumps(chart_course_completed),
        'status_distribution_json': json.dumps(status_distribution),
        'dept_labels_json': json.dumps([d['name'] for d in dept_stats]),
        'dept_rates_json': json.dumps([d['rate'] for d in dept_stats]),
        'dept_enr_json': json.dumps([d['total_enrollments'] for d in dept_stats]),
        'courses_data_json': json.dumps(courses_data),
    }
    return render(request, 'trainer_courses_dashboard.html', context)


def trainer_courses_create_info(request):
    """Tạo khóa học mới - Bước 1: Thông tin cơ bản"""
    if not request.user.is_authenticated:
        return redirect('/login/?next=' + request.path)
    if get_user_role(request.user) != 'trainer':
        return redirect('trainee_courses')

    errors = {}
    draft = request.session.get('draft_course', {})
    form = CourseForm(initial=draft)

    if request.method == 'POST':
        form = CourseForm(request.POST)
        if form.is_valid():
            cleaned = form.cleaned_data
            form_data = {
                'title': cleaned.get('title', ''),
                'code': cleaned.get('code', ''),
                'description': cleaned.get('description', ''),
                'date_start': cleaned.get('date_start').strftime('%Y-%m-%d') if cleaned.get('date_start') else '',
                'date_end': cleaned.get('date_end').strftime('%Y-%m-%d') if cleaned.get('date_end') else '',
                'status': cleaned.get('status', 'draft'),
            }
            request.session['draft_course'] = form_data
            return redirect('trainer_courses_create_assign')
        else:
            errors = {field: err[0] for field, err in form.errors.items()}
            form_data = request.POST.dict()
    else:
        form_data = draft

    context = {
        'step': 1,
        'errors': errors,
        'form_data': form_data,
        'draft': form_data,
        'form': form,
    }
    return render(request, 'trainer_courses_create_info.html', context)


def trainer_courses_create_assign(request):
    """Tạo khóa học mới - Bước 2: Phân công học viên"""
    if not request.user.is_authenticated:
        return redirect('/login/?next=' + request.path)
    if get_user_role(request.user) != 'trainer':
        return redirect('trainee_courses')

    draft = request.session.get('draft_course', {})
    if not draft:
        return redirect('trainer_courses_create_info')
    
    # Lấy danh sách phòng ban và nhân viên kèm thông tin phòng ban, chi nhánh
    departments = Department.objects.all().order_by('id')
    trainees = User.objects.filter(is_staff=False).select_related('employee_info__dep', 'employee_info__branch').order_by('last_name', 'first_name')

    if request.method == 'POST':
        trainee_ids = request.POST.getlist('trainee_ids')
        request.session['draft_trainees'] = trainee_ids
        return redirect('trainer_courses_create_review')

    context = {
        'step': 2,
        'draft': draft,
        'form_data': draft,
        'trainees': trainees,
        'departments': departments,
        'selected_ids': request.session.get('draft_trainees', []),
    }
    return render(request, 'trainer_courses_create_assign.html', context)


def trainer_courses_create_review(request):
    """Tạo khóa học mới - Bước 3: Xem lại & Xuất bản"""
    if not request.user.is_authenticated:
        return redirect('/login/?next=' + request.path)
    if get_user_role(request.user) != 'trainer':
        return redirect('trainee_courses')

    draft = request.session.get('draft_course', {})
    if not draft:
        return redirect('trainer_courses_create_info')
    trainee_ids = request.session.get('draft_trainees', [])
    trainees = User.objects.filter(id__in=trainee_ids)

    if request.method == 'POST':
        action = request.POST.get('action', '')

        if action == 'back':
            return redirect('trainer_courses_create_assign')

        if action == 'publish':
            code = draft.get('code', '').strip().upper()
            title = draft.get('title', 'Khóa học đào tạo mới')
            description = draft.get('description', '')
            status = draft.get('status', 'draft')

            try:
                date_start = datetime.strptime(draft.get('date_start', ''), '%Y-%m-%d').date()
            except (ValueError, TypeError):
                date_start = date.today()
            try:
                date_end = datetime.strptime(draft.get('date_end', ''), '%Y-%m-%d').date()
            except (ValueError, TypeError):
                date_end = date.today()

            with transaction.atomic():
                # Tạo khóa học mới
                course = Course.objects.create(
                    code=code,
                    title=title,
                    description=description,
                    creator=request.user,
                    date_start=date_start,
                    date_end=date_end,
                    status=status,
                )

                # Thêm CourseAccess cho trainer
                CourseAccess.objects.get_or_create(
                    emp=request.user,
                    course=course,
                    defaults={'role': 'trainer'}
                )

                # Ghi danh học viên
                for tid in trainee_ids:
                    try:
                        trainee_user = User.objects.get(id=int(tid))
                        CourseEnrollment.objects.get_or_create(
                            emp=trainee_user,
                            course=course,
                            defaults={'study_process': 0, 'is_assigned': True}
                        )
                    except (User.DoesNotExist, ValueError):
                        pass

            # Xóa session keys tạm
            request.session.pop('draft_course', None)
            request.session.pop('draft_trainees', None)

            messages.success(request, f'Khóa học "{title}" đã được tạo và kích hoạt thành công!')
            return redirect('trainer_course_detail', course_id=course.id)

    context = {
        'step': 3,
        'draft': draft,
        'trainees': trainees,
    }
    return render(request, 'trainer_courses_create_review.html', context)


def trainer_course_delete(request, course_id):
    """Soft delete khóa học (đổi status thành completed)"""
    if not request.user.is_authenticated or get_user_role(request.user) != 'trainer':
        return redirect('courses_home')

    course = get_object_or_404(Course, id=course_id)
    if request.method == 'POST':
        course.status = 'completed'
        course.save()
        messages.success(request, f'Khóa học "{course.title}" đã được đánh dấu kết thúc.')
    return redirect('trainer_courses')


def trainer_course_publish(request, course_id):
    """Xuất bản khóa học từ Bản nháp sang Đang triển khai"""
    if not request.user.is_authenticated or get_user_role(request.user) != 'trainer':
        return redirect('courses_home')

    course = get_object_or_404(Course, id=course_id)
    course.status = 'ongoing'
    course.save()
    messages.success(request, f'Khóa học "{course.title}" đã được xuất bản thành công! Học viên đã có thể thấy và tham gia học tập.')

    next_url = request.GET.get('next') or request.POST.get('next')
    if next_url:
        return redirect(next_url)
    return redirect('trainer_course_detail', course_id=course.id)


# ============================================================
# PHÂN HỆ HỌC VIÊN (TRAINEE VIEWS)
# Phục vụ nhân viên/giáo viên: Tự động tải khóa học cá nhân
# ============================================================

def trainee_courses(request):
    """Màn hình danh sách khóa học của học viên (Loại trừ bản nháp draft)"""
    if not request.user.is_authenticated:
        return redirect('/login/?next=' + request.path)
    if get_user_role(request.user) == 'trainer':
        return redirect('trainer_courses')

    # Lấy danh sách khóa học ĐƯỢC PHÂN CÔNG cho chính user đang đăng nhập (loại bỏ bản nháp draft)
    enrollments = list(CourseEnrollment.objects.filter(
        emp=request.user
    ).exclude(
        course__status='draft'
    ).select_related(
        'course', 'course__creator', 'course__exam'
    ).prefetch_related('course__materials'))

    studying_count = sum(1 for e in enrollments if not e.is_completed)
    completed_count = sum(1 for e in enrollments if e.is_completed)
    upcoming_exam_count = sum(1 for e in enrollments if hasattr(e.course, 'exam') and e.course.exam and not e.is_pass)

    # Lấy danh sách các khóa học Đang triển khai mà học viên CHƯA tham gia để có thể Đăng ký tự chọn
    my_enrolled_ids = [e.course_id for e in enrollments]
    available_courses = list(Course.objects.filter(
        status='ongoing'
    ).exclude(
        id__in=my_enrolled_ids
    ).select_related('creator').prefetch_related('materials').order_by('-date_start', '-id'))

    # Chương 07 - Lab VI: Lấy danh sách khóa học vừa xem từ session
    recent_viewed_ids = [item['id'] for item in request.session.get('viewed_courses', [])]
    recent_courses = []
    if recent_viewed_ids:
        # Lấy thông tin hoàn thành khóa học của học viên hiện tại để hiển thị chuẩn
        user_enr_map = {
            e.course_id: e for e in CourseEnrollment.objects.filter(emp=request.user, course_id__in=recent_viewed_ids)
        }
        courses_by_id = {c.id: c for c in Course.objects.filter(id__in=recent_viewed_ids).exclude(status='draft')}
        for cid in recent_viewed_ids:
            if cid in courses_by_id:
                c = courses_by_id[cid]
                enr = user_enr_map.get(cid)
                c.user_is_completed = (enr.is_completed or enr.is_pass) if enr else False
                c.user_progress = enr.study_process if enr else 0
                recent_courses.append(c)

    context = {
        'enrollments': enrollments,
        'available_courses': available_courses,
        'studying_count': studying_count,
        'completed_count': completed_count,
        'upcoming_exam_count': upcoming_exam_count,
        'recent_courses': recent_courses[:3],
    }
    return render(request, 'trainee_courses.html', context)


def trainee_course_detail(request, course_id=1):
    """
    Màn hình chi tiết khóa học của học viên:
    - Hiển thị thanh tracking tiến độ học tập (phần trăm và số bài đã hoàn thành).
    - Đánh dấu bài nào đã học (để tránh học lại) và bài nào cần học tiếp theo.
    - Khóa bài thi: Chỉ khi học viên học xong 100% bài giảng mới mở khóa khu vực nhập passcode và thi.
    """
    if not request.user.is_authenticated:
        return redirect('/login/?next=' + request.path)

    is_trainer = (get_user_role(request.user) == 'trainer')
    is_preview = (is_trainer and request.GET.get('preview') == '1')

    if is_trainer and not is_preview:
        return redirect('trainer_course_detail', course_id=course_id)

    course = get_object_or_404(Course.objects.select_related('creator', 'exam'), id=course_id)

    # Chương 07 - Lab VI: Lưu trữ danh sách khóa học vừa xem vào session
    if request.user.is_authenticated:
        viewed_courses = request.session.get('viewed_courses', [])
        course_item = {'id': course.id, 'title': course.title, 'code': course.code}
        if course_item in viewed_courses:
            viewed_courses.remove(course_item)
        viewed_courses.insert(0, course_item)
        request.session['viewed_courses'] = viewed_courses[:10]

    # Chặn học viên xem khóa học bản nháp
    if not is_trainer and course.status == 'draft':
        messages.warning(request, f'Khóa học "{course.title}" đang ở trạng thái Bản nháp và chưa được xuất bản.')
        return redirect('trainee_courses')

    materials = list(course.materials.all().order_by('order', 'id'))
    total_materials = len(materials)
    exam = get_course_exam(course)

    enrollment = CourseEnrollment.objects.filter(course=course, emp=request.user).first()
    latest_response = None
    if exam and not is_preview:
        latest_response = CourseExamResponse.objects.filter(
            exam=exam, emp=request.user
        ).order_by('-submission_date').first()

    # -------------------------------------------------------------------------
    # TRACKING TIẾN ĐỘ & ĐÁNH DẤU BÀI ĐÃ HỌC TRÁNH HỌC LẠI
    # -------------------------------------------------------------------------
    completed_mats_dict = request.session.get('completed_materials', {})
    learned_ids = set(completed_mats_dict.get(str(course.id), []))

    is_course_finished = bool(enrollment and (enrollment.is_completed or enrollment.is_pass))

    # Tính số bài đã học dựa theo tỷ lệ study_process nếu có sẵn dữ liệu
    completed_by_process = 0
    if enrollment and enrollment.study_process > 0 and total_materials > 0:
        if is_course_finished:
            completed_by_process = total_materials
        else:
            completed_by_process = int(round(enrollment.study_process / 100.0 * total_materials))

    completed_materials_count = 0
    next_material_to_study = None

    for idx, mat in enumerate(materials):
        # Đánh dấu bài đã học nếu: khóa học đã xong, hoặc bài có trong session, hoặc theo tiến độ ban đầu
        if is_course_finished or (mat.id in learned_ids) or (idx < completed_by_process):
            mat.is_completed = True
            mat.status_label = 'Đã học'
            completed_materials_count += 1
        else:
            mat.is_completed = False
            if next_material_to_study is None:
                mat.is_current = True
                mat.status_label = 'Đang học'
                next_material_to_study = mat
            else:
                mat.is_current = False
                mat.status_label = 'Chưa học'

    # Tính toán phần trăm tiến độ học tập thực tế
    if total_materials > 0:
        if is_course_finished:
            study_percent = 100
        else:
            study_percent = int(round(completed_materials_count / total_materials * 100))
            if enrollment and enrollment.study_process > study_percent:
                study_percent = enrollment.study_process
    else:
        study_percent = 100

    # Điều kiện để MỞ KHÓA BÀI THI CUỐI KHÓA: Phải học xong tất cả bài giảng
    all_materials_completed = (completed_materials_count >= total_materials) if total_materials > 0 else True
    if is_course_finished or (enrollment and enrollment.study_process >= 100):
        all_materials_completed = True

    context = {
        'course': course,
        'materials': materials,
        'total_materials': total_materials,
        'completed_materials_count': completed_materials_count,
        'study_percent': study_percent,
        'all_materials_completed': all_materials_completed,
        'next_material_to_study': next_material_to_study,
        'exam': exam,
        'enrollment': enrollment,
        'latest_response': latest_response,
        'is_preview': is_preview,
    }
    return render(request, 'trainee_courses_{id}.html', context)


def trainee_course_self_enroll(request, course_id=1):
    """
    [CHƯƠNG 02 & 07 - MIS3010] Học viên tự đăng ký tham gia khóa học không bắt buộc (Tự chọn):
    - Đánh dấu is_assigned=False để phân biệt với khóa học do Trainer chỉ định bắt buộc (is_assigned=True).
    - Chỉ áp dụng đối với các khóa học đang triển khai (status='ongoing').
    """
    if not request.user.is_authenticated:
        return redirect('/login/?next=' + request.path)
    if get_user_role(request.user) == 'trainer':
        return redirect('trainer_courses')

    course = get_object_or_404(Course, id=course_id)
    if course.status != 'ongoing':
        messages.warning(request, f'Khóa học "{course.title}" hiện không mở cho học viên tự đăng ký.')
        return redirect('trainee_courses')

    enrollment, created = CourseEnrollment.objects.get_or_create(
        course=course,
        emp=request.user,
        defaults={'study_process': 0, 'is_assigned': False}
    )
    if created:
        messages.success(request, f'Bạn đã đăng ký thành công khóa học tự chọn "{course.title}"! Hãy bắt đầu bài học đầu tiên.')
    else:
        messages.info(request, f'Bạn đã được ghi danh vào khóa học "{course.title}".')

    return redirect('trainee_course_detail', course_id=course.id)


def trainee_course_material(request, course_id=1, materials_id=1):
    """Phòng học trực tuyến / Đọc bài giảng (Hỗ trợ Giảng viên xem trước tài liệu)"""
    if not request.user.is_authenticated:
        return redirect('/login/?next=' + request.path)

    course = get_object_or_404(Course.objects.select_related('creator', 'exam'), id=course_id)
    is_preview = (get_user_role(request.user) == 'trainer')

    # Chặn học viên xem bài giảng của khóa học bản nháp
    if not is_preview and course.status == 'draft':
        messages.warning(request, f'Khóa học "{course.title}" đang ở trạng thái Bản nháp và chưa được xuất bản.')
        return redirect('trainee_courses')

    material = get_object_or_404(CourseMaterial, id=materials_id, course=course)

    all_materials = list(course.materials.order_by('order', 'id'))
    prev_material = None
    next_material = None
    current_idx = 0

    for idx, m in enumerate(all_materials):
        if m.id == material.id:
            current_idx = idx
            if idx > 0:
                prev_material = all_materials[idx - 1]
            if idx + 1 < len(all_materials):
                next_material = all_materials[idx + 1]
            break

    enrollment = CourseEnrollment.objects.filter(emp=request.user, course=course).first() if not is_preview else None
    exam = get_course_exam(course)
    latest_response = CourseExamResponse.objects.filter(
        exam=exam, emp=request.user
    ).order_by('-submission_date').first() if (exam and not is_preview) else None

    # Ghi nhận bài giảng này đã học vào session và cập nhật tiến độ cho học viên
    if not is_preview:
        completed_mats_dict = request.session.get('completed_materials', {})
        course_key = str(course.id)
        learned_ids = set(completed_mats_dict.get(course_key, []))
        learned_ids.add(material.id)
        completed_mats_dict[course_key] = list(learned_ids)
        request.session['completed_materials'] = completed_mats_dict
        request.session.modified = True

        total = len(all_materials)
        learned_count = len(learned_ids.intersection({m.id for m in all_materials}))
        all_materials_completed = (learned_count >= total) if total > 0 else True

        if total > 0 and enrollment:
            # Tính phần trăm: đọc đến bài nào thì tính tối thiểu đến bài đó
            num_done = max(len(learned_ids), current_idx + 1)
            progress = int(round(num_done / total * 100))
            if progress > enrollment.study_process and not enrollment.is_pass:
                enrollment.study_process = progress
                enrollment.save(update_fields=['study_process'])
    else:
        learned_count = len(all_materials)
        all_materials_completed = True

    context = {
        'course': course,
        'material': material,
        'all_materials': all_materials,
        'prev_material': prev_material,
        'next_material': next_material,
        'enrollment': enrollment,
        'exam': exam,
        'latest_response': latest_response,
        'is_preview': is_preview,
        'all_materials_completed': all_materials_completed,
        'learned_count': learned_count,
    }
    return render(request, 'trainee_course_{id}_{materials_id}.html', context)


def trainee_course_exam(request, course_id=1):
    """Phòng thi cuối khóa (Hỗ trợ Giảng viên xem trước đề thi & Bảo mật Passcode)"""
    if not request.user.is_authenticated:
        return redirect('/login/?next=' + request.path)

    course = get_object_or_404(Course.objects.select_related('creator', 'exam'), id=course_id)
    exam = get_course_exam(course)
    is_preview = (get_user_role(request.user) == 'trainer')

    # Chặn học viên thi khóa học bản nháp
    if not is_preview and course.status == 'draft':
        messages.warning(request, f'Khóa học "{course.title}" đang ở trạng thái Bản nháp và chưa được xuất bản.')
        return redirect('trainee_courses')

    unlocked_session_key = f'exam_unlocked_{exam.id}' if exam else None
    passcode_error = None
    is_unlocked = is_preview  # Giảng viên luôn mở chế độ xem trước

    if not is_preview:
        enrollment = CourseEnrollment.objects.filter(emp=request.user, course=course).first()
        latest_response = CourseExamResponse.objects.filter(
            exam=exam, emp=request.user
        ).order_by('-submission_date').first() if exam else None

        # CHÍNH SÁCH KHÓA PHÒNG THI:
        # Nếu học viên đã từng nộp bài thi (bất kể đạt hay chưa đạt), phòng thi sẽ khóa.
        # Học viên chỉ được xem lại kết quả và đối soát đáp án, KHÔNG được làm bài lại.
        if latest_response or (enrollment and enrollment.is_pass):
            messages.info(request, 'Bạn đã hoàn thành bài thi cho khóa học này. Hệ thống không cho phép làm bài lại, bạn có thể xem lại kết quả và đáp án chi tiết.')
            return redirect('trainee_course_exam_result', course_id=course.id)



        # Xử lý bảo mật Passcode:
        if exam and exam.passcode:
            # Kiểm tra trạng thái đã mở khóa trong phiên session
            if request.session.get(unlocked_session_key):
                is_unlocked = True

            # Kiểm tra passcode gửi qua GET (từ form trang chi tiết)
            passcode_param = request.GET.get('passcode', '').strip().upper()
            if passcode_param:
                if passcode_param == exam.passcode.upper():
                    request.session[unlocked_session_key] = True
                    is_unlocked = True
                else:
                    messages.error(request, 'Mã dự thi (Passcode) không chính xác. Vui lòng kiểm tra lại!')
                    return redirect('trainee_course_detail', course_id=course.id)
    else:
        enrollment = None
        latest_response = None
        is_unlocked = True

    questions = exam.questions.prefetch_related('choices').all().order_by('question_number') if exam else []

    if request.method == 'POST' and exam:
        # Xử lý mở khóa phòng thi bằng Passcode tại chính màn hình phòng thi
        action = request.POST.get('action')
        if action == 'unlock_exam':
            entered_code = request.POST.get('entered_passcode', '').strip().upper()
            if exam.passcode and entered_code == exam.passcode.upper():
                request.session[unlocked_session_key] = True
                is_unlocked = True
                messages.success(request, 'Mở khóa phòng thi thành công! Chúc bạn làm bài tốt.')
            else:
                passcode_error = 'Mã bảo mật (Passcode) không chính xác. Vui lòng kiểm tra lại!'
                is_unlocked = False

            context = {
                'course': course,
                'exam': exam,
                'questions': questions,
                'is_preview': is_preview,
                'is_unlocked': is_unlocked,
                'passcode_error': passcode_error,
            }
            return render(request, 'trainee_course_{id}_exam.html', context)

        # Chặn nếu học viên đã có bài nộp trước đó (bảo vệ chống gửi lại request POST)
        if not is_preview and (latest_response or (enrollment and enrollment.is_pass)):
            messages.warning(request, 'Bạn đã hoàn thành bài thi trước đó và không được phép làm bài lại!')
            return redirect('trainee_course_exam_result', course_id=course.id)

        # Bảo mật kiểm tra Passcode khi nộp bài
        passcode_entered = request.POST.get('passcode', '').strip().upper()
        if not is_preview and exam.passcode and passcode_entered != exam.passcode:
            messages.error(request, 'Mã dự thi (Passcode) không chính xác. Vui lòng thử lại!')
            return redirect('trainee_course_detail', course_id=course.id)

        # Tính điểm trắc nghiệm tự động
        correct_count = 0
        total_q = questions.count()

        for q in questions:
            user_choice = request.POST.get(f'question_{q.id}')
            if user_choice:
                try:
                    if int(user_choice) == q.correct_choice:
                        correct_count += 1
                except (ValueError, TypeError):
                    pass

        score = round((correct_count / total_q * 100), 1) if total_q > 0 else 0.0
        is_passed = (score >= exam.passing_score)

        if is_preview:
            # Lưu kết quả thi thử nghiệm của Giảng viên (Trainer) để xem điểm và đối chiếu
            with transaction.atomic():
                response, _ = CourseExamResponse.objects.update_or_create(
                    emp=request.user,
                    exam=exam,
                    defaults={
                        'passcode': exam.passcode,
                        'duration': exam.duration,
                        'score': score,
                        'is_passed': is_passed,
                    }
                )
                response.details.all().delete()
                details_to_create = []
                for q in questions:
                    user_choice_raw = request.POST.get(f'question_{q.id}')
                    if user_choice_raw:
                        try:
                            answer_int = int(user_choice_raw)
                            is_correct = (answer_int == q.correct_choice)
                            details_to_create.append(
                                CourseExamResponseDetail(
                                    response=response,
                                    question=q,
                                    answer=answer_int,
                                    is_correct=is_correct
                                )
                            )
                        except (ValueError, TypeError):
                            pass
                    else:
                        details_to_create.append(
                            CourseExamResponseDetail(
                                response=response,
                                question=q,
                                answer=0,
                                is_correct=False
                            )
                        )
                if details_to_create:
                    CourseExamResponseDetail.objects.bulk_create(details_to_create)

            messages.success(request, f'Bạn đã hoàn thành bài thi thử nghiệm của Trainer! Kết quả: {score}/100 điểm ({"Đạt chuẩn" if is_passed else "Chưa đạt"}).')
            return redirect(f'/courses/trainee/course/{course.id}/exam/result/?preview=1')

        with transaction.atomic():
            # Lưu lượt thi thực tế vào bảng CourseExamResponse
            response = CourseExamResponse.objects.create(
                emp=request.user,
                exam=exam,
                passcode=passcode_entered or exam.passcode,
                duration=exam.duration,
                score=score,
                is_passed=is_passed
            )

            # Lưu chi tiết từng câu trả lời dạng bulk_create vào bảng CourseExamResponseDetail
            details_to_create = []
            for q in questions:
                user_choice_raw = request.POST.get(f'question_{q.id}')
                if user_choice_raw:
                    try:
                        answer_int = int(user_choice_raw)
                        is_correct = (answer_int == q.correct_choice)
                        details_to_create.append(
                            CourseExamResponseDetail(
                                response=response,
                                question=q,
                                answer=answer_int,
                                is_correct=is_correct
                            )
                        )
                    except (ValueError, TypeError):
                        pass
                else:
                    # Trường hợp học viên bỏ trống không chọn câu trả lời
                    details_to_create.append(
                        CourseExamResponseDetail(
                            response=response,
                            question=q,
                            answer=0,
                            is_correct=False
                        )
                    )

            if details_to_create:
                CourseExamResponseDetail.objects.bulk_create(details_to_create)

            # Cập nhật kết quả vào bảng CourseEnrollment của học viên
            enrollment = CourseEnrollment.objects.filter(emp=request.user, course=course).first()
            if enrollment:
                enrollment.is_pass = is_passed
                if is_passed:
                    enrollment.is_completed = True
                    enrollment.study_process = 100
                if not enrollment.exam and exam:
                    enrollment.exam = exam
                enrollment.save()

        return redirect('trainee_course_exam_result', course_id=course.id)

    context = {
        'course': course,
        'exam': exam,
        'questions': questions,
        'is_preview': is_preview,
        'is_unlocked': is_unlocked,
        'passcode_error': passcode_error,
    }
    return render(request, 'trainee_course_{id}_exam.html', context)


def trainee_course_exam_result(request, course_id=1):
    """
    Màn hình kết quả bài thi của học viên:
    - Hiển thị điểm số đạt được, điểm chuẩn yêu cầu, xếp loại Đạt/Chưa đạt.
    - KHÔNG CHO PHÉP THI LẠI: Sau khi kết thúc, phòng thi được khóa vĩnh viễn.
    - Cho phép học viên xem lại toàn bộ bài làm của mình: đối chiếu câu trả lời đã chọn,
      đáp án chính xác của đề thi, và đánh giá đúng/sai từng câu.
    """
    if not request.user.is_authenticated:
        return redirect('/login/?next=' + request.path)
    is_trainer = (get_user_role(request.user) == 'trainer')
    is_preview = (is_trainer and request.GET.get('preview') == '1')
    if is_trainer and not is_preview:
        return redirect('trainer_course_dashboard', course_id=course_id)

    course = get_object_or_404(Course.objects.select_related('creator', 'exam'), id=course_id)
    if course.status == 'draft':
        messages.warning(request, f'Khóa học "{course.title}" đang ở trạng thái Bản nháp và chưa được xuất bản.')
        return redirect('trainee_courses')

    exam = get_course_exam(course)

    # Lấy lượt thi gần nhất của chính user đang đăng nhập
    latest_response = CourseExamResponse.objects.filter(
        exam=exam, emp=request.user
    ).order_by('-submission_date').first() if exam else None

    enrollment = CourseEnrollment.objects.filter(emp=request.user, course=course).first()
    is_passed = latest_response.is_passed if latest_response else (enrollment.is_pass if enrollment else False)
    score = latest_response.score if latest_response else (100.0 if is_passed else 0.0)

    # -------------------------------------------------------------------------
    # Chuẩn bị dữ liệu xem lại chi tiết bài làm & đối soát đáp án đúng/sai
    # -------------------------------------------------------------------------
    questions_review = []
    correct_count = 0
    total_questions = 0

    if exam:
        # Lấy toàn bộ danh sách câu hỏi trong đề thi kèm theo các lựa chọn
        exam_questions = exam.questions.prefetch_related('choices').all().order_by('question_number')
        total_questions = exam_questions.count()

        # Tạo từ điển ánh xạ đáp án học viên đã chọn: question_id -> {answer: số thứ tự chọn, is_correct: bool}
        user_answers = {}
        if latest_response:
            for detail in latest_response.details.all():
                user_answers[detail.question_id] = {
                    'answer': detail.answer,
                    'is_correct': detail.is_correct
                }

        # Ký tự chữ cái tương ứng thứ tự đáp án (1->A, 2->B, 3->C, 4->D, 5->E)
        choice_letters = {1: 'A', 2: 'B', 3: 'C', 4: 'D', 5: 'E'}

        for q in exam_questions:
            ans_info = user_answers.get(q.id)
            user_choice = ans_info['answer'] if ans_info else 0
            # Kiểm tra câu trả lời có đúng hay không
            is_correct = (user_choice == q.correct_choice) if user_choice > 0 else False
            if is_correct:
                correct_count += 1

            # Duyệt qua các phương án A, B, C, D của câu hỏi
            choices_data = []
            for c in q.choices.all().order_by('choice_number'):
                is_user_pick = (c.choice_number == user_choice)
                is_right_answer = (c.choice_number == q.correct_choice)
                choices_data.append({
                    'number': c.choice_number,
                    'letter': choice_letters.get(c.choice_number, str(c.choice_number)),
                    'content': c.content,
                    # Đánh dấu phương án học viên đã chọn
                    'is_user_choice': is_user_pick,
                    # Đánh dấu đáp án chuẩn của câu hỏi
                    'is_correct_choice': is_right_answer,
                    # Trạng thái cụ thể để template hiển thị màu sắc và nhãn trực quan
                    'is_user_choice_correct': (is_user_pick and is_right_answer),
                    'is_user_choice_wrong': (is_user_pick and not is_right_answer),
                })

            questions_review.append({
                'number': q.question_number,
                'caption': q.caption,
                'user_choice': user_choice,
                'user_letter': choice_letters.get(user_choice, 'Chưa chọn') if user_choice > 0 else 'Chưa chọn',
                'correct_choice': q.correct_choice,
                'correct_letter': choice_letters.get(q.correct_choice, 'A'),
                'is_correct': is_correct,
                'has_answered': (user_choice > 0),
                'choices': choices_data,
            })

    wrong_count = max(0, total_questions - correct_count)

    context = {
        'course': course,
        'exam': exam,
        'response': latest_response,
        'score': score,
        'is_passed': is_passed,
        'enrollment': enrollment,
        'questions_review': questions_review,
        'correct_count': correct_count,
        'wrong_count': wrong_count,
        'total_questions': total_questions,
        'is_preview': is_preview,
    }
    return render(request, 'trainee_course_{id}_exam_result.html', context)
