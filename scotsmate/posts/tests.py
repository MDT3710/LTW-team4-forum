from datetime import date
from django.test import TestCase, Client
from django.contrib.auth.models import Group, User
from django.urls import reverse
from .models import Post, PostAttachment, PostReaction, PostComment, PostCommentReaction
from .forms import PostForm, PostCommentForm
from home.models import Department, EmployeeInformation
from home.roles import ROLE_ADMIN, ROLE_EMPLOYEE, ROLE_MANAGER


class PostModelTest(TestCase):
    """Kiểm thử tầng Model: Post, PostAttachment, PostReaction, PostComment theo đúng ERD"""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password123')
        self.post = Post.objects.create(author=self.user, title='Tiêu đề bài viết', content='Nội dung bài viết mẫu')

    def test_post_creation(self):
        self.assertEqual(self.post.title, 'Tiêu đề bài viết')
        self.assertEqual(self.post.content, 'Nội dung bài viết mẫu')
        self.assertEqual(self.post.author, self.user)
        self.assertEqual(self.post.reaction_count, 0)
        self.assertEqual(self.post.comment_count, 0)
        self.assertIn('Post #', str(self.post))

    def test_post_attachment(self):
        att = PostAttachment.objects.create(post=self.post, file_name='document.pdf')
        self.assertEqual(att.file_name, 'document.pdf')
        self.assertIn('document.pdf', str(att))

    def test_post_reaction(self):
        reaction = PostReaction.objects.create(post=self.post, emp=self.user, time_reacted='Vừa xong')
        self.assertEqual(self.post.reaction_count, 1)
        self.assertIn('testuser reacted', str(reaction))

    def test_post_comment(self):
        comment = PostComment.objects.create(post=self.post, emp=self.user, content='Bình luận hay', time_reacted='Vừa xong')
        self.assertEqual(self.post.comment_count, 1)
        self.assertIn('Comment by testuser', str(comment))


class PostFormTest(TestCase):
    """Kiểm thử tầng Form: PostForm và PostCommentForm"""

    def test_post_form_valid(self):
        form = PostForm(data={'title': 'Tiêu đề', 'content': 'Nội dung hợp lệ'})
        self.assertTrue(form.is_valid())

    def test_post_form_invalid_blank_content(self):
        form = PostForm(data={'title': 'Tiêu đề', 'content': '   '})
        self.assertFalse(form.is_valid())
        self.assertIn('content', form.errors)

    def test_comment_form_valid(self):
        form = PostCommentForm(data={'content': 'Bình luận hợp lệ'})
        self.assertTrue(form.is_valid())

    def test_comment_form_invalid_blank(self):
        form = PostCommentForm(data={'content': '  '})
        self.assertFalse(form.is_valid())
        self.assertIn('content', form.errors)


