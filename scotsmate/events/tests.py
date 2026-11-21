from datetime import timedelta

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from home.models import Branch, Department
from home.roles import ROLE_ADMIN, ROLE_EMPLOYEE, ROLE_MANAGER
from .models import Event, EventRegistration


class EventsModuleTests(TestCase):
    def setUp(self):
        self.admin_group, _ = Group.objects.get_or_create(name=ROLE_ADMIN)
        self.mgr_group, _ = Group.objects.get_or_create(name=ROLE_MANAGER)
        self.emp_group, _ = Group.objects.get_or_create(name=ROLE_EMPLOYEE)

        self.admin_user = User.objects.create_user(
            username='admin_ev', password='pw', first_name='Admin', last_name='IT'
        )
        self.admin_user.groups.add(self.admin_group)

        self.mgr_a = User.objects.create_user(
            username='mgr_a', password='pw', first_name='Trần Minh', last_name='Đức'
        )
        self.mgr_a.groups.add(self.mgr_group)

        self.mgr_b = User.objects.create_user(
            username='mgr_b', password='pw', first_name='Lê Thu', last_name='Hà'
        )
        self.mgr_b.groups.add(self.mgr_group)

        self.emp = User.objects.create_user(
            username='emp_1', password='pw', first_name='Phạm Lan', last_name='Chi'
        )
        self.emp.groups.add(self.emp_group)

        self.emp2 = User.objects.create_user(
            username='emp_2', password='pw', first_name='Nguyễn Văn', last_name='An'
        )
        self.emp2.groups.add(self.emp_group)

        self.branch = Branch.objects.create(
            name='Chi nhánh Cầu Giấy', region=Branch.RegionChoices.NORTH, address='Hà Nội'
        )
        self.dept = Department.objects.create(name='Nhân sự', manager=self.mgr_a)

        now = timezone.now()
        self.upcoming_event = Event.objects.create(
            title='Workshop Scots 2026',
            category=Event.CATEGORY_WORKSHOP,
            description='Mô tả workshop',
            agenda='09:00 Khai mạc',
            date_start=now + timedelta(days=3),
            date_end=now + timedelta(days=3, hours=3),
            location='Hội trường tầng 5',
            branch=self.branch,
            department=self.dept,
            organizer=self.mgr_a,
            max_participants=1,
            status=Event.STATUS_UPCOMING,
        )
        self.ongoing_event = Event.objects.create(
            title='Sự kiện Đang diễn ra',
            category=Event.CATEGORY_TRAINING,
            description='Đang chạy',
            date_start=now - timedelta(hours=1),
            date_end=now + timedelta(hours=2),
            location='Phòng 201',
            organizer=self.admin_user,
            max_participants=20,
            status=Event.STATUS_UPCOMING,
        )
        self.cancelled_event = Event.objects.create(
            title='Sự kiện Đã hủy',
            category=Event.CATEGORY_CULTURE,
            description='Đã hủy bỏ',
            date_start=now + timedelta(days=5),
            date_end=now + timedelta(days=5, hours=2),
            location='Sảnh A',
            organizer=self.mgr_a,
            max_participants=30,
            status=Event.STATUS_CANCELLED,
        )
        self.past_event = Event.objects.create(
            title='Giải Thể thao Q3',
            category=Event.CATEGORY_SPORTS,
            description='Đã diễn ra',
            date_start=now - timedelta(days=10),
            date_end=now - timedelta(days=10) + timedelta(hours=4),
            location='Nhà thi đấu',
            organizer=self.mgr_a,
            max_participants=50,
            status=Event.STATUS_COMPLETED,
        )

    def test_requires_login_and_rbac_for_employee_manager_admin(self):
        self.assertEqual(self.client.get(reverse('events_list')).status_code, 302)

        # Nhân viên thường xem được danh sách/chi tiết nhưng KHÔNG được tạo/sửa/xóa
        self.client.force_login(self.emp)
        self.assertEqual(self.client.get(reverse('events_list')).status_code, 200)
        self.assertEqual(
            self.client.get(reverse('event_detail', kwargs={'event_id': self.upcoming_event.id})).status_code,
            200,
        )
        self.assertEqual(self.client.get(reverse('event_create')).status_code, 302)
        self.assertEqual(
            self.client.get(reverse('event_edit', kwargs={'event_id': self.upcoming_event.id})).status_code,
            302,
        )
        self.assertEqual(
            self.client.post(reverse('event_delete', kwargs={'event_id': self.upcoming_event.id})).status_code,
            302,
        )
        self.assertTrue(Event.objects.filter(id=self.upcoming_event.id).exists())

        # Trưởng phòng khác (mgr_b) sửa và xóa được bất kỳ sự kiện nào theo use case
        self.client.force_login(self.mgr_b)
        edit_url = reverse('event_edit', kwargs={'event_id': self.upcoming_event.id})
        res_edit = self.client.post(edit_url, {
            'title': 'Workshop Đã Cập Nhật',
            'category': Event.CATEGORY_WORKSHOP,
            'description': 'Mô tả cập nhật',
            'date_start': timezone.localtime(self.upcoming_event.date_start).strftime('%Y-%m-%dT%H:%M'),
            'date_end': timezone.localtime(self.upcoming_event.date_end).strftime('%Y-%m-%dT%H:%M'),
            'location': 'Phòng Hội thảo',
            'max_participants': '10',
            'status': Event.STATUS_UPCOMING,
        })
        self.assertEqual(res_edit.status_code, 302)
        self.upcoming_event.refresh_from_db()
        self.assertEqual(self.upcoming_event.title, 'Workshop Đã Cập Nhật')

        # Admin xóa được sự kiện
        self.client.force_login(self.admin_user)
        res_del = self.client.post(reverse('event_delete', kwargs={'event_id': self.cancelled_event.id}))
        self.assertRedirects(res_del, reverse('events_list'), fetch_redirect_response=False)
        self.assertFalse(Event.objects.filter(id=self.cancelled_event.id).exists())

    def test_event_create_blocks_past_date_start_and_invalid_end_date_preserving_input(self):
        self.client.force_login(self.mgr_a)
        now = timezone.localtime(timezone.now())

        # date_start trong quá khứ -> bị chặn và giữ nguyên dữ liệu đã nhập
        past_res = self.client.post(reverse('event_create'), {
            'title': 'Sự kiện Quá khứ',
            'category': Event.CATEGORY_TRAINING,
            'description': 'Mô tả test',
            'date_start': (now - timedelta(days=1)).strftime('%Y-%m-%dT%H:%M'),
            'date_end': (now + timedelta(days=1)).strftime('%Y-%m-%dT%H:%M'),
            'location': 'Hà Nội',
            'max_participants': '20',
        })
        self.assertEqual(past_res.status_code, 200)
        self.assertFalse(Event.objects.filter(title='Sự kiện Quá khứ').exists())
        self.assertContains(past_res, 'Sự kiện Quá khứ')
        self.assertContains(past_res, 'không được nằm trong quá khứ')

        # date_end <= date_start -> bị chặn
        bad_end_res = self.client.post(reverse('event_create'), {
            'title': 'Sự kiện Lỗi Giờ',
            'category': Event.CATEGORY_TRAINING,
            'description': 'Mô tả test',
            'date_start': (now + timedelta(days=2, hours=3)).strftime('%Y-%m-%dT%H:%M'),
            'date_end': (now + timedelta(days=2, hours=1)).strftime('%Y-%m-%dT%H:%M'),
            'location': 'Hà Nội',
            'max_participants': '20',
        })
        self.assertEqual(bad_end_res.status_code, 200)
        self.assertFalse(Event.objects.filter(title='Sự kiện Lỗi Giờ').exists())
        self.assertContains(bad_end_res, 'phải diễn ra sau thời gian bắt đầu')

    def test_event_edit_cannot_reduce_max_participants_below_registered(self):
        EventRegistration.objects.create(event=self.ongoing_event, user=self.emp)
        EventRegistration.objects.create(event=self.ongoing_event, user=self.emp2)

        self.client.force_login(self.mgr_a)
        res = self.client.post(reverse('event_edit', kwargs={'event_id': self.ongoing_event.id}), {
            'title': self.ongoing_event.title,
            'category': self.ongoing_event.category,
            'description': self.ongoing_event.description,
            'date_start': timezone.localtime(self.ongoing_event.date_start).strftime('%Y-%m-%dT%H:%M'),
            'date_end': timezone.localtime(self.ongoing_event.date_end).strftime('%Y-%m-%dT%H:%M'),
            'location': self.ongoing_event.location,
            'max_participants': '1',
            'status': Event.STATUS_UPCOMING,
        })
        self.assertEqual(res.status_code, 200)
        self.ongoing_event.refresh_from_db()
        self.assertEqual(self.ongoing_event.max_participants, 20)

    def test_register_toggle_post_only_before_start_and_respects_capacity(self):
        reg_url = reverse('event_register_toggle_api', kwargs={'event_id': self.upcoming_event.id})

        self.client.force_login(self.emp)
        # GET không được phép thay đổi đăng ký
        get_res = self.client.get(reg_url)
        self.assertEqual(get_res.status_code, 405)
        self.assertFalse(EventRegistration.objects.filter(event=self.upcoming_event, user=self.emp).exists())

        # Đăng ký hợp lệ trước khi bắt đầu
        post_res = self.client.post(reg_url)
        self.assertEqual(post_res.status_code, 200)
        self.assertTrue(post_res.json()['registered'])
        self.assertEqual(post_res.json()['my_events_count'], 1)

        # Đã đầy chỗ (max_participants=1) -> emp2 không đăng ký được
        self.client.force_login(self.emp2)
        full_res = self.client.post(reg_url)
        self.assertEqual(full_res.status_code, 400)
        self.assertFalse(full_res.json()['success'])

        # Sự kiện đang diễn ra (date_start <= now) -> KHÔNG cho phép đăng ký mới hoặc hủy đăng ký
        EventRegistration.objects.create(event=self.ongoing_event, user=self.emp)
        ongoing_url = reverse('event_register_toggle_api', kwargs={'event_id': self.ongoing_event.id})
        self.client.force_login(self.emp)
        cancel_ongoing = self.client.post(ongoing_url)
        self.assertEqual(cancel_ongoing.status_code, 400)
        self.assertTrue(EventRegistration.objects.filter(event=self.ongoing_event, user=self.emp).exists())

        self.client.force_login(self.emp2)
        join_ongoing = self.client.post(ongoing_url)
        self.assertEqual(join_ongoing.status_code, 400)
        self.assertFalse(EventRegistration.objects.filter(event=self.ongoing_event, user=self.emp2).exists())

    def test_tab_counts_match_rendered_events_and_realtime_badges(self):
        self.client.force_login(self.emp)

        all_res = self.client.get(reverse('events_list'), {'tab': 'all'})
        self.assertEqual(all_res.status_code, 200)
        counts = all_res.context['counts']
        self.assertEqual(counts['all'], len(all_res.context['events']))
        self.assertContains(all_res, 'Đã hủy')
        self.assertContains(all_res, 'Đang diễn ra')

        up_res = self.client.get(reverse('events_list'), {'tab': 'upcoming'})
        self.assertEqual(counts['upcoming'], len(up_res.context['events']))
        self.assertNotIn(self.cancelled_event, up_res.context['events'])
        self.assertNotIn(self.past_event, up_res.context['events'])

        past_res = self.client.get(reverse('events_list'), {'tab': 'past'})
        self.assertEqual(counts['past'], len(past_res.context['events']))
        self.assertIn(self.past_event, past_res.context['events'])
