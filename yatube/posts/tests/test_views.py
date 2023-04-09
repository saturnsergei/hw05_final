import shutil
import tempfile
from django import forms
from django.test import TestCase, Client, override_settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.conf import settings
from django.core.cache import cache
from posts.models import Post, Group, Comment, Follow

TEMP_MEDIA_ROOT = tempfile.mkdtemp(dir=settings.BASE_DIR)
User = get_user_model()


@override_settings(MEDIA_ROOT=TEMP_MEDIA_ROOT)
class PostPagesTests(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username='HasNoName')
        cls.group = Group.objects.create(
            title='Группа',
            slug='test-slug',
            description='Описание'
        )
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
        cls.post = Post.objects.create(
            text='Текст поста',
            author=cls.user,
            group=cls.group,
            image=uploaded,
        )
        cls.comment = Comment.objects.create(
            post=cls.post,
            text='текст комментария',
            author=cls.user,
        )

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        cache.clear()
        self.guest_client = Client()
        self.authorized_client = Client()
        self.authorized_client.force_login(PostPagesTests.user)

    def test_pages_uses_correct_template(self):
        """URL-адрес использует соответствующий шаблон."""
        templates_pages_names = {
            reverse('posts:index'): 'posts/index.html',
            reverse('posts:group_list',
                    kwargs={'slug': 'test-slug'}): 'posts/group_list.html',
            reverse('posts:profile',
                    kwargs={'username': 'HasNoName'}): 'posts/profile.html',
            reverse('posts:post_details',
                    kwargs={'post_id':
                            PostPagesTests.post.pk}): 'posts/post_detail.html',
            reverse('posts:post_create'): 'posts/create_post.html',
            reverse('posts:post_edit',
                    kwargs={'post_id':
                            PostPagesTests.post.pk}): 'posts/create_post.html',
            '/unexisting_page/': 'core/404.html'
        }
        for reverse_name, template in templates_pages_names.items():
            with self.subTest(reverse_name=reverse_name):
                response = self.authorized_client.get(reverse_name)
                self.assertTemplateUsed(response, template)

    def test_index_page_show_correct_context(self):
        """Шаблон главной страницы сформирован с правильным контекстом."""
        response = self.authorized_client.get(reverse('posts:index'))
        page_obj = response.context['page_obj']
        posts = Post.objects.all()
        self.assertQuerysetEqual(page_obj, posts, lambda x: x)

    def test_group_page_show_correct_context(self):
        """Шаблон страницы группы сформирован с правильным контекстом и
        содержит посты с группой"""
        response = self.authorized_client.get(
            reverse('posts:group_list', kwargs={'slug': 'test-slug'}))
        page_obj = response.context['page_obj']
        posts = PostPagesTests.group.posts.all()
        self.assertQuerysetEqual(page_obj, posts, lambda x: x)

    def test_profile_page_show_correct_context(self):
        """Шаблон страницы группы сформирован с правильным контекстом и
        содержит посты указанного пользователя"""
        response = self.authorized_client.get(
            reverse('posts:profile', kwargs={'username': 'HasNoName'}))
        page_obj = response.context['page_obj']
        posts = PostPagesTests.user.posts.all()
        self.assertQuerysetEqual(page_obj, posts, lambda x: x)

    def test_follow_index_page_show_correct_context(self):
        """Новая запись пользователя появляется в ленте тех,
        кто на него подписан и не появляется в ленте тех, кто не подписан."""
        follower = User.objects.create_user(username='Follower')
        follower_client = Client()
        follower_client.force_login(follower)
        Follow.objects.create(
            user=follower,
            author=PostPagesTests.user
        )
        response = follower_client.get(reverse('posts:follow_index'))
        page_obj = response.context['page_obj']
        posts = PostPagesTests.user.posts.all()
        self.assertQuerysetEqual(page_obj, posts, lambda x: x)

    def test_user_can_follow_and_unfollow(self):
        """Авторизованный пользователь может подписываться на других
        пользователей и удалять их из подписок."""
        follower = User.objects.create_user(username='Follower')
        follower_client = Client()
        follower_client.force_login(follower)
        response = follower_client.get(
            reverse('posts:profile_follow',
                    kwargs={'username': 'HasNoName'}), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            Follow.objects.filter(
                user=follower,
                author=PostPagesTests.user,
            ).exists()
        )
        response_unfollow = follower_client.get(
            reverse('posts:profile_unfollow',
                    kwargs={'username': 'HasNoName'}), follow=True)
        self.assertEqual(response_unfollow.status_code, 200)
        self.assertEqual(Follow.objects.filter(
            user=follower,
            author=PostPagesTests.user
        ).count(), 0)

    def test_post_detail_show_correct_context(self):
        """Шаблон страницы поста сформирован с правильным контекстом"""
        response = (self.authorized_client.
                    get(reverse('posts:post_details',
                        kwargs={'post_id':
                                PostPagesTests.post.pk})))
        self.assertEqual(response.context.get('post').text, 'Текст поста')
        self.assertEqual(response.context.get('post').pub_date,
                         PostPagesTests.post.pub_date)
        self.assertEqual(response.context.get('post').author,
                         PostPagesTests.user)
        self.assertEqual(response.context.get('post').group,
                         PostPagesTests.group)

    def test_paginator(self):
        """Пагинатор показывает правильное количество постов"""
        pages_names = {
            'index': reverse('posts:index'),
            'group': reverse('posts:group_list', kwargs={'slug': 'test-slug'}),
            'profile': reverse('posts:profile',
                               kwargs={'username': 'HasNoName'})
        }

        posts = []
        for i in range(1, 13):
            post = Post(
                text='Текст поста',
                author=PostPagesTests.user,
                group=PostPagesTests.group
            )
            posts.append(post)
        Post.objects.bulk_create(posts)

        for page, reverse_name in pages_names.items():
            with self.subTest(reverse_name=reverse_name):
                response_first_page = self.client.get(reverse_name)
                self.assertEqual(len(
                    response_first_page.context['page_obj']), 10)

                response_second_page = self.client.get(
                    reverse_name + '?page=2')
                self.assertEqual(len(
                    response_second_page.context['page_obj']), 3)

    def form_show_correct_context(self, reverse_name):
        response = self.authorized_client.get(reverse_name)
        form_fields = {
            'text': forms.fields.CharField,
            'group': forms.models.ModelChoiceField,
        }

        for value, expected in form_fields.items():
            with self.subTest(value=value):
                form_field = response.context.get('form').fields.get(value)
                self.assertIsInstance(form_field, expected)

    def test_create_page_show_correct_context(self):
        """Форма создания сформирована с правильным контекстом"""
        self.form_show_correct_context(reverse('posts:post_create'))

    def test_edit_page_show_correct_context(self):
        """Форма редактирования сформирована с правильным контекстом"""
        self.form_show_correct_context(
            reverse('posts:post_edit',
                    kwargs={'post_id': PostPagesTests.post.pk}))

    def test_post_doesnt_exists_at_undesired_group(self):
        """Пост не попал в группу, для которой не был предназначен"""
        Group.objects.create(
            title='Вторая группа',
            slug='second-slug',
            description='Описание'
        )
        response = self.authorized_client.get(
            reverse('posts:group_list', kwargs={'slug': 'second-slug'}))
        self.assertEqual(len(response.context['page_obj']), 0)

    def test_index_page_show_correct_context(self):
        """Комментарий появляется на странице поста`"""
        response = self.guest_client.get(
            reverse('posts:post_details', 
                    kwargs={'post_id': PostPagesTests.post.pk}))
        comments_context = response.context['comments']
        comments = PostPagesTests.post.comments.all()
        self.assertQuerysetEqual(comments_context, comments, lambda x: x)

    def test_cache_index_page(self):
        new_post = Post.objects.create(
            text='Текст поста',
            author=PostPagesTests.user,
            group=PostPagesTests.group,
        )
        response = self.authorized_client.get(reverse('posts:index'))
        posts = response.content
        new_post.delete()
        response_first = self.authorized_client.get(reverse('posts:index'))
        posts_first = response_first.content
        self.assertEqual(posts_first, posts)
        cache.clear()
        response_second = self.authorized_client.get(reverse('posts:index'))
        posts_second = response_second.content
        self.assertNotEqual(posts_first, posts_second)
