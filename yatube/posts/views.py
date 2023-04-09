from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.cache import cache_page
from .forms import PostForm, CommentForm
from .models import Post, Group, Follow

User = get_user_model()

COUNT_POST = 10
TITLE_LENGTH = 30


def paginate(request, posts):
    paginator = Paginator(posts, COUNT_POST)
    page_number = request.GET.get('page')
    return paginator.get_page(page_number)


@cache_page(20, key_prefix='index_page')
def index(request):
    post_list = Post.objects.select_related('group').all()
    page_obj = paginate(request, post_list)
    context = {
        'page_obj': page_obj,
    }
    return render(request, 'posts/index.html', context)


def group_posts(request, slug):
    group = get_object_or_404(Group, slug=slug)
    posts = group.posts.all()
    page_obj = paginate(request, posts)
    context = {
        'group': group,
        'page_obj': page_obj,
        'title': f'Записи сообщества {group}',
    }
    return render(request, 'posts/group_list.html', context)


def profile(request, username):
    template = 'posts/profile.html'
    user = get_object_or_404(User, username=username)
    posts = user.posts.all()
    paginator = Paginator(posts, COUNT_POST)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    following = False
    if request.user.is_authenticated:
        following = Follow.objects.filter(
            user=request.user,
            author=user
        ).exists()

    context = {
        'author': user,
        'count': paginator.count,
        'page_obj': page_obj,
        'following': following
    }
    return render(request, template, context)


def post_details(request, post_id):
    template = 'posts/post_detail.html'
    post = get_object_or_404(Post, pk=post_id)
    form = CommentForm()
    comments = post.comments.all()

    context = {
        'id': post_id,
        'post': post,
        'title': post.text[:TITLE_LENGTH],
        'form': form,
        'comments': comments
    }
    return render(request, template, context)


@login_required
def post_create(request):
    form = PostForm(request.POST or None, files=request.FILES or None)

    if form.is_valid():
        post = form.save(commit=False)
        post.author = request.user
        post.save()
        return redirect('posts:profile', request.user)

    return render(request, 'posts/create_post.html', {'form': form})


@login_required
def post_edit(request, post_id):
    post = get_object_or_404(Post, pk=post_id)

    if post.author != request.user:
        return redirect('posts:post_details', post_id)

    if request.method == 'POST':
        form = PostForm(
            request.POST,
            files=request.FILES or None,
            instance=post)
        if form.is_valid():
            form.save()
            return redirect('posts:post_details', post_id)
        else:
            context = {
                'form': form,
                'is_edit': True
            }
            return render(request, 'posts/create_post.html', context)

    form = PostForm(instance=post)
    context = {
        'form': form,
        'is_edit': True
    }
    return render(request, 'posts/create_post.html', context)


@login_required
def add_comment(request, post_id):
    post = get_object_or_404(Post, pk=post_id)
    form = CommentForm(request.POST or None)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.author = request.user
        comment.post = post
        comment.save()
    return redirect('posts:post_details', post_id=post_id)


@login_required
def follow_index(request):
    post_ids = request.user.follower.values_list('author__posts', flat=True)
    post_list = Post.objects.filter(id__in=post_ids).all()
    page_obj = paginate(request, post_list)
    context = {
        'page_obj': page_obj,
    }
    return render(request, 'posts/follow.html', context)


@login_required
def profile_follow(request, username):
    author = get_object_or_404(User, username=username)

    if not request.user == author:

        following = Follow.objects.filter(
            user=request.user,
            author=author
        ).exists()

        if not following:
            Follow.objects.create(
                user=request.user,
                author=author
            )
    return redirect('posts:profile', username)


@login_required
def profile_unfollow(request, username):
    author = get_object_or_404(User, username=username)
    follower = Follow.objects.filter(
        user=request.user,
        author=author
    )
    follower.delete()
    return redirect('posts:profile', username)
