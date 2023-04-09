import shutil
import tempfile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from posts.forms import PostForm
from posts.models import Post, Group

TEMP_MEDIA_ROOT = tempfile.mkdtemp(dir=settings.BASE_DIR)
User = get_user_model()


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class PostFormTests(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username='HasNoName')
        cls.group = Group.objects.create(
            title='Группа',
            slug='test-slug',
            description='Описание'
        )
        cls.post = Post.objects.create(
            text='Текст поста',
            author=cls.user,
            group=cls.group
        )
        cls.form = PostForm(instance=PostFormTests.post)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.authorized_client = Client()
        self.authorized_client.force_login(PostFormTests.user)

    def test_post_create_success(self):
        """Валидная форма создает запись в Post."""
        post_count = Post.objects.count()
        small_img = (
            b'\x47\x49\x46\x38\x39\x61\x02\x00'
            b'\x01\x00\x80\x00\x00\x00\x00\x00'
            b'\xFF\xFF\xFF\x21\xF9\x04\x00\x00'
            b'\x00\x00\x00\x2C\x00\x00\x00\x00'
            b'\x02\x00\x01\x00\x00\x02\x02\x0C'
            b'\x0A\x00\x3B'
        )
        uploaded = SimpleUploadedFile(
            name='small.jpeg',
            content=small_img,
            content_type='image/jpeg'
        )
        form_data = {
            'text': 'Текст поста',
            'group': PostFormTests.group.pk,
            'author': self.user,
            'image': uploaded,
        }
        response = self.authorized_client.post(
            reverse('posts:post_create'),
            data=form_data,
            follow=True
        )
        self.assertRedirects(response, reverse(
            'posts:profile', kwargs={'username': 'HasNoName'}))
        self.assertEqual(Post.objects.count(), post_count + 1)
        self.assertTrue(
            Post.objects.filter(
                text='Текст поста',
                group=PostFormTests.group.pk,
                author=self.user,
                image='posts/small.jpeg'
            ).exists()
        )

    def test_post_edit_success(self):
        """Валидная форма изменяет запись в Post."""
        form_data = {
            'text': 'Новый текст поста',
            'group': PostFormTests.group.pk,
        }
        post_count = Post.objects.count()
        response = self.authorized_client.post(
            reverse('posts:post_edit',
                    kwargs={'post_id':
                            PostFormTests.post.pk}),
            data=form_data,
            follow=True
        )
        self.assertRedirects(response, reverse(
            'posts:post_details', kwargs={'post_id': PostFormTests.post.pk}))
        self.assertEqual(Post.objects.count(), post_count)
        post = Post.objects.get(pk=PostFormTests.post.pk)
        self.assertEqual(form_data['text'], post.text)
        self.assertEqual(form_data['group'], post.group.pk)
        self.assertEqual(PostFormTests.user, post.author)
