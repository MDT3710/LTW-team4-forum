import tempfile
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Attachment, Conversation, ConversationMember, Message, StaffProfile


class MessageChatViewTests(TestCase):
    def setUp(self):
        self.user_me = User.objects.create_user(
            username='minhanh',
            password='password123',
            first_name='Minh',
            last_name='Anh',
        )
        self.user_other = User.objects.create_user(
            username='minhduc',
            password='password123',
            first_name='Trần Minh',
            last_name='Đức',
        )
        StaffProfile.objects.create(
            user=self.user_other,
            position='Trainer',
            department='Phòng Đào tạo',
        )

        self.group = Conversation.objects.create(
            title='Tư vấn Cầu Giấy',
            conversation_type=Conversation.TYPE_GROUP,
            group_type=Conversation.GROUP_TYPE_INTERNAL,
            created_by=self.user_other,
        )
        ConversationMember.objects.create(
            conversation=self.group,
            user=self.user_me,
            role=ConversationMember.ROLE_MEMBER,
        )
        ConversationMember.objects.create(
            conversation=self.group,
            user=self.user_other,
            role=ConversationMember.ROLE_ADMIN,
        )

    def test_group_detail_renders_messages_and_bubbles(self):
        Message.objects.create(
            conversation=self.group,
            sender=self.user_other,
            content='Chào cả nhóm!',
        )
        Message.objects.create(
            conversation=self.group,
            sender=self.user_me,
            content='Em đã nhận được thông tin.',
        )

        self.client.force_login(self.user_me)
        response = self.client.get(
            reverse('group_detail', kwargs={'group_id': self.group.id}),
            HTTP_HOST='127.0.0.1',
        )

        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8')
        self.assertIn('Chào cả nhóm!', html)
        self.assertIn('Em đã nhận được thông tin.', html)
        self.assertIn('bg-[#134c81]', html)
        self.assertIn('bg-[#edf4fb]', html)
        self.assertIn('chatBox.scrollTop = chatBox.scrollHeight', html)
        self.assertIn('name="content"', html)
        self.assertIn('enctype="multipart/form-data"', html)
        self.assertLess(html.index('class="conversation-list'), html.index('class="workspace-card'))
        self.assertLess(html.index('class="workspace-card'), html.index('class="chat-sidebar'))

    @override_settings(MEDIA_ROOT=tempfile.gettempdir())
    def test_group_detail_post_text_and_attachment_prg(self):
        self.client.force_login(self.user_me)
        old_updated_at = self.group.updated_at - timedelta(hours=1)
        Conversation.objects.filter(id=self.group.id).update(updated_at=old_updated_at)

        uploaded = SimpleUploadedFile(
            'Huong-dan-workshop.pdf',
            b'%PDF-1.4 sample content',
            content_type='application/pdf',
        )
        url = reverse('group_detail', kwargs={'group_id': self.group.id})
        response = self.client.post(
            url,
            {'content': 'Gửi tài liệu nhóm', 'attachment': uploaded},
            HTTP_HOST='127.0.0.1',
        )

        self.assertRedirects(response, url, fetch_redirect_response=False)
        self.assertEqual(self.group.messages.count(), 1)
        msg = self.group.messages.first()
        self.assertEqual(msg.sender, self.user_me)
        self.assertEqual(msg.content, 'Gửi tài liệu nhóm')
        self.assertIsNotNone(msg.attachment)
        self.assertEqual(Attachment.objects.filter(message=msg).count(), 1)

        self.group.refresh_from_db()
        self.assertGreater(self.group.updated_at, old_updated_at)

        get_resp = self.client.get(url, HTTP_HOST='127.0.0.1')
        self.assertEqual(get_resp.status_code, 200)
        html = get_resp.content.decode('utf-8')
        self.assertIn('Huong-dan-workshop.pdf', html)
        self.assertIn('Tải file', html)
        self.assertIn(msg.attachment.url, html)

    def test_group_detail_post_fallback_first_user_when_anonymous(self):
        url = reverse('group_detail', kwargs={'group_id': self.group.id})
        response = self.client.post(
            url,
            {'content': 'Tin nhắn chưa login'},
            HTTP_HOST='127.0.0.1',
        )

        self.assertRedirects(response, url, fetch_redirect_response=False)
        msg = self.group.messages.first()
        self.assertIsNotNone(msg)
        self.assertEqual(msg.sender, User.objects.first())

        get_resp = self.client.get(url, HTTP_HOST='127.0.0.1')
        html = get_resp.content.decode('utf-8')
        self.assertIn('Tin nhắn chưa login', html)
        self.assertIn('Bạn •', html)

    def test_group_detail_post_empty_ignored_still_redirects(self):
        self.client.force_login(self.user_me)
        url = reverse('group_detail', kwargs={'group_id': self.group.id})
        response = self.client.post(url, {'content': '   '}, HTTP_HOST='127.0.0.1')

        self.assertRedirects(response, url, fetch_redirect_response=False)
        self.assertEqual(self.group.messages.count(), 0)

    def test_group_detail_auto_creates_missing_group_and_avoids_404(self):
        self.client.force_login(self.user_me)
        response = self.client.get(
            reverse('group_detail', kwargs={'group_id': 99}),
            HTTP_HOST='127.0.0.1',
        )
        self.assertEqual(response.status_code, 200)
        auto_group = Conversation.objects.get(id=99, conversation_type=Conversation.TYPE_GROUP)
        self.assertEqual(auto_group.title, 'Nhóm Thảo Luận #99')
        self.assertTrue(auto_group.members.filter(id=self.user_me.id).exists())
        self.assertEqual(auto_group.messages.count(), 1)

        direct = Conversation.objects.create(conversation_type=Conversation.TYPE_DIRECT)
        direct_resp = self.client.get(
            reverse('group_detail', kwargs={'group_id': direct.id}),
            HTTP_HOST='127.0.0.1',
        )
        self.assertEqual(direct_resp.status_code, 302)
        follow_resp = self.client.get(direct_resp['Location'], HTTP_HOST='127.0.0.1')
        self.assertEqual(follow_resp.status_code, 200)

    def test_messages_list_renders_dynamic_sidebar_conversations(self):
        direct = Conversation.objects.create(
            conversation_type=Conversation.TYPE_DIRECT,
            created_by=self.user_me,
        )
        ConversationMember.objects.create(conversation=direct, user=self.user_me)
        ConversationMember.objects.create(conversation=direct, user=self.user_other)
        Message.objects.create(
            conversation=direct,
            sender=self.user_other,
            content='Tin nhắn trực tiếp mới nhất',
        )

        self.client.force_login(self.user_me)
        response = self.client.get(reverse('messages_list'), HTTP_HOST='127.0.0.1')
        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8')
        self.assertIn('Tư vấn Cầu Giấy', html)
        self.assertIn('Trần Minh Đức', html)
        self.assertIn('Tin nhắn trực tiếp mới nhất', html)
        self.assertIn(reverse('group_detail', kwargs={'group_id': self.group.id}), html)
        self.assertIn(reverse('inbox_detail', kwargs={'user_id': self.user_other.id}), html)

    @override_settings(MEDIA_ROOT=tempfile.gettempdir())
    def test_inbox_detail_creates_direct_conversation_and_sends_messages(self):
        self.client.force_login(self.user_me)
        url = reverse('inbox_detail', kwargs={'user_id': self.user_other.id})

        get_resp = self.client.get(url, HTTP_HOST='127.0.0.1')
        self.assertEqual(get_resp.status_code, 200)
        self.assertEqual(
            Conversation.objects.filter(conversation_type=Conversation.TYPE_DIRECT).count(),
            1,
        )

        uploaded = SimpleUploadedFile(
            'Tinh-huong-CSHV.pdf',
            b'%PDF-1.4 case study',
            content_type='application/pdf',
        )
        post_resp = self.client.post(
            url,
            {'content': 'Em gửi bài thực hành ạ', 'attachment': uploaded},
            HTTP_HOST='127.0.0.1',
        )
        self.assertRedirects(post_resp, url, fetch_redirect_response=False)
        self.assertEqual(
            Conversation.objects.filter(conversation_type=Conversation.TYPE_DIRECT).count(),
            1,
        )

        direct_conv = Conversation.objects.get(conversation_type=Conversation.TYPE_DIRECT)
        self.assertEqual(direct_conv.messages.count(), 1)
        msg = direct_conv.messages.first()
        self.assertEqual(msg.sender, self.user_me)

        Message.objects.create(
            conversation=direct_conv,
            sender=self.user_other,
            content='Anh đã nhận được bài nhé.',
            created_at=timezone.now(),
        )

        get_after = self.client.get(url, HTTP_HOST='127.0.0.1')
        html = get_after.content.decode('utf-8')
        self.assertIn('Em gửi bài thực hành ạ', html)
        self.assertIn('Tinh-huong-CSHV.pdf', html)
        self.assertIn('Tải file', html)
        self.assertIn('Anh đã nhận được bài nhé.', html)
        self.assertIn('bg-[#134c81]', html)
        self.assertIn('bg-[#edf4fb]', html)

    def test_inbox_detail_self_chat_does_not_collide_with_other_direct(self):
        self.client.force_login(self.user_me)
        self.client.get(
            reverse('inbox_detail', kwargs={'user_id': self.user_other.id}),
            HTTP_HOST='127.0.0.1',
        )
        self.client.get(
            reverse('inbox_detail', kwargs={'user_id': self.user_me.id}),
            HTTP_HOST='127.0.0.1',
        )
        self.assertEqual(
            Conversation.objects.filter(conversation_type=Conversation.TYPE_DIRECT).count(),
            2,
        )


