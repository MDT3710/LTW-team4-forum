from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from .models import Post, PostAttachment, PostReaction, PostComment
from .forms import PostForm, PostCommentForm


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
        # Khi đã đăng nhập, truy cập /newfeeds/ tải trang Bảng tin (home.html)
        response = self.client.get(reverse('newfeeds'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'home.html')

        # Khi đã đăng nhập, truy cập / sẽ chuyển hướng sang /newfeeds/
        response_root = self.client.get('/')
        self.assertEqual(response_root.status_code, 302)
        self.assertRedirects(response_root, reverse('newfeeds'))

    def test_unauthenticated_user_redirected_to_login(self):
        # Chưa đăng nhập: khi truy cập trang web (/) hoặc (/newfeeds/) đều vào trang đăng nhập trước
        anonymous_client = Client()

        res_root = anonymous_client.get('/')
        self.assertEqual(res_root.status_code, 302)
        self.assertRedirects(res_root, reverse('login'))

        res_feed = anonymous_client.get(reverse('newfeeds'))
        self.assertEqual(res_feed.status_code, 302)
        self.assertRedirects(res_feed, reverse('login'))

    def test_login_success_redirects_to_newfeeds(self):
        # Sau khi đăng nhập thành công, người dùng mới vào được trang newfeeds
        anonymous_client = Client()
        response = anonymous_client.post(reverse('login'), {
            'username': 'minhanh',
            'password': 'password123'
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('newfeeds'))

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
        self.assertRedirects(response, reverse('newfeeds'))
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
        res = self.client.post(reverse('update_profile_bio_api'), {
            'bio': 'Đây là lời giới thiệu kiểm thử mới.',
            'job_title': 'Chuyên gia khảo thí IELTS',
            'branch': 'Scots English Cầu Giấy',
            'join_date': '01/01/2023',
            'email': 'testuser@scotsmate.vn',
            'phone': '0988888888'
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['bio'], 'Đây là lời giới thiệu kiểm thử mới.')
        self.assertEqual(data['job_title'], 'Chuyên gia khảo thí IELTS')
        self.assertEqual(data['branch'], 'Scots English Cầu Giấy')
        self.assertEqual(data['join_date'], '01/01/2023')
        self.assertEqual(data['email'], 'testuser@scotsmate.vn')
        self.assertEqual(data['phone'], '0988888888')

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
        from posts.colleagues import save_user_custom_profiles
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
        save_user_custom_profiles({})

    def test_avatar_synchronized_everywhere(self):
        """Kiểm tra ảnh đại diện sau khi cập nhật được đồng bộ ở tất cả mọi nơi"""
        from django.core.files.uploadedfile import SimpleUploadedFile
        from posts.colleagues import get_profile_details, save_user_custom_profiles

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

        # Clean up
        save_user_custom_profiles({})