class PostViewTest(TestCase):
    """Kiểm thử tầng View và API AJAX"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='minhanh', password='password123', first_name='Minh Anh', last_name='Nguyễn')
        self.client.login(username='minhanh', password='password123')
        self.post = Post.objects.create(author=self.user, title='Bài viết test', content='Nội dung thử nghiệm')

    def test_home_feed_view(self):
        # Khi đã đăng nhập, truy cập /home/ tải trang Bảng tin (home.html)
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'home.html')

        # Khi đã đăng nhập, truy cập / sẽ chuyển hướng sang /home/
        response_root = self.client.get('/')
        self.assertEqual(response_root.status_code, 302)
        self.assertRedirects(response_root, reverse('home'))

    def test_unauthenticated_user_redirected_to_login(self):
        # Chưa đăng nhập: khi truy cập trang web (/) hoặc (/home/) đều vào trang đăng nhập trước
        anonymous_client = Client()

        res_root = anonymous_client.get('/')
        self.assertEqual(res_root.status_code, 302)
        self.assertRedirects(res_root, reverse('login'))

        res_feed = anonymous_client.get(reverse('home'))
        self.assertEqual(res_feed.status_code, 302)
        self.assertRedirects(res_feed, f"{reverse('login')}?next={reverse('home')}")

    def test_login_success_redirects_to_home(self):
        # Sau khi đăng nhập thành công, người dùng mới vào được trang home
        anonymous_client = Client()
        response = anonymous_client.post(reverse('login'), {
            'username': 'minhanh',
            'password': 'password123'
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('home'))

    def test_login_with_next_param(self):
        anonymous_client = Client()
        response = anonymous_client.post(reverse('login') + '?next=' + reverse('profile'), {
            'username': 'minhanh',
            'password': 'password123'
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('profile'))

    def test_authenticated_user_visiting_login_redirected(self):
        # Người dùng đã đăng nhập vào /login/ sẽ tự động chuyển hướng theo redirect_authenticated_user
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('home'))

    def test_login_invalid_credentials(self):
        anonymous_client = Client()
        response = anonymous_client.post(reverse('login'), {
            'username': 'minhanh',
            'password': 'wrongpassword'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Tên đăng nhập hoặc mật khẩu không chính xác')

    def test_logout_redirects_to_login(self):
        # Đăng xuất qua GET hoặc POST đều chuyển về trang login
        res_get = self.client.get(reverse('logout'))
        self.assertEqual(res_get.status_code, 302)
        self.assertRedirects(res_get, reverse('login'))

        self.client.login(username='minhanh', password='password123')
        res_post = self.client.post(reverse('logout'))
        self.assertEqual(res_post.status_code, 302)
        self.assertRedirects(res_post, reverse('login'))

    def test_post_create_get(self):
        response = self.client.get(reverse('post_create'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'post_create.html')

    def test_post_create_post(self):
        response = self.client.post(reverse('post_create'), {
            'title': 'Chủ đề mới',
            'content': 'Nội dung bài viết mới tạo qua form'
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('home'))
        new_post = Post.objects.filter(title='Chủ đề mới').first()
        self.assertIsNotNone(new_post)
        self.assertEqual(new_post.author, self.user)

    def test_profile_view(self):
        response = self.client.get(reverse('profile'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'profile.html')

    def test_toggle_like_api(self):
        # Like
        res = self.client.post(reverse('post_like_api', args=[self.post.id]))
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()['liked'])
        self.assertEqual(res.json()['count'], 1)

        # Unlike
        res = self.client.post(reverse('post_like_api', args=[self.post.id]))
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.json()['liked'])
        self.assertEqual(res.json()['count'], 0)

    def test_post_likes_list_api(self):
        PostReaction.objects.create(post=self.post, emp=self.user, time_reacted='Vừa xong')
        res = self.client.get(reverse('post_likes_api', args=[self.post.id]))
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['count'], 1)

    def test_add_comment_api(self):
        res = self.client.post(reverse('post_comment_api', args=[self.post.id]), {
            'content': 'Bình luận qua API'
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['comment']['content'], 'Bình luận qua API')

    def test_delete_comment_api(self):
        comment = PostComment.objects.create(post=self.post, emp=self.user, content='Xóa tôi đi')
        res = self.client.post(reverse('comment_delete_api', args=[comment.id]))
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()['success'])
        self.assertFalse(PostComment.objects.filter(id=comment.id).exists())

    def test_edit_post_api(self):
        res = self.client.post(reverse('post_edit_api', args=[self.post.id]), {
            'title': 'Tiêu đề đã sửa',
            'content': 'Nội dung đã sửa'
        })
        self.assertEqual(res.status_code, 200)
        self.post.refresh_from_db()
        self.assertEqual(self.post.title, 'Tiêu đề đã sửa')
        self.assertEqual(self.post.content, 'Nội dung đã sửa')

    def test_delete_post_api(self):
        res = self.client.post(reverse('post_delete_api', args=[self.post.id]))
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()['success'])
        self.assertFalse(Post.objects.filter(id=self.post.id).exists())

    def test_update_profile_bio_api(self):
        from posts.colleagues import get_profile_details, load_user_custom_profiles, save_user_custom_profiles
        initial_profiles = load_user_custom_profiles()
        try:
            expected_hr = get_profile_details(self.user)
            res = self.client.post(reverse('update_profile_bio_api'), {
                'bio': 'Đây là lời giới thiệu kiểm thử mới.',
                'job_title': 'Giả mạo chức danh',
                'branch': 'Chi nhánh giả mạo',
                'join_date': '01/01/2023',
                'email': 'testuser@scotsmate.vn',
                'phone': '0988888888'
            })
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertTrue(data['success'])
            self.assertEqual(data['bio'], 'Đây là lời giới thiệu kiểm thử mới.')
            self.assertEqual(data['job_title'], expected_hr['job_title'])
            self.assertEqual(data['branch'], expected_hr['branch'])
            self.assertEqual(data['join_date'], '01/01/2023')
            self.assertEqual(data['email'], 'testuser@scotsmate.vn')
            self.assertEqual(data['phone'], '0988888888')
        finally:
            save_user_custom_profiles(initial_profiles)

    def test_topbar_user_avatar_in_navbar(self):
        res = self.client.get(reverse('profile'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'id="topbar-user-avatar"')

    def test_update_profile_avatar_api(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        avatar_file = SimpleUploadedFile("avatar.png", b"fake image bytes", content_type="image/png")
        res = self.client.post(reverse('update_profile_avatar_api'), {
            'avatar': avatar_file
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['success'])
        self.assertIn('/media/avatars/', data['avatar_url'])

    def test_update_profile_cover_api(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        cover_file = SimpleUploadedFile("cover.jpg", b"fake cover image bytes", content_type="image/jpeg")
        res = self.client.post(reverse('update_profile_cover_api'), {
            'cover': cover_file
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['success'])
        self.assertIn('/media/covers/', data['cover_url'])

    def test_profile_view_no_following_section(self):
        res = self.client.get(reverse('profile'))
        self.assertEqual(res.status_code, 200)
        self.assertNotContains(res, 'id="sidebar-following-count"')
        self.assertNotContains(res, 'id="following-modal"')
        self.assertNotContains(res, 'Giới thiệu · Quyền riêng tư · Điều khoản')
        self.assertNotContains(res, 'profile-sidebar-footer')
        self.assertContains(res, 'id="btn-edit-bio"')

    def test_other_profile_view_no_follow_button(self):
        other_user = User.objects.create_user(username='otheruser_test', password='password123')
        res = self.client.get(reverse('user_profile', args=[other_user.username]))
        self.assertEqual(res.status_code, 200)
        self.assertNotContains(res, 'btn-follow-toggle')
        self.assertNotContains(res, 'Theo dõi')
        self.assertContains(res, 'Nhắn tin')

    def test_update_profile_bio_updates_email(self):
        from posts.colleagues import load_user_custom_profiles, save_user_custom_profiles
        initial_profiles = load_user_custom_profiles()
        try:
            res = self.client.post(reverse('update_profile_bio_api'), {
                'bio': 'Test Bio',
                'job_title': 'Developer',
                'branch': 'Hanoi',
                'join_date': '01/01/2024',
                'email': 'new_email@scotsenglish.edu.vn',
                'phone': '0123456789'
            })
            self.assertEqual(res.status_code, 200)
            self.user.refresh_from_db()
            self.assertEqual(self.user.email, 'new_email@scotsenglish.edu.vn')

            prof_res = self.client.get(reverse('profile'))
            self.assertEqual(prof_res.status_code, 200)
            self.assertContains(prof_res, 'new_email@scotsenglish.edu.vn')
        finally:
            save_user_custom_profiles(initial_profiles)

    def test_avatar_synchronized_everywhere(self):
        """Kiểm tra ảnh đại diện sau khi cập nhật được đồng bộ ở tất cả mọi nơi"""
        from django.core.files.uploadedfile import SimpleUploadedFile
        from posts.colleagues import get_profile_details, load_user_custom_profiles, save_user_custom_profiles

        initial_profiles = load_user_custom_profiles()
        try:
            avatar_file = SimpleUploadedFile("my_avatar.png", b"test_image_bytes", content_type="image/png")
            upload_res = self.client.post(reverse('update_profile_avatar_api'), {'avatar': avatar_file})
            self.assertEqual(upload_res.status_code, 200)
            new_avatar_url = upload_res.json()['avatar_url']

            # 1. get_profile_details phản ánh đúng
            details = get_profile_details(self.user)
            self.assertEqual(details['avatar'], new_avatar_url)

            # 2. Tạo bài viết & bình luận của user
            post = Post.objects.create(author=self.user, content="Post with updated avatar", visibility="Toàn công ty")
            comment = PostComment.objects.create(post=post, emp=self.user, content="Comment with updated avatar")
            reaction = PostReaction.objects.create(post=post, emp=self.user)

            # 3. Kiểm tra trang newfeeds (home)
            home_res = self.client.get(reverse('home'))
            self.assertEqual(home_res.status_code, 200)
            self.assertContains(home_res, new_avatar_url)

            # 4. Kiểm tra trang profile
            prof_res = self.client.get(reverse('profile'))
            self.assertEqual(prof_res.status_code, 200)
            self.assertContains(prof_res, new_avatar_url)

            # 5. Kiểm tra API likes
            likes_res = self.client.get(reverse('post_likes_api', args=[post.id]))
            self.assertEqual(likes_res.status_code, 200)
            users = likes_res.json()['users']
            self.assertTrue(any(u['username'] == self.user.username and u['avatar'] == new_avatar_url for u in users))

            # 6. Kiểm tra API add comment trả về avatar_url mới
            comment_res = self.client.post(reverse('post_comment_api', args=[post.id]), {'content': 'Another comment'})
            self.assertEqual(comment_res.status_code, 200)
            self.assertEqual(comment_res.json()['comment']['avatar_url'], new_avatar_url)
        finally:
            # Khôi phục dữ liệu ban đầu thay vì xóa trắng
            save_user_custom_profiles(initial_profiles)


class PostPermissionAndPersistenceTest(TestCase):
    """Kiểm thử phân quyền (Admin, Trưởng phòng, Nhân viên), phạm vi hiển thị và DB bình luận/cảm xúc."""

    def setUp(self):
        self.dept_it = Department.objects.create(
            name='Phát triển & vận hành ứng dụng',
            block=Department.BlockChoices.TECHNOLOGY,
        )
        self.dept_hr = Department.objects.create(
            name='Nhân sự',
            block=Department.BlockChoices.LEGAL_HR,
        )
        self.dept_acad = Department.objects.create(
            name='Học thuật',
            block=Department.BlockChoices.ACADEMY,
        )

        grp_admin, _ = Group.objects.get_or_create(name=ROLE_ADMIN)
        grp_tp, _ = Group.objects.get_or_create(name=ROLE_MANAGER)
        grp_emp, _ = Group.objects.get_or_create(name=ROLE_EMPLOYEE)

        self.admin_user = User.objects.create_user(username='itadmin', password='pw', first_name='IT', last_name='Admin')
        self.admin_user.groups.add(grp_admin)
        EmployeeInformation.objects.create(
            emp_id=self.admin_user, dep=self.dept_it, gender='OTHER',
            NIN='000000000001', tel='0900000001', date_of_birth=date(1995, 1, 1),
        )

        self.tp_hr = User.objects.create_user(username='tphr', password='pw', first_name='TP', last_name='HR')
        self.tp_hr.groups.add(grp_tp)
        self.dept_hr.manager = self.tp_hr
        self.dept_hr.save()
        EmployeeInformation.objects.create(
            emp_id=self.tp_hr, dep=self.dept_hr, gender='OTHER',
            NIN='000000000002', tel='0900000002', date_of_birth=date(1994, 1, 1),
        )

        self.nv_hr = User.objects.create_user(username='nvhr', password='pw', first_name='NV', last_name='HR')
        self.nv_hr.groups.add(grp_emp)
        EmployeeInformation.objects.create(
            emp_id=self.nv_hr, dep=self.dept_hr, gender='OTHER',
            NIN='000000000003', tel='0900000003', date_of_birth=date(1996, 1, 1),
        )

        self.nv_acad = User.objects.create_user(username='nvacad', password='pw', first_name='NV', last_name='Acad')
        self.nv_acad.groups.add(grp_emp)
        EmployeeInformation.objects.create(
            emp_id=self.nv_acad, dep=self.dept_acad, gender='OTHER',
            NIN='000000000004', tel='0900000004', date_of_birth=date(1997, 1, 1),
        )

        self.private_post = Post.objects.create(
            author=self.nv_hr,
            title='Bài riêng tư',
            content='Chỉ tác giả và Admin thấy',
            visibility=Post.VISIBILITY_PRIVATE,
        )
        self.dept_post = Post.objects.create(
            author=self.nv_hr,
            title='Bài nội bộ Nhân sự',
            content='Chỉ phòng Nhân sự và Admin thấy',
            visibility=Post.VISIBILITY_DEPARTMENT,
        )

    def test_visibility_enforced_across_detail_and_apis(self):
        c_acad = Client()
        c_acad.login(username='nvacad', password='pw')

        # Đồng nghiệp khác phòng bị chặn cả bài private lẫn bài department trên các API
        for p in (self.private_post, self.dept_post):
            self.assertEqual(c_acad.post(reverse('post_like_api', args=[p.id])).status_code, 403)
            self.assertEqual(c_acad.get(reverse('post_likes_api', args=[p.id])).status_code, 403)
            self.assertEqual(
                c_acad.post(reverse('post_comment_api', args=[p.id]), {'content': 'Xem ké'}).status_code,
                403,
            )
            cmt = PostComment.objects.create(post=p, emp=self.nv_hr, content='Gốc')
            self.assertEqual(c_acad.post(reverse('comment_like_api', args=[cmt.id])).status_code, 403)
            self.assertEqual(c_acad.get(reverse('post_detail', args=[p.id])).status_code, 302)

        # Trưởng phòng cùng phòng Nhân sự vẫn KHÔNG xem/tương tác bài PRIVATE của nhân viên khác
        c_tp = Client()
        c_tp.login(username='tphr', password='pw')
        self.assertEqual(c_tp.post(reverse('post_like_api', args=[self.private_post.id])).status_code, 403)
        # Nhưng xem/tương tác được bài DEPARTMENT cùng phòng ban
        self.assertEqual(c_tp.get(reverse('post_detail', args=[self.dept_post.id])).status_code, 200)
        self.assertEqual(c_tp.post(reverse('post_like_api', args=[self.dept_post.id])).status_code, 200)

    def test_admin_has_full_access_and_truong_phong_is_restricted(self):
        cmt_other = PostComment.objects.create(post=self.dept_post, emp=self.nv_hr, content='Bình luận của NV HR')

        # Trưởng phòng không được sửa/xóa bài viết hay bình luận của người khác
        c_tp = Client()
        c_tp.login(username='tphr', password='pw')
        self.assertEqual(
            c_tp.post(reverse('post_edit_api', args=[self.dept_post.id]), {'title': 'Hack', 'content': 'Hack'}).status_code,
            403,
        )
        self.assertEqual(c_tp.post(reverse('post_delete_api', args=[self.dept_post.id])).status_code, 403)
        self.assertEqual(c_tp.post(reverse('comment_delete_api', args=[cmt_other.id])).status_code, 403)

        # Admin có toàn quyền xem, sửa, xóa mọi bài viết & bình luận (kể cả PRIVATE)
        c_admin = Client()
        c_admin.login(username='itadmin', password='pw')
        self.assertEqual(c_admin.get(reverse('post_detail', args=[self.private_post.id])).status_code, 200)
        home_res = c_admin.get(reverse('home'))
        self.assertContains(home_res, self.private_post.content)
        self.assertContains(home_res, f'openEditPostModal({self.private_post.id})')

        edit_res = c_admin.post(reverse('post_edit_api', args=[self.private_post.id]), {
            'title': 'Admin sửa tiêu đề',
            'content': 'Admin sửa nội dung',
        })
        self.assertEqual(edit_res.status_code, 200)
        self.private_post.refresh_from_db()
        self.assertEqual(self.private_post.title, 'Admin sửa tiêu đề')

        self.assertEqual(c_admin.post(reverse('comment_delete_api', args=[cmt_other.id])).status_code, 200)
        self.assertFalse(PostComment.objects.filter(id=cmt_other.id).exists())
        self.assertEqual(c_admin.post(reverse('post_delete_api', args=[self.private_post.id])).status_code, 200)
        self.assertFalse(Post.objects.filter(id=self.private_post.id).exists())

    def test_db_comment_reply_cascade_and_reactions(self):
        c_hr = Client()
        c_hr.login(username='nvhr', password='pw')

        # Bình luận gốc bắt đầu bằng @nvhr không bị tự động đoán thành reply
        res_root = c_hr.post(reverse('post_comment_api', args=[self.dept_post.id]), {
            'content': '@nvhr bình luận gốc có mention'
        })
        self.assertEqual(res_root.status_code, 200)
        root_id = res_root.json()['comment']['id']
        self.assertIsNone(res_root.json()['comment']['parent_id'])

        # Phản hồi trực tiếp bằng parent_id
        res_reply = c_hr.post(reverse('post_comment_api', args=[self.dept_post.id]), {
            'content': 'Đây là phản hồi trong DB',
            'parent_id': root_id,
        })
        self.assertEqual(res_reply.status_code, 200)
        reply_id = res_reply.json()['comment']['id']
        self.assertEqual(res_reply.json()['comment']['parent_id'], root_id)

        # Like bình luận lưu trong PostCommentReaction
        like_res = c_hr.post(reverse('comment_like_api', args=[reply_id]))
        self.assertEqual(like_res.status_code, 200)
        self.assertTrue(like_res.json()['liked'])
        self.assertEqual(PostCommentReaction.objects.filter(comment_id=reply_id, emp=self.nv_hr).count(), 1)

        # Xóa bình luận cha tự động cascade xóa reply con
        del_res = c_hr.post(reverse('comment_delete_api', args=[root_id]))
        self.assertEqual(del_res.status_code, 200)
        self.assertFalse(PostComment.objects.filter(id__in=[root_id, reply_id]).exists())

    def test_upload_svg_rejected_invalid_email_rejected_and_inbox_link(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        c_hr = Client()
        c_hr.login(username='nvhr', password='pw')

        svg_file = SimpleUploadedFile("bad.svg", b"<svg></svg>", content_type="image/svg+xml")
        res_svg = c_hr.post(reverse('update_profile_avatar_api'), {'avatar': svg_file})
        self.assertEqual(res_svg.status_code, 400)

        res_email = c_hr.post(reverse('update_profile_bio_api'), {'email': 'khong-phai-email'})
        self.assertEqual(res_email.status_code, 400)

        prof_res = c_hr.get(reverse('user_profile', args=[self.nv_acad.username]))
        self.assertEqual(prof_res.status_code, 200)
        self.assertContains(prof_res, reverse('inbox_detail', args=[self.nv_acad.id]))