class GroupCreateViewTests(TestCase):
    def setUp(self):
        self.creator = User.objects.create_user(
            username='creator',
            password='password123',
            first_name='Minh',
            last_name='Anh',
        )
        self.colleague = User.objects.create_user(
            username='colleague',
            password='password123',
            first_name='Lê',
            last_name='Thu Hà',
        )

    def test_group_create_post_creates_group_and_redirects_to_detail(self):
        self.client.force_login(self.creator)
        url = reverse('group_create')
        post_resp = self.client.post(
            url,
            {
                'title': 'Nhóm Onboarding Mới',
                'branch': 'Chi nhánh Hà Đông',
                'members': [str(self.colleague.id)],
            },
            HTTP_HOST='127.0.0.1',
        )

        group = Conversation.objects.get(title='Nhóm Onboarding Mới')
        target_url = reverse('group_detail', kwargs={'group_id': group.id})
        self.assertRedirects(post_resp, target_url, status_code=302, target_status_code=200)
        self.assertEqual(group.conversation_type, Conversation.TYPE_GROUP)
        self.assertEqual(group.branch, 'Chi nhánh Hà Đông')
        self.assertTrue(
            ConversationMember.objects.filter(
                conversation=group, user=self.creator, role=ConversationMember.ROLE_ADMIN
            ).exists()
        )
        self.assertTrue(
            ConversationMember.objects.filter(
                conversation=group, user=self.colleague, role=ConversationMember.ROLE_MEMBER
            ).exists()
        )

