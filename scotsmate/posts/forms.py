from django import forms
from django.contrib.auth.forms import AuthenticationForm
from .models import Post, PostAttachment, PostComment


class ScotsmateAuthenticationForm(AuthenticationForm):
    """
    Form đăng nhập kế thừa Django AuthenticationForm (Chương 7 MIS3010).
    Tùy biến thông báo lỗi tiếng Việt và các thuộc tính trường nhập liệu.
    """
    error_messages = {
        'invalid_login': 'Tên đăng nhập hoặc mật khẩu không chính xác. Vui lòng kiểm tra lại!',
        'inactive': 'Tài khoản này hiện đang bị vô hiệu hóa.',
    }

    def __init__(self, request=None, *args, **kwargs):
        super().__init__(request=request, *args, **kwargs)
        self.fields['username'].widget.attrs.update({
            'class': 'login-input',
            'id': 'username',
            'placeholder': 'Tên đăng nhập (vd: minhanh, thuha, admin)',
            'autofocus': True,
        })
        self.fields['password'].widget.attrs.update({
            'class': 'login-input',
            'id': 'password',
            'placeholder': 'Mật khẩu',
        })


class PostForm(forms.ModelForm):
    """
    Form tạo và chỉnh sửa bài đăng (bảng `post` trong ERD).
    """
    class Meta:
        model = Post
        fields = ['title', 'content', 'visibility']
        widgets = {
            'title': forms.TextInput(attrs={
                'id': 'post-title-input',
                'class': 'topic-title-input',
                'placeholder': 'Nhập hoặc chọn chủ đề...',
            }),
            'content': forms.Textarea(attrs={
                'id': 'composer-text',
                'class': 'composer-textarea',
                'placeholder': 'Bạn muốn chia sẻ điều gì với đồng nghiệp Scots English hôm nay?...',
                'rows': 4,
                'required': True,
            }),
            'visibility': forms.TextInput(attrs={
                'id': 'post-visibility-input',
            }),
        }
        labels = {
            'title': 'Chủ đề / Tiêu đề',
            'content': 'Nội dung bài viết',
            'visibility': 'Phạm vi hiển thị',
        }

    def clean_visibility(self):
        visibility = self.cleaned_data.get('visibility', '').strip()
        if visibility not in [Post.VISIBILITY_COMPANY, Post.VISIBILITY_DEPARTMENT, Post.VISIBILITY_PRIVATE]:
            return Post.VISIBILITY_COMPANY
        return visibility

    def clean_content(self):
        content = self.cleaned_data.get('content', '').strip()
        if not content:
            raise forms.ValidationError("Nội dung bài viết không được để trống.")
        return content


class PostCommentForm(forms.ModelForm):
    """
    Form bình luận dưới bài viết (bảng `post_comment` trong ERD).
    """
    class Meta:
        model = PostComment
        fields = ['content']
        widgets = {
            'content': forms.TextInput(attrs={
                'class': 'text-input comment-text-field',
                'placeholder': 'Viết bình luận… (Enter để gửi)',
                'required': True,
            })
        }
        labels = {
            'content': 'Nội dung bình luận',
        }

    def clean_content(self):
        content = self.cleaned_data.get('content', '').strip()
        if not content:
            raise forms.ValidationError("Nội dung bình luận không được để trống.")
        return content


class PostAttachmentForm(forms.ModelForm):
    """
    Form đính kèm tệp tin / hình ảnh vào bài viết (bảng `post_attachment` trong ERD).
    """
    class Meta:
        model = PostAttachment
        fields = ['file', 'file_name']
        widgets = {
            'file': forms.FileInput(attrs={
                'class': 'file-input',
                'accept': 'image/*,.pdf,.doc,.docx',
            }),
            'file_name': forms.TextInput(attrs={
                'class': 'file-name-input',
                'placeholder': 'Tên tệp đính kèm',
            }),
        }
