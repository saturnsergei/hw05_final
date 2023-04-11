from http import HTTPStatus
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.cache import cache
from posts.models import Post, Group

User = get_user_model()


class StaticURLTests(TestCase):
    def test_homepage(self):
        guest_client = Client()
        response = guest_client.get('/')
        self.assertEqual(response.status_code, HTTPStatus.OK)


class PostsURLTest(TestCase):

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

    def setUp(self):
        cache.clear()
        self.guest_client = Client()
        self.authorized_client = Client()
        self.authorized_client.force_login(PostsURLTest.user)
        self.second_user = User.objects.create_user(username='secondUser')
        self.second_client = Client()
        self.second_client.force_login(self.second_user)

    def test_home_url_exists_at_desired_location(self):
        """Главная страница доступна любому пользователю."""
        response = self.guest_client.get(reverse('posts:index'))
        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_group_url_exists_at_desired_location(self):
        """Страница группы доступна любому пользователю."""
        response = self.guest_client.get(
            reverse('posts:group_list', kwargs={'slug': 'test-slug'}))
        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_profile_url_exists_at_desired_location(self):
        """Страница профиля доступна любому пользователю."""
        response = self.guest_client.get(
            reverse('posts:profile', kwargs={'username': 'HasNoName'}))
        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_post_url_exists_at_desired_location(self):
        """Страница поста доступна любому пользователю."""
        response = self.guest_client.get(
            reverse('posts:post_details',
                    kwargs={'post_id': PostsURLTest.post.pk}))
        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_post_edit_url_exists_at_desired_location_author(self):
        """Страница редактирования поста доступна только автору."""
        response = self.authorized_client.get(
            reverse('posts:post_edit',
                    kwargs={'post_id':
                            PostsURLTest.post.pk}), Follow=True)
        self.assertEqual(response.status_code, HTTPStatus.OK)

        response_second = self.second_client.get(
            reverse('posts:post_edit', kwargs={'post_id':
                    PostsURLTest.post.pk}))
        self.assertEqual(response_second.status_code, HTTPStatus.FOUND)

    def test_post_create_url_exists_at_desired_location_authorized(self):
        """Страница создания поста доступна авторизованному пользователю."""
        response = self.authorized_client.get(reverse('posts:post_create'))
        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_unexisting_page(self):
        """Несуществующая страница поста недоступна."""
        response = self.guest_client.get('/unexisting_page/')
        self.assertEqual(response.status_code, HTTPStatus.NOT_FOUND)

    def test_urls_uses_correct_template(self):
        """URL-адрес использует соответствующий шаблон."""
        templates_url_names = {
            'posts/index.html': reverse('posts:index'),
            'posts/group_list.html': reverse(
                'posts:group_list', kwargs={'slug': 'test-slug'}),
            'posts/profile.html': reverse(
                'posts:profile', kwargs={'username': 'HasNoName'}),
            'posts/post_detail.html': reverse(
                'posts:post_details',
                kwargs={'post_id': PostsURLTest.post.pk}),
            'posts/create_post.html': reverse('posts:post_create'),
        }

        for template, address in templates_url_names.items():
            with self.subTest(address=address):
                response = self.authorized_client.get(address)
                self.assertTemplateUsed(response, template)

    def test_edit_not_author_uses_correct_template(self):
        """URL-адрес для не автора поста использует
        соответствующий шаблон."""
        response = self.second_client.get(
            reverse('posts:post_edit',
                    kwargs={'post_id': PostsURLTest.post.pk}), follow=True)
        self.assertTemplateUsed(response, 'posts/post_detail.html')

    def test_guest_uses_correct_template(self):
        """URL-адрес для анонимного пользователя использует
        соответствующий шаблон."""
        templates_url_names = {
            reverse('posts:post_create'): 'users/login.html',
            reverse('posts:post_edit', kwargs={
                'post_id': PostsURLTest.post.pk}): 'users/login.html'
        }

        for address, template in templates_url_names.items():
            with self.subTest(address=address):
                response = self.guest_client.get(address, follow=True)
                self.assertTemplateUsed(response, template)

    def test_comment_create_url_exists_at_desired_location_authorized(self):
        """Комментарий может оставлять только авторизованный пользователь."""
        response = self.authorized_client.get(
            reverse('posts:add_comment',
                    kwargs={'post_id':
                            PostsURLTest.post.pk}), follow=True)
        self.assertEqual(response.status_code, HTTPStatus.OK)
