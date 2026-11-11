from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Post(models.Model):
    """
    Bảng: post
    Đại diện cho bài viết được tạo bởi nhân viên/người dùng.
    """
    VISIBILITY_COMPANY = 'Toàn công ty'
    VISIBILITY_DEPARTMENT = 'Phòng ban'
    VISIBILITY_PRIVATE = 'Chỉ mình tôi'

    VISIBILITY_CHOICES = [
        (VISIBILITY_COMPANY, 'Toàn công ty'),
        (VISIBILITY_DEPARTMENT, 'Phòng ban'),
        (VISIBILITY_PRIVATE, 'Chỉ mình tôi'),
    ]

    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='posts',
        db_column='author_id',
        verbose_name="Tác giả"
    )
    title = models.CharField(max_length=200, blank=True, default='', verbose_name="Tiêu đề")
    content = models.TextField(verbose_name="Nội dung bài viết")
    visibility = models.CharField(
        max_length=50,
        choices=VISIBILITY_CHOICES,
        default=VISIBILITY_COMPANY,
        blank=True,
        verbose_name="Phạm vi hiển thị"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Thời gian tạo")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Thời gian cập nhật")

    class Meta:
        db_table = 'post'
        verbose_name = "Bài đăng"
        verbose_name_plural = "Danh sách bài đăng"
        ordering = ['-created_at']

    def __str__(self):
        return f"Post #{self.id} - {self.title or self.content[:30]}"

    @property
    def reaction_count(self):
        return self.reactions.count()

    @property
    def comment_count(self):
        return self.comments.count()


class PostAttachment(models.Model):
    """
    Bảng: post_attachment
    Đại diện cho tệp tin/ảnh đính kèm trong bài viết.
    """
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name='attachments',
        db_column='post_id',
        verbose_name="Bài đăng"
    )
    file_name = models.CharField(max_length=200, verbose_name="Tên tệp đính kèm")
    file = models.FileField(upload_to='post_attachments/', blank=True, null=True, verbose_name="Tệp đính kèm")

    class Meta:
        db_table = 'post_attachment'
        verbose_name = "Tệp đính kèm bài viết"
        verbose_name_plural = "Danh sách tệp đính kèm"

    def save(self, *args, **kwargs):
        if not self.file_name and self.file:
            self.file_name = self.file.name.split('/')[-1]
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.file_name} (Post #{self.post_id})"

    @property
    def is_image(self):
        name = (self.file_name or (self.file.name if self.file else '')).lower()
        return any(name.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.bmp', '.ico'])

    @property
    def is_video(self):
        name = (self.file_name or (self.file.name if self.file else '')).lower()
        return any(name.endswith(ext) for ext in ['.mp4', '.mov', '.webm', '.ogg', '.m4v', '.avi'])

    @property
    def extension(self):
        name = (self.file_name or (self.file.name if self.file else '')).lower()
        return name.split('.')[-1] if '.' in name else ''


class PostReaction(models.Model):
    """
    Bảng: post_reaction
    Đại diện cho tương tác/like của nhân viên với bài viết.
    """
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name='reactions',
        db_column='post_id',
        verbose_name="Bài đăng"
    )
    emp = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='post_reactions',
        db_column='emp_id',
        verbose_name="Nhân viên tương tác"
    )
    time_reacted = models.CharField(
        max_length=200,
        blank=True,
        default='',
        verbose_name="Thời gian tương tác"
    )

    class Meta:
        db_table = 'post_reaction'
        unique_together = ('post', 'emp')
        verbose_name = "Lượt tương tác"
        verbose_name_plural = "Danh sách tương tác"

    def save(self, *args, **kwargs):
        if not self.time_reacted:
            self.time_reacted = timezone.now().strftime("%Y-%m-%d %H:%M:%S")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.emp.username} reacted to Post #{self.post_id}"


class PostComment(models.Model):
    """
    Bảng: post_comment
    Đại diện cho bình luận của nhân viên dưới bài viết.
    """
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name='comments',
        db_column='post_id',
        verbose_name="Bài đăng"
    )
    emp = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='post_comments',
        db_column='emp_id',
        verbose_name="Nhân viên bình luận"
    )
    content = models.TextField(verbose_name="Nội dung bình luận")
    time_reacted = models.CharField(
        max_length=200,
        blank=True,
        default='',
        verbose_name="Thời gian bình luận"
    )

    class Meta:
        db_table = 'post_comment'
        verbose_name = "Bình luận bài viết"
        verbose_name_plural = "Danh sách bình luận"
        ordering = ['id']

    def save(self, *args, **kwargs):
        if not self.time_reacted:
            self.time_reacted = timezone.now().strftime("%Y-%m-%d %H:%M:%S")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Comment by {self.emp.username} on Post #{self.post_id}: {self.content[:30]}"
