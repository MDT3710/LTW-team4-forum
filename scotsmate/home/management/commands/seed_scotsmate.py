from datetime import date, timedelta
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from courses.models import (
    Course,
    CourseAccess,
    CourseEnrollment,
    CourseExam,
    CourseExamQuestion,
    CourseExamResponse,
    CourseExamResponseDetail,
    CourseMaterial,
    CourseQuestionChoice,
)
from documents.models import (
    Document,
    DocumentAccess,
    DocumentCategory,
    DocumentUpdateProposal,
)
from events.models import Event, EventRegistration
from home.models import Branch, Department
from home.roles import ensure_role_groups
from message.models import Conversation, ConversationMember, Message, StaffProfile
from posts.models import Post, PostComment, PostReaction
from surveys.models import (
    Survey,
    SurveyAccess,
    SurveyDetail,
    SurveyEssayQuestion,
    SurveyMultipleChoiceQuestion,
    SurveyQuestionChoice,
    SurveyResponse,
    SurveyResponseDetail,
)


class Command(BaseCommand):
    help = 'Khởi tạo dữ liệu mẫu đầy đủ cho tất cả 7 phân hệ của ScotsMate trên 15 tài khoản chuẩn.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Xóa sạch dữ liệu các module nghiệp vụ trước khi seed lại (giữ nguyên tài khoản, phòng ban, chi nhánh).',
        )

    def handle(self, *args, **options):
        ensure_role_groups()
        if options.get('reset'):
            self._reset_modules()

        if not options.get('reset') and (
            Post.objects.exists()
            or Course.objects.exists()
            or Document.objects.exists()
            or Survey.objects.exists()
            or Event.objects.exists()
            or Conversation.objects.exists()
        ):
            self.stdout.write(
                self.style.WARNING(
                    'CSDL đã có dữ liệu module. Dùng --reset nếu muốn tạo mới lại toàn bộ dữ liệu mẫu.'
                )
            )
            return

        users = {u.username: u for u in User.objects.select_related('employee_info', 'employee_info__dep', 'employee_info__branch')}
        if not users:
            self.stdout.write(self.style.ERROR('Không tìm thấy tài khoản nào trong auth_user.'))
            return

        def pick(username, fallback='admin'):
            return users.get(username) or users.get(fallback) or next(iter(users.values()))

        with transaction.atomic():
            self._seed_staff_profiles(users)
            self._seed_posts(pick)
            self._seed_messages(pick, list(users.values()))
            self._seed_courses(pick)
            self._seed_documents(pick)
            self._seed_surveys(pick, list(users.values()))
            self._seed_events(pick, list(users.values()))

        self.stdout.write(self.style.SUCCESS('Đã seed đầy đủ dữ liệu mẫu cho cả 7 phân hệ ScotsMate!'))

    def _reset_modules(self):
        PostReaction.objects.all().delete()
        PostComment.objects.all().delete()
        Post.objects.all().delete()

        Message.objects.all().delete()
        ConversationMember.objects.all().delete()
        Conversation.objects.all().delete()

        CourseExamResponseDetail.objects.all().delete()
        CourseExamResponse.objects.all().delete()
        CourseEnrollment.objects.all().delete()
        CourseQuestionChoice.objects.all().delete()
        CourseExamQuestion.objects.all().delete()
        CourseExam.objects.all().delete()
        CourseMaterial.objects.all().delete()
        CourseAccess.objects.all().delete()
        Course.objects.all().delete()

        DocumentUpdateProposal.objects.all().delete()
        DocumentAccess.objects.all().delete()
        Document.objects.all().delete()
        DocumentCategory.objects.all().delete()

        SurveyResponseDetail.objects.all().delete()
        SurveyResponse.objects.all().delete()
        SurveyAccess.objects.all().delete()
        SurveyDetail.objects.all().delete()
        SurveyQuestionChoice.objects.all().delete()
        SurveyMultipleChoiceQuestion.objects.all().delete()
        SurveyEssayQuestion.objects.all().delete()
        Survey.objects.all().delete()

        EventRegistration.objects.all().delete()
        Event.objects.all().delete()
        self.stdout.write(self.style.NOTICE('Đã xóa dữ liệu cũ của các module nghiệp vụ.'))

    def _seed_staff_profiles(self, users):
        for u in users.values():
            emp_info = getattr(u, 'employee_info', None)
            dept_name = emp_info.dep.name if emp_info and emp_info.dep else 'Scots English'
            branch_name = emp_info.branch.name if emp_info and emp_info.branch else 'Hà Nội'
            StaffProfile.objects.get_or_create(
                user=u,
                defaults={
                    'department': dept_name,
                    'branch': branch_name,
                    'position': 'Admin IT' if u.is_superuser else dept_name,
                },
            )

    def _seed_posts(self, pick):
        admin = pick('admin')
        hr_mgr = pick('tranminhduc')
        hr_emp = pick('phamlanchi')
        tr_mgr = pick('lethuha')
        trainer = pick('minhanh')
        rd_mgr = pick('mailinh')
        teacher_mgr = pick('tranthibich')
        ctv_mgr = pick('nguyenthihoa')
        ctv = pick('dangquanghuy')

        posts_data = [
            (
                hr_mgr,
                'Thông báo cập nhật quy trình chấm công & nghỉ phép Quý IV/2026',
                'Toàn thể CBNV vui lòng cập nhật biểu mẫu đề xuất nghỉ phép trên mục Tài liệu nội bộ trước ngày 25 hàng tháng để Phòng Nhân sự tổng hợp kịp thời.',
                Post.VISIBILITY_COMPANY,
            ),
            (
                tr_mgr,
                'Khai giảng chuỗi đào tạo Phương pháp giảng dạy & Kiểm soát chất lượng lớp học',
                'Các thầy cô, giảng viên và nhân viên mới kiểm tra mục Khóa học trên ScotsMate để hoàn thành bài giảng và bài kiểm tra đánh giá trước thứ 6 tuần này.',
                Post.VISIBILITY_COMPANY,
            ),
            (
                admin,
                'Thông báo nâng cấp hệ thống ScotsMate theo phân quyền chuẩn mới',
                'Hệ thống đã hoàn tất đồng bộ 7 phân hệ (Tài khoản, Bài đăng, Nhắn tin, Đào tạo, Tài liệu, Khảo sát, Sự kiện) và bật tính năng tự khôi phục mật khẩu qua email.',
                Post.VISIBILITY_COMPANY,
            ),
            (
                rd_mgr,
                'Chia sẻ học liệu Cambridge & IELTS phiên bản cập nhật R&D',
                'Phòng R&D vừa đưa lên danh mục Tài liệu R&D & Học thuật bộ giáo trình tham khảo mới cho các lớp Kids & Teens.',
                Post.VISIBILITY_DEPARTMENT,
            ),
            (
                ctv_mgr,
                'Lịch điều phối lớp và phản hồi giờ dạy Cộng tác viên tuần tới',
                'Các bạn cộng tác viên và chuyên viên phòng QLGV&HV kiểm tra kỹ lịch phân công trong nhóm chat Bộ phận Cộng tác viên nhé.',
                Post.VISIBILITY_DEPARTMENT,
            ),
            (
                hr_emp,
                'Ghi chú chuẩn bị hồ sơ tổng kết đánh giá cuối năm',
                'Bản nháp cá nhân để rà soát checklist công việc tháng 11.',
                Post.VISIBILITY_PRIVATE,
            ),
        ]

        created_posts = []
        for author, title, content, vis in posts_data:
            created_posts.append(
                Post.objects.create(author=author, title=title, content=content, visibility=vis)
            )

        if created_posts:
            PostReaction.objects.get_or_create(post=created_posts[0], emp=hr_emp)
            PostReaction.objects.get_or_create(post=created_posts[0], emp=tr_mgr)
            PostReaction.objects.get_or_create(post=created_posts[1], emp=trainer)
            PostReaction.objects.get_or_create(post=created_posts[1], emp=ctv)
            PostReaction.objects.get_or_create(post=created_posts[2], emp=teacher_mgr)

            PostComment.objects.create(
                post=created_posts[0], emp=hr_emp, content='Đã rõ thông tin quy trình mới ạ.'
            )
            PostComment.objects.create(
                post=created_posts[1], emp=ctv, content='Em đã đăng ký khóa học và đang ôn tập chuẩn bị làm bài test ạ.'
            )
            PostComment.objects.create(
                post=created_posts[2], emp=hr_mgr, content='Cảm ơn team IT đã nâng cấp rất mượt!'
            )

    def _seed_messages(self, pick, all_users):
        hr_mgr = pick('tranminhduc')
        hr_emp = pick('phamlanchi')
        tr_mgr = pick('lethuha')
        trainer = pick('minhanh')
        tr_emp = pick('hoangnam')
        rec_mgr = pick('lanphuong')
        rec_emp = pick('ducanh')
        rd_mgr = pick('mailinh')
        rd_emp = pick('nguyenvanan')
        tea_mgr = pick('tranthibich')
        tea_emp = pick('hoangminhduc')
        ctv_mgr = pick('nguyenthihoa')
        ctv = pick('dangquanghuy')
        admin = pick('admin')

        groups = [
            (
                'Thông báo Toàn hệ thống ScotsMate',
                'Hà Nội',
                admin,
                all_users,
                [
                    (admin, 'Chào mừng anh/chị đến với kênh thông báo vận hành ScotsMate!'),
                    (hr_mgr, 'Phòng Nhân sự đã cập nhật thông tin nhân sự đầy đủ cho các phòng ban.'),
                ],
            ),
            (
                'Nhóm Phòng Đào tạo & Trainer',
                'Hà Nội',
                tr_mgr,
                [tr_mgr, trainer, tr_emp, tea_mgr, ctv],
                [
                    (tr_mgr, 'Tuần này chúng ta hoàn thiện 2 khóa đào tạo chuyên môn trên hệ thống.'),
                    (trainer, 'Em đã soạn xong bộ 5 câu hỏi kiểm tra và passcode SCOTS2026 cho khóa CSKH & Giảng dạy ạ.'),
                    (tr_emp, 'Em đã xem trước tài liệu bài giảng, chuẩn bị rất chi tiết ạ.'),
                ],
            ),
            (
                'Nhóm Điều phối Giáo viên & Cộng tác viên',
                'Hà Nội',
                ctv_mgr,
                [ctv_mgr, tea_mgr, tea_emp, ctv, rec_mgr, rec_emp],
                [
                    (ctv_mgr, 'Các bạn CTV cập nhật xác nhận lịch đứng lớp cuối tuần tại đây nhé.'),
                    (ctv, 'Dạ em đã nhận lịch ca sáng thứ 7 tại cơ sở Cầu Giấy ạ.'),
                ],
            ),
            (
                'Nhóm Liên phòng Nhân sự & R&D',
                'Hà Nội',
                hr_mgr,
                [hr_mgr, hr_emp, rd_mgr, rd_emp],
                [
                    (rd_mgr, 'Phòng R&D gửi danh mục tài liệu học thuật để HR đồng bộ đào tạo hội nhập.'),
                ],
            ),
        ]

        for title, branch, creator, members, msgs in groups:
            convo = Conversation.objects.create(
                title=title,
                conversation_type=Conversation.TYPE_GROUP,
                branch=branch,
                created_by=creator,
            )
            seen = set()
            for u in [creator] + list(members):
                if u.id in seen:
                    continue
                seen.add(u.id)
                role = ConversationMember.ROLE_ADMIN if u.id == creator.id else ConversationMember.ROLE_MEMBER
                ConversationMember.objects.create(conversation=convo, user=u, role=role)
            for sender, text in msgs:
                Message.objects.create(conversation=convo, sender=sender, content=text)

        direct_pairs = [
            (hr_mgr, hr_emp, [(hr_mgr, 'Chi kiểm tra giúp anh danh sách nhân sự tháng 11 nhé.'), (hr_emp, 'Dạ em đang tổng hợp và gửi anh trước 16h ạ.')]),
            (tr_mgr, trainer, [(tr_mgr, 'Ánh chuẩn bị mở đợt thi khóa KH-SCOTS-01 chưa?'), (trainer, 'Dạ rồi chị, passcode là SCOTS2026 ạ.')]),
            (ctv_mgr, ctv, [(ctv_mgr, 'Huy nhớ làm bài khảo sát và bài thi hội nhập nhé.'), (ctv, 'Dạ vâng em cảm ơn chị Hoa ạ!')]),
        ]
        for u1, u2, msgs in direct_pairs:
            if u1.id == u2.id:
                continue
            convo = Conversation.objects.create(
                conversation_type=Conversation.TYPE_DIRECT,
                created_by=u1,
            )
            ConversationMember.objects.create(conversation=convo, user=u1, role=ConversationMember.ROLE_MEMBER)
            ConversationMember.objects.create(conversation=convo, user=u2, role=ConversationMember.ROLE_MEMBER)
            for sender, text in msgs:
                Message.objects.create(conversation=convo, sender=sender, content=text)

    def _seed_courses(self, pick):
        tr_mgr = pick('lethuha')
        trainer = pick('minhanh')
        hr_emp = pick('phamlanchi')
        tr_emp = pick('hoangnam')
        rec_emp = pick('ducanh')
        rd_emp = pick('nguyenvanan')
        tea_emp = pick('hoangminhduc')
        ctv = pick('dangquanghuy')

        today = date.today()

        # Course 1: Ongoing (with full materials, exam, enrollments, responses)
        c1 = Course.objects.create(
            creator=trainer,
            code='KH-SCOTS-01',
            title='Văn hóa Doanh nghiệp & Quy chuẩn Dịch vụ Scots English',
            description='Khóa đào tạo bắt buộc giúp CBNV và Cộng tác viên nắm vững giá trị cốt lõi, quy trình phục vụ học viên và chuẩn giao tiếp tại Scots English.',
            date_start=today - timedelta(days=7),
            date_end=today + timedelta(days=21),
            status='ongoing',
        )
        CourseAccess.objects.create(emp=trainer, course=c1, role='trainer')
        CourseAccess.objects.create(emp=tr_mgr, course=c1, role='manager')

        CourseMaterial.objects.create(
            course=c1,
            name='Bài 1: Tầm nhìn, Sứ mệnh & Giá trị cốt lõi Scots',
            file_type='pdf',
            duration_minutes=30,
            order=1,
            summary='Giới thiệu hệ giá trị Scots English và tiêu chuẩn ứng xử nội bộ.',
            key_points=['Tận tâm với học viên', 'Chuẩn mực sư phạm quốc tế', 'Minh bạch và hợp tác'],
            scenario_title='Xử lý thắc mắc phụ huynh giờ cao điểm',
            scenario_content='Tình huống: Phụ huynh phản hồi chưa nhận được báo cáo học tập tuần.\nCách xử lý: Lắng nghe, ghi nhận thông tin và phối hợp chuyên viên QLGV&HV phản hồi trong 2 giờ.',
            content='Nội dung chi tiết về văn hóa dịch vụ 5 sao tại hệ thống Scots English Australia.',
        )
        CourseMaterial.objects.create(
            course=c1,
            name='Bài 2: Quy trình phối hợp giữa Giáo viên, CTV và Tư vấn',
            file_type='slide',
            duration_minutes=40,
            order=2,
            summary='Chuẩn hóa luồng thông tin giữa bộ phận học thuật, QLGV&HV và CTV.',
            key_points=['Cập nhật sĩ số đúng giờ', 'Bàn giao nhận xét sau mỗi buổi học'],
            scenario_title='Bàn giao lớp khi có giáo viên thay ca',
            scenario_content='Tình huống: Giáo viên chính đột xuất bận.\nCách xử lý: CTV nhận giáo án và điểm danh qua cổng nội bộ trước giờ vào lớp 30 phút.',
            content='Hướng dẫn chi tiết quy trình bàn giao giáo án và báo cáo buổi dạy.',
        )

        exam1 = CourseExam.objects.create(
            course=c1,
            title='Bài kiểm tra Quy chuẩn Dịch vụ & Văn hóa Scots',
            passcode='SCOTS2026',
            duration=30,
            passing_score=60.0,
            is_active=True,
        )
        q1_data = [
            ('Giá trị cốt lõi ưu tiên hàng đầu trong dịch vụ học viên tại Scots English là gì?', 1, [
                'Tận tâm, minh bạch và lấy học viên làm trung tâm',
                'Chỉ xử lý khi có văn bản khiếu nại',
                'Từ chối hỗ trợ ngoài giờ hành chính',
                'Không cần ghi nhận phản hồi',
            ]),
            ('Khi có sự cố lớp học, thời hạn tối đa để phản hồi bước đầu cho phụ huynh là bao lâu?', 2, [
                'Trong vòng 7 ngày làm việc',
                'Trong vòng 2 giờ kể từ lúc tiếp nhận',
                'Đợi đến cuối khóa học',
                'Không cần phản hồi lại',
            ]),
            ('Tài khoản Cộng tác viên (CTV part-time) trên ScotsMate được phân quyền như thế nào ở phân hệ Đào tạo?', 3, [
                'Truy cập trang tạo khóa học của Trainer',
                'Truy cập trang Quản trị /admin/',
                'Tham gia học tập và làm bài kiểm tra với vai trò Trainee',
                'Phê duyệt khảo sát toàn công ty',
            ]),
            ('Mã passcode để mở bài kiểm tra đánh giá của khóa học KH-SCOTS-01 được thiết lập bởi ai?', 1, [
                'Trainer phụ trách khóa học / Admin',
                'Bất kỳ học viên nào',
                'Hệ thống tự sinh ngẫu nhiên mỗi giây',
                'Khách bên ngoài hệ thống',
            ]),
        ]
        q1_objs = []
        for idx, (caption, correct_idx, choices) in enumerate(q1_data, start=1):
            q = CourseExamQuestion.objects.create(
                exam=exam1, question_number=idx, caption=caption, correct_choice=correct_idx
            )
            for c_idx, c_text in enumerate(choices, start=1):
                CourseQuestionChoice.objects.create(question=q, choice_number=c_idx, content=c_text)
            q1_objs.append((q, correct_idx))

        # Enrollments for C1
        CourseEnrollment.objects.create(
            emp=hr_emp, course=c1, exam=exam1, study_process=100, is_pass=True, is_completed=True, is_assigned=True
        )
        resp1 = CourseExamResponse.objects.create(
            emp=hr_emp, exam=exam1, passcode='SCOTS2026', duration=12, score=100.0, is_passed=True
        )
        for q, correct_idx in q1_objs:
            CourseExamResponseDetail.objects.create(
                response=resp1, question=q, answer=correct_idx, is_correct=True
            )

        CourseEnrollment.objects.create(
            emp=ctv, course=c1, exam=exam1, study_process=50, is_pass=False, is_completed=False, is_assigned=True
        )
        CourseEnrollment.objects.create(
            emp=tr_emp, course=c1, exam=exam1, study_process=100, is_pass=False, is_completed=False, is_assigned=True
        )
        CourseEnrollment.objects.create(
            emp=rec_emp, course=c1, exam=exam1, study_process=0, is_pass=False, is_completed=False, is_assigned=False
        )

        # Course 2: Ongoing (Academic & Teaching methodology)
        c2 = Course.objects.create(
            creator=tr_mgr,
            code='KH-SCOTS-02',
            title='Phương pháp Giảng dạy Tương tác & Quản lý Lớp học Hiện đại',
            description='Trang bị kỹ năng điều phối lớp học tiếng Anh tương tác cao dành cho Trainer, nhân viên Đào tạo và Cộng tác viên giảng dạy.',
            date_start=today - timedelta(days=3),
            date_end=today + timedelta(days=30),
            status='ongoing',
        )
        CourseAccess.objects.create(emp=tr_mgr, course=c2, role='trainer')
        CourseAccess.objects.create(emp=trainer, course=c2, role='assistant')
        CourseMaterial.objects.create(
            course=c2,
            name='Bài 1: Kỹ thuật dẫn dắt Warm-up & Classroom Management',
            file_type='video',
            duration_minutes=45,
            order=1,
            summary='Tổ chức hoạt động khởi động 5 phút đầu giờ hiệu quả.',
            key_points=['Tạo tâm lý thoải mái', 'Khuyến khích học viên giao tiếp ngay từ phút đầu'],
            content='Hướng dẫn 5 mẫu hoạt động warm-up theo từng nhóm tuổi.',
        )
        exam2 = CourseExam.objects.create(
            course=c2,
            title='Kiểm tra Phương pháp Giảng dạy Tương tác',
            passcode='TEACH2026',
            duration=25,
            passing_score=70.0,
            is_active=True,
        )
        q2 = CourseExamQuestion.objects.create(
            exam=exam2,
            question_number=1,
            caption='Mục tiêu chính của hoạt động Warm-up đầu buổi học là gì?',
            correct_choice=2,
        )
        for c_idx, c_text in enumerate([
            'Kiểm tra bài cũ gây áp lực cho học viên',
            'Tạo không khí tích cực, kích hoạt ngôn ngữ tự nhiên',
            'Thay thế toàn bộ nội dung ngữ pháp',
            'Kéo dài thời gian nghỉ giải lao',
        ], start=1):
            CourseQuestionChoice.objects.create(question=q2, choice_number=c_idx, content=c_text)

        CourseEnrollment.objects.create(
            emp=ctv, course=c2, exam=exam2, study_process=50, is_pass=False, is_completed=False, is_assigned=True
        )
        CourseEnrollment.objects.create(
            emp=tea_emp, course=c2, exam=exam2, study_process=100, is_pass=True, is_completed=True, is_assigned=True
        )

        # Course 3: Completed course + Course 4: Draft
        c3 = Course.objects.create(
            creator=trainer,
            code='KH-SCOTS-03',
            title='An toàn Thông tin & Bảo mật Dữ liệu Học viên',
            description='Khóa đào tạo định kỳ về nguyên tắc bảo mật tài khoản, dữ liệu cá nhân và phòng tránh rủi ro an ninh mạng.',
            date_start=today - timedelta(days=45),
            date_end=today - timedelta(days=10),
            status='completed',
        )
        CourseAccess.objects.create(emp=trainer, course=c3, role='trainer')
        CourseMaterial.objects.create(
            course=c3,
            name='Bài 1: Nguyên tắc đặt mật khẩu và tự khôi phục qua email',
            file_type='pdf',
            duration_minutes=20,
            order=1,
            summary='Hướng dẫn sử dụng chức năng Quên mật khẩu an toàn trên ScotsMate.',
        )
        CourseEnrollment.objects.create(
            emp=rd_emp, course=c3, study_process=100, is_pass=True, is_completed=True, is_assigned=True
        )

        c4 = Course.objects.create(
            creator=trainer,
            code='KH-SCOTS-04',
            title='Chuẩn bị Khóa Hội nhập Nhân sự Mới (Tháng 12)',
            description='Khóa đào tạo bản nháp đang biên soạn giáo trình cho đợt tuyển dụng cuối năm.',
            date_start=today + timedelta(days=10),
            date_end=today + timedelta(days=40),
            status='draft',
        )
        CourseAccess.objects.create(emp=trainer, course=c4, role='trainer')

    def _seed_documents(self, pick):
        admin = pick('admin')
        hr_mgr = pick('tranminhduc')
        hr_emp = pick('phamlanchi')
        tr_mgr = pick('lethuha')
        tr_emp = pick('hoangnam')
        rd_mgr = pick('mailinh')
        rd_emp = pick('nguyenvanan')
        ctv_mgr = pick('nguyenthihoa')
        ctv = pick('dangquanghuy')

        dept_hr = Department.objects.filter(id=1).first()
        dept_tr = Department.objects.filter(id=2).first()
        dept_rd = Department.objects.filter(id=11).first()
        dept_ctv = Department.objects.filter(id=28).first()

        cat_hr = DocumentCategory.objects.create(
            name='Quy định & Chính sách HR',
            code='DM-HR',
            icon_name='shield',
            description='Nội quy lao động, chính sách phúc lợi và quy trình nhân sự Scots English.',
            display_order=1,
        )
        cat_tr = DocumentCategory.objects.create(
            name='Tài liệu Đào tạo & Giảng dạy',
            code='DM-TRAIN',
            icon_name='book',
            description='Giáo án chuẩn, sổ tay Trainer và hướng dẫn tổ chức đào tạo nội bộ.',
            display_order=2,
        )
        cat_it = DocumentCategory.objects.create(
            name='Hướng dẫn Vận hành Hệ thống',
            code='DM-IT',
            icon_name='settings',
            description='Tài liệu hướng dẫn sử dụng cổng ScotsMate, quản lý tài khoản và bảo mật.',
            display_order=3,
        )
        cat_rd = DocumentCategory.objects.create(
            name='Tài liệu R&D & Học thuật',
            code='DM-RD',
            icon_name='layers',
            description='Khung chương trình nghiên cứu học thuật và tài liệu cập nhật đề thi.',
            display_order=4,
        )

        def make_pdf(filename, text):
            body = (
                b'%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n% '
                + text.encode('utf-8')
            )
            return ContentFile(body, name=filename)

        now = timezone.now()
        d1 = Document.objects.create(
            title='Sổ tay Nhân viên Scots English 2026',
            code='DOC-HR-001',
            category=cat_hr,
            description='Tổng hợp quy định giờ làm việc, nghỉ phép, khen thưởng và văn hóa nội bộ.',
            file=make_pdf('so-tay-nhan-vien-2026.pdf', 'So tay nhan vien Scots English 2026'),
            access_scope='ALL',
            creator=hr_emp,
            approver=hr_mgr,
            status='APPROVED',
            request_type='NEW',
            is_visible=True,
            approved_at=now,
        )
        Document.objects.create(
            title='Hướng dẫn Sử dụng ScotsMate cho Nhân viên & Quản lý',
            code='DOC-IT-001',
            category=cat_it,
            description='Hướng dẫn đăng nhập, đổi/khôi phục mật khẩu qua email và quy chuẩn 7 phân hệ.',
            file=make_pdf('huong-dan-scotsmate-2026.pdf', 'Huong dan su dung ScotsMate'),
            access_scope='ALL',
            creator=admin,
            approver=admin,
            status='APPROVED',
            request_type='NEW',
            is_visible=True,
            approved_at=now,
        )
        d3 = Document.objects.create(
            title='Bộ Tiêu chuẩn Lớp học Cộng tác viên (CTV)',
            code='DOC-CTV-001',
            category=cat_tr,
            description='Tài liệu hướng dẫn quy trình chấm công, bàn giao lớp và tiêu chuẩn trợ giảng/giáo viên CTV.',
            file=make_pdf('tieu-chuan-ctv.pdf', 'Tieu chuan lop hoc CTV'),
            access_scope='DEPARTMENT',
            creator=ctv,
            approver=ctv_mgr,
            status='APPROVED',
            request_type='NEW',
            is_visible=True,
            approved_at=now,
        )
        if dept_ctv:
            DocumentAccess.objects.create(document=d3, department=dept_ctv)

        d4 = Document.objects.create(
            title='Khung Học thuật Chương trình Teens & IELTS Q4/2026',
            code='DOC-RD-001',
            category=cat_rd,
            description='Tài liệu nội bộ phòng R&D và Đào tạo về cập nhật giáo trình và bộ đề kiểm tra.',
            file=make_pdf('khung-hoc-thuat-rd.pdf', 'Khung hoc thuat R&D'),
            access_scope='DEPARTMENT',
            creator=rd_emp,
            approver=rd_mgr,
            status='APPROVED',
            request_type='NEW',
            is_visible=True,
            approved_at=now,
        )
        if dept_rd:
            DocumentAccess.objects.create(document=d4, department=dept_rd)
        if dept_tr:
            DocumentAccess.objects.create(document=d4, department=dept_tr)

        # Pending NEW document (Department HR - visible to tranminhduc & admin in approve list)
        pending_hr = Document.objects.create(
            title='Biểu mẫu Đề xuất Đào tạo Nâng cao (Chờ duyệt HR)',
            code='DOC-HR-002',
            category=cat_hr,
            description='Đề xuất mẫu phiếu đăng ký đào tạo nội bộ cho nhân sự các chi nhánh.',
            file=make_pdf('bieu-mau-dao-tao.pdf', 'Bieu mau de xuat dao tao'),
            access_scope='DEPARTMENT',
            creator=hr_emp,
            status='PENDING',
            request_type='NEW',
        )
        if dept_hr:
            DocumentAccess.objects.create(document=pending_hr, department=dept_hr)

        # Pending UPDATE document (Department Đào tạo - visible to lethuha & admin in approve list)
        pending_tr = Document.objects.create(
            title='Tài liệu Hướng dẫn Trainer Soạn Đề Thi (Chờ duyệt Đào tạo)',
            code='DOC-TR-002',
            category=cat_tr,
            description='Bản cập nhật hướng dẫn thiết lập mã passcode và ma trận câu hỏi.',
            file=make_pdf('huong-dan-soan-de-v1.pdf', 'Huong dan soan de v1'),
            access_scope='DEPARTMENT',
            creator=tr_emp,
            status='PENDING',
            request_type='UPDATE',
        )
        if dept_tr:
            DocumentAccess.objects.create(document=pending_tr, department=dept_tr)
        DocumentUpdateProposal.objects.create(
            document=pending_tr,
            proposed_title='Tài liệu Hướng dẫn Trainer Soạn Đề Thi (Phiên bản 2.0)',
            proposed_category=cat_tr,
            proposed_file=make_pdf('huong-dan-soan-de-v2.pdf', 'Huong dan soan de v2'),
            proposed_scope='DEPARTMENT',
            submitted_by=tr_emp,
            approver=tr_mgr,
        )

    def _seed_surveys(self, pick, all_users):
        hr_mgr = pick('tranminhduc')
        hr_emp = pick('phamlanchi')
        tr_mgr = pick('lethuha')
        tr_emp = pick('hoangnam')
        rd_mgr = pick('mailinh')
        rd_emp = pick('nguyenvanan')
        ctv = pick('dangquanghuy')

        dept_hr = Department.objects.filter(id=1).first() or Department.objects.first()
        dept_tr = Department.objects.filter(id=2).first() or dept_hr
        dept_rd = Department.objects.filter(id=11).first() or dept_hr

        mc_ct = ContentType.objects.get_for_model(SurveyMultipleChoiceQuestion)
        essay_ct = ContentType.objects.get_for_model(SurveyEssayQuestion)

        now = timezone.now()

        # Survey 1: Approved, open, non-anonymous, with responses
        s1 = Survey.objects.create(
            department=dept_hr,
            creator=hr_emp,
            approver=hr_mgr,
            name='Khảo sát Mức độ Hài lòng Môi trường Làm việc Quý IV/2026',
            is_approved=True,
            is_respondable=True,
            is_visible=True,
            anonymous=False,
            description='Khảo sát thu thập ý kiến toàn bộ CBNV về điều kiện làm việc, phúc lợi và công cụ ScotsMate.',
            response_deadline=now + timedelta(days=14),
        )
        mc1 = SurveyMultipleChoiceQuestion.objects.create(max_choice=1)
        c1_a = SurveyQuestionChoice.objects.create(question=mc1, content='Rất hài lòng')
        c1_b = SurveyQuestionChoice.objects.create(question=mc1, content='Hài lòng')
        c1_c = SurveyQuestionChoice.objects.create(question=mc1, content='Bình thường - Cần cải thiện thêm')
        q1_1 = SurveyDetail.objects.create(
            survey=s1, question_type=mc_ct, object_id=mc1.id,
            caption='Bạn đánh giá thế nào về môi trường làm việc và sự phối hợp giữa các phòng ban?',
            is_required=True,
        )
        es1 = SurveyEssayQuestion.objects.create(max_character=500)
        q1_2 = SurveyDetail.objects.create(
            survey=s1, question_type=essay_ct, object_id=es1.id,
            caption='Đề xuất cải tiến giúp công việc hằng ngày tại Scots English hiệu quả hơn:',
            is_required=False,
        )
        for u in all_users:
            SurveyAccess.objects.create(
                emp=u,
                survey=s1,
                can_respond=True,
                can_view_responses=(u.id in {hr_mgr.id, hr_emp.id}),
            )

        # Responses for Survey 1
        r1 = SurveyResponse.objects.create(survey=s1, respondent=tr_emp, submission_date=now - timedelta(days=1))
        SurveyResponseDetail.objects.create(survey_response=r1, question=q1_1, answer=str(c1_a.id))
        SurveyResponseDetail.objects.create(survey_response=r1, question=q1_2, answer='Hệ thống ScotsMate giúp tìm tài liệu đào tạo nhanh hơn nhiều.')

        r2 = SurveyResponse.objects.create(survey=s1, respondent=ctv, submission_date=now - timedelta(hours=8))
        SurveyResponseDetail.objects.create(survey_response=r2, question=q1_1, answer=str(c1_b.id))
        SurveyResponseDetail.objects.create(survey_response=r2, question=q1_2, answer='Mong có thêm lịch nhắc sự kiện đào tạo sớm hơn 3 ngày.')

        # Survey 2: Approved, open, anonymous
        s2 = Survey.objects.create(
            department=dept_tr,
            creator=tr_mgr,
            approver=tr_mgr,
            name='Đánh giá Chất lượng Khóa Đào tạo Nội bộ 2026 (Ẩn danh)',
            is_approved=True,
            is_respondable=True,
            is_visible=True,
            anonymous=True,
            description='Khảo sát ẩn danh góp ý về nội dung bài giảng, tài liệu và bài kiểm tra của Phòng Đào tạo.',
            response_deadline=now + timedelta(days=20),
        )
        mc2 = SurveyMultipleChoiceQuestion.objects.create(max_choice=1)
        c2_a = SurveyQuestionChoice.objects.create(question=mc2, content='Phù hợp thực tế công việc')
        c2_b = SurveyQuestionChoice.objects.create(question=mc2, content='Cần bổ sung thêm tình huống mẫu')
        q2_1 = SurveyDetail.objects.create(
            survey=s2, question_type=mc_ct, object_id=mc2.id,
            caption='Mức độ sát thực tế của các tình huống trong khóa đào tạo vừa qua:',
            is_required=True,
        )
        for u in all_users:
            SurveyAccess.objects.create(
                emp=u,
                survey=s2,
                can_respond=True,
                can_view_responses=(u.id == tr_mgr.id),
            )
        r3 = SurveyResponse.objects.create(survey=s2, respondent=hr_emp, submission_date=now - timedelta(hours=4))
        SurveyResponseDetail.objects.create(survey_response=r3, question=q2_1, answer=str(c2_a.id))

        # Survey 3 & 4: Pending approval in HR and R&D departments
        s3 = Survey.objects.create(
            department=dept_hr,
            creator=hr_emp,
            name='Khảo sát Nhu cầu Gắn kết & Teambuilding Cuối năm',
            is_approved=False,
            is_respondable=True,
            is_visible=True,
            anonymous=False,
            description='Đang chờ Trưởng phòng Nhân sự (tranminhduc) phê duyệt phát hành.',
            response_deadline=now + timedelta(days=10),
        )
        mc3 = SurveyMultipleChoiceQuestion.objects.create(max_choice=1)
        SurveyQuestionChoice.objects.create(question=mc3, content='Du lịch nghỉ dưỡng 2 ngày 1 đêm')
        SurveyQuestionChoice.objects.create(question=mc3, content='Gala Dinner & Tôn vinh tại Hà Nội')
        SurveyDetail.objects.create(
            survey=s3, question_type=mc_ct, object_id=mc3.id,
            caption='Hình thức tổ chức sự kiện tổng kết cuối năm bạn mong muốn:',
            is_required=True,
        )

        s4 = Survey.objects.create(
            department=dept_rd,
            creator=rd_emp,
            name='Khảo sát Góp ý Giáo trình Teens & IELTS Q1/2027',
            is_approved=False,
            is_respondable=True,
            is_visible=True,
            anonymous=False,
            description='Đang chờ Trưởng phòng R&D (mailinh) phê duyệt.',
            response_deadline=now + timedelta(days=12),
        )
        es4 = SurveyEssayQuestion.objects.create(max_character=400)
        SurveyDetail.objects.create(
            survey=s4, question_type=essay_ct, object_id=es4.id,
            caption='Những điểm cần điều chỉnh trong giáo trình hiện tại:',
            is_required=True,
        )

    def _seed_events(self, pick, all_users):
        admin = pick('admin')
        hr_mgr = pick('tranminhduc')
        hr_emp = pick('phamlanchi')
        tr_mgr = pick('lethuha')
        trainer = pick('minhanh')
        tea_mgr = pick('tranthibich')
        ctv = pick('dangquanghuy')

        branch_default = Branch.objects.first()
        dept_hr = Department.objects.filter(id=1).first()
        dept_tr = Department.objects.filter(id=2).first()
        dept_it = Department.objects.filter(id=13).first()
        dept_tea = Department.objects.filter(id=12).first()

        now = timezone.now()

        ev1 = Event.objects.create(
            title='Workshop Phương pháp Giảng dạy Chủ động & Ứng dụng Công nghệ',
            category=Event.CATEGORY_WORKSHOP,
            description='Hội thảo chuyên môn kết hợp chia sẻ kinh nghiệm thực tế từ đội ngũ Trainer và bộ phận Quản lý giáo viên & học viên.',
            agenda='08:30 - Đón tiếp & Check-in\n09:00 - Chia sẻ mô hình lớp học tương tác\n10:30 - Thảo luận tình huống cùng CTV & Giáo viên',
            date_start=now + timedelta(days=5, hours=2),
            date_end=now + timedelta(days=5, hours=5),
            location='Hội trường tầng 5 - Trụ sở Cầu Giấy, Hà Nội',
            branch=branch_default,
            department=dept_tr,
            organizer=tr_mgr,
            max_participants=80,
            status=Event.STATUS_UPCOMING,
        )
        ev2 = Event.objects.create(
            title='Ngày hội Văn hóa Scots English & Vinh danh Nhân sự Tiêu biểu Q4',
            category=Event.CATEGORY_CEREMONY,
            description='Sự kiện gắn kết thường quý nhằm tôn vinh các cá nhân, tập thể có đóng góp nổi bật trong công tác đào tạo và vận hành.',
            agenda='14:00 - Khai mạc & Tổng kết Quý IV\n15:00 - Trao giải Nhân sự & Trainer tiêu biểu\n16:30 - Giao lưu văn nghệ nội bộ',
            date_start=now + timedelta(days=12),
            date_end=now + timedelta(days=12, hours=4),
            location='Trung tâm Hội nghị Scots English - Hà Nội',
            branch=branch_default,
            department=dept_hr,
            organizer=hr_mgr,
            max_participants=120,
            status=Event.STATUS_UPCOMING,
        )
        ev3 = Event.objects.create(
            title='Tập huấn Hệ thống ScotsMate & Quy chuẩn An toàn Dữ liệu',
            category=Event.CATEGORY_TRAINING,
            description='Hướng dẫn chi tiết cho Trưởng phòng và Nhân sự cách vận hành luồng phê duyệt tài liệu, khảo sát, quản trị nhóm chat và khôi phục mật khẩu.',
            agenda='09:00 - Giới thiệu luồng nghiệp vụ 7 module\n10:00 - Hỏi đáp trực tiếp cùng Phòng IT',
            date_start=now + timedelta(days=2),
            date_end=now + timedelta(days=2, hours=2),
            location='Phòng Họp Trực tuyến Zoom / Google Meet ScotsMate',
            branch=branch_default,
            department=dept_it,
            organizer=admin,
            max_participants=100,
            status=Event.STATUS_UPCOMING,
        )
        ev4 = Event.objects.create(
            title='Giải Giao lưu Cầu lông & Thể thao Scots Mở rộng',
            category=Event.CATEGORY_SPORTS,
            description='Hoạt động rèn luyện thể thao giao lưu giữa các phòng ban và cơ sở khu vực Hà Nội.',
            agenda='07:30 - Khởi động\n08:00 - Thi đấu vòng bảng\n11:00 - Trao huy chương',
            date_start=now - timedelta(days=14),
            date_end=now - timedelta(days=14) + timedelta(hours=4),
            location='Nhà thi đấu Quận Cầu Giấy',
            branch=branch_default,
            department=dept_tea,
            organizer=tea_mgr,
            max_participants=60,
            status=Event.STATUS_COMPLETED,
        )

        for ev, attendees in [
            (ev1, [trainer, tea_mgr, ctv, hr_emp]),
            (ev2, [hr_emp, tr_mgr, trainer, ctv]),
            (ev3, [hr_mgr, tr_mgr, ctv]),
            (ev4, [hr_emp, ctv, trainer]),
        ]:
            for u in attendees:
                EventRegistration.objects.get_or_create(
                    event=ev,
                    user=u,
                    defaults={'attended': (ev.status == Event.STATUS_COMPLETED)},
                )