class GroupCreateEmptyDbViewTests(TestCase):
    def test_group_create_anonymous_fallback_creates_admin_demo_and_default_title(self):
        post_resp = self.client.post(
            reverse('group_create'),
            {'title': '   '},
            HTTP_HOST='127.0.0.1',
        )
        default_user = User.objects.get(username='admin_demo')
        self.assertEqual(default_user.first_name, 'Quân')
        self.assertEqual(default_user.last_name, 'Nguyễn')

        group = Conversation.objects.get(title='Nhóm trò chuyện mới')
        target_url = reverse('group_detail', kwargs={'group_id': group.id})
        self.assertRedirects(post_resp, target_url, status_code=302, target_status_code=200)


class InboxCreateViewTests(TestCase):
    def test_inbox_create_get_lists_and_filters_colleagues(self):
        user_a = User.objects.create_user(
            username='usera', first_name='Minh', last_name='Anh'
        )
        user_b = User.objects.create_user(
            username='duc_nguyen', first_name='Đức', last_name='Nguyễn'
        )
        user_c = User.objects.create_user(
            username='thu_ha', first_name='Thu', last_name='Hà'
        )
        StaffProfile.objects.create(user=user_b, position='Trainer', branch='Chi nhánh Cầu Giấy')
        StaffProfile.objects.create(user=user_c, position='Nhân sự', branch='Chi nhánh Hà Đông')

        self.client.force_login(user_a)
        resp = self.client.get(reverse('inbox_create'), HTTP_HOST='127.0.0.1')
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode('utf-8')
        self.assertIn('Đức Nguyễn', html)
        self.assertIn('Thu Hà', html)
        self.assertNotIn(user_a, resp.context['users'])

        filtered = self.client.get(
            reverse('inbox_create'),
            {'q': 'Đức', 'branch': 'Chi nhánh Cầu Giấy'},
            HTTP_HOST='127.0.0.1',
        )
        filtered_html = filtered.content.decode('utf-8')
        self.assertIn('Đức Nguyễn', filtered_html)
        self.assertNotIn('Thu Hà', filtered_html)

    def test_inbox_create_post_creates_or_reuses_direct_and_redirects_to_inbox_detail(self):
        user_a = User.objects.create_user(
            username='usera', first_name='Minh', last_name='Anh'
        )
        user_b = User.objects.create_user(
            username='duc_nguyen', first_name='Đức', last_name='Nguyễn'
        )
        self.client.force_login(user_a)

        url = reverse('inbox_create')
        resp1 = self.client.post(url, {'user_id': str(user_b.id)}, HTTP_HOST='127.0.0.1')
        target_url = reverse('inbox_detail', kwargs={'user_id': user_b.id})
        self.assertRedirects(resp1, target_url, status_code=302, target_status_code=200)
        self.assertEqual(
            Conversation.objects.filter(conversation_type=Conversation.TYPE_DIRECT).count(),
            1,
        )

        resp2 = self.client.post(url, {'user_id': str(user_b.id)}, HTTP_HOST='127.0.0.1')
        self.assertRedirects(resp2, target_url, status_code=302, target_status_code=200)
        self.assertEqual(
            Conversation.objects.filter(conversation_type=Conversation.TYPE_DIRECT).count(),
            1,
        )


