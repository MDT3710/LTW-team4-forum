from datetime import date, timedelta
from pathlib import Path
from django.conf import settings
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
        admin = pick('admin')
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

        today = date.today()
        materials_dir = Path(settings.MEDIA_ROOT) / 'courses' / 'materials'

        def attach_file(mat, filename):
            if (materials_dir / filename).is_file():
                mat.file.name = f'courses/materials/{filename}'
                mat.save(update_fields=['file'])
            else:
                body = b'%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n'
                mat.file.save(filename, ContentFile(body), save=True)

        def build_exam_questions(exam_obj, q_specs):
            q_objs = []
            for idx, (caption, correct_idx, choices) in enumerate(q_specs, start=1):
                q = CourseExamQuestion.objects.create(
                    exam=exam_obj, question_number=idx, caption=caption, correct_choice=correct_idx
                )
                for c_idx, c_text in enumerate(choices, start=1):
                    CourseQuestionChoice.objects.create(question=q, choice_number=c_idx, content=c_text)
                q_objs.append((q, correct_idx))
            return q_objs

        def record_exam_attempt(emp, exam_obj, q_objs, picked_choices, duration=15):
            correct_cnt = sum(1 for (q, ans), pick_c in zip(q_objs, picked_choices) if pick_c == ans)
            score = round(correct_cnt / len(q_objs) * 100, 1) if q_objs else 0.0
            is_passed = score >= exam_obj.passing_score
            resp = CourseExamResponse.objects.create(
                emp=emp,
                exam=exam_obj,
                passcode=exam_obj.passcode,
                duration=duration,
                score=score,
                is_passed=is_passed,
            )
            for (q, ans), pick_c in zip(q_objs, picked_choices):
                CourseExamResponseDetail.objects.create(
                    response=resp, question=q, answer=pick_c, is_correct=(pick_c == ans)
                )
            return resp

        # =====================================================================
        # 1. KH-1026 (ONGOING - creator: minhanh, assistant: lethuha)
        #    Có đủ 4 định dạng (PDF, DOCX, Video MP4), bài thi 5 câu, đủ trạng thái học viên
        # =====================================================================
        c1 = Course.objects.create(
            creator=trainer,
            code='KH-1026',
            title='Văn hóa Doanh nghiệp & Quy chuẩn Dịch vụ 5 Sao Scots English',
            description='Khóa đào tạo trọng tâm về bộ quy chuẩn đón tiếp phụ huynh/học viên, nguyên tắc giao tiếp nội bộ và xử lý tình huống dịch vụ tại hệ thống Scots English.',
            date_start=today - timedelta(days=10),
            date_end=today + timedelta(days=20),
            status='ongoing',
        )
        CourseAccess.objects.create(emp=trainer, course=c1, role='trainer')
        CourseAccess.objects.create(emp=tr_mgr, course=c1, role='assistant')

        m1_1 = CourseMaterial.objects.create(
            course=c1,
            name='Bài 1: Quy chuẩn tiếp đón & giao tiếp chuyên nghiệp tại cơ sở',
            file_type='pdf',
            duration_minutes=25,
            order=1,
            summary='Chuẩn hóa tác phong, nụ cười, lời chào và quy trình đón tiếp phụ huynh – học viên khi tới trung tâm.',
            key_points=[
                {'title': '3 giây ấn tượng đầu tiên', 'desc': 'Chủ động đứng dậy chào bằng ánh mắt thân thiện ngay khi phụ huynh bước vào sảnh.'},
                {'title': 'Lắng nghe thấu cảm', 'desc': 'Không ngắt lời phụ huynh; ghi chú đầy đủ thông tin lớp và tên học viên.'},
                {'title': 'Phản hồi đúng cam kết', 'desc': 'Mọi yêu cầu cần xác minh chuyên môn phải hẹn giờ phản hồi cụ thể trong 2 giờ.'},
                {'title': 'Đồng bộ bộ phận', 'desc': 'Chuyển tiếp thông tin gọn gàng giữa Tư vấn, QLGV&HV và Giáo viên đứng lớp.'},
            ],
            scenario_title='Phụ huynh phản ánh chưa nhận được nhận xét buổi học tuần',
            scenario_content='Tình huống: Phụ huynh tới quầy lễ tân bày tỏ không hài lòng vì cuối tuần vẫn chưa nhận được báo cáo học tập của bé.\nCách xử lý: Xin lỗi chân thành vì sự bất tiện, kiểm tra ngay trên hệ thống và liên hệ chuyên viên QLGV&HV phụ trách lớp gửi bản cập nhật trong vòng 2 giờ kèm lời nhắn xác nhận.',
            content='<p>Tài liệu PDF đính kèm hướng dẫn chi tiết từng điểm chạm dịch vụ tại quầy lễ tân và phòng tư vấn.</p>',
        )
        attach_file(m1_1, 'Quy_chuan_tiep_don_va_giao_tiep.pdf')

        m1_2 = CourseMaterial.objects.create(
            course=c1,
            name='Bài 2: Nguyên tắc vàng trong giao tiếp sư phạm & nội bộ',
            file_type='pdf',
            duration_minutes=30,
            order=2,
            summary='Hệ thống hóa các nguyên tắc giao tiếp tích cực giữa nhân sự vận hành, giáo viên và cộng tác viên.',
            key_points=[
                {'title': 'Ngôn từ tích cực', 'desc': 'Ưu tiên cách diễn đạt mang tính giải pháp thay vì đổ lỗi khi phối hợp ca dạy.'},
                {'title': 'Tôn trọng sự khác biệt', 'desc': 'Giao tiếp cởi mở, lịch sự với cả giáo viên nước ngoài, giáo viên Việt Nam và CTV.'},
            ],
            scenario_title='Bất đồng lịch phân công dạy bù vào giờ cao điểm',
            scenario_content='Tình huống: Giáo viên và điều phối viên hiểu nhầm khung giờ dạy bù cuối tuần.\nCách xử lý: Trao đổi trực tiếp trên nhóm điều phối chính thức, đối chiếu lịch xác nhận bằng văn bản và chốt phương án dự phòng sớm nhất.',
            content='<p>Học viên đọc kỹ tài liệu PDF để nắm 6 nguyên tắc cốt lõi khi giao tiếp trong môi trường giáo dục.</p>',
        )
        attach_file(m1_2, 'Nguyen_tac_vang_giao_tiep.pdf')

        m1_3 = CourseMaterial.objects.create(
            course=c1,
            name='Bài 3: Biểu mẫu & Checklist bàn giao tác nghiệp hằng ngày (Word)',
            file_type='doc',
            duration_minutes=20,
            order=3,
            summary='Tải về tài liệu Word hướng dẫn quy trình kiểm tra sĩ số, tài sản lớp học và bàn giao ca.',
            key_points=[
                {'title': 'Checklist đầu ca', 'desc': 'Kiểm tra thiết bị trình chiếu, loa, danh sách học viên trước giờ học 15 phút.'},
                {'title': 'Báo cáo cuối ca', 'desc': 'Cập nhật ngay học viên vắng mặt để bộ phận chăm sóc phụ huynh liên hệ kịp thời.'},
            ],
            content='<p>Nhân viên tải file DOCX đính kèm để dùng trực tiếp tại cơ sở.</p>',
        )
        attach_file(m1_3, 'Tai_lieu_nghiep_vu_mau.docx')

        m1_4 = CourseMaterial.objects.create(
            course=c1,
            name='Bài 4: Video minh họa xử lý tình huống dịch vụ thực tế',
            file_type='video',
            duration_minutes=35,
            order=4,
            summary='Video tình huống thực tế về cách tiếp nhận góp ý phụ huynh và phối hợp đa phòng ban.',
            key_points=[
                {'title': 'Quan sát ngôn ngữ cơ thể', 'desc': 'Giữ tư thế cởi mở, ghi chép nghiêm túc khi tiếp nhận phản hồi.'},
                {'title': 'Chốt hành động rõ ràng', 'desc': 'Luôn tóm tắt lại hướng giải quyết trước khi kết thúc cuộc trò chuyện.'},
            ],
            content='<p>Xem hết video bài giảng để hoàn tất 100% giáo trình trước khi mở phòng thi.</p>',
        )
        attach_file(m1_4, 'video_bai_giang_mau.mp4')

        exam1 = CourseExam.objects.create(
            course=c1,
            title='Kiểm tra Năng lực Quy chuẩn Dịch vụ 5 Sao Scots',
            passcode='SCOTS2026',
            duration=30,
            passing_score=80.0,
            is_active=True,
        )
        q1_objs = build_exam_questions(exam1, [
            ('Khi phụ huynh bước vào sảnh cơ sở Scots English, nhân sự cần phản ứng đầu tiên như thế nào?', 1, [
                'Chủ động đứng dậy, giao tiếp bằng ánh mắt và chào đón niềm nở',
                'Đợi phụ huynh lại gần bàn mới ngẩng lên hỏi',
                'Tiếp tục xử lý việc trên máy tính rồi vẫy tay ra hiệu chờ',
                'Chỉ mỉm cười mà không cần chào hỏi',
            ]),
            ('Thời hạn cam kết tối đa để phản hồi bước đầu khi phụ huynh cần xác minh thông tin lớp học là bao lâu?', 2, [
                'Trong vòng 7 ngày làm việc',
                'Trong vòng 2 giờ kể từ khi tiếp nhận thông tin',
                'Cuối tháng khi tổng kết sĩ số',
                'Không cần phản hồi nếu chưa có kết quả cuối cùng',
            ]),
            ('Trong giao tiếp nội bộ giữa Giáo viên, CTV và Điều phối viên, điều nào sau đây được ưu tiên nhất?', 3, [
                'Trao đổi truyền miệng không cần xác nhận',
                'Giữ thông tin riêng không chia sẻ cho ca sau',
                'Dùng ngôn từ xây dựng và xác nhận rõ trên kênh điều phối chính thức',
                'Chờ hết tuần mới báo cáo lịch thay đổi',
            ]),
            ('Trước giờ vào lớp học bao nhiêu phút nhân sự cơ sở cần hoàn tất kiểm tra thiết bị phòng học?', 2, [
                'Đúng lúc chuông reo vào lớp',
                'Trước giờ học tối thiểu 15 phút',
                'Sau khi học viên vào lớp 10 phút',
                'Chỉ kiểm tra khi giáo viên yêu cầu',
            ]),
            ('Bộ checklist tác nghiệp hằng ngày tại cơ sở cần đảm bảo những nội dung nào? (Chọn đáp án đầy đủ nhất)', 5, [
                'Kiểm tra thiết bị máy chiếu/âm thanh',
                'Cập nhật danh sách sĩ số & học viên vắng',
                'Bàn giao đầy đủ ghi chú ca trực cho ca sau',
                'Phối hợp QLGV&HV phản hồi phụ huynh',
                'Tất cả các phương án trên đều đúng',
            ]),
        ])

        # Enrollments đa dạng trạng thái cho KH-1026
        CourseEnrollment.objects.create(
            emp=hr_emp, course=c1, exam=exam1, study_process=100, is_pass=True, is_completed=True, is_assigned=True
        )
        record_exam_attempt(hr_emp, exam1, q1_objs, [1, 2, 3, 2, 5], duration=11)

        CourseEnrollment.objects.create(
            emp=tea_emp, course=c1, exam=exam1, study_process=100, is_pass=False, is_completed=False, is_assigned=True
        )
        record_exam_attempt(tea_emp, exam1, q1_objs, [1, 1, 1, 2, 1], duration=18)  # 40 điểm (Trượt -> đã khóa thi lại)

        # hoangnam đã học 100% bài giảng và SẴN SÀNG nhập passcode SCOTS2026 để thi thử ngay
        CourseEnrollment.objects.create(
            emp=tr_emp, course=c1, exam=exam1, study_process=100, is_pass=False, is_completed=False, is_assigned=True
        )
        # dangquanghuy (CTV) mới học 50% (2/4 bài) -> đang học dở, chưa mở khóa thi
        CourseEnrollment.objects.create(
            emp=ctv, course=c1, exam=exam1, study_process=50, is_pass=False, is_completed=False, is_assigned=True
        )
        # ducanh tự chọn 25%
        CourseEnrollment.objects.create(
            emp=rec_emp, course=c1, exam=exam1, study_process=25, is_pass=False, is_completed=False, is_assigned=False
        )
        # Lưu ý: nguyenvanan CHƯA ghi danh vào KH-1026 để test luồng "Đăng ký tự chọn"!

        # =====================================================================
        # 2. KH-1027 (ONGOING - creator: minhanh)
        #    Kỹ năng Tư vấn Tuyển sinh & Đàm phán Tái tục
        # =====================================================================
        c2 = Course.objects.create(
            creator=trainer,
            code='KH-1027',
            title='Kỹ năng Tư vấn Tuyển sinh & Chăm sóc Tái tục Học viên',
            description='Trang bị kịch bản tư vấn lộ trình học tập chuẩn Cambridge/IELTS và kỹ năng đàm phán giữ chân học viên tái tục.',
            date_start=today - timedelta(days=5),
            date_end=today + timedelta(days=25),
            status='ongoing',
        )
        CourseAccess.objects.create(emp=trainer, course=c2, role='trainer')

        m2_1 = CourseMaterial.objects.create(
            course=c2,
            name='Bài 1: Kịch bản tư vấn tái tục theo giai đoạn học tập',
            file_type='pdf',
            duration_minutes=30,
            order=1,
            summary='Xây dựng lộ trình tư vấn tái tục từ mốc 70% khóa học hiện tại.',
            key_points=[
                {'title': 'Bám sát kết quả học tập', 'desc': 'Dùng báo cáo tiến độ thực tế của học viên làm cơ sở thuyết phục.'},
                {'title': 'Tư vấn lộ trình tiếp nối', 'desc': 'Chỉ rõ mục tiêu đầu ra ở cấp độ kế tiếp phù hợp năng lực của bé.'},
            ],
            content='<p>Tài liệu PDF đính kèm kịch bản gọi điện và gặp trực tiếp phụ huynh tái tục.</p>',
        )
        attach_file(m2_1, 'Kich_ban_tu_van_tai_tuc.pdf')

        m2_2 = CourseMaterial.objects.create(
            course=c2,
            name='Bài 2: Nghệ thuật đàm phán & xử lý từ chối học phí',
            file_type='pdf',
            duration_minutes=35,
            order=2,
            summary='Kỹ thuật lắng nghe, đồng cảm và giải tỏa băn khoăn về học phí hoặc lịch học.',
            key_points=[
                {'title': 'Cô lập đúng rào cản', 'desc': 'Xác định phụ huynh đang băn khoăn về hiệu quả học, thời gian hay chi phí.'},
                {'title': 'Quy đổi giá trị', 'desc': 'So sánh giá trị tiến bộ thực tế của học viên với mức đầu tư khóa mới.'},
            ],
            content='<p>Đọc kỹ tài liệu PDF để nắm 5 mẫu câu xử lý từ chối phổ biến.</p>',
        )
        attach_file(m2_2, 'Nghe_thuat_dam_phan.pdf')

        m2_3 = CourseMaterial.objects.create(
            course=c2,
            name='Bài 3: Thực hành mô phỏng cuộc gọi tư vấn',
            file_type='video',
            duration_minutes=25,
            order=3,
            summary='Video tình huống mô phỏng cuộc gọi hẹn gặp tư vấn tái tục.',
            key_points=[
                {'title': 'Mở đầu thu hút', 'desc': 'Chia sẻ ngay 1 điểm tiến bộ cụ thể của học viên trong tháng.'},
            ],
        )
        attach_file(m2_3, 'video_bai_giang_mau.mp4')

        exam2 = CourseExam.objects.create(
            course=c2,
            title='Đánh giá Kỹ năng Tư vấn & Tái tục',
            passcode='SALES26',
            duration=25,
            passing_score=75.0,
            is_active=True,
        )
        q2_objs = build_exam_questions(exam2, [
            ('Thời điểm vàng để bắt đầu lộ trình trao đổi tái tục với phụ huynh là khi nào?', 2, [
                'Sau khi khóa học kết thúc 2 tuần',
                'Khi học viên hoàn thành khoảng 70% thời lượng khóa hiện tại',
                'Ngay buổi học đầu tiên của khóa',
                'Chỉ khi phụ huynh chủ động hỏi',
            ]),
            ('Đúng hay Sai: Khi phụ huynh băn khoăn học phí, tư vấn viên nên lắng nghe cô lập nguyên nhân trước khi đề xuất gói ưu đãi.', 1, [
                'Đúng, phải lắng nghe và xác định đúng rào cản trước',
                'Sai, chỉ cần gửi bảng giá ưu đãi ngay lập tức',
            ]),
            ('Cơ sở thuyết phục cao nhất khi tư vấn học viên lên cấp độ tiếp theo là gì?', 3, [
                'Chỉ nhắc tên giáo viên nổi tiếng',
                'Tạo áp lực sắp hết chỗ',
                'Kết quả kiểm tra & báo cáo tiến bộ thực tế của chính học viên',
                'Giảm giá sâu hơn đối thủ',
            ]),
            ('Mục tiêu của bước mở đầu cuộc gọi tư vấn tái tục là gì?', 1, [
                'Chia sẻ điểm tiến bộ nổi bật của học viên và đặt lịch trao đổi cụ thể',
                'Đọc thuộc lòng chương trình khuyến mãi',
                'Yêu cầu đóng tiền qua điện thoại ngay',
                'Hỏi thăm chung chung không có mục tiêu',
            ]),
        ])

        CourseEnrollment.objects.create(
            emp=rec_mgr, course=c2, exam=exam2, study_process=100, is_pass=True, is_completed=True, is_assigned=True
        )
        record_exam_attempt(rec_mgr, exam2, q2_objs, [2, 1, 3, 1], duration=9)

        CourseEnrollment.objects.create(
            emp=rec_emp, course=c2, exam=exam2, study_process=100, is_pass=False, is_completed=False, is_assigned=True
        )
        CourseEnrollment.objects.create(
            emp=tea_mgr, course=c2, exam=exam2, study_process=0, is_pass=False, is_completed=False, is_assigned=True
        )
        CourseEnrollment.objects.create(
            emp=ctv, course=c2, exam=exam2, study_process=33, is_pass=False, is_completed=False, is_assigned=False
        )

        # =====================================================================
        # 3. KH-1028 (ONGOING, KHÔNG CÓ BÀI THI - creator: lethuha)
        #    Dùng để test luồng học hết 100% bài giảng tự hoàn thành khóa học (is_completed=True)
        # =====================================================================
        c3 = Course.objects.create(
            creator=tr_mgr,
            code='KH-1028',
            title='Quy chế Phối hợp Liên phòng ban & Theo dõi Tiến độ Vận hành',
            description='Khóa học chuẩn hóa quy chế phối hợp giữa Khối Học thuật, HR, Tuyển dụng GV và Bộ phận Cộng tác viên kèm bài kiểm tra cuối khóa.',
            date_start=today - timedelta(days=2),
            date_end=today + timedelta(days=35),
            status='ongoing',
        )
        CourseAccess.objects.create(emp=tr_mgr, course=c3, role='trainer')

        m3_1 = CourseMaterial.objects.create(
            course=c3,
            name='Bài 1: Quy chế phối hợp giữa Phòng Đào tạo, QLGV&HV và HR',
            file_type='pdf',
            duration_minutes=20,
            order=1,
            summary='Phân rõ đầu mối chịu trách nhiệm trong từng khâu vận hành lớp học và nhân sự.',
            key_points=[
                {'title': 'Rõ vai – Đúng người', 'desc': 'Mỗi yêu cầu đều có phòng ban chủ trì và phòng ban phối hợp cụ thể.'},
                {'title': 'SLA phản hồi nội bộ', 'desc': 'Cam kết phản hồi yêu cầu liên phòng ban trong 4 giờ làm việc.'},
            ],
        )
        attach_file(m3_1, 'Quy_che_phoi_hop.pdf')

        m3_2 = CourseMaterial.objects.create(
            course=c3,
            name='Bài 2: Quy trình theo dõi tiến độ & báo cáo chất lượng định kỳ',
            file_type='pdf',
            duration_minutes=25,
            order=2,
            summary='Hướng dẫn cập nhật chỉ số tiến độ tuần và cảnh báo sớm nguy cơ trễ hạn.',
            key_points=[
                {'title': 'Cập nhật mỗi thứ 6', 'desc': 'Tổng hợp dữ liệu học tập, khảo sát và tài liệu đúng lịch.'},
            ],
        )
        attach_file(m3_2, 'Quy_trinh_theo_doi_tien_do.pdf')

        exam3 = CourseExam.objects.create(
            course=c3,
            title='Kiểm tra Quy chế Phối hợp Liên phòng ban',
            passcode='VHANH26',
            duration=20,
            passing_score=75.0,
            is_active=True,
        )
        q3 = seed_questions(exam3, [
            (
                'SLA phản hồi yêu cầu phối hợp nội bộ giữa các phòng ban là bao lâu?',
                ['4 giờ làm việc', '48 giờ làm việc', '5 ngày làm việc', 'Cuối tháng'],
                1,
            ),
            (
                'Báo cáo tiến độ học tập, khảo sát và tài liệu định kỳ được tổng hợp vào thời điểm nào?',
                ['Thứ 2 đầu tuần', 'Mỗi thứ 6 hàng tuần', 'Ngày mùng 1 hàng tháng', 'Cuối quý'],
                2,
            ),
            (
                'Nguyên tắc phân công xử lý yêu cầu liên phòng ban là gì?',
                ['Ai rảnh thì làm', 'Rõ phòng ban chủ trì và phòng ban phối hợp', 'Chuyển hết cho HR', 'Không cần ghi nhận'],
                2,
            ),
            (
                'Khi phát hiện hạng mục có nguy cơ trễ hạn, đầu mối cần làm gì?',
                ['Im lặng chờ hết hạn', 'Cảnh báo sớm và đề xuất phương án xử lý', 'Xóa khỏi báo cáo', 'Đợi cuối quý báo cáo'],
                2,
            ),
        ])

        CourseEnrollment.objects.create(emp=hr_emp, course=c3, exam=exam3, study_process=50, is_assigned=True)
        CourseEnrollment.objects.create(emp=ctv, course=c3, exam=exam3, study_process=0, is_assigned=True)
        CourseEnrollment.objects.create(emp=rd_emp, course=c3, exam=exam3, study_process=100, is_completed=True, is_pass=True, is_assigned=False)
        seed_response(rd_emp, exam3, q3, [1, 2, 2, 2], 12, days_ago=1)

        # =====================================================================
        # 4. KH-1029 (ONGOING - creator: admin, assistant: minhanh)
        #    Phân loại Dữ liệu & An toàn Thiết bị Tại Cơ sở
        # =====================================================================
        c4 = Course.objects.create(
            creator=admin,
            code='KH-1029',
            title='An toàn Dữ liệu Học viên & Bảo mật Tài khoản ScotsMate',
            description='Đào tạo chuẩn bảo mật thông tin học viên, phân loại tài liệu nội bộ và sử dụng tính năng tự khôi phục mật khẩu an toàn.',
            date_start=today - timedelta(days=4),
            date_end=today + timedelta(days=28),
            status='ongoing',
        )
        CourseAccess.objects.create(emp=admin, course=c4, role='trainer')
        CourseAccess.objects.create(emp=trainer, course=c4, role='assistant')

        m4_1 = CourseMaterial.objects.create(
            course=c4,
            name='Bài 1: Quy định phân loại dữ liệu & quyền truy cập theo phòng ban',
            file_type='pdf',
            duration_minutes=20,
            order=1,
            summary='Phân biệt dữ liệu Công khai nội bộ và dữ liệu Giới hạn theo phòng ban.',
            key_points=[
                {'title': 'Nguyên tắc tối thiểu', 'desc': 'Chỉ cấp quyền truy cập tài liệu cho đúng phòng ban liên quan.'},
            ],
        )
        attach_file(m4_1, 'Quy_dinh_phan_loai_du_lieu.pdf')

        m4_2 = CourseMaterial.objects.create(
            course=c4,
            name='Bài 2: Tiêu chuẩn an toàn thiết bị & tài khoản đăng nhập',
            file_type='pdf',
            duration_minutes=20,
            order=2,
        )
        attach_file(m4_2, 'Tieu_chuan_an_toan_thiet_bi.pdf')

        exam4 = CourseExam.objects.create(
            course=c4,
            title='Kiểm tra Nhận thức An toàn Dữ liệu',
            passcode='SEC2026',
            duration=20,
            passing_score=66.0,
            is_active=True,
        )
        q4_objs = build_exam_questions(exam4, [
            ('Khi nhân viên quên mật khẩu tài khoản ScotsMate, cần xử lý theo luồng nào?', 2, [
                'Mượn tài khoản đồng nghiệp để làm việc tạm',
                'Sử dụng chức năng Quên mật khẩu để hệ thống gửi liên kết đặt lại qua email',
                'Nhờ bạn cùng phòng gửi mật khẩu của họ',
                'Tự đăng ký một tài khoản mới ngoài hệ thống',
            ]),
            ('Tài liệu có phạm vi DEPARTMENT trên ScotsMate cho phép đối tượng nào xem?', 1, [
                'Nhân sự thuộc các phòng ban được cấp quyền, người tạo, Trưởng phòng quản lý và Admin',
                'Tất cả người dùng kể cả phòng ban không liên quan',
                'Khách bên ngoài không cần đăng nhập',
                'Chỉ duy nhất người tạo xem được',
            ]),
            ('Khi rời khỏi bàn làm việc ở trung tâm, nhân sự cần làm gì?', 1, [
                'Khóa màn hình máy tính và đăng xuất các phiên quan trọng khi hết ca',
                'Giữ nguyên màn hình mở trang quản trị',
                'Ghi mật khẩu ra giấy dán cạnh màn hình',
                'Tắt màn hình nhưng không khóa Windows',
            ]),
        ])
        CourseEnrollment.objects.create(emp=rd_emp, course=c4, exam=exam4, study_process=100, is_assigned=True)
        CourseEnrollment.objects.create(emp=hr_mgr, course=c4, exam=exam4, study_process=50, is_assigned=True)

        # =====================================================================
        # 5. KH-0925 (COMPLETED - creator: minhanh)
        #    Khóa học đã kết thúc -> Test Trainer CHỈ ĐƯỢC XEM chi tiết & báo cáo, KHÔNG được sửa!
        # =====================================================================
        c5 = Course.objects.create(
            creator=trainer,
            code='KH-0925',
            title='Đào tạo Hội nhập Văn hóa & Nghiệp vụ Cơ sở Quý III/2026',
            description='Đợt đào tạo hội nhập tập trung Quý III/2026 đã hoàn tất tổng kết và lưu trữ hồ sơ đánh giá toàn hệ thống.',
            date_start=today - timedelta(days=60),
            date_end=today - timedelta(days=15),
            status='completed',
        )
        CourseAccess.objects.create(emp=trainer, course=c5, role='trainer')

        m5_1 = CourseMaterial.objects.create(
            course=c5,
            name='Bài 1: Tổng quan mô hình tổ chức Scots English Australia',
            file_type='pdf',
            duration_minutes=30,
            order=1,
            summary='Giới thiệu cơ cấu 7 khối và vai trò các phòng ban hỗ trợ cơ sở.',
        )
        attach_file(m5_1, 'Quy_chuan_tiep_don_va_giao_tiep.pdf')

        m5_2 = CourseMaterial.objects.create(
            course=c5,
            name='Bài 2: Quy trình thực hành báo cáo cuối khóa & nghiệm thu',
            file_type='pdf',
            duration_minutes=25,
            order=2,
            summary='Hướng dẫn tổng hợp kết quả đánh giá sau đào tạo.',
        )
        attach_file(m5_2, 'Bai_thuc_hanh_-_Chuong_7.pdf')

        exam5 = CourseExam.objects.create(
            course=c5,
            title='Kiểm tra Tổng kết Hội nhập Q3/2026',
            passcode='Q3DONE',
            duration=30,
            passing_score=75.0,
            is_active=True,
        )
        q5_objs = build_exam_questions(exam5, [
            ('Khối Học thuật tại Scots English gồm những phòng ban trọng tâm nào?', 1, [
                'Phòng R&D và Phòng Quản lý Giáo viên & Học viên',
                'Phòng Tài chính và Phòng Kế toán',
                'Phòng Hạ tầng và An toàn thông tin',
                'Phòng Marketing và Truyền thông',
            ]),
            ('Bộ phận Cộng tác viên (Giáo viên part-time) thuộc sự phụ trách điều phối trực tiếp của ai trong bảng phân công?', 2, [
                'Phòng Tài chính',
                'Nhân sự phụ trách bộ phận Cộng tác viên (nguyenthihoa)',
                'Phòng Pháp chế',
                'Phòng Sáng tạo & Sản xuất',
            ]),
            ('Sau khi khóa đào tạo chuyển sang trạng thái Đã kết thúc (completed), Trainer có thể thực hiện thao tác nào?', 3, [
                'Sửa tên khóa học và thêm học viên mới',
                'Đổi đề thi và xóa học viên đã thi',
                'Xem lại thông tin khóa học và báo cáo thống kê kết quả học viên',
                'Xuất bản lại thành bản nháp',
            ]),
            ('Tài khoản Admin trên ScotsMate có vai trò như thế nào đối với 7 module hệ thống?', 4, [
                'Chỉ xem bài đăng',
                'Không vào được module nào',
                'Chỉ quản lý sự kiện',
                'Quản trị tài khoản qua /admin/ và có toàn quyền hỗ trợ 7 phân hệ',
            ]),
        ])

        for emp_u, passed, picks, dur in [
            (hr_emp, True, [1, 2, 3, 4], 10),
            (tr_emp, True, [1, 2, 3, 4], 14),
            (rec_emp, True, [1, 2, 3, 1], 19),   # 75.0 (Đạt vừa đủ)
            (rd_emp, False, [1, 1, 3, 1], 22),   # 50.0 (Chưa đạt)
            (tea_emp, True, [1, 2, 3, 4], 13),
            (ctv, False, [2, 2, 1, 1], 24),      # 25.0 (Chưa đạt)
        ]:
            CourseEnrollment.objects.create(
                emp=emp_u, course=c5, exam=exam5, study_process=100, is_pass=passed, is_completed=passed, is_assigned=True
            )
            record_exam_attempt(emp_u, exam5, q5_objs, picks, duration=dur)

        # =====================================================================
        # 6. KH-0924 (COMPLETED - creator: lethuha)
        # =====================================================================
        c6 = Course.objects.create(
            creator=tr_mgr,
            code='KH-0924',
            title='Chuẩn hóa Giáo án Tương tác Khối Học thuật Q3/2026',
            description='Khóa bồi dưỡng phương pháp thiết kế giáo án số hóa đã hoàn thành trong Quý III/2026.',
            date_start=today - timedelta(days=75),
            date_end=today - timedelta(days=30),
            status='completed',
        )
        CourseAccess.objects.create(emp=tr_mgr, course=c6, role='trainer')

        m6_1 = CourseMaterial.objects.create(
            course=c6,
            name='Bài 1: Cấu trúc giáo án tương tác chuẩn',
            file_type='pdf',
            duration_minutes=30,
            order=1,
            summary='Tài liệu chuẩn hóa khung giáo án tương tác 4 bước.',
        )
        attach_file(m6_1, 'MIS3010_Lap_trinh_web_-_Chuong_04.pdf')

        exam6 = CourseExam.objects.create(
            course=c6,
            title='Kiểm tra Chuẩn hóa Giáo án Q3/2026',
            passcode='ACADQ3',
            duration=20,
            passing_score=80.0,
            is_active=True,
        )
        q6_objs = build_exam_questions(exam6, [
            ('Bước quan trọng nhất giúp học viên chủ động nói ngay đầu tiết học là gì?', 1, [
                'Hoạt động Warm-up gắn ngữ cảnh giao tiếp thực tế',
                'Cho học viên chép từ vựng 15 phút đầu giờ',
                'Kiểm tra bài cũ bằng bài viết dài',
                'Bỏ qua bước giới thiệu mục tiêu bài học',
            ]),
        ])
        for emp_u, passed, picks in [
            (tea_mgr, True, [1]),
            (rd_mgr, True, [1]),
            (ctv_mgr, True, [1]),
            (ctv, False, [2]),
        ]:
            CourseEnrollment.objects.create(
                emp=emp_u, course=c6, exam=exam6, study_process=100, is_pass=passed, is_completed=passed, is_assigned=True
            )
            record_exam_attempt(emp_u, exam6, q6_objs, picks, duration=8)

        # =====================================================================
        # 7 & 8. KH-1130 & KH-1131 (DRAFT - minhanh & lethuha)
        #        Test cô lập khóa nháp với Trainee & test nút Xuất bản / Soạn thảo
        # =====================================================================
        c7 = Course.objects.create(
            creator=trainer,
            code='KH-1130',
            title='Chiến dịch Chăm sóc Học viên Dịp Cuối năm 2026 (Bản nháp)',
            description='Khóa đào tạo bản nháp đang biên soạn bài giảng và đề thi trước khi phát hành cho toàn bộ cơ sở.',
            date_start=today + timedelta(days=7),
            date_end=today + timedelta(days=37),
            status='draft',
        )
        CourseAccess.objects.create(emp=trainer, course=c7, role='trainer')
        m7_1 = CourseMaterial.objects.create(
            course=c7,
            name='Bài 1 (Nháp): Kế hoạch tương tác phụ huynh cuối năm',
            file_type='pdf',
            duration_minutes=20,
            order=1,
        )
        attach_file(m7_1, 'Kich_ban_tu_van_tai_tuc.pdf')

        c8 = Course.objects.create(
            creator=tr_mgr,
            code='KH-1131',
            title='Workshop Nâng cao Năng lực Giảng viên Nguồn (Bản nháp)',
            description='Khóa đào tạo nội bộ dành cho đội ngũ Giảng viên & Quản lý học thuật (đang ở trạng thái bản nháp).',
            date_start=today + timedelta(days=14),
            date_end=today + timedelta(days=44),
            status='draft',
        )
        CourseAccess.objects.create(emp=tr_mgr, course=c8, role='trainer')
        CourseMaterial.objects.create(
            course=c8,
            name='Bài 1 (Nháp): Khung đánh giá năng lực sư phạm',
            file_type='doc',
            duration_minutes=25,
            order=1,
            summary='Đề cương nháp đang hoàn thiện.',
        )

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