class ChatToolbarFeatureTests(TestCase):
    def setUp(self):
        self.user_me = User.objects.create_user(
            username='me', password='pw', first_name='Minh', last_name='Anh'
        )
        self.user_other = User.objects.create_user(
            username='other', password='pw', first_name='Đức', last_name='Nguyễn'
        )
        self.group = Conversation.objects.create(
            title='Nhóm Kỹ Thuật',
            conversation_type=Conversation.TYPE_GROUP,
            created_by=self.user_me,
        )
        self.membership = ConversationMember.objects.create(
            conversation=self.group,
            user=self.user_me,
            role=ConversationMember.ROLE_ADMIN,
        )

    def test_toggle_mute_updates_membership_and_ui_label_on_group_and_inbox(self):
        self.client.force_login(self.user_me)

        group_url = reverse('group_detail', kwargs={'group_id': self.group.id})
        mute_url = reverse('toggle_mute', kwargs={'convo_id': self.group.id})

        resp1 = self.client.post(mute_url, HTTP_HOST='127.0.0.1')
        self.assertRedirects(resp1, group_url, fetch_redirect_response=False)
        self.membership.refresh_from_db()
        self.assertTrue(self.membership.is_muted)

        html_muted = self.client.get(group_url, HTTP_HOST='127.0.0.1').content.decode('utf-8')
        self.assertIn('Bật thông báo', html_muted)
        self.assertIn('Đã tắt thông báo', html_muted)

        resp2 = self.client.post(mute_url, HTTP_HOST='127.0.0.1')
        self.assertRedirects(resp2, group_url, fetch_redirect_response=False)
        self.membership.refresh_from_db()
        self.assertFalse(self.membership.is_muted)

        html_unmuted = self.client.get(group_url, HTTP_HOST='127.0.0.1').content.decode('utf-8')
        self.assertIn('Tắt thông báo', html_unmuted)

        # Verify direct inbox toggle-mute also redirects cleanly back to inbox_detail
        inbox_url = reverse('inbox_detail', kwargs={'user_id': self.user_other.id})
        self.client.get(inbox_url, HTTP_HOST='127.0.0.1')
        direct = Conversation.objects.get(conversation_type=Conversation.TYPE_DIRECT)
        direct_mute_url = reverse('toggle_mute', kwargs={'convo_id': direct.id})
        resp_direct = self.client.post(direct_mute_url, HTTP_HOST='127.0.0.1')
        self.assertRedirects(resp_direct, inbox_url, fetch_redirect_response=False)
        self.assertTrue(
            ConversationMember.objects.get(conversation=direct, user=self.user_me).is_muted
        )

    @override_settings(MEDIA_ROOT=tempfile.gettempdir())
    def test_sidebar_renders_media_and_document_drawers_with_counts_and_search_panel(self):
        self.client.force_login(self.user_me)
        group_url = reverse('group_detail', kwargs={'group_id': self.group.id})

        img_file = SimpleUploadedFile('workshop.png', b'\x89PNG\r\n\x1a\n', content_type='image/png')
        pdf_file = SimpleUploadedFile('tai-lieu.pdf', b'%PDF-1.4 test', content_type='application/pdf')

        self.client.post(group_url, {'content': 'Ảnh buổi học', 'attachment': img_file}, HTTP_HOST='127.0.0.1')
        self.client.post(group_url, {'content': 'File tài liệu', 'attachment': pdf_file}, HTTP_HOST='127.0.0.1')

        resp = self.client.get(group_url, HTTP_HOST='127.0.0.1')
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode('utf-8')

        self.assertIn('File phương tiện (1)', html)
        self.assertIn('File (1)', html)
        self.assertIn('id="media-panel"', html)
        self.assertIn('id="file-panel"', html)
        self.assertIn('workshop.png', html)
        self.assertIn('tai-lieu.pdf', html)
        self.assertIn('id="in-chat-search-panel"', html)
        self.assertIn('id="in-chat-search-input"', html)
        self.assertIn('msg-inline-image', html)

    def test_rename_group_and_direct_nickname_flows(self):
        self.client.force_login(self.user_me)

        group_url = reverse('group_detail', kwargs={'group_id': self.group.id})
        rename_group_url = reverse('rename_conversation', kwargs={'convo_id': self.group.id})

        resp_g = self.client.post(
            rename_group_url,
            {'nickname': 'Đội Đào Tạo Cầu Giấy'},
            HTTP_HOST='127.0.0.1',
        )
        self.assertRedirects(resp_g, group_url, fetch_redirect_response=False)
        self.group.refresh_from_db()
        self.assertEqual(self.group.title, 'Đội Đào Tạo Cầu Giấy')
        html_g = self.client.get(group_url, HTTP_HOST='127.0.0.1').content.decode('utf-8')
        self.assertIn('Đội Đào Tạo Cầu Giấy', html_g)

        # Blank rename keeps existing group title
        self.client.post(rename_group_url, {'nickname': '   '}, HTTP_HOST='127.0.0.1')
        self.group.refresh_from_db()
        self.assertEqual(self.group.title, 'Đội Đào Tạo Cầu Giấy')

        # 1-1 nickname + reset back to default display name
        inbox_url = reverse('inbox_detail', kwargs={'user_id': self.user_other.id})
        self.client.get(inbox_url, HTTP_HOST='127.0.0.1')
        direct = Conversation.objects.get(conversation_type=Conversation.TYPE_DIRECT)
        rename_direct_url = reverse('rename_conversation', kwargs={'convo_id': direct.id})

        resp_d = self.client.post(
            rename_direct_url,
            {'nickname': 'Anh Đức Mentor'},
            HTTP_HOST='127.0.0.1',
        )
        self.assertRedirects(resp_d, inbox_url, fetch_redirect_response=False)
        html_nick = self.client.get(inbox_url, HTTP_HOST='127.0.0.1').content.decode('utf-8')
        self.assertIn('Anh Đức Mentor', html_nick)
        self.assertIn('Tên thật: Đức Nguyễn', html_nick)

        self.client.post(rename_direct_url, {'reset': '1'}, HTTP_HOST='127.0.0.1')
        direct.refresh_from_db()
        self.assertIsNone(direct.title)
        html_reset = self.client.get(inbox_url, HTTP_HOST='127.0.0.1').content.decode('utf-8')
        self.assertNotIn('Anh Đức Mentor', html_reset)
        self.assertIn('Đức Nguyễn', html_reset)

    def test_technical_admin_account_hidden_from_selectors_and_formatted_cleanly(self):
        bare_admin = User.objects.create_superuser(username='admin', email='admin@gmail.com', password='pw')
        self.client.force_login(self.user_me)

        for route_name in ('group_create', 'inbox_create'):
            resp = self.client.get(reverse(route_name), HTTP_HOST='127.0.0.1')
            self.assertNotIn(bare_admin, resp.context['users'])

        inbox_admin_html = self.client.get(
            reverse('inbox_detail', kwargs={'user_id': bare_admin.id}),
            HTTP_HOST='127.0.0.1',
        ).content.decode('utf-8')
        self.assertIn('Quản trị viên hệ thống', inbox_admin_html)
